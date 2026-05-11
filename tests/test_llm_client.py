import pytest
import asyncio
import json
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch, call
from core.llm_client import AsyncRateLimiter, get_rate_limiter, LLMClient, get_llm_client

@pytest.mark.asyncio
async def test_async_rate_limiter():
    limiter = AsyncRateLimiter(600) # 10 requests per second -> interval 0.1s
    assert limiter.rate == 600
    assert limiter.interval == 0.1
    
    start = asyncio.get_event_loop().time()
    await limiter.wait() # First call is immediate
    await limiter.wait() # Second call should wait ~0.1s
    end = asyncio.get_event_loop().time()
    
    assert end - start >= 0.09 # Allow some margin

@pytest.mark.asyncio
async def test_get_rate_limiter():
    from core.llm_client import _rate_limiters
    _rate_limiters.clear()
    l1 = get_rate_limiter("p1", 10)
    l2 = get_rate_limiter("p1", 10)
    assert l1 is l2
    assert l1.rate == 10

class MockResponse:
    def __init__(self, status, text, json_data):
        self.status = status
        self._text = text
        self._json_data = json_data
    async def text(self): return self._text
    async def json(self): return self._json_data
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass

@pytest.mark.asyncio
async def test_llm_client_init():
    with patch("core.llm_client.LLM_PROFILES", {"p1": {"api_url": "url", "model": "m", "rpm": 10}, "default": {}}):
        client = LLMClient(profile_name="p1", agent_id="a1")
        assert client.api_url == "url"
        assert client.model == "m"
        assert client.agent_id == "a1"

@pytest.mark.asyncio
async def test_chat_completion_success():
    client = LLMClient()
    mock_resp = MockResponse(200, "", {"choices": [{"message": {"content": "Hello"}}]})
    
    with patch("aiohttp.ClientSession.post", return_value=mock_resp), \
         patch("core.llm_client.GLOBAL_RATE_LIMITER.wait", new_callable=AsyncMock), \
         patch("core.llm_client.USE_MULTI_PROVIDER", False):
        
        response = await client.chat_completion([{"role": "user", "content": "Hi"}])
        assert response == "Hello"

@pytest.mark.asyncio
async def test_chat_completion_failover():
    client = LLMClient()
    # First call returns 429, second returns 200
    mock_resp_429 = MockResponse(429, "Too many requests", {})
    mock_resp_200 = MockResponse(200, "", {"choices": [{"message": {"content": "Success"}}]})
    
    with patch("aiohttp.ClientSession.post", side_effect=[mock_resp_429, mock_resp_200]), \
         patch("core.llm_client.GLOBAL_RATE_LIMITER.wait", new_callable=AsyncMock), \
         patch("core.llm_client.USE_MULTI_PROVIDER", True), \
         patch("core.llm_client.LLM_PROFILES", {"p1": {"api_url": "u1"}, "p2": {"api_url": "u2"}, "default": {}}), \
         patch("config.ALLOWED_LLM_PROFILES", ["p1", "p2"]):
        
        # We need to ensure available_profiles has > 1 item
        response = await client.chat_completion([{"role": "user", "content": "Hi"}])
        assert response == "Success"

@pytest.mark.asyncio
async def test_chat_completion_retry_on_empty(caplog):
    import logging
    caplog.set_level(logging.WARNING)
    client = LLMClient()
    mock_resp_empty = MockResponse(200, "", {"choices": [{"message": {"content": ""}}]})
    mock_resp_val = MockResponse(200, "", {"choices": [{"message": {"content": "Value"}}]})
    
    with patch("aiohttp.ClientSession.post", side_effect=[mock_resp_empty, mock_resp_val]), \
         patch("asyncio.sleep", new_callable=AsyncMock), \
         patch("core.llm_client.GLOBAL_RATE_LIMITER.wait", new_callable=AsyncMock), \
         patch("core.llm_client.USE_MULTI_PROVIDER", False):
        
        response = await client.chat_completion([{"role": "user", "content": "Hi"}])
        assert response == "Value"
        assert "LLM returned empty content" in caplog.text

@pytest.mark.asyncio
async def test_extract_json():
    client = LLMClient()
    # Case 1: Direct JSON
    assert await client.extract_json('{"a": 1}') == {"a": 1}
    # Case 2: Markdown block
    assert await client.extract_json('Here is it: ```json\n{"b": 2}\n```') == {"b": 2}
    # Case 3: Bare block
    assert await client.extract_json('```\n{"c": 3}\n```') == {"c": 3}
    # Case 4: Braces find
    assert await client.extract_json('Noise {"d": 4} noise') == {"d": 4}
    # Case 5: Fail
    assert await client.extract_json('No json here') is None

@pytest.mark.asyncio
async def test_chat_completion_structured_toon():
    client = LLMClient()
    mock_resp = MockResponse(200, "", {"choices": [{"message": {"content": "key: value"}}]})
    
    with patch("core.llm_client.LLMClient.chat_completion", return_value="key: value"), \
         patch("core.llm_client.USE_TOON", True), \
         patch("core.llm_client.toon_decode", return_value={"key": "value"}):
        
        data = await client.chat_completion_structured([{"role": "user", "content": "test"}])
        assert data == {"key": "value"}

@pytest.mark.asyncio
async def test_chat_completion_structured_json_fallback():
    client = LLMClient()
    
    with patch("core.llm_client.LLMClient.chat_completion", return_value='{"key": "json"}'), \
         patch("core.llm_client.USE_TOON", True), \
         patch("core.llm_client.toon_decode", side_effect=Exception("Toon fail")):
        
        data = await client.chat_completion_structured([{"role": "user", "content": "test"}])
        assert data == {"key": "json"}

@pytest.mark.asyncio
async def test_token_tracking():
    memory = MagicMock()
    memory.log_token_usage = AsyncMock()
    client = LLMClient(agent_id="agent1", project_id="proj1", memory=memory)
    
    mock_resp = MockResponse(200, "", {
        "choices": [{"message": {"content": "Done"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    })
    
    with patch("aiohttp.ClientSession.post", return_value=mock_resp), \
         patch("core.llm_client.GLOBAL_RATE_LIMITER.wait", new_callable=AsyncMock), \
         patch("core.llm_client.USE_MULTI_PROVIDER", False):
        
        await client.chat_completion([{"role": "user", "content": "test"}])
        # Wait for the async task to log usage
        await asyncio.sleep(0.1)
        memory.log_token_usage.assert_called_once()

@pytest.mark.asyncio
async def test_async_rate_limiter_no_rate():
    limiter = AsyncRateLimiter(0)
    await limiter.wait() # Should return immediately

@pytest.mark.asyncio
async def test_chat_completion_with_auth():
    client = LLMClient()
    mock_resp = MockResponse(200, "", {"choices": [{"message": {"content": "Hello"}}]})
    
    with patch("aiohttp.ClientSession.post", return_value=mock_resp) as mock_post, \
         patch("core.llm_client.LLM_PROFILES", {"default": {"api_url": "u", "api_key": "secret"}}), \
         patch("core.llm_client.GLOBAL_RATE_LIMITER.wait", new_callable=AsyncMock):
        
        await client.chat_completion([{"role": "user", "content": "Hi"}])
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer secret"

@pytest.mark.asyncio
async def test_chat_completion_429_no_multi_provider(caplog):
    client = LLMClient()
    mock_resp_429 = MockResponse(429, "Too many", {})
    mock_resp_200 = MockResponse(200, "", {"choices": [{"message": {"content": "Ok"}}]})
    
    with patch("aiohttp.ClientSession.post", side_effect=[mock_resp_429, mock_resp_200]), \
         patch("asyncio.sleep", new_callable=AsyncMock), \
         patch("core.llm_client.USE_MULTI_PROVIDER", False):
        
        await client.chat_completion([{"role": "user", "content": "Hi"}])
        assert "Rate limit (429) hit. Retrying" in caplog.text

@pytest.mark.asyncio
async def test_chat_completion_api_error():
    client = LLMClient()
    mock_resp_500 = MockResponse(500, "Internal Error", {})
    
    with patch("aiohttp.ClientSession.post", return_value=mock_resp_500):
        with pytest.raises(RuntimeError, match="LLM API error: 500"):
            await client.chat_completion([{"role": "user", "content": "Hi"}])

@pytest.mark.asyncio
async def test_chat_completion_format_fallback():
    client = LLMClient()
    mock_resp = MockResponse(200, "", {"response": "Fallback Content"})
    
    with patch("aiohttp.ClientSession.post", return_value=mock_resp):
        res = await client.chat_completion([{"role": "user", "content": "Hi"}])
        assert res == "Fallback Content"

@pytest.mark.asyncio
async def test_chat_completion_unexpected_format():
    client = LLMClient()
    mock_resp = MockResponse(200, "", {"weird": "format"})
    
    with patch("aiohttp.ClientSession.post", return_value=mock_resp):
        with pytest.raises(ValueError, match="Unexpected response format"):
            await client.chat_completion([{"role": "user", "content": "Hi"}])

@pytest.mark.asyncio
async def test_chat_completion_timeout_retry():
    client = LLMClient()
    with patch("aiohttp.ClientSession.post", side_effect=asyncio.TimeoutError), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(asyncio.TimeoutError):
            await client.chat_completion([{"role": "user", "content": "Hi"}])

@pytest.mark.asyncio
async def test_structured_response_cleaning():
    client = LLMClient()
    # Test line 437 branch
    with patch("core.llm_client.LLMClient.chat_completion", return_value="Some text ```json\n{\"a\":1}\n``` other text"), \
         patch("core.llm_client.toon_decode", return_value={"a": 1}):
        data = await client.chat_completion_structured([])
        assert data == {"a": 1}

    # Test line 442 branch (broken block)
    with patch("core.llm_client.LLMClient.chat_completion", return_value="```\nline1\nline2\n```"), \
         patch("core.llm_client.toon_decode", return_value={"l": 1}):
        data = await client.chat_completion_structured([])
        assert data == {"l": 1}

@pytest.mark.asyncio
async def test_calculate_savings_branches():
    # To test calculate_savings, we need to call chat_completion_structured with USE_TOON=True
    client = LLMClient()
    
    # JSON response -> savings = 0 (line 457)
    with patch("core.llm_client.LLMClient.chat_completion", return_value='{"a":1}'), \
         patch("core.llm_client.USE_TOON", True):
        # We need to trigger the callback. The callback is passed to chat_completion.
        # Let's mock chat_completion to call its callback.
        async def mock_chat(*args, **kwargs):
            cb = kwargs.get("saved_tokens_callback")
            if cb: cb(kwargs.get("messages")[0]["content"]) # Dummy call
            return '{"a":1}'
        
        with patch.object(client, "chat_completion", side_effect=mock_chat):
            await client.chat_completion_structured([])

    # Toon response -> savings (line 470)
    async def mock_chat_toon(*args, **kwargs):
        cb = kwargs.get("saved_tokens_callback")
        if cb: cb("toon: data")
        return "toon: data"

    with patch.object(client, "chat_completion", side_effect=mock_chat_toon), \
         patch("core.llm_client.toon_decode", return_value={"key": "value"}), \
         patch("core.llm_client.USE_TOON", True):
        await client.chat_completion_structured([])

@pytest.mark.asyncio
async def test_structured_empty_responses(caplog):
    client = LLMClient()
    # Empty raw response
    with patch("core.llm_client.LLMClient.chat_completion", return_value=""):
        assert await client.chat_completion_structured([]) == {}
    
    # Empty after cleaning
    with patch("core.llm_client.LLMClient.chat_completion", return_value="```json\n\n```"):
        assert await client.chat_completion_structured([]) == {}

@pytest.mark.asyncio
async def test_chat_completion_structured_no_system_msg():
    client = LLMClient()
    with patch.object(client, "chat_completion", new_callable=AsyncMock) as mock_chat, \
         patch("core.llm_client.USE_TOON", True):
        mock_chat.return_value = "{}"
        await client.chat_completion_structured([{"role": "user", "content": "hi"}])
        # Should have inserted a system message
        messages = mock_chat.call_args[1]["messages"]
        assert messages[0]["role"] == "system"

@pytest.mark.asyncio
async def test_generate_methods():
    client = LLMClient()
    with patch.object(client, "chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Result"
        
        await client.generate_code("print hello")
        await client.review_code("code")
        await client.fix_error("code", "error")
        await client.generate_tests("code")
        await client.generate("system", "user")
        await client.generate_structured("system", "user")
        
        assert mock_chat.call_count == 6

def test_get_llm_client():
    from core.llm_client import _global_llm_client
    c1 = get_llm_client()
    c2 = get_llm_client()
    assert c1 is c2

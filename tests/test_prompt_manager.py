import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from core.prompt_manager import PromptManager

@pytest.fixture
def mock_memory():
    memory = AsyncMock()
    memory.get_agent_prompt.return_value = None
    memory.get_config.return_value = None
    return memory

@pytest.fixture
def mock_redis():
    with patch("redis.from_url") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

@pytest.mark.asyncio
async def test_prompt_manager_init_redis_fail(mock_memory):
    with patch("redis.from_url", side_effect=Exception("Redis connection failed")):
        pm = PromptManager(mock_memory)
        assert pm.redis_client is None

@pytest.mark.asyncio
async def test_get_prompt_default(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    pm.redis_client = None  # Force no redis
    
    prompt = await pm.get_prompt("unknown_agent", "some_task")
    assert prompt["system_prompt"] == "You are an expert unknown_agent developer."
    assert prompt["template"] == "Implement the task: some_task"

@pytest.mark.asyncio
async def test_get_prompt_from_memory(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    pm.redis_client = None
    
    mock_memory.get_agent_prompt.return_value = {
        "system_prompt": "Custom System",
        "task_templates": {"task1": "Template 1"}
    }
    
    prompt = await pm.get_prompt("backend", "task1")
    assert prompt["system_prompt"] == "Custom System"
    assert prompt["template"] == "Template 1"

@pytest.mark.asyncio
async def test_get_prompt_from_redis(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    mock_redis.get.return_value = json.dumps({
        "system_prompt": "Cached System",
        "task_templates": {"task1": "Cached Template"}
    })
    
    prompt = await pm.get_prompt("backend", "task1")
    assert prompt["system_prompt"] == "Cached System"
    assert prompt["template"] == "Cached Template"
    mock_redis.get.assert_called_with("prompts:backend")

@pytest.mark.asyncio
async def test_get_prompt_redis_error(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    mock_redis.get.side_effect = Exception("Redis error")
    
    # Should fallback to memory
    mock_memory.get_agent_prompt.return_value = {
        "system_prompt": "Memory System",
        "task_templates": {}
    }
    
    prompt = await pm.get_prompt("backend", "task1")
    assert prompt["system_prompt"] == "Memory System"

@pytest.mark.asyncio
async def test_initialize_default_prompts(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    
    # Mock USE_TOON as True for this test
    with patch("core.prompt_manager.USE_TOON", True):
        await pm.initialize_default_prompts(force=True)
    
    # Check if save_agent_prompt was called for all defaults
    assert mock_memory.save_agent_prompt.call_count >= 10
    mock_memory.set_config.assert_called_with("prompt_version", "v2-toon")

@pytest.mark.asyncio
async def test_initialize_default_prompts_skip(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    mock_memory.get_config.return_value = "v2-json"
    
    with patch("core.prompt_manager.USE_TOON", False):
        await pm.initialize_default_prompts(force=False)
    
    mock_memory.save_agent_prompt.assert_not_called()

@pytest.mark.asyncio
async def test_initialize_default_prompts_redis_flush_error(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    mock_redis.delete.side_effect = Exception("Flush error")
    
    await pm.initialize_default_prompts(force=True)
    # Should not raise exception
    assert mock_memory.save_agent_prompt.called

@pytest.mark.asyncio
async def test_get_prompt_save_to_redis(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    mock_redis.get.return_value = None
    mock_memory.get_agent_prompt.return_value = {
        "system_prompt": "New Prompt",
        "task_templates": {}
    }
    
    await pm.get_prompt("backend")
    mock_redis.set.assert_called()

@pytest.mark.asyncio
async def test_get_prompt_redis_set_error(mock_memory, mock_redis):
    pm = PromptManager(mock_memory)
    mock_redis.get.return_value = None
    mock_redis.set.side_effect = Exception("Redis set error")
    mock_memory.get_agent_prompt.return_value = {
        "system_prompt": "New Prompt",
        "task_templates": {}
    }
    
    # Should not raise exception
    prompt = await pm.get_prompt("backend")
    assert prompt["system_prompt"] == "New Prompt"

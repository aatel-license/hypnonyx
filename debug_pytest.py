import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from tests.test_base_agent import MockAgent

@pytest.mark.asyncio
async def test_task_worker_retry_logic():
    mock_memory = MagicMock()
    mock_memory.update_task_status = AsyncMock()
    mock_memory.log_action = AsyncMock()
    mock_memory.get_top_domain_knowledge = AsyncMock(return_value=[])
    mock_memory.get_agent_documents = AsyncMock(return_value=[])
    mock_memory.get_retrospectives = AsyncMock(return_value=[])

    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.execute = AsyncMock(side_effect=[Exception("fail"), {"status": "success"}])

        with patch("agents.base_agent.MAX_RETRIES", 2), \
             patch("agents.base_agent.asyncio.sleep", new_callable=AsyncMock):

            agent.running = True
            await agent.tasks_queue.put({"task_id": "t1", "type": "coding"})

            worker_task = asyncio.create_task(agent._task_worker())
            await asyncio.sleep(0.2)

            agent.running = False
            await worker_task

            print("Call count inside pytest:", agent.execute.call_count)


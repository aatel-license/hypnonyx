import asyncio
from unittest.mock import AsyncMock, MagicMock
from tests.test_base_agent import MockAgent

async def main():
    mock_memory = MagicMock()
    mock_memory.update_task_status = AsyncMock()
    mock_memory.log_action = AsyncMock()
    mock_memory.get_top_domain_knowledge = AsyncMock(return_value=[])
    mock_memory.get_agent_documents = AsyncMock(return_value=[])
    mock_memory.get_retrospectives = AsyncMock(return_value=[])
    
    agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
    agent.execute = AsyncMock(side_effect=[Exception("fail"), {"status": "success"}])
    agent.running = True
    await agent.tasks_queue.put({"task_id": "t1", "type": "coding"})
    
    task = asyncio.create_task(agent._task_worker())
    await asyncio.sleep(0.5)
    agent.running = False
    await task
    print("Call count:", agent.execute.call_count)

asyncio.run(main())

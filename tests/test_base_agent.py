import pytest
import asyncio
import json
from typing import Dict, Any, List, Optional
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from agents.base_agent import BaseAgent

class TestAgent(BaseAgent):
    async def execute(self, task: Dict):
        return {"status": "success", "data": "done"}

@pytest.fixture
def mock_memory():
    m = MagicMock()
    m.update_task_status = AsyncMock()
    m.log_action = AsyncMock()
    m.get_top_domain_knowledge = AsyncMock(return_value=[])
    m.get_agent_documents = AsyncMock(return_value=[])
    m.get_retrospectives = AsyncMock(return_value=[])
    m.get_domain_knowledge_by_topic = AsyncMock(return_value=None)
    m.save_domain_knowledge = AsyncMock()
    return m

@pytest.fixture
def mock_broker():
    with patch("core.message_broker.MessageBroker", autospec=True) as mock:
        broker_instance = mock.return_value
        broker_instance.connect = AsyncMock()
        broker_instance.subscribe = AsyncMock()
        broker_instance.publish = AsyncMock()
        broker_instance.send_heartbeat = AsyncMock()
        broker_instance.report_idle = AsyncMock()
        broker_instance.stop = AsyncMock()
        yield broker_instance

@pytest.mark.asyncio
async def test_base_agent_init(mock_memory):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        assert agent.agent_id == "a1"
        assert agent.agent_type == "backend"
        assert agent.project_id == "project"

@pytest.mark.asyncio
async def test_base_agent_start_stop(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        
        # We need to mock _task_worker etc. to not block
        with patch.object(agent, "_task_worker", new_callable=AsyncMock), \
             patch.object(agent, "_heartbeat_worker", new_callable=AsyncMock), \
             patch.object(agent, "_idle_checker", new_callable=AsyncMock):
            
            # Start in a task to allow gather to run
            start_task = asyncio.create_task(agent.start())
            await asyncio.sleep(0.1)
            assert agent.running == True
            assert mock_broker.connect.called
            assert mock_broker.subscribe.call_count >= 1
            
            await agent.stop()
            assert agent.running == False
            assert mock_broker.stop.called
            await start_task

@pytest.mark.asyncio
async def test_handle_new_task(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        
        # Valid task
        task = {"task_id": "t1", "type": "coding", "agent_type": "backend"}
        await agent._handle_new_task(task)
        assert agent.tasks_queue.qsize() == 1
        assert "t1" in agent.pending_task_ids
        
        # Duplicate task
        await agent._handle_new_task(task)
        assert agent.tasks_queue.qsize() == 1 # Still 1
        
        # Task for another agent
        task2 = {"task_id": "t2", "type": "coding", "agent_type": "frontend"}
        await agent._handle_new_task(task2)
        assert agent.tasks_queue.qsize() == 1 # Still 1
        
        # Assigned to someone else
        task3 = {"task_id": "t3", "type": "coding", "assigned_to": "other_agent"}
        await agent._handle_new_task(task3)
        assert agent.tasks_queue.qsize() == 1 # Still 1

@pytest.mark.asyncio
async def test_handle_scrum_ceremony(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True) as mock_llm:
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.completed_tasks = ["t1"]
        
        mock_llm_instance = agent.llm_client
        mock_llm_instance.generate_structured = AsyncMock(return_value={"feedback": "Good", "sentiment": "positive"})
        
        msg = {"type": "retrospective_request", "sprint_id": 1}
        await agent._handle_scrum_ceremony(msg)
        
        assert mock_broker.publish.called
        args = mock_broker.publish.call_args
        assert args[1]["sprint_id"] == 1
        assert args[1]["feedback"] == "Good"

@pytest.mark.asyncio
async def test_task_worker_success(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.running = True
        
        task = {"task_id": "t1", "type": "coding", "description": "desc"}
        await agent.tasks_queue.put(task)
        agent.pending_task_ids.add("t1")
        
        # Run worker for a short time
        worker_task = asyncio.create_task(agent._task_worker())
        await asyncio.sleep(0.5)
        agent.running = False
        await worker_task
        
        assert "t1" in agent.completed_tasks
        assert "t1" not in agent.pending_task_ids
        mock_memory.update_task_status.assert_called_with("t1", "in_progress", assigned_to="a1")
        assert mock_broker.publish.called # TASKS_STARTED and TASKS_COMPLETED

@pytest.mark.asyncio
async def test_task_worker_failure(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.execute = AsyncMock(return_value={"status": "failed", "reason": "bug"})
        agent.running = True
        
        task = {"task_id": "t1", "type": "coding"}
        await agent.tasks_queue.put(task)
        agent.pending_task_ids.add("t1")
        
        worker_task = asyncio.create_task(agent._task_worker())
        await asyncio.sleep(0.5)
        agent.running = False
        await worker_task
        
        assert "t1" in agent.failed_tasks
        assert "t1" not in agent.pending_task_ids

@pytest.mark.asyncio
async def test_perform_research(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        
        # Mock subprocess
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b'[{"title": "Result"}]', b''))
        mock_proc.returncode = 0
        
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch.object(agent, "_synthesize_and_store_knowledge", new_callable=AsyncMock):
            
            results = await agent.perform_research("query")
            assert results == [{"title": "Result"}]

@pytest.mark.asyncio
async def test_synthesize_and_store_knowledge(mock_memory):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        mock_llm = agent.llm_client
        mock_llm.generate_structured = AsyncMock(return_value={
            "domain": "d", "topic": "t", "synthesized_summary": "s", "key_points": ["p"]
        })
        
        # Case 1: New knowledge
        mock_memory.get_domain_knowledge_by_topic = AsyncMock(return_value=None)
        await agent._synthesize_and_store_knowledge("q", "c")
        assert mock_memory.save_domain_knowledge.called
        
        # Case 2: Update existing
        mock_memory.get_domain_knowledge_by_topic = AsyncMock(return_value={"id": "uuid", "source_count": 1})
        await agent._synthesize_and_store_knowledge("q", "c")
        assert mock_memory.save_domain_knowledge.call_count == 2

@pytest.mark.asyncio
async def test_heartbeat_and_idle(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = TestAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.running = True
        
        # Mock intervals
        with patch("agents.base_agent.HEARTBEAT_INTERVAL", 0.1), \
             patch("agents.base_agent.MAX_IDLE_TIME", 0.1):
            
            hb_task = asyncio.create_task(agent._heartbeat_worker())
            idle_task = asyncio.create_task(agent._idle_checker())
            
            await asyncio.sleep(0.3)
            agent.running = False
            await hb_task
            await idle_task
            
            assert mock_broker.send_heartbeat.called
            assert mock_broker.report_idle.called

def test_normalize_files():
    agent = TestAgent("a1", "backend", None, "/tmp/project")
    # Dict input
    assert agent.normalize_files({"f1.py": "code"}) == {"f1.py": "code"}
    # List of dicts
    assert agent.normalize_files([{"path": "f2.py", "content": "code2"}]) == {"f2.py": "code2"}
    # List of tuples
    assert agent.normalize_files([("f3.py", "code3")]) == {"f3.py": "code3"}
    # Empty
    assert agent.normalize_files(None) == {}

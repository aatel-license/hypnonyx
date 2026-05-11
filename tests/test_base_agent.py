import pytest
import asyncio
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call
from agents.base_agent import BaseAgent

class MockAgent(BaseAgent):
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
def mock_skill_manager():
    with patch("agents.base_agent.SkillManager", autospec=True) as mock:
        sm = mock.return_value
        sm.get_skill.return_value = "code"
        sm.resolve_all_skills_for_agent.return_value = []
        sm.find_skill_by_trigger.return_value = None
        yield sm

@pytest.fixture
def mock_broker():
    with patch("agents.base_agent.MessageBroker", autospec=True) as mock:
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
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        assert agent.agent_id == "a1"
        assert agent.agent_type == "backend"
        assert agent.project_id == "project"

@pytest.mark.asyncio
async def test_base_agent_start_stop(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        
        with patch.object(agent, "_task_worker", new_callable=AsyncMock), \
             patch.object(agent, "_heartbeat_worker", new_callable=AsyncMock), \
             patch.object(agent, "_idle_checker", new_callable=AsyncMock):
            
            start_task = asyncio.create_task(agent.start())
            await asyncio.sleep(0.1)
            assert agent.running == True
            assert mock_broker.connect.called
            
            await agent.stop()
            assert agent.running == False
            assert mock_broker.stop.called
            await start_task

@pytest.mark.asyncio
async def test_handle_new_task(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        
        # Valid task
        task = {"task_id": "t1", "type": "coding", "agent_type": "backend"}
        await agent._handle_new_task(task)
        assert agent.tasks_queue.qsize() == 1
        
        # Invalid
        await agent._handle_new_task(None)
        await agent._handle_new_task({"task_id": "t2"}) # Missing type
        assert agent.tasks_queue.qsize() == 1

@pytest.mark.asyncio
async def test_handle_assigned_task(mock_memory):
    agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
    await agent._handle_assigned_task({"assigned_to": "a1", "task_id": "t1"})
    assert agent.tasks_queue.qsize() == 1

@pytest.mark.asyncio
async def test_handle_scrum_ceremony(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True) as mock_llm:
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.completed_tasks = ["t1"]
        
        mock_llm.return_value.generate_structured = AsyncMock(return_value={"feedback": "Good", "sentiment": "positive"})
        
        msg = {"type": "retrospective_request", "sprint_id": 1}
        await agent._handle_scrum_ceremony(msg)
        
        assert mock_broker.publish.called
        args, _ = mock_broker.publish.call_args
        assert args[1]["sprint_id"] == 1

@pytest.mark.asyncio
async def test_task_worker_retry_logic(mock_memory, mock_broker):
    original_sleep = asyncio.sleep
    async def mock_sleep(delay):
        await original_sleep(0.01)
        
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.execute = AsyncMock(side_effect=[Exception("fail"), {"status": "success"}])
        
        with patch("agents.base_agent.MAX_RETRIES", 2), \
             patch("agents.base_agent.asyncio.sleep", side_effect=mock_sleep):
            
            agent.running = True
            await agent.tasks_queue.put({"task_id": "t1", "type": "coding"})
            
            worker_task = asyncio.create_task(agent._task_worker())
            await original_sleep(0.2)
            
            agent.running = False
            await worker_task
            
            assert agent.execute.call_count == 2
            assert "t1" in agent.completed_tasks

@pytest.mark.asyncio
async def test_perform_research(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b'[{"title": "Result"}]', b''))
        mock_proc.returncode = 0
        
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch.object(agent, "_synthesize_and_store_knowledge", new_callable=AsyncMock):
            
            results = await agent.perform_research("query")
            assert results == [{"title": "Result"}]

@pytest.mark.asyncio
async def test_synthesize_and_store_knowledge(mock_memory):
    with patch("core.llm_client.LLMClient", autospec=True) as mock_llm:
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        mock_llm.return_value.generate_structured = AsyncMock(return_value={
            "domain": "d", "topic": "t", "synthesized_summary": "s", "key_points": ["p"]
        })
        
        await agent._synthesize_and_store_knowledge("q", "c")
        assert mock_memory.save_domain_knowledge.called

@pytest.mark.asyncio
async def test_heartbeat_and_idle(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        
        real_sleep = asyncio.sleep
        async def fast_sleep(delay):
            await real_sleep(0.001)

        with patch("agents.base_agent.HEARTBEAT_INTERVAL", 0.01), \
             patch("agents.base_agent.MAX_IDLE_TIME", 0.01), \
             patch("agents.base_agent.asyncio.sleep", side_effect=fast_sleep):
            
            agent.running = True
            hb_task = asyncio.create_task(agent._heartbeat_worker())
            idle_task = asyncio.create_task(agent._idle_checker())
            
            agent.last_activity = time.time() - 1.0
            await asyncio.sleep(0.1)
            
            agent.running = False
            await asyncio.gather(hb_task, idle_task)
            
            assert mock_broker.send_heartbeat.called
            assert mock_broker.report_idle.called

def test_normalize_files():
    agent = MockAgent("a1", "backend", None, "/tmp/project")
    assert agent.normalize_files({"f1.py": "code"}) == {"f1.py": "code"}
    assert agent.normalize_files([{"path": "f2.py", "content": "code2"}]) == {"f2.py": "code2"}

def test_base_agent_execute_not_implemented():
    agent = BaseAgent("a", "b", MagicMock(), "/tmp/p")
    with pytest.raises(NotImplementedError):
        asyncio.run(agent.execute({}))

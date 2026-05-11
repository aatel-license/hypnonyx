import logging; logging.basicConfig(level=logging.DEBUG)
import pytest
import asyncio
import json
import time
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
        
        task = {"task_id": "t1", "type": "coding", "agent_type": "backend"}
        await agent._handle_new_task(task)
        assert agent.tasks_queue.qsize() == 1
        assert "t1" in agent.pending_task_ids
        
        await agent._handle_new_task(task)
        assert agent.tasks_queue.qsize() == 1
        
        task2 = {"task_id": "t2", "type": "coding", "agent_type": "frontend"}
        await agent._handle_new_task(task2)
        assert agent.tasks_queue.qsize() == 1
        
        task3 = {"task_id": "t3", "type": "coding", "assigned_to": "other_agent"}
        await agent._handle_new_task(task3)
        assert agent.tasks_queue.qsize() == 1

@pytest.mark.asyncio
async def test_handle_scrum_ceremony(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True) as mock_llm:
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.completed_tasks = ["t1"]
        
        mock_llm_instance = agent.llm_client
        mock_llm_instance.generate_structured = AsyncMock(return_value={"feedback": "Good", "sentiment": "positive"})
        
        msg = {"type": "retrospective_request", "sprint_id": 1}
        await agent._handle_scrum_ceremony(msg)
        
        assert mock_broker.publish.called
        args, kwargs = mock_broker.publish.call_args
        assert args[1]["sprint_id"] == 1
        assert args[1]["feedback"] == "Good"

@pytest.mark.asyncio
async def test_task_worker_success(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.running = True
        
        task = {"task_id": "t1", "type": "coding", "description": "desc"}
        await agent.tasks_queue.put(task)
        agent.pending_task_ids.add("t1")
        
        worker_task = asyncio.create_task(agent._task_worker())
        await asyncio.sleep(0.5)
        agent.running = False
        await worker_task
        
        assert "t1" in agent.completed_tasks
        assert "t1" not in agent.pending_task_ids

@pytest.mark.asyncio
async def test_task_worker_failure(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
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
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        mock_llm = agent.llm_client
        mock_llm.generate_structured = AsyncMock(return_value={
            "domain": "d", "topic": "t", "synthesized_summary": "s", "key_points": ["p"]
        })
        
        mock_memory.get_domain_knowledge_by_topic = AsyncMock(return_value=None)
        await agent._synthesize_and_store_knowledge("q", "c")
        assert mock_memory.save_domain_knowledge.called
        
        mock_memory.get_domain_knowledge_by_topic = AsyncMock(return_value={"id": "uuid", "source_count": 1})
        await agent._synthesize_and_store_knowledge("q", "c")
        assert mock_memory.save_domain_knowledge.call_count == 2

@pytest.mark.asyncio
async def test_heartbeat_and_idle(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        agent.running = True
        
        # Mock intervals and sleep to avoid waiting 10s
        real_sleep = asyncio.sleep
        async def fast_sleep(delay):
            await real_sleep(0.001)

        with patch("agents.base_agent.HEARTBEAT_INTERVAL", 0.01), \
             patch("agents.base_agent.MAX_IDLE_TIME", 0.01), \
             patch("agents.base_agent.asyncio.sleep", side_effect=fast_sleep):
            
            hb_task = asyncio.create_task(agent._heartbeat_worker())
            idle_task = asyncio.create_task(agent._idle_checker())
            
            # Ensure idle time is large enough
            agent.last_activity = time.time() - 1.0
            
            await asyncio.sleep(0.1) # REAL sleep
            agent.running = False
            await asyncio.gather(hb_task, idle_task)
            
            assert mock_broker.send_heartbeat.called
            assert mock_broker.report_idle.called

@pytest.mark.asyncio
async def test_handle_new_task_validation(mock_memory):
    agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
    # Empty message
    await agent._handle_new_task(None)
    # Non-dict
    await agent._handle_new_task("string")
    # Missing ID/Type
    await agent._handle_new_task({"task_id": "t1"})
    assert agent.tasks_queue.qsize() == 0

@pytest.mark.asyncio
async def test_handle_assigned_task(mock_memory):
    agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
    await agent._handle_assigned_task({"assigned_to": "a1", "task_id": "t1"})
    assert agent.tasks_queue.qsize() == 1
    
    await agent._handle_assigned_task({"assigned_to": "other"})
    assert agent.tasks_queue.qsize() == 1

@pytest.mark.asyncio
async def test_handle_scrum_ceremony_skip(mock_memory, mock_broker):
    agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
    agent.completed_tasks = []
    agent.failed_tasks = []
    await agent._handle_scrum_ceremony({"type": "retrospective_request"})
    assert not mock_broker.publish.called

@pytest.mark.asyncio
async def test_handle_backlog_refinement(mock_memory, mock_broker):
    with patch("core.llm_client.LLMClient", autospec=True) as mock_llm:
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        mock_llm_instance = agent.llm_client
        mock_llm_instance.generate = AsyncMock(return_value="query")
        mock_llm_instance.generate_structured = AsyncMock(return_value=[{"description": "new", "priority": 1}])
        
        # Mock research
        with patch.object(agent, "perform_research", new_callable=AsyncMock) as mock_res:
            mock_res.return_value = [{"title": "R", "body": "B", "href": "H"}]
            
            msg = {
                "type": "backlog_refinement_request",
                "project_id": "project",
                "sprint_id": 1,
                "failed_tasks": [{"description": "failing", "agent_type": "backend"}]
            }
            await agent._handle_backlog_refinement(msg)
            assert mock_broker.publish.called

@pytest.mark.asyncio
async def test_task_worker_skill_resolution(mock_memory, mock_broker):
    agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
    agent.skill_manager = MagicMock()
    agent.skill_manager.get_skill.return_value = "skill code"
    agent.skill_manager.resolve_all_skills_for_agent.return_value = ["s1"]
    
    agent.running = True
    task = {"task_id": "t1", "type": "coding", "skill": "explicit_skill"}
    await agent.tasks_queue.put(task)
    
    worker_task = asyncio.create_task(agent._task_worker())
    await asyncio.sleep(0.5)
    agent.running = False
    await worker_task
    
    assert "explicit_skill" in agent._resolved_skills or "s1" in agent._resolved_skills
    assert agent.current_skill_content is not None

@pytest.mark.asyncio
async def test_task_worker_context_injection(mock_memory, mock_broker):
    agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
    mock_memory.get_top_domain_knowledge.return_value = [{"domain": "d", "topic": "t", "synthesized_summary": "s"}]
    mock_memory.get_agent_documents.return_value = [{"source": "src", "doc_type": "txt", "content": "data"}]
    
    agent.running = True
    task = {"task_id": "t1", "type": "coding"}
    await agent.tasks_queue.put(task)
    
    with patch.object(agent, "execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"status": "success"}
        worker_task = asyncio.create_task(agent._task_worker())
        await asyncio.sleep(0.5)
        agent.running = False
        await worker_task
        
        # Check injected context
        injected_task = mock_exec.call_args[0][0]
        assert "_agile_context" in injected_task
        assert "Domain Expertise" in injected_task["_agile_context"]
        assert "Attached Documentation" in injected_task["_agile_context"]

@pytest.mark.asyncio
async def test_task_worker_retry_logic(mock_memory, mock_broker):
    agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
    # First attempt fails with exception, second succeeds
    agent.execute = AsyncMock(side_effect=[Exception("fail"), {"status": "success"}])
    agent.running = True
    
    with patch("agents.base_agent.MAX_RETRIES", 2), \
         patch("agents.base_agent.asyncio.sleep", new_callable=AsyncMock):
        
        task = {"task_id": "t1", "type": "coding"}
        await agent.tasks_queue.put(task)
        
        worker_task = asyncio.create_task(agent._task_worker())
        await asyncio.sleep(0.5)
        agent.running = False
        await worker_task
        
        assert "t1" in agent.completed_tasks
        assert agent.execute.call_count == 2

@pytest.mark.asyncio
async def test_retry_context_and_fix_instruction(mock_memory):
    with patch("core.llm_client.LLMClient", autospec=True):
        agent = MockAgent("a1", "backend", mock_memory, "/tmp/project")
        task = {
            "task_id": "t1",
            "type": "coding",
            "metadata": {"is_retry": True, "last_error": "SyntaxError"}
        }
        
        with patch.object(agent, "perform_research", new_callable=AsyncMock) as mock_res:
            mock_res.return_value = [{"title": "Fix", "href": "url", "body": "B"}]
            
            ctx = await agent.collect_retry_context(task)
            assert "SyntaxError" in ctx
            assert "url" in ctx
            
            instr = await agent.get_auto_fix_instruction(task)
            assert "RETRY" in instr

def test_inject_skill_context():
    agent = MockAgent("a1", "backend", None, "/tmp/project")
    agent.current_skill_content = "USE PYTHON"
    prompt = agent._inject_skill_context("Write code")
    assert "<skill_guidelines>" in prompt
    assert "USE PYTHON" in prompt

def test_normalize_files():
    agent = MockAgent("a1", "backend", None, "/tmp/project")
    assert agent.normalize_files({"f1.py": "code"}) == {"f1.py": "code"}
    assert agent.normalize_files([{"path": "f2.py", "content": "code2"}]) == {"f2.py": "code2"}
    assert agent.normalize_files([("f3.py", "code3")]) == {"f3.py": "code3"}
    assert agent.normalize_files(None) == {}

import pytest
import asyncio
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch
from core.memory import MemorySystem

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    memory_dir = tmp_path / "memory"
    with patch("core.memory.DB_PATH", str(db_path)), \
         patch("core.memory.MEMORY_DIR", memory_dir):
        yield db_path, memory_dir

@pytest.mark.asyncio
async def test_memory_initialize(temp_db):
    db_path, memory_dir = temp_db
    memory = MemorySystem()
    await memory.initialize()
    
    assert db_path.exists()
    assert memory_dir.exists()
    
    # Check tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "project_memory" in tables
    assert "tasks" in tables
    assert "token_usage" in tables
    conn.close()

@pytest.mark.asyncio
async def test_memory_migration(temp_db):
    db_path, _ = temp_db
    # Create legacy table
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            type TEXT,
            agent TEXT,
            description TEXT,
            priority INTEGER,
            status TEXT,
            metadata TEXT,
            created_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    cursor.execute("INSERT INTO tasks (task_id, type, agent, description) VALUES ('t1', 'type1', 'agent1', 'desc1')")
    conn.commit()
    conn.close()
    
    memory = MemorySystem()
    await memory.initialize()
    
    # Verify migration
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT agent_type FROM tasks WHERE task_id='t1'")
    row = cursor.fetchone()
    assert row[0] == "agent1"
    conn.close()

@pytest.mark.asyncio
async def test_log_action(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.log_action("agent1", "action1", "desc1", project_id="p1", metadata={"key": "val"})
    
    conn = sqlite3.connect(temp_db[0])
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM project_memory WHERE agent='agent1'")
    row = cursor.fetchone()
    assert row["action"] == "action1"
    assert json.loads(row["metadata"]) == {"key": "val"}
    conn.close()

@pytest.mark.asyncio
async def test_tasks_crud(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    
    # Create
    await memory.create_task("task1", "coding", "developer", "Write code", project_id="p1")
    
    # Get
    task = await memory.get_task("task1")
    assert task["description"] == "Write code"
    assert task["status"] == "pending"
    
    # Update status
    await memory.update_task_status("task1", "completed", assigned_to="dev1")
    task = await memory.get_task("task1")
    assert task["status"] == "completed"
    assert task["assigned_to"] == "dev1"
    assert task["completed_at"] is not None
    
    # Get all
    tasks = await memory.get_all_tasks(project_id="p1")
    assert len(tasks) == 1
    
    # Has tasks
    assert await memory.has_tasks("p1") == True
    assert await memory.has_tasks("p2") == False
    
    # Pending
    await memory.create_task("task2", "test", "qa", "Test code", project_id="p1")
    pending = await memory.get_pending_tasks(project_id="p1")
    assert len(pending) == 1 # Only task2 is pending
    assert pending[0]["task_id"] == "task2"

@pytest.mark.asyncio
async def test_recent_actions(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.log_action("a", "b", "c", project_id="p1")
    
    actions = await memory.get_recent_actions(limit=5, project_id="p1")
    assert len(actions) == 1
    assert actions[0]["agent"] == "a"

@pytest.mark.asyncio
async def test_get_projects(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.log_action("a", "b", "c", project_id="p1")
    await memory.create_task("t1", "t", "a", "d", project_id="p2")
    
    projects = await memory.get_projects()
    assert "p1" in projects
    assert "p2" in projects

@pytest.mark.asyncio
async def test_clear_project_data(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.log_action("a", "b", "c", project_id="p1")
    
    # Create retro file
    retro_file = temp_db[1] / "retrospective.md"
    retro_file.write_text("content")
    
    await memory.clear_project_data("p1")
    
    assert await memory.get_projects() == []
    assert not retro_file.exists()

@pytest.mark.asyncio
async def test_architecture_decisions(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.save_architecture_decision("d1", "Title", "Desc", "Rat", "Me")
    
    conn = sqlite3.connect(temp_db[0])
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM architecture_decisions WHERE decision_id='d1'")
    assert cursor.fetchone()[0] == "Title"
    conn.close()

@pytest.mark.asyncio
async def test_agent_prompts(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.save_agent_prompt("architect", "You are an architect", {"task": "template"})
    
    prompt = await memory.get_agent_prompt("architect")
    assert prompt["system_prompt"] == "You are an architect"
    assert prompt["task_templates"] == {"task": "template"}
    
    await memory.update_agent_prompt("architect", "New prompt")
    prompt = await memory.get_agent_prompt("architect")
    assert prompt["system_prompt"] == "New prompt"

@pytest.mark.asyncio
async def test_token_usage_and_stats(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.log_token_usage("agent1", "p1", "gpt-4", 100, 50, 150, 0.01, is_toon=True, saved_tokens=10)
    
    stats = await memory.get_agent_stats(project_id="p1")
    assert len(stats) == 1
    assert stats[0]["agent_id"] == "agent1"
    assert stats[0]["total_cost"] == 0.01
    assert stats[0]["toon_calls_count"] == 1
    assert stats[0]["total_saved_tokens"] == 10

@pytest.mark.asyncio
async def test_agent_documents(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    doc_id = await memory.add_agent_document("backend", "guide", "manual", "content")
    
    docs = await memory.get_agent_documents("backend")
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id
    
    await memory.delete_agent_document(doc_id)
    docs = await memory.get_agent_documents("backend")
    assert len(docs) == 0

@pytest.mark.asyncio
async def test_domain_knowledge(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.save_domain_knowledge("id1", "agent1", "domain1", "topic1", "summary", ["point1"], ["contr1"], 5, 0.9)
    
    knowledge = await memory.get_domain_knowledge_by_topic("agent1", "topic1")
    assert knowledge["synthesized_summary"] == "summary"
    assert knowledge["key_points"] == ["point1"]
    
    top = await memory.get_top_domain_knowledge("agent1", limit=1)
    assert len(top) == 1
    assert top[0]["topic"] == "topic1"

@pytest.mark.asyncio
async def test_scrum_flow(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    
    # Sprint
    sprint_id = await memory.create_sprint("p1", sprint_number=1)
    active = await memory.get_active_sprint("p1")
    assert active["sprint_id"] == sprint_id
    
    await memory.complete_sprint(sprint_id)
    assert await memory.get_active_sprint("p1") is None
    
    # Retrospective
    await memory.save_retrospective_feedback(sprint_id, "backend", "Good sprint", "positive")
    fbs = await memory.get_sprint_retrospective(sprint_id)
    assert len(fbs) == 1
    
    # Retrospectives history
    history = await memory.get_retrospectives(project_id="p1")
    assert len(history) == 1
    assert history[0]["sprint"]["sprint_id"] == sprint_id

@pytest.mark.asyncio
async def test_sprint_counter(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    val = await memory.increment_sprint_counter("p1")
    assert val == 1
    val = await memory.increment_sprint_counter("p1")
    assert val == 2
    
    counter = await memory.get_sprint_counter("p1")
    assert counter["total_sprints_completed"] == 2
    
    assert (await memory.get_sprint_counter("p2"))["total_sprints_completed"] == 0

@pytest.mark.asyncio
async def test_releases(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.increment_sprint_counter("p1")
    release_id = await memory.create_release("p1", "v1.0", 1, 8, "Notes")
    
    releases = await memory.get_releases("p1")
    assert len(releases) == 1
    assert releases[0]["version"] == "v1.0"

@pytest.mark.asyncio
async def test_backlog_refinement(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    sprint_id = await memory.create_sprint("p1")
    item_id = await memory.save_refinement_proposal("p1", sprint_id, "architect", "New feature")
    
    items = await memory.get_refinement_proposals("p1", sprint_id=sprint_id)
    assert len(items) == 1
    assert items[0]["description"] == "New feature"
    
    items_all = await memory.get_refinement_proposals("p1")
    assert len(items_all) == 1
    
    await memory.accept_refinement_proposals("p1", sprint_id)
    items = await memory.get_refinement_proposals("p1", sprint_id=sprint_id)
    assert items[0]["accepted"] == 1

@pytest.mark.asyncio
async def test_config_and_prompts(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.set_config("k1", "v1")
    assert await memory.get_config("k1") == "v1"
    assert await memory.get_config("k2") is None
    
    await memory.save_agent_prompt("a1", "p1")
    await memory.clear_agent_prompts()
    assert await memory.get_agent_prompt("a1") is None

@pytest.mark.asyncio
async def test_save_task_utility(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    task = {
        "task_id": "ut1",
        "project_id": "p1",
        "type": "feature",
        "agent_type": "backend",
        "description": "Desc",
        "metadata": {"m": 1},
        "depends_on": ["t0"]
    }
    await memory.save_task(task)
    
    db_task = await memory.get_task("ut1")
    assert db_task["type"] == "feature"
    assert db_task["depends_on"] == ["t0"]

@pytest.mark.asyncio
async def test_initialize_missing_columns(temp_db):
    db_path, _ = temp_db
    # Create tables with missing columns
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE project_memory (id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE sprints (sprint_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE token_usage (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    
    memory = MemorySystem()
    await memory.initialize()
    # If no error, columns were added
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tasks)")
    cols = [c[1] for c in cursor.fetchall()]
    assert "project_id" in cols
    assert "type" in cols
    conn.close()

@pytest.mark.asyncio
async def test_add_retrospective(temp_db):
    memory = MemorySystem()
    # No initialize needed for this as it's file based
    memory.memory_dir.mkdir(exist_ok=True)
    await memory.add_retrospective("Retro1", "Everything is fine")
    
    retro_file = temp_db[1] / "retrospective.md"
    assert "Everything is fine" in retro_file.read_text()

@pytest.mark.asyncio
async def test_memory_exception_branches(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    
    # Test update_task with no updates (line 418)
    await memory.update_task("t1", {})
    
    # Test update_task metadata (line 429)
    await memory.create_task("t1", "t", "a", "d")
    await memory.update_task("t1", {"metadata": {"new": 1}})
    task = await memory.get_task("t1")
    assert task["metadata"] == {"new": 1}
    
    # Test JSON errors in get_task (lines 393, 399)
    conn = sqlite3.connect(temp_db[0])
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET metadata='invalid', depends_on='invalid' WHERE task_id='t1'")
    conn.commit()
    conn.close()
    
    task = await memory.get_task("t1")
    assert task["metadata"] == {}
    assert task["depends_on"] == []

@pytest.mark.asyncio
async def test_get_all_tasks_json_error(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    await memory.create_task("t1", "t", "a", "d")
    conn = sqlite3.connect(temp_db[0])
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET metadata='invalid', depends_on='invalid'")
    conn.commit()
    conn.close()
    
    tasks = await memory.get_all_tasks()
    assert tasks[0]["metadata"] == {}
    assert tasks[0]["depends_on"] == []
    
    # Also for pending tasks
    pending = await memory.get_pending_tasks()
    assert pending[0]["metadata"] == {}

@pytest.mark.asyncio
async def test_update_task_error(temp_db, caplog):
    import logging
    caplog.set_level(logging.ERROR)
    memory = MemorySystem()
    await memory.initialize()
    
    # Trigger error by passing non-dict as updates if possible, or mocking cursor
    with patch("sqlite3.Cursor.execute", side_effect=Exception("DB Error")):
        await memory.update_task("t1", {"status": "ok"})
        assert "Error updating task" in caplog.text

@pytest.mark.asyncio
async def test_clear_project_data_error(temp_db, caplog):
    import logging
    caplog.set_level(logging.ERROR)
    memory = MemorySystem()
    await memory.initialize()
    
    with patch("sqlite3.Cursor.execute", side_effect=Exception("Wipe Error")):
        await memory.clear_project_data("p1")
        assert "Error wiping project data" in caplog.text

@pytest.mark.asyncio
async def test_get_domain_knowledge_none(temp_db):
    memory = MemorySystem()
    await memory.initialize()
    assert await memory.get_domain_knowledge_by_topic("none", "none") is None

import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.skills import SkillManager, SkillAwareAgent, create_default_skills

@pytest.fixture
def temp_skills_dir(tmp_path):
    skills_dir = tmp_path / ".claude"
    skills_dir.mkdir()
    return skills_dir

def test_skill_manager_init():
    manager = SkillManager(["/tmp/skills"])
    assert len(manager.skills_dirs) == 1
    assert manager.skills == {}

def test_skill_manager_initialize(temp_skills_dir):
    with patch("pathlib.Path.home", return_value=temp_skills_dir.parent):
        # Path.home() / ".claude" will be temp_skills_dir
        manager = SkillManager()
        manager.initialize(workspace_root=temp_skills_dir.parent)
        # Should find home .claude and workspace .claude (which are the same here)
        assert len(manager.skills_dirs) >= 1

def test_load_all_skills(temp_skills_dir):
    # Create a skill
    skill_path = temp_skills_dir / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("Skill content")
    
    manager = SkillManager([str(temp_skills_dir)])
    manager.load_all_skills()
    assert "test-skill" in manager.skills
    assert manager.skills["test-skill"]["content"] == "Skill content"

def test_load_skill_fail(temp_skills_dir):
    manager = SkillManager([str(temp_skills_dir)])
    assert manager._load_skill("non-existent") is None

def test_load_skill_exception(temp_skills_dir):
    skill_path = temp_skills_dir / "bad-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("content")
    
    manager = SkillManager([str(temp_skills_dir)])
    with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
        assert manager._load_skill("bad-skill", temp_skills_dir) is None

def test_parse_skill_metadata():
    manager = SkillManager()
    content = """---
description: Test Skill
agent_types: [backend]
---
# Content"""
    metadata = manager._parse_skill_metadata(content)
    assert metadata["description"] == "Test Skill"
    assert metadata["agent_types"] == ["backend"]

def test_parse_skill_metadata_invalid_yaml():
    manager = SkillManager()
    content = """---
invalid yaml : [ :
---
# Content"""
    metadata = manager._parse_skill_metadata(content)
    assert metadata["description"] == "" # Default

def test_get_skill(temp_skills_dir):
    manager = SkillManager([str(temp_skills_dir)])
    manager.create_skill("s1", "content1")
    assert manager.get_skill("s1") == "content1"
    assert manager.get_skill("unknown") is None

def test_get_skills_for_agent(temp_skills_dir):
    manager = SkillManager([str(temp_skills_dir)])
    manager.create_skill("s1", "c1", metadata={"agent_types": ["backend"]})
    manager.create_skill("s2", "c2", metadata={"agent_types": ["frontend"]})
    manager.create_skill("s3", "c3") # All agents
    
    backend_skills = manager.get_skills_for_agent("backend")
    assert len(backend_skills) == 2
    assert any(s["name"] == "s1" for s in backend_skills)
    assert any(s["name"] == "s3" for s in backend_skills)

def test_apply_skill_to_prompt(temp_skills_dir):
    manager = SkillManager([str(temp_skills_dir)])
    manager.create_skill("s1", "Skill Rules")
    prompt = "Do task"
    enhanced = manager.apply_skill_to_prompt("s1", prompt)
    assert "Skill Rules" in enhanced
    assert "Do task" in enhanced
    
    assert manager.apply_skill_to_prompt("unknown", prompt) == prompt

def test_find_skill_by_trigger(temp_skills_dir):
    manager = SkillManager([str(temp_skills_dir)])
    manager.create_skill("s1", "c1", metadata={"triggers": ["apple", "banana"]})
    assert manager.find_skill_by_trigger("I want an apple") == "s1"
    assert manager.find_skill_by_trigger("No fruits here") is None

def test_agent_skill_mapping():
    manager = SkillManager()
    manager.set_agent_skill_mapping({"backend": ["s1"]})
    manager.set_common_skills(["common1"])
    
    assert manager.get_agent_skills("backend") == ["s1"]
    assert manager.get_common_skills_for_agent("backend") == ["common1"]
    
    all_skills = manager.resolve_all_skills_for_agent("backend")
    assert "s1" in all_skills
    assert "common1" in all_skills

def test_resolve_all_skills_fallback(temp_skills_dir):
    manager = SkillManager([str(temp_skills_dir)])
    manager.create_skill("fallback-skill", "c", metadata={"triggers": ["task for backend"]})
    
    # No mapping set
    all_skills = manager.resolve_all_skills_for_agent("backend")
    assert all_skills == ["fallback-skill"]

@pytest.mark.asyncio
async def test_skill_aware_agent():
    mock_manager = MagicMock()
    mock_manager.get_skill.return_value = "Skill Content"
    mock_manager.find_skill_by_trigger.return_value = None
    mock_manager.get_skills_for_agent.return_value = []
    
    class MockAgent(SkillAwareAgent):
        def __init__(self, skill_manager):
            super().__init__(skill_manager=skill_manager)
            self.agent_type = "backend"
            
    agent = MockAgent(mock_manager)
    
    # Explicit skill in task
    task = {"skill": "s1"}
    content = await agent.load_skill_for_task(task)
    assert content == "Skill Content"
    mock_manager.get_skill.assert_called_with("s1")
    
    # Trigger detection
    mock_manager.get_skill.reset_mock()
    mock_manager.find_skill_by_trigger.return_value = "s2"
    task = {"description": "trigger me"}
    content = await agent.load_skill_for_task(task)
    assert content == "Skill Content"
    mock_manager.get_skill.assert_called_with("s2")
    
    # Default agent skills
    mock_manager.get_skill.reset_mock()
    mock_manager.find_skill_by_trigger.return_value = None
    mock_manager.get_skills_for_agent.return_value = [{"content": "Agent Skill"}]
    task = {}
    content = await agent.load_skill_for_task(task)
    assert content == "Agent Skill"

def test_enhance_prompt_with_skill():
    agent = SkillAwareAgent()
    prompt = "Task"
    assert agent.enhance_prompt_with_skill(prompt, None) == prompt
    
    enhanced = agent.enhance_prompt_with_skill(prompt, "Skill Content")
    assert "<skill_context>" in enhanced
    assert "Skill Content" in enhanced

def test_create_skill_with_metadata(temp_skills_dir):
    manager = SkillManager([str(temp_skills_dir)])
    metadata = {"agent_types": ["backend"]}
    manager.create_skill("meta-skill", "content", metadata=metadata)
    assert "meta-skill" in manager.skills
    assert manager.skills["meta-skill"]["metadata"]["agent_types"] == ["backend"]

def test_load_all_skills_nested(temp_skills_dir):
    # Test line 66: self._load_skill(skill_name, s_dir)
    skill_dir = temp_skills_dir / "nested"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("content")
    
    manager = SkillManager([str(temp_skills_dir)])
    manager.load_all_skills()
    assert "nested" in manager.skills

def test_get_skills_for_agent_no_metadata(temp_skills_dir):
    # Test line 148 branch
    manager = SkillManager([str(temp_skills_dir)])
    manager.create_skill("no-meta", "content")
    skills = manager.get_skills_for_agent("any")
    assert any(s["name"] == "no-meta" for s in skills)

def test_create_default_skills_full(temp_skills_dir):
    create_default_skills(temp_skills_dir)
    # This covers create_default_skills entirely
    assert (temp_skills_dir / "backend-api" / "SKILL.md").exists()

@pytest.mark.asyncio
async def test_skill_aware_agent_no_skill_manager():
    agent = SkillAwareAgent()
    assert isinstance(agent.skill_manager, SkillManager)

def test_main_block_coverage():
    # To cover the if __name__ == "__main__": block without actually running it as main
    # we can use a trick or just ignore it. 
    # But let's try to run the logic inside it.
    from core.skills import create_default_skills, SkillManager
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_path = Path(tmpdir) / ".claude"
        create_default_skills(skills_path)
        manager = SkillManager([str(skills_path)])
        manager.initialize()
        assert "backend-api" in manager.list_skills()
        assert manager.get_skill("backend-api") is not None
        assert manager.find_skill_by_trigger("create a REST api") == "backend-api"

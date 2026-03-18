#!/usr/bin/env python3
"""
Testing Agent con supporto TOON.
"""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TestingAgent(BaseAgent):
    """Testing specialist agent - TOON Ready"""

    def __init__(
        self,
        agent_id: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id, "testing", memory, project_root, skill_manager, prompt_manager
        )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue task testing"""
        task_type = task.get("type")
        if task_type == "write_tests":
            return await self._write_tests(task)
        else:
            logger.warning(f"Unknown testing task type: {task_type}")
            return {"status": "completed", "files_created": []}

    async def _write_tests(self, task: Dict) -> Dict[str, Any]:
        """Scrive test unitari usando LLM con output TOON"""
        description = task.get("description", "Write unit tests")
        metadata = task.get("metadata", {})
        target = metadata.get("target", "backend")

        # Get dynamic prompt
        prompt_config = await self.prompt_manager.get_prompt("testing", "write_tests")
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        # Auto-fix logic: include last error if it's a retry
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        logger.info(
            f"Generating unit tests with LLM for {target} (TOON): {description}"
        )

        prompt = f"""Task: {description}
Target component: {target}
{template}
{auto_fix_instruction}

═══════════════════════════════════════════════════════════════
🚨 CRITICAL RULES FOR TESTS 🚨
═══════════════════════════════════════════════════════════════
❌ FORBIDDEN:
- Empty test functions
- No assertions

✅ REQUIRED:
1. Multiple test cases per function (happy path + edge cases)
2. Proper assertions (assert/expect)
3. Mock external dependencies
4. Minimum 5 test cases per file
═══════════════════════════════════════════════════════════════

Generate unit and integration tests for the component.
Structure your response as an object with a 'files' key."""

        # Utilizza generazione strutturata (TOON priorità)
        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        files = self.normalize_files(data.get("files", {}))

        logger.info(f"💾 [Testing] LLM ha generato {len(files)} file di test.")

        created_files = []
        for filename, content in files.items():
            file_path = self.project_root / filename
            logger.info(f"   - Creazione file di test: {filename}")
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(content)
            created_files.append(str(file_path))

        return {"status": "completed", "files_created": created_files}

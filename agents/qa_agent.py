#!/usr/bin/env python3
"""
QA Agent con supporto TOON.
"""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class QAAgent(BaseAgent):
    """QA specialist agent - TOON Ready"""

    def __init__(
        self,
        agent_id: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id, "qa", memory, project_root, skill_manager, prompt_manager
        )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue task QA"""
        task_type = task.get("type")
        if task_type == "write_e2e_tests":
            return await self._write_e2e_tests(task)
        elif task_type == "validate_project":
            return await self._validate_project(task)
        else:
            logger.warning(f"Unknown QA task type: {task_type}")
            return {"status": "completed", "files_created": []}

    async def _write_e2e_tests(self, task: Dict) -> Dict[str, Any]:
        """Scrive test E2E usando LLM con output TOON"""
        description = task.get("description", "Write E2E tests")
        metadata = task.get("metadata", {})

        prompt_config = await self.prompt_manager.get_prompt("qa", "write_e2e_tests")
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        logger.info(f"Generating E2E tests with LLM (TOON): {description}")

        prompt = f"""Task: {description}
{template}
{auto_fix_instruction}

Generate E2E tests for the application. Use the appropriate testing framework.
Structure your response as an object with a 'files' key."""

        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        files = self.normalize_files(data.get("files", {}))

        created_files = []
        for filename, content in files.items():
            file_path = self.project_root / filename
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(content)
            created_files.append(str(file_path))

        return {"status": "completed", "files_created": created_files}

    async def _validate_project(self, task: Dict) -> Dict[str, Any]:
        """Valida il progetto usando LLM"""
        description = task.get("description", "Validate project")
        prompt_config = await self.prompt_manager.get_prompt("qa", "validate_project")
        system_prompt = prompt_config["system_prompt"]
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        logger.info(f"Validating project with LLM: {description}")

        prompt = f"Validate the project based on this description: {description}\n{auto_fix_instruction}"

        response = await self.llm_client.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

        return {"status": "completed", "validation_report": response}

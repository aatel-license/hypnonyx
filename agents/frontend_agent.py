#!/usr/bin/env python3
"""
Frontend Agent con supporto TOON.
"""

import logging
from typing import Dict, Any
from pathlib import Path

from agents.base_agent import BaseAgent
from utils.framework_detector import detect_tech_stack, get_framework_context
from utils.code_examples import get_frontend_example

logger = logging.getLogger(__name__)


class FrontendAgent(BaseAgent):
    """Frontend developer agent - TOON Ready"""

    def __init__(
        self,
        agent_id: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id, "frontend", memory, project_root, skill_manager, prompt_manager
        )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue task frontend"""
        task_type = task.get("type")

        if task_type == "create_ui":
            return await self._create_ui(task)
        elif task_type == "integrate_api":
            return await self._integrate_api(task)
        else:
            logger.warning(f"Unknown frontend task type: {task_type}")
            return {"status": "completed", "files_created": []}

    async def _create_ui(self, task: Dict) -> Dict[str, Any]:
        """Crea UI usando LLM con output TOON"""
        metadata = task.get("metadata", {})
        description = task.get("description", "Create UI components")

        # Detect tech stack
        logger.info(f"🔍 [Frontend] Rilevamento tech stack per {self.project_root}...")
        tech_stack = await detect_tech_stack(self.project_root)
        logger.info(f"📑 [Frontend] Stack rilevato: {tech_stack}")

        framework_context = get_framework_context(tech_stack)
        frontend_framework = tech_stack.get("frontend", "unknown")
        frontend_example = get_frontend_example(frontend_framework)

        logger.info(
            f"🎨 [Frontend] Utilizzo esempio UI per framework: {frontend_framework}"
        )

        # Get dynamic prompt
        prompt_config = await self.prompt_manager.get_prompt("frontend", "create_ui")
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        logger.info(f"🧠 [Frontend] Chiamata LLM Client (Structured/TOON)...")

        # Auto-fix logic: include last error if it's a retry
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        # Iniezione contesto agile
        agile_context = task.get("_agile_context", "")
        if agile_context:
            logger.info("Injecting agile retrospective context into Frontend prompt")

        # MVP Mode Instruction
        mvp_instruction = ""
        if metadata.get("mvp", False):
            mvp_instruction = "\n⚡ MVP MODE: Skip Auth views/logic, use MOCK data if backend is not ready, keep it thin. ⚡\n"

        prompt = f"""Task: {description}
Details: {metadata}
{template}
{auto_fix_instruction}
{mvp_instruction}

{framework_context}

{agile_context}

═══════════════════════════════════════════════════════════════
🚨 CRITICAL RULES FOR UI GENERATION 🚨
═══════════════════════════════════════════════════════════════

YOU MUST GENERATE COMPLETE, READY-TO-RUN FRONTEND CODE:

❌ FORBIDDEN:
- Placeholder components
- "implement logic here" comments
- Missing imports
- Generic "Hello World" boilerplate

✅ REQUIRED:
1. index.html: A complete, valid HTML entry point linking to the script.
2. Beautiful, responsive layout (use modern CSS/Grid/Flexbox).
3. State management (useState/Vue-reactive etc.).
4. Real data flow if integrated.
5. Modern typography and colors.

EXAMPLE OF ACCEPTABLE OUTPUT STRUCTURE:
{frontend_example}
═══════════════════════════════════════════════════════════════

IMPORTANT: Your response must include 'frontend/index.html'.

Structure your response as an object with a 'files' key."""

        # Utilizza generazione strutturata (TOON priorità)
        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        files = self.normalize_files(data.get("files", {}))

        frontend_dir = self.project_root / "frontend"
        frontend_dir.mkdir(exist_ok=True, parents=True)

        created_files = []
        for filename, content in files.items():
            file_path = self.project_root / filename
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(content)
            created_files.append(str(file_path))

        return {"status": "completed", "files_created": created_files}

    async def _integrate_api(self, task: Dict) -> Dict[str, Any]:
        """Integra le API nel frontend con output TOON"""
        metadata = task.get("metadata", {})
        description = task.get("description", "Integrate backend APIs")

        # Detect tech stack
        tech_stack = await detect_tech_stack(self.project_root)
        framework_context = get_framework_context(tech_stack)

        logger.info(f"🔗 [Frontend] Integrazione API per: {description}")

        # Get dynamic prompt
        prompt_config = await self.prompt_manager.get_prompt(
            "frontend", "integrate_api"
        )
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        # Auto-fix logic: include last error if it's a retry
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        prompt = f"""Task: {description}
{template}
{auto_fix_instruction}

{framework_context}

Generate the API service/integration code. 
Structure your response as an object with a 'files' key."""

        # Utilizza generazione strutturata (TOON priorità)
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

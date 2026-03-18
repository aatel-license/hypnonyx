#!/usr/bin/env python3
"""
Backend Agent con supporto TOON e generazione strutturata.
"""

import logging
from typing import Dict, Any
from pathlib import Path

from agents.base_agent import BaseAgent
from utils.framework_detector import detect_tech_stack, get_framework_context
from utils.code_examples import get_crud_example

logger = logging.getLogger(__name__)


class BackendAgent(BaseAgent):
    """Backend developer agent - TOON Ready"""

    def __init__(
        self,
        agent_id: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id, "backend", memory, project_root, skill_manager, prompt_manager
        )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue task backend"""
        task_type = task.get("type")

        if task_type == "implement_api":
            return await self._implement_api(task)
        elif task_type == "implement_auth":
            return await self._implement_auth(task)
        else:
            logger.warning(f"Unknown backend task type: {task_type}")
            return {"status": "completed", "files_created": []}

    async def _implement_api(self, task: Dict) -> Dict[str, Any]:
        """Implementa REST API usando LLM con output TOON"""
        description = task.get("description", "Implement REST API")
        metadata = task.get("metadata", {})

        # Detect tech stack from architecture
        logger.info(f"🔍 [Backend] Rilevamento tech stack per {self.project_root}...")
        tech_stack = await detect_tech_stack(self.project_root)
        logger.info(f"📑 [Backend] Stack rilevato: {tech_stack}")

        framework_context = get_framework_context(tech_stack)
        backend_framework = tech_stack.get("backend", "unknown")
        crud_example = get_crud_example(backend_framework)

        logger.info(
            f"🛠️ [Backend] Utilizzo esempio CRUD per framework: {backend_framework}"
        )

        # Get dynamic prompt
        prompt_config = await self.prompt_manager.get_prompt("backend", "implement_api")
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        logger.info(f"🧠 [Backend] Chiamata LLM Client (Structured/TOON)...")

        # Auto-fix logic: include last error if it's a retry
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        # Iniezione contesto agile
        agile_context = task.get("_agile_context", "")
        if agile_context:
            logger.info("Injecting agile retrospective context into Backend prompt")

        # MVP Mode Instruction
        mvp_instruction = ""
        if metadata.get("mvp", False):
            mvp_instruction = (
                "\n⚡ MVP MODE: Skip Auth, use MOCK data, keep it thin. ⚡\n"
            )

        prompt = f"""Task: {description}
Details: {metadata}
{template}
{auto_fix_instruction}
{mvp_instruction}

{framework_context}

{agile_context}

═══════════════════════════════════════════════════════════════
🚨 CRITICAL RULES FOR CODE GENERATION 🚨
═══════════════════════════════════════════════════════════════

YOU MUST GENERATE COMPLETE, PRODUCTION-READY CODE:

❌ FORBIDDEN:
- Placeholder code (e.g., "# TODO", "pass", "placeholder")
- Empty functions (must have actual logic)
- diff syntax (no + or - prefixes)
- Comments like "implement later"
- Minimal/stub implementations

✅ REQUIRED:
1. Complete CRUD operations (GET, POST, PUT, DELETE)
2. Database integration (models, schemas, queries)
3. Proper error handling (try/except or framework-equivalent)
4. Input validation
5. Docstrings/comments for all functions
6. All necessary imports
7. Minimum 300 bytes per file

EXAMPLE OF ACCEPTABLE OUTPUT:
{crud_example}

THIS IS THE MINIMUM STANDARD. Go above and beyond this.
═══════════════════════════════════════════════════════════════

Generate the necessary backend API files. Use the requested programming language and framework.
Structure your response as an object with 'files' and 'requirements' keys."""

        # Utilizza generazione strutturata (TOON priorità)
        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        files = self.normalize_files(data.get("files", {}))
        reqs = data.get("requirements", ["fastapi", "uvicorn", "pydantic"])

        logger.info(f"💾 [Backend] LLM ha generato {len(files)} file.")

        backend_dir = self.project_root / "backend"
        backend_dir.mkdir(exist_ok=True, parents=True)

        created_files = []
        for filename, content in files.items():
            file_path = self.project_root / filename
            logger.info(f"   - Creazione file: {filename}")
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(content)
            created_files.append(str(file_path))

        # Create requirements
        req_content = "\n".join(reqs)
        (backend_dir / "requirements.txt").write_text(req_content)
        created_files.append(str(backend_dir / "requirements.txt"))
        logger.info(
            f"📦 [Backend] Generato requirements.txt con {len(reqs)} pacchetti."
        )

        return {"status": "completed", "files_created": created_files}

    async def _implement_auth(self, task: Dict) -> Dict[str, Any]:
        """Implementa autenticazione usando LLM con output TOON"""
        metadata = task.get("metadata", {})
        description = task.get("description", "Implement authentication")

        if metadata.get("mvp", False):
            logger.info("⚡ MVP MODE: skipping authentication implementation.")
            return {"status": "completed", "files_created": []}

        # Get dynamic prompt
        prompt_config = await self.prompt_manager.get_prompt(
            "backend", "implement_auth"
        )
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        # Auto-fix logic: include last error if it's a retry
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        logger.info(f"Generating Authentication with LLM (TOON): {description}")

        prompt = f"""Task: {description}
{template}
{auto_fix_instruction}

Generate the necessary authentication files. Use the requested programming language and framework.
Structure your response as an object with 'files' and 'requirements' keys."""

        # Utilizza generazione strutturata (TOON priorità)
        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        files = self.normalize_files(data.get("files", {}))

        backend_dir = self.project_root / "backend"
        backend_dir.mkdir(exist_ok=True, parents=True)

        created_files = []
        for filename, content in files.items():
            file_path = self.project_root / filename
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(content)
            created_files.append(str(file_path))

        return {"status": "completed", "files_created": created_files}

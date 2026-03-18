#!/usr/bin/env python3
"""
DevOps Agent con supporto TOON.
"""

import logging
from typing import Dict, Any
from pathlib import Path
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DevOpsAgent(BaseAgent):
    """DevOps developer agent - TOON Ready"""

    def __init__(
        self,
        agent_id: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id, "devops", memory, project_root, skill_manager, prompt_manager
        )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue task devops"""
        task_type = task.get("type")
        if task_type == "create_docker":
            return await self._create_docker(task)
        elif task_type == "setup_ci":
            return await self._setup_ci(task)
        elif task_type == "create_startup_script":
            return await self._create_startup_script(task)
        elif task_type == "speaking_commit":
            return await self._speaking_commit(task)
        else:
            logger.warning(f"Unknown devops task type: {task_type}")
            return {"status": "completed", "files_created": []}

    async def _create_startup_script(self, task: Dict) -> Dict[str, Any]:
        """Crea uno script di avvio professionale usando LLM con output TOON"""
        description = task.get("description", "Create startup script")
        metadata = task.get("metadata", {})

        # Auto-fix logic: include last error if it's a retry
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        # Get dynamic prompt
        prompt_config = await self.prompt_manager.get_prompt(
            "devops", "create_startup_script"
        )
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        logger.info(f"Generating startup script with LLM (TOON): {description}")

        prompt = f"""Task: {description}
{template}
{auto_fix_instruction}

The script should:
1. Check for necessary dependencies (e.g., python, node, docker).
2. Handle environment variables.
3. Start all components (backend, frontend, database) in the background.
4. Provide clear logging or output.
5. Be robust and handle errors.

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

            if filename.endswith(".sh"):
                try:
                    import os
                    import stat

                    st = os.stat(file_path)
                    os.chmod(file_path, st.st_mode | stat.S_IEXEC)
                except Exception as e:
                    logger.warning(f"Impossibile rendere eseguibile {filename}: {e}")

            created_files.append(str(file_path))

        return {"status": "completed", "files_created": created_files}

    async def _speaking_commit(self, task: Dict) -> Dict[str, Any]:
        """Genera un commit descrittivo usando LLM con output TOON"""
        metadata = task.get("metadata", {})
        task_description = metadata.get("description", "")
        files_modified = metadata.get("files", [])

        context = ""
        for f in files_modified:
            f_path = Path(f)
            if f_path.exists():
                context += f"\n--- {f} ---\n{f_path.read_text()[:1000]}...\n"

        prompt_config = await self.prompt_manager.get_prompt(
            "devops", "speaking_commit"
        )
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        prompt = f"""
Original Task: {task_description}
Files modified: {", ".join(files_modified)}

{template}

Context of changes:
{context}

Structure your response as an object with a 'commit_message' key.
"""

        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        commit_message = data.get(
            "commit_message", f"feat: completed {task_description[:30]}"
        )

        import subprocess

        try:
            logger.info(f"📝 [DevOps] Esecuzione commit: '{commit_message}'")
            subprocess.run(["git", "add", "."], cwd=self.project_root, check=True)
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )
            commit_hash = hash_result.stdout.strip()[:8]

            logger.info(
                f"✅ [DevOps] Commit completato: {commit_message} ({commit_hash})"
            )
            return {
                "status": "completed",
                "commit_hash": commit_hash,
                "message": commit_message,
            }
        except Exception as e:
            logger.error(f"❌ [DevOps] Git commit fallito: {e}")
            return {"status": "failed", "error": str(e)}

    async def _create_docker(self, task: Dict) -> Dict[str, Any]:
        """Crea configurazione Docker usando LLM con output TOON"""
        description = task.get("description", "Create Docker configuration")
        metadata = task.get("metadata", {})

        prompt_config = await self.prompt_manager.get_prompt("devops", "create_docker")
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        logger.info(f"Generating Docker config with LLM (TOON): {description}")

        prompt = f"""Task: {description}
{template}
{auto_fix_instruction}

═══════════════════════════════════════════════════════════════
🚨 CRITICAL RULES FOR DOCKER CONFIG 🚨
═══════════════════════════════════════════════════════════════
❌ FORBIDDEN:
- Comments like "configure this later"
- Missing environment variables
- No health checks

✅ REQUIRED:
1. Multi-stage Docker builds
2. Proper base images (alpine, slim)
3. Health checks for all services
4. Volume mounts
5. docker-compose with all services
═══════════════════════════════════════════════════════════════

Generate Dockerfile for backend/ and a docker-compose.yml in root.
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

    async def _setup_ci(self, task: Dict) -> Dict[str, Any]:
        """Setup CI/CD usando LLM con output TOON"""
        description = task.get("description", "Setup CI/CD pipeline")

        prompt_config = await self.prompt_manager.get_prompt("devops", "setup_ci")
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        logger.info(f"Setting up CI/CD with LLM (TOON): {description}")

        prompt = f"""Task: {description}
{template}
{auto_fix_instruction}
Generate GitHub Actions workflow file in '.github/workflows/ci.yml'.

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

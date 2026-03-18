#!/usr/bin/env python3
"""
Universal Agent - A configurable agent that can take on any role.
"""

import logging
from typing import Dict, Any, List
from pathlib import Path

from agents.base_agent import BaseAgent
from utils.framework_detector import detect_tech_stack, get_framework_context
from utils.code_examples import get_crud_example

logger = logging.getLogger(__name__)


class UniversalAgent(BaseAgent):
    """
    Universal Specialist Agent.
    Instead of hardcoded logic for each role, it dynamically loads its
    persona and task instructions from the database.
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,  # e.g. "backend", "frontend", "qa"
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id, agent_type, memory, project_root, skill_manager, prompt_manager
        )
        logger.info(f"UniversalAgent [{agent_id}] initialized as type: {agent_type}")

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """
        Generic execution logic for any task type.
        """
        task_type = task.get("type", "generic")
        description = task.get("description", "Perform task")
        metadata = task.get("metadata", {})

        logger.info(
            f"🚀 [UniversalAgent:{self.agent_type}] Executing task: {task_type}"
        )

        # 1. Fetch Persona and Task Template from PromptManager
        prompt_config = await self.prompt_manager.get_prompt(self.agent_type, task_type)
        if not prompt_config:
            logger.warning(
                f"No prompt configuration found for {self.agent_type}:{task_type}"
            )
            return {
                "status": "failed",
                "error": f"No prompt configured for {self.agent_type}:{task_type}",
            }

        system_prompt = prompt_config.get(
            "system_prompt", f"You are a expert {self.agent_type} developer."
        )
        template = prompt_config.get("template", "")

        # 2. Dynamic Context Enhancement (Tech Stack, CRUD examples, etc.)
        # We inject these only if relevant to the agent type
        framework_context = ""
        crud_example = ""
        tech_context = ""

        if self.agent_type in ["backend", "frontend", "database"]:
            tech_stack = await detect_tech_stack(self.project_root)
            framework_context = get_framework_context(tech_stack)

            if self.agent_type == "backend":
                framework = tech_stack.get("backend", "fastapi")
                crud_example = (
                    f"\nEXAMPLE OF ACCEPTABLE OUTPUT:\n{get_crud_example(framework)}\n"
                )
            elif self.agent_type == "database":
                tech_context = (
                    f"\nTarget Database: {tech_stack.get('database', 'sqlite')}\n"
                )

        # 3. Instruction Assembly
        auto_fix_instruction = await self.get_auto_fix_instruction(task)
        agile_context = task.get("_agile_context", "")

        # MVP Mode
        mvp_instruction = ""
        if metadata.get("mvp", False):
            mvp_instruction = (
                "\n⚡ MVP MODE: Keep it minimal, focus on core functionality. ⚡\n"
            )

        prompt = f"""Task: {description}
Details: {metadata}

{template}

{auto_fix_instruction}
{mvp_instruction}

{framework_context}
{tech_context}
{crud_example}

{agile_context}

═══════════════════════════════════════════════════════════════
🚨 CRITICAL RULES FOR GENERATION 🚨
═══════════════════════════════════════════════════════════════
- Generate COMPLETE, production-ready code.
- NO placeholders (# TODO, etc.).
- Proper error handling and comments.
- Structure your response as an object with 'files' and optionally 'requirements' keys.
═══════════════════════════════════════════════════════════════
"""

        if task_type == "speaking_commit":
            return await self._execute_speaking_commit(task, system_prompt, template)

        # 4. LLM Call
        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        # 5. Generic File Persistence
        files = self.normalize_files(data.get("files", {}))
        created_files = []

        for filename, content in files.items():
            file_path = self.project_root / filename
            logger.info(f"   - Writing file: {filename}")
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(content)
            created_files.append(str(file_path))

        # 6. Generic Requirements Handling
        reqs = data.get("requirements", [])
        if reqs:
            # We try to find where to put requirements
            # If tech stack is known, we use it, otherwise fallback to project root
            backend_dir = self.project_root / "backend"
            req_file = self.project_root / "requirements.txt"
            if backend_dir.exists():
                req_file = backend_dir / "requirements.txt"

            if req_file.exists():
                try:
                    old_reqs = req_file.read_text().splitlines()
                    new_reqs = sorted(list(set(old_reqs + reqs)))
                    req_file.write_text("\n".join(new_reqs))
                except Exception as e:
                    logger.warning(f"Could not update requirements file: {e}")
            else:
                req_file.parent.mkdir(exist_ok=True, parents=True)
                req_file.write_text("\n".join(reqs))

            created_files.append(str(req_file))
            logger.info(f"📦 Requirements updated in {req_file.name}")

        return {"status": "completed", "files_created": created_files}

    async def _execute_speaking_commit(
        self, task: Dict, system_prompt: str, template: str
    ) -> Dict[str, Any]:
        """Specialized execution for git commits"""
        metadata = task.get("metadata", {})
        task_description = metadata.get("description", "")
        files_modified = metadata.get("files", [])

        context = ""
        for f in files_modified:
            f_path = self.project_root / f
            if f_path.exists() and f_path.is_file():
                try:
                    context += f"\n--- {f} ---\n{f_path.read_text()[:500]}...\n"
                except Exception:
                    pass

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
        commit_message = data.get(
            "commit_message", f"feat: completed {task_description[:30]}"
        )

        import subprocess

        try:
            logger.info(
                f"📝 [UniversalAgent:devops] Esecuzione commit: '{commit_message}'"
            )
            subprocess.run(["git", "add", "."], cwd=self.project_root, check=True)
            # Check if there are changes to commit
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )
            if not status.stdout.strip():
                logger.info("No changes to commit (working tree clean).")
                return {
                    "status": "completed",
                    "message": "No changes to commit",
                    "commit_hash": "none",
                }

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

            logger.info(f"✅ [UniversalAgent:devops] Commit completato: {commit_hash}")
            return {
                "status": "completed",
                "commit_hash": commit_hash,
                "message": commit_message,
            }
        except Exception as e:
            logger.error(f"❌ [UniversalAgent:devops] Git commit fallito: {e}")
            return {"status": "failed", "error": str(e)}

#!/usr/bin/env python3
"""
Prompt Manager con integrazione SQLite e Redis
"""

import json
import logging
from typing import Dict
import redis
from config import REDIS_URL, USE_TOON


logger = logging.getLogger(__name__)

# ← ADD THIS
FORMAT_INSTRUCTION = (
    "Return your output in TOON format as instructed."
    if USE_TOON else
    "Return your output as valid JSON only. No markdown, no backticks."
)

STRUCTURE_GUIDE = """
CRITICAL ARCHITECTURAL CONSTRAINTS:
- BACKEND: All code MUST be in 'backend/app/'. (Entry: 'backend/app/main.py', API: 'backend/app/api/', Models: 'backend/app/models/')
- FRONTEND: All code MUST be in 'frontend/src/'. (Entry: 'frontend/src/App.tsx', Components: 'frontend/src/components/')
- SCRIPTS: All utility scripts MUST be in 'scripts/'.
- TESTS: All tests MUST be in 'tests/'.
- ROOT: Only 'requirements.txt', 'docker-compose.yml', and '.env' are allowed in the project root.
- CONSISTENCY: Do not create duplicate files. Check existing structure before creating new paths.
"""



class PromptManager:
    """Gestore dei prompt centralizzato con caching Redis"""

    def __init__(self, memory):
        self.memory = memory
        self.redis_client = None
        try:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            logger.info(f"✓ Connesso a Redis: {REDIS_URL}")
        except Exception as e:
            logger.warning(
                f"⚠ Redis non disponibile ({e}). Il sistema userà solo SQLite."
            )
            self.redis_client = None

    async def get_prompt(self, agent_type: str, task_type: str = None) -> Dict[str, str]:
        redis_key = f"prompts:{agent_type}"

        if self.redis_client:
            try:
                cached = self.redis_client.get(redis_key)
                if cached:
                    data = json.loads(cached)
                    return self._process_data(data, task_type)
            except Exception as e:
                logger.error(f"Errore lettura Redis: {e}")

        data = await self.memory.get_agent_prompt(agent_type)
        if data:
            if self.redis_client:
                try:
                    self.redis_client.set(redis_key, json.dumps(data), ex=3600)
                except Exception as e:
                    logger.error(f"Errore scrittura Redis: {e}")
            return self._process_data(data, task_type)

        return self._get_default_prompt(agent_type, task_type)

    def _process_data(self, data: Dict, task_type: str) -> Dict[str, str]:
        result = {"system_prompt": data.get("system_prompt", ""), "template": ""}
        if task_type:
            templates = data.get("task_templates", {})
            result["template"] = templates.get(task_type, "")
        return result

    def _get_default_prompt(self, agent_type: str, task_type: str) -> Dict[str, str]:
        logger.warning(f"Nessun prompt configurato nel DB per {agent_type}. Uso default.")
        return {
            "system_prompt": f"You are an expert {agent_type} developer.",
            "template": f"Implement the task: {task_type}" if task_type else "",
        }

    async def initialize_default_prompts(self, force: bool = False):
        """Popola il DB con i prompt correnti per migrazione"""

        # ← ADD VERSION CHECK to force re-init when USE_TOON changes
        VERSION = f"v2-{'toon' if USE_TOON else 'json'}"
        cached_version = await self.memory.get_config("prompt_version")
        if cached_version == VERSION and not force:
            logger.info(f"Prompts già inizializzati ({VERSION}), skip.")
            return

        defaults = {
            "backend": {
                "system": f"You are an expert backend developer. {FORMAT_INSTRUCTION} {STRUCTURE_GUIDE}",
                "tasks": {
                    "implement_api": "Implement the core API logic and endpoints in 'backend/app/api/'.",
                    "implement_auth": "Implement the authentication system in 'backend/app/core/auth.py'.",
                },
            },
            "frontend": {
                "system": f"You are an expert frontend developer. {FORMAT_INSTRUCTION} {STRUCTURE_GUIDE}",
                "tasks": {
                    "create_ui": "Create UI components in 'frontend/src/components/'. Use TypeScript (.tsx).",
                    "integrate_api": "Integrate frontend with the backend API.",
                },
            },
            "database": {
                "system": f"You are an expert database administrator. {FORMAT_INSTRUCTION} {STRUCTURE_GUIDE}",
                "tasks": {
                    "design_schema": "Design the database schema in 'backend/app/models/'.",
                    "create_migrations": "Create database migrations in 'database/migrations/'.",
                },
            },
            "devops": {
                "system": f"You are an expert DevOps engineer and Git specialist. {FORMAT_INSTRUCTION} {STRUCTURE_GUIDE}",
                "tasks": {
                    "create_docker": "Create container configuration (e.g., Dockerfile, Compose).",
                    "setup_ci": "Setup CI/CD pipeline configuration.",
                    "create_startup_script": "Create a startup script in 'scripts/start.sh'.",
                    "speaking_commit": "Generate a Conventional Commit message.",
                },
            },
            "testing": {
                "system": f"You are an expert QA engineer. {FORMAT_INSTRUCTION} {STRUCTURE_GUIDE} Always use mocking libraries.",
                "tasks": {
                    "write_tests": "Write unit tests in 'tests/unit/'."
                },
            },
            "qa": {
                "system": f"You are an expert QA lead. {FORMAT_INSTRUCTION} {STRUCTURE_GUIDE}",
                "tasks": {
                    "write_e2e_tests": "Write end-to-end tests in 'tests/e2e/'.",
                    "validate_project": "Validate the entire project requirements.",
                },
            },
            "researcher": {
                "system": f"You are a senior technical researcher. {STRUCTURE_GUIDE} Return a clean markdown report.",
                "tasks": {
                    "research_tech_stack": "Research the most modern and stable tech stack for the project.",
                    "search_docs": "Analyze official documentation.",
                },
            },
            "reviewer": {
                "system": f"You are a senior code reviewer. {FORMAT_INSTRUCTION} {STRUCTURE_GUIDE} You MUST reject any PR that violates the folder structure or creates duplicates.",
                "tasks": {
                    "review_task": "Check for folder structure, requirements, standards, and security. REJECT if duplicates or wrong paths are used."
                },
            },
            "architect": {
                "system": f"You are a senior software architect. {FORMAT_INSTRUCTION} {STRUCTURE_GUIDE} Ensure all design decisions respect the standard layout.",
                "tasks": {
                    "design_architecture": "Design the technical architecture. MANDATORY: Specify the exact folder structure following the provided guide."
                },
            },
            "scrum_master": {
                "system": f"You are an expert Scrum Master. {STRUCTURE_GUIDE}",
                "tasks": {
                    "sprint_planning": "Plan the next sprint.",
                    "retrospective": "Analyze feedback and generate action items.",
                    "backlog_refinement": "Refine the product backlog.",
                },
            },
        }


        for agent, pdata in defaults.items():
            await self.memory.save_agent_prompt(agent, pdata["system"], pdata["tasks"])

        # ← flush Redis cache so new prompts are picked up immediately
        if self.redis_client:
            for agent in defaults:
                try:
                    self.redis_client.delete(f"prompts:{agent}")
                except Exception:
                    pass

        await self.memory.set_config("prompt_version", VERSION)
        logger.info(f"✓ Prompt inizializzati ({VERSION})")
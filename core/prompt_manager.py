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
                "system": f"You are an expert backend developer. {FORMAT_INSTRUCTION} CRITICAL: Always write files using paths relative to the project root (e.g., 'backend/main.py'), NEVER absolute paths.",
                "tasks": {
                    "implement_api": "Implement the core API logic and endpoints as requested.",
                    "implement_auth": "Implement the requested authentication and authorization system.",
                },
            },
            "frontend": {
                "system": f"You are an expert frontend developer. {FORMAT_INSTRUCTION} CRITICAL: Always write files using paths relative to the project root (e.g., 'frontend/src/App.js'), NEVER absolute paths.",
                "tasks": {
                    "create_ui": "Create UI components using the requested technology (HTML/CSS/JS, React, Vue, etc.).",
                    "integrate_api": "Integrate frontend with the backend API.",
                },
            },
            "database": {
                "system": f"You are an expert database administrator. {FORMAT_INSTRUCTION} CRITICAL: Always write files using paths relative to the project root (e.g., 'database/schema.sql'), NEVER absolute paths.",
                "tasks": {
                    "design_schema": "Design the database schema (SQL or NoSQL as requested).",
                    "create_migrations": "Create database migrations or initialization scripts.",
                },
            },
            "devops": {
                "system": f"You are an expert DevOps engineer and Git specialist. {FORMAT_INSTRUCTION} CRITICAL: Always write files using paths relative to the project root (e.g., 'docker/Dockerfile'), NEVER absolute paths.",
                "tasks": {
                    "create_docker": "Create container configuration (e.g., Dockerfile, Compose).",
                    "setup_ci": "Setup CI/CD pipeline configuration.",
                    "create_startup_script": "Create a professional startup script (e.g., dashboard.sh or start.py) that launches all project components (backend, frontend, etc.). It should handle dependency checks and environment variables.",
                    "speaking_commit": "Generate a highly descriptive and meaningful commit message based on the provided changes and task description. Follow Conventional Commits format.",
                },
            },
            "testing": {
                "system": f"You are an expert QA engineer. {FORMAT_INSTRUCTION} CRITICAL: Always use mocking libraries (e.g., 'unittest.mock' or 'pytest-mock') to isolate components. Write tests using paths relative to the project root.",
                "tasks": {
                    "write_tests": "Write unit and integration tests for the requested component. MANDATORY: Use mocks for all external dependencies and cross-module calls."
                },
            },
            "qa": {
                "system": f"You are an expert QA lead. {FORMAT_INSTRUCTION} CRITICAL: Always write files using paths relative to the project root (e.g., 'tests/e2e/test_main.py'), NEVER absolute paths.",
                "tasks": {
                    "write_e2e_tests": "Write end-to-end tests for the complete application.",
                    "validate_project": "Validate the entire project requirements.",
                },
            },
            "researcher": {
                # ← no FORMAT_INSTRUCTION: uses chat_completion directly
                "system": "You are a senior technical researcher. Analyze documentation and versions. Return a clean markdown report. CRITICAL: References should be exact and actionable.",
                "tasks": {
                    "research_tech_stack": "Research the most modern and stable tech stack for the project.",
                    "search_docs": "Analyze official documentation for the requested technology.",
                },
            },
            "reviewer": {
                "system": f"You are a senior code reviewer. You must be CRITICAL but balanced. Proactively differentiate between architectural flaws and minor implementation details. {FORMAT_INSTRUCTION}",
                "tasks": {
                    "review_task": "Analyze the implemented work. 1. If ARCHITECTURE: Focus on structural correctness, scalability, and completeness. DO NOT reject for missing code-level logic like specific if/else checks if the design is solid. 2. If CODE: Check for folder structure, requirements, standards, and security. Provide an approval status and specific, actionable comments."
                },
            },
            "architect": {
                "system": f"You are a senior software architect. Your goal is to design a robust, scalable, and well-structured architecture. {FORMAT_INSTRUCTION} with decisions and design patterns.",
                "tasks": {
                    "design_architecture": "Design the technical architecture for the project. Create architecture.md with: 1. System Overview. 2. Component Diagram. 3. Detailed Folder Structure. 4. API Endpoints Specification (Methods, URLs, Response structures). 5. Database Schema (Normalized). 6. Security (Auth strategy, Hashing). 7. ADRs."
                },
            },
            "scrum_master": {
                # ← no FORMAT_INSTRUCTION: uses generate_structured with its own prompts
                "system": "You are an expert Scrum Master. Your goal is to facilitate agile ceremonies, manage the backlog, and ensure the team follows Scrum principles. You must coordinate the agents and collect their feedback.",
                "tasks": {
                    "sprint_planning": "Plan the next sprint. Analyze the backlog and select the priority tasks for the current sprint.",
                    "retrospective": "Facilitate the sprint retrospective. Analyze feedback from all agents and generate a summary report with action items.",
                    "backlog_refinement": "Refine the product backlog. Clarify requirements and break down large tasks into smaller, manageable items.",
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
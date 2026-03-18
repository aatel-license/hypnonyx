#!/usr/bin/env python3
"""
Database Agent con supporto TOON.
"""

import logging
from typing import Dict, Any
from pathlib import Path

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DatabaseAgent(BaseAgent):
    """Database administrator agent - TOON Ready"""

    def __init__(
        self,
        agent_id: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id, "database", memory, project_root, skill_manager, prompt_manager
        )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue task database"""
        task_type = task.get("type")

        if task_type == "design_schema":
            return await self._design_schema(task)
        elif task_type == "create_migrations":
            return await self._create_migrations(task)
        else:
            logger.warning(f"Unknown database task type: {task_type}")
            return {"status": "completed", "files_created": []}

    async def _design_schema(self, task: Dict) -> Dict[str, Any]:
        """Progetta schema database usando LLM con output TOON"""
        description = task.get("description", "Design database schema")
        metadata = task.get("metadata", {})

        # Get dynamic prompt
        prompt_config = await self.prompt_manager.get_prompt(
            "database", "design_schema"
        )
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        # Auto-fix logic: include last error if it's a retry
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        logger.info(f"Designing database schema with LLM (TOON): {description}")

        prompt = f"""Task: {description}
{template}
{auto_fix_instruction}

═══════════════════════════════════════════════════════════════
🚨 CRITICAL RULES FOR DATABASE SCHEMA 🚨
═══════════════════════════════════════════════════════════════

YOU MUST GENERATE COMPLETE DATABASE SCHEMA:

❌ FORBIDDEN:
- Placeholder tables or columns
- Missing foreign keys
- No indexes
- Comments like "add more fields"

✅ REQUIRED:
1. All necessary tables with proper relationships
2. Foreign keys with ON DELETE/UPDATE constraints
3. Indexes on frequently queried columns
4. NOT NULL constraints where appropriate
5. DEFAULT values where useful
6. UNIQUE constraints for identifying columns
7. Timestamps (created_at, updated_at) on all tables
8. Primary keys (auto-increment or UUID)

Example PostgreSQL schema:
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
═══════════════════════════════════════════════════════════════

Generate a schema.sql file in 'database/'.
Structure your response as an object with a 'files' key."""

        # Utilizza generazione strutturata (TOON priorità)
        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        files = self.normalize_files(data.get("files", {}))

        logger.info(f"💾 [Database] LLM ha generato {len(files)} file di schema.")

        db_dir = self.project_root / "database"
        db_dir.mkdir(exist_ok=True, parents=True)

        created_files = []
        for filename, content in files.items():
            file_path = self.project_root / filename
            logger.info(f"   - Creazione file schema: {filename}")
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(content)
            created_files.append(str(file_path))

        return {"status": "completed", "files_created": created_files}

    async def _create_migrations(self, task: Dict) -> Dict[str, Any]:
        """Crea migrations usando LLM con output TOON"""
        description = task.get("description", "Create database migrations")
        metadata = task.get("metadata", {})

        # Get dynamic prompt
        prompt_config = await self.prompt_manager.get_prompt(
            "database", "create_migrations"
        )
        system_prompt = prompt_config["system_prompt"]
        template = prompt_config["template"]

        # Auto-fix logic: include last error if it's a retry
        auto_fix_instruction = await self.get_auto_fix_instruction(task)

        logger.info(f"Creating migrations with LLM (TOON): {description}")

        prompt = f"""Task: {description}
{template}
{auto_fix_instruction}
Generate a migration SQL file in 'database/migrations/001_initial_schema.sql' and a Python runner 'database/run_migrations.py'.

Structure your response as an object with a 'files' key."""

        # Utilizza generazione strutturata (TOON priorità)
        data = await self.llm_client.generate_structured(
            system_prompt=system_prompt, prompt=prompt
        )
        if not data:
            data = {}

        files = self.normalize_files(data.get("files", {}))

        logger.info(f"💾 [Database] LLM ha generato {len(files)} file di migration.")

        created_files = []
        for filename, content in files.items():
            file_path = self.project_root / filename
            logger.info(f"   - Creazione file migration: {filename}")
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(content)
            if filename.endswith(".py"):
                file_path.chmod(0o755)
            created_files.append(str(file_path))

        return {"status": "completed", "files_created": created_files}

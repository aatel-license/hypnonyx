#!/usr/bin/env python3
"""
Framework Detection Utility

Reads architecture.md and tech_stack.md to determine the technology stack
for a project, enabling context-aware code generation.
"""

import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


async def detect_tech_stack(project_root: Path) -> Dict[str, str]:
    """
    Read architecture.md and tech_stack.md to determine frameworks.

    Returns:
        Dict with keys: backend, frontend, database, language
    """
    tech = {
        "backend": "unknown",
        "frontend": "unknown",
        "database": "unknown",
        "language": "unknown",
    }

    # Files to check
    files_to_check = [project_root / "architecture.md", project_root / "tech_stack.md"]

    content_combined = ""
    for file_path in files_to_check:
        if file_path.exists():
            content_combined += " " + file_path.read_text().lower()

    if not content_combined.strip():
        logger.warning(f"No architecture files found in {project_root}")
        return tech

    # Backend framework detection
    if "fastapi" in content_combined:
        tech["backend"] = "fastapi"
    elif "flask" in content_combined:
        tech["backend"] = "flask"
    elif "django" in content_combined:
        tech["backend"] = "django"
    elif "express" in content_combined or "express.js" in content_combined:
        tech["backend"] = "express"
    elif "spring boot" in content_combined or "spring" in content_combined:
        tech["backend"] = "spring"
    elif "nest" in content_combined or "nestjs" in content_combined:
        tech["backend"] = "nestjs"
    elif "rails" in content_combined or "ruby on rails" in content_combined:
        tech["backend"] = "rails"

    # Frontend framework detection
    if "react" in content_combined:
        tech["frontend"] = "react"
    elif "vue" in content_combined or "vue.js" in content_combined:
        tech["frontend"] = "vue"
    elif "angular" in content_combined:
        tech["frontend"] = "angular"
    elif "svelte" in content_combined:
        tech["frontend"] = "svelte"
    elif "next" in content_combined or "next.js" in content_combined:
        tech["frontend"] = "nextjs"
    elif (
        "vanilla" in content_combined
        or "plain js" in content_combined
        or "vanilla js" in content_combined
        or "javascript" in content_combined
    ):
        tech["frontend"] = "vanilla"

    # Database detection
    if "postgresql" in content_combined or "postgres" in content_combined:
        tech["database"] = "postgresql"
    elif "mysql" in content_combined:
        tech["database"] = "mysql"
    elif "mongodb" in content_combined or "mongo" in content_combined:
        tech["database"] = "mongodb"
    elif "sqlite" in content_combined:
        tech["database"] = "sqlite"
    elif "redis" in content_combined:
        tech["database"] = "redis"

    # Programming language detection
    if "python" in content_combined:
        tech["language"] = "python"
    elif "typescript" in content_combined:
        tech["language"] = "typescript"
    elif ("javascript" in content_combined or "node" in content_combined) and tech[
        "language"
    ] == "unknown":
        tech["language"] = "javascript"
    elif "java" in content_combined and "javascript" not in content_combined:
        tech["language"] = "java"
    elif "ruby" in content_combined:
        tech["language"] = "ruby"
    elif "go" in content_combined or "golang" in content_combined:
        tech["language"] = "go"

    logger.info(f"Detected tech stack: {tech}")
    return tech


def get_framework_context(tech: Dict[str, str]) -> str:
    """
    Generate context text about the detected frameworks for use in prompts.
    """
    backend = tech.get("backend", "unknown")
    frontend = tech.get("frontend", "unknown")
    database = tech.get("database", "unknown")
    language = tech.get("language", "unknown")

    context = f"""
DETECTED TECHNOLOGY STACK:
- Backend Framework: {backend.upper()}
- Frontend Framework: {frontend.upper()}
- Database: {database.upper()}
- Language: {language.upper()}

YOU MUST generate code compatible with this stack.
Use the appropriate syntax, imports, and patterns for {backend} / {frontend} / {database}.
"""
    return context

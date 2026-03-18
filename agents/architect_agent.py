#!/usr/bin/env python3
"""
Planner Architect Agent - Specializzato nella progettazione dell'architettura con supporto TOON.
"""

import asyncio
import logging
from typing import Dict, Any, List
import json
import time
from pathlib import Path


from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PlannerArchitectAgent(BaseAgent):
    """Agent che progetta l'architettura tecnica del progetto - TOON Ready"""

    def __init__(
        self,
        agent_id: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type="architect",
            memory=memory,
            project_root=project_root,
            skill_manager=skill_manager,
            prompt_manager=prompt_manager,
        )

    async def _handle_scrum_ceremony(self, message: Dict):
        """Gestisce le cerimonie Scrum"""
        ceremony_type = message.get("type")

        if ceremony_type == "retrospective_request":
            await super()._handle_scrum_ceremony(message)

        elif ceremony_type == "release_request":
            await self._generate_release_notes(message)

    async def _generate_release_notes(self, message: Dict) -> None:
        """Genera release notes e roadmap"""
        from config import get_topics

        version = message.get("version", "v?.?")
        sprint_start = message.get("sprint_start", 1)
        sprint_end = message.get("sprint_end", message.get("sprint_id", 1))
        project_id = message.get("project_id", self.project_id)

        arch_content = ""
        arch_path = self.project_root / "architecture.md"
        if arch_path.exists():
            arch_content = arch_path.read_text()[:3000]

        all_tasks = await self.memory.get_all_tasks(project_id)
        completed = [t for t in all_tasks if t.get("status") == "completed"]
        completed_desc = "\n".join(
            f"- {t.get('description', '')[:100]}" for t in completed[-30:]
        )

        prompt = f"""Generate professional release notes and a technical roadmap for release {version}.

Architecture (excerpt):
{arch_content[:1500]}

Completed tasks:
{completed_desc}

Output should be clear Markdown."""

        response = await self.llm_client.chat_completion(
            [
                {"role": "system", "content": "You are a Senior Architect."},
                {"role": "user", "content": prompt},
            ]
        )

        if response:
            release_file = self.project_root / f"release_notes_{version}.md"
            release_file.write_text(
                f"# Release Notes {version}\n\n**Sprint**: {sprint_start} → {sprint_end}\n\n{response}"
            )

            await self.broker.publish(
                get_topics(self.project_id)["SCRUM_REPORT"],
                {
                    "sprint_id": message.get("sprint_id"),
                    "agent_type": self.agent_type,
                    "feedback": response[:1000],
                    "sentiment": "positive",
                    "is_release_notes": True,
                    "version": version,
                    "timestamp": time.time(),
                },
            )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue il design dell'architettura"""
        task_type = task.get("type")
        if task_type in ["design_architecture", "architect"]:
            return await self._design_architecture(task)
        return {"status": "failed", "error": f"Unknown task type: {task_type}"}

    async def _design_architecture(self, task: Dict) -> Dict[str, Any]:
        """Progetta l'architettura"""
        description = task.get("description", "")
        metadata = task.get("metadata", {})

        tech_stack_content = ""
        tech_stack_path = self.project_root / "tech_stack.md"
        if tech_stack_path.exists():
            tech_stack_content = tech_stack_path.read_text()

        existing_arch_content = ""
        arch_path = self.project_root / "architecture.md"
        if arch_path.exists():
            existing_arch_content = arch_path.read_text()

        is_mvp = metadata.get("mvp", False)
        prompt_config = await self.prompt_manager.get_prompt(
            "architect", "design_architecture"
        )
        system_prompt = prompt_config["system_prompt"]

        if is_mvp:
            system_prompt = "Design a minimal MVP. Skip Auth. Focus on CORE only."
        elif not system_prompt:
            system_prompt = (
                "You are a Senior Architect. Output ONLY architecture.md content."
            )

        skill_context = ""
        if hasattr(self, "current_skill_content") and self.current_skill_content:
            skill_context = f"\nSkill Guidelines: {self.current_skill_content}\n"

        prompt = f"""
Project Description: {description}
Tech Stack: {tech_stack_content or "Standard stack"}
Existing Architecture: {existing_arch_content}
{skill_context}

Generate a professional architecture.md including: overview, components (mermaid), folder structure, API specs, DB schema, security.
"""

        auto_fix = await self.get_auto_fix_instruction(task)
        if auto_fix:
            prompt += f"\n🚨 FIX PREVIOUS ISSUES: \n{auto_fix}\n"

        response = await self.llm_client.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

        if not response:
            return {"status": "failed", "error": "LLM response was empty"}

        architecture_path = self.project_root / "architecture.md"
        architecture_path.write_text(response)

        return {
            "status": "completed",
            "files_created": ["architecture.md"],
            "architecture_summary": response[:200] + "...",
        }

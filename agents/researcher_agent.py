#!/usr/bin/env python3
"""
Researcher Agent con supporto TOON.
"""

import logging
from typing import Dict, Any
from pathlib import Path
import json

from agents.base_agent import BaseAgent
from config import SITUATION_LLM_MAPPING

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Agent che effettua ricerche tecniche - TOON Ready"""

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
            agent_type="researcher",
            memory=memory,
            project_root=project_root,
            skill_manager=skill_manager,
            prompt_manager=prompt_manager,
        )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue ricerca tecnica"""
        task_type = task.get("type")
        if task_type in ["research_tech_stack", "search_docs"]:
            return await self._research_tech(task)
        return {"status": "failed", "error": f"Unknown task type: {task_type}"}

    async def _research_tech(self, task: Dict) -> Dict[str, Any]:
        """Esegue la ricerca e salva i risultati"""
        description = task.get("description", "")
        metadata = task.get("metadata", {})

        # FIX: metadata potrebbe essere None se arriva dal DB malformato
        if not isinstance(metadata, dict):
            metadata = {}

        tech_prefs = metadata.get("tech_prefs", {})
        if not isinstance(tech_prefs, dict):
            tech_prefs = {}

        context_str = ""
        for k, v in tech_prefs.items():
            context_str += f"{k.capitalize()} Preference: {v}\n"

        # Use LLM (Chat) for the query string
        query_prompt = f"""Generate 1 (ONE) web search query for: {description}
Preferences: {context_str}
Output ONLY the query string. Max 8 keywords."""

        research_profile = SITUATION_LLM_MAPPING.get("research")

        try:
            query_response = await self.llm_client.chat_completion(
                [{"role": "user", "content": query_prompt}],
                profile_name=research_profile,
            )
            query = query_response.strip().strip('"').strip("'")
        except Exception as e:
            logger.warning(
                f"Query generation failed, using description as fallback: {e}"
            )
            query = description[:100]

        logger.info(f"Researcher Query: {query}")

        try:
            research_results = await self.perform_research(query)
        except Exception as e:
            logger.warning(f"Web research failed, proceeding without results: {e}")
            research_results = []

        enriched_results = []
        SKIP_DOMAINS = ("youtube.com", "youtu.be", "twitter.com", "x.com", "instagram.com", "facebook.com", "reddit.com")
        for res in research_results[:3]:
            if "href" in res:
                if any(domain in res["href"] for domain in SKIP_DOMAINS):
                    logger.warning(f"Skipping non-scrapable URL: {res['href']}")
                    enriched_results.append(res)
                    continue
                try:
                    content_data = await self.read_web_page(res["href"])
                    if content_data and content_data.get("content"):
                        res["full_content"] = content_data["content"][:3000]
                except Exception as e:
                    logger.warning(f"Failed to fetch page {res.get('href')}: {e}")
            enriched_results.append(res)

        system_prompt = "You are a senior technical researcher. Synthesize results into tech_stack.md."
        prompt = f"""
Task: {description}
Context: {context_str}
Search Results: {json.dumps(enriched_results)[:6000]}

Generate a professional markdown report (tech_stack.md) including: recommended stack (honoring preferences), implementation guide (code snippets), resources, gotchas, and folder structure.
"""

        response = await self.llm_client.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            profile_name=research_profile,
        )

        # FIX: self.project_root può essere str o Path — normalizziamo sempre a Path
        project_path = Path(self.project_root)
        project_path.mkdir(parents=True, exist_ok=True)

        tech_stack_path = project_path / "tech_stack.md"
        tech_stack_path.write_text(response, encoding="utf-8")

        logger.info(f"✅ tech_stack.md scritto in {tech_stack_path}")

        return {
            "status": "completed",
            "files_created": ["tech_stack.md"],
            "research_summary": response[:200] + "...",
        }

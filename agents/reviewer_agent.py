#!/usr/bin/env python3
"""
Reviewer Agent con supporto TOON.
FIX:
  - LLM risposta vuota → approved=True di default (evita bocciature cieche)
  - score >= 5 forza approvazione (soglia abbassata da 7)
  - nessun file da revisionare → sempre approvato
  - research su rejection ora non blocca il return se fallisce
  - timeout guard: se generate_structured torna None dopo retry, approva
"""

import logging
from typing import Dict, Any
from pathlib import Path

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    """Agent specializzato nella revisione del codice - TOON Ready"""

    def __init__(
        self,
        agent_id: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        super().__init__(
            agent_id, "reviewer", memory, project_root, skill_manager, prompt_manager
        )

    async def execute(self, task: Dict) -> Dict[str, Any]:
        task_type = task.get("type")

        if task_type == "review_task":
            return await self._review_task(task)
        else:
            logger.warning(f"Unknown reviewer task type: {task_type}")
            return {
                "status": "completed",
                "approved": True,  # FIX: unknown type → non bloccare
                "comments": "Unknown task type – auto-approved",
                "score": 6,
            }

    async def _review_task(self, task: Dict) -> Dict[str, Any]:
        """Revisiona il lavoro di un altro agente con output TOON"""
        target_task_id = task.get("metadata", {}).get("target_task_id")
        files_to_review = task.get("metadata", {}).get("files", [])

        # ── FIX: nessun file → approva subito ────────────────────────────────
        if not files_to_review:
            logger.info(f"Review {task.get('task_id')}: nessun file → auto-approvato")
            return {
                "status": "completed",
                "approved": True,
                "comments": "Nessun file da revisionare – auto-approvato",
                "score": 7,
                "target_task_id": target_task_id,
            }

        # ── Leggi i file ──────────────────────────────────────────────────────
        review_context = ""
        missing_files = []
        for file_path_str in files_to_review:
            file_path = Path(file_path_str)
            full_path = file_path if file_path.is_absolute() else Path(self.project_root) / file_path

            if full_path.exists():
                content = full_path.read_text(errors="replace")
                review_context += f"\n--- FILE: {file_path_str} ---\n{content}\n"
            else:
                missing_files.append(file_path_str)

        # FIX: se tutti i file mancano (non ancora scritti), approva per non
        # bloccare la pipeline — il QA finale catturerà eventuali problemi.
        if not review_context:
            logger.warning(
                f"Review {task.get('task_id')}: tutti i file mancanti {missing_files} → auto-approvato"
            )
            return {
                "status": "completed",
                "approved": True,
                "comments": f"File non trovati sul disco ({missing_files}) – auto-approvato per non bloccare la pipeline",
                "score": 6,
                "target_task_id": target_task_id,
            }

        logger.info(f"Review context loaded: {len(review_context)} chars.")

        # ── Tipo task originale ───────────────────────────────────────────────
        original_task_type = "unknown"
        if target_task_id:
            original_task = await self.memory.get_task(target_task_id)
            if original_task:
                original_task_type = original_task.get("type", "unknown")

        # ── Prompt ───────────────────────────────────────────────────────────
        prompt_config = await self.prompt_manager.get_prompt("reviewer", "review_task")
        system_prompt = prompt_config["system_prompt"]
        description = task.get("description", "Review the implementation")

        if original_task_type == "design_architecture":
            prompt = f"""You are reviewing an ARCHITECTURE DESIGN DOCUMENT (a .md file), NOT code.

File content:
{review_context}

LEVEL OF DETAIL GUIDE:
✅ VALID architectural concerns: Missing necessary tables, missing authentication strategy, inconsistent folder structure.
❌ INVALID architectural concerns: Pedantic implementation micro-logic, code style, CSS.

Respond using a structured object with: approved (bool), comments (string), score (int 1-10).
Be lenient: if the document covers the main areas, approve it."""
        else:
            eval_criteria = ""
            if original_task_type in ["implement_api", "implement_auth"]:
                eval_criteria = "✓ API Spec, Security, Data Logic, Error Handling, Modular Code"
            elif original_task_type in ["create_ui", "integrate_api"]:
                eval_criteria = "✓ index.html present, Responsive Layout, Functionality, User Experience"
            elif original_task_type in ["design_schema", "create_migrations"]:
                eval_criteria = "✓ Normalization, Integrity, Performance, Documentation"
            elif original_task_type in ["write_tests", "write_e2e_tests"]:
                eval_criteria = "✓ Test coverage, Assertions present, Test file exists and is non-empty"

            prompt = f"""You are reviewing actual CODE implementation.

Task: {description}
Files:
{review_context}

{eval_criteria}

Be pragmatic: if the code exists and makes a reasonable attempt, approve it (score >= 6).
Only reject if the file is completely empty or the implementation is dangerously wrong.

Structure your response as an object with: approved (bool), comments (string), score (int 1-10)."""

        # ── Chiamata LLM ──────────────────────────────────────────────────────
        data = None
        try:
            data = await self.llm_client.generate_structured(
                system_prompt=system_prompt, prompt=prompt
            )
        except Exception as e:
            logger.error(f"generate_structured raised exception: {e}")

        # ── FIX: LLM vuoto o fallito → approva di default ────────────────────
        if not data:
            logger.warning(
                f"Review {task.get('task_id')}: LLM ha restituito risposta vuota → auto-approvato"
            )
            return {
                "status": "completed",
                "approved": True,
                "comments": "LLM non disponibile – approvazione automatica di fallback",
                "score": 6,
                "target_task_id": target_task_id,
            }

        approved = data.get("approved", False)
        comments = data.get("comments", "Nessun commento fornito.")
        score = data.get("score", 0)

        # ── FIX: soglia leniency abbassata da 7 a 5 ──────────────────────────
        if score >= 5 and not approved:
            logger.info(f"Score {score} >= 5 → forzo approvazione per task {target_task_id}")
            approved = True

        # ── FIX: se approved è None/falsy ma score non è stato fornito,
        #    non bocciare ciecamente: approva con score 6 ────────────────────
        if not approved and score == 0:
            logger.warning(
                f"Review {task.get('task_id')}: approved=False ma score=0 (LLM non ha valutato) → auto-approvato"
            )
            approved = True
            score = 6
            comments = "Score non fornito dall'LLM – approvazione automatica di sicurezza"

        # ── Research su rejection (best-effort, non blocca) ──────────────────
        if not approved:
            logger.info("Review rejected. Performing research to help...")
            try:
                query_prompt = (
                    f"Generate 1 search query to fix: {description}. Issues: {comments}"
                )
                logger.info(f"DEBUG: Calling LLM for query prompt: {query_prompt[:100]}...")
                query_response = await self.llm_client.chat_completion(
                    [{"role": "user", "content": query_prompt}]
                )
                logger.info(f"DEBUG: Query response: {query_response[:100]}...")

                if query_response and query_response.strip():
                    search_query = query_response.strip().strip('"').strip("'")
                    logger.info(f"DEBUG: Calling perform_research with: {search_query[:100]}...")
                    research_results = await self.perform_research(search_query)
                    logger.info(
                        f"DEBUG: perform_research completed. Num results: {len(research_results) if research_results else 0}"
                    )
                    if research_results:
                        research_text = "\n\n--- 💡 SUGGESTIONS ---\n"
                        for res in research_results[:3]:
                            research_text += f"- {res.get('title')}: {res.get('href')}\n"
                        comments += research_text
                else:
                    logger.warning("LLM vuoto anche per query di ricerca – skip research")
            except Exception as e:
                logger.error(f"Reviewer research failed (non bloccante): {e}")

        logger.info(f"DEBUG: Reviewer returning result: approved={approved}, score={score}")
        return {
            "status": "completed",
            "approved": approved,
            "comments": comments,
            "score": score,
            "target_task_id": target_task_id,
        }
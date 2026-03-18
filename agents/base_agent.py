#!/usr/bin/env python3
"""
Base Agent con FIX per ricezione e esecuzione task
FIX applicati:
  - _heartbeat_worker: invia heartbeat anche DURANTE perform_research (task attivo)
  - _task_worker: pending_task_ids rimosso DOPO completamento, non prima
  - _handle_new_task: protezione duplicati rafforzata (controlla anche current_task)
  - perform_research: aggiorna last_activity durante la ricerca per evitare idle falso
"""

import asyncio
import logging
import sys
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import time

from core.message_broker import MessageBroker
from config import (
    get_topics,
    MAX_IDLE_TIME,
    HEARTBEAT_INTERVAL,
    MAX_RETRIES,
    AGENT_LLM_MAPPING,
    SITUATION_LLM_MAPPING,
)

logger = logging.getLogger(__name__)


class BaseAgent:
    """Agent base con GESTIONE TASK FUNZIONANTE"""

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        memory,
        project_root: str,
        skill_manager=None,
        prompt_manager=None,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.memory = memory
        self.project_root = Path(project_root)
        self.project_id = self.project_root.name
        self.skill_manager = skill_manager
        self.prompt_manager = prompt_manager

        from core.llm_client import LLMClient

        profile_name = AGENT_LLM_MAPPING.get(self.agent_type, "default")
        self.llm_client = LLMClient(
            profile_name=profile_name,
            agent_id=self.agent_id,
            project_id=self.project_id,
            memory=self.memory,
        )

        self.tasks_queue = asyncio.Queue()
        self.current_task: Optional[Dict] = None
        self.completed_tasks: List[str] = []
        self.failed_tasks: List[str] = []
        # FIX: include anche i task in esecuzione, non solo in coda
        self.pending_task_ids: set = set()

        self.running = False
        self.last_activity = time.time()

        self.broker = MessageBroker(agent_id, project_id=self.project_id)
        self.broker.agent_type = agent_type

        logger.info(f"Inizializzato {agent_type} agent: {agent_id}")

    async def start(self):
        """Avvia l'agent"""
        self.running = True
        await self.broker.connect()

        await self.broker.subscribe(
            get_topics(self.project_id)["TASKS_NEW"], self._handle_new_task
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["TASKS_ASSIGNED"], self._handle_assigned_task
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["HELP_REQUEST"], self._handle_help_request
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["BUGS_REPORTED"], self._handle_bug_report
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["SCRUM_CEREMONY"], self._handle_scrum_ceremony
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["BACKLOG_REFINEMENT"],
            self._handle_backlog_refinement,
        )

        tasks = [self._task_worker(), self._heartbeat_worker(), self._idle_checker()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_new_task(self, message: Dict):
        """Handler per nuovi task"""
        logger.info(
            f"Agent {self.agent_id} ha ricevuto nuovo task: {message.get('task_id')} type={message.get('type')}"
        )

        if not message or not isinstance(message, dict):
            logger.error(f"Agent {self.agent_id}: Received empty or non-dict message")
            return

        task_id = message.get("task_id")
        task_type = message.get("type")
        agent_type = message.get("agent_type")

        if not task_id or not task_type:
            logger.error(
                f"Agent {self.agent_id}: Incomplete task - id={task_id}, type={task_type}"
            )
            return

        if agent_type and agent_type != self.agent_type:
            logger.debug(
                f"Agent {self.agent_id}: Task {task_id} not for me (want {agent_type}, am {self.agent_type})"
            )
            return

        assigned_to = message.get("assigned_to")
        if assigned_to and assigned_to != self.agent_id:
            logger.debug(
                f"Agent {self.agent_id}: Task {task_id} explicitly assigned to {assigned_to}. Skipping."
            )
            return

        # FIX: controlla anche se è il task correntemente in esecuzione
        current_task_id = (
            self.current_task.get("task_id") if self.current_task else None
        )
        if task_id in self.pending_task_ids or task_id == current_task_id:
            logger.warning(
                f"Agent {self.agent_id}: Task {task_id} already in queue or processing. Skipping."
            )
            return

        self.pending_task_ids.add(task_id)
        await self.tasks_queue.put(message)
        logger.info(
            f"Agent {self.agent_id}: Accepted task {task_id} of type {task_type}"
        )

    async def _handle_assigned_task(self, message: Dict):
        if message.get("assigned_to") == self.agent_id:
            await self.tasks_queue.put(message)

    async def _handle_help_request(self, message: Dict):
        pass

    async def _handle_bug_report(self, message: Dict):
        pass

    async def _handle_scrum_ceremony(self, message: Dict):
        if message.get("type") == "retrospective_request":
            sprint_id = message.get("sprint_id")

            recent_work = {
                "completed": self.completed_tasks[-5:] if self.completed_tasks else [],
                "failed": self.failed_tasks[-3:] if self.failed_tasks else [],
            }

            if not recent_work["completed"] and not recent_work["failed"]:
                logger.info(
                    f"Agent {self.agent_id} skipping retrospective for sprint {sprint_id} (no recent work)"
                )
                return

            logger.info(
                f"Agent {self.agent_id} preparing retrospective feedback for sprint {sprint_id}"
            )

            extra_instruction = ""
            if self.agent_type == "frontend":
                extra_instruction = "\n            IMPORTANT FOR FRONTEND: Always verify if you need backend routes that don't exist yet. If you are blocked by missing backend routes, YOU MUST explicitly signal the missing routes in your feedback so tasks can be created to unblock you."

            prompt = f"""As a {self.agent_type} agent, provide a brief feedback (2 sentences) for the sprint retrospective.
            Recent work: {json.dumps(recent_work)}{extra_instruction}
            IMPORTANT: If you have failed tasks in your recent work, you MUST be critical and use "negative" or "neutral" sentiment. Be honest about difficulties.
            Respond with JSON: {{"feedback": "your feedback", "sentiment": "positive|neutral|negative"}}"""

            try:
                retro_profile = SITUATION_LLM_MAPPING.get("retrospective")
                data = await self.llm_client.generate_structured(
                    system_prompt=f"You are a professional {self.agent_type} developer in an agile team.",
                    prompt=prompt,
                    profile_name=retro_profile,
                )
                feedback = data.get("feedback", "N/A")
                sentiment = data.get("sentiment", "neutral")

                await self.broker.publish(
                    get_topics(self.project_id)["SCRUM_REPORT"],
                    {
                        "sprint_id": sprint_id,
                        "agent_type": self.agent_type,
                        "agent_id": self.agent_id,
                        "feedback": feedback,
                        "sentiment": sentiment,
                        "timestamp": time.time(),
                    },
                )
            except Exception as e:
                import traceback

                print(traceback.format_exc())
                logger.error(f"Error generating retrospective feedback: {e}")

    async def _handle_backlog_refinement(self, message: Dict):
        if message.get("type") != "backlog_refinement_request":
            return
        if message.get("project_id") != self.project_id:
            return

        sprint_id = message.get("sprint_id")
        pending_summary = message.get("pending_tasks_summary", "")
        failed_tasks_info = message.get("failed_tasks", [])

        recent_completed = self.completed_tasks[-5:] if self.completed_tasks else []
        core_agents = {
            "architect",
            "orchestrator",
            "backend",
            "frontend",
            "scrum_master",
        }
        if (
            self.agent_type not in core_agents
            and not failed_tasks_info
            and not recent_completed
        ):
            logger.info(
                f"Agent {self.agent_id} skipping backlog refinement (not core, no active context)"
            )
            return

        logger.info(f"Agent {self.agent_id} preparando proposte Backlog Refinement...")

        relevant_failures = [
            t
            for t in failed_tasks_info
            if self.agent_type in t.get("agent_type", "").lower()
            or self.agent_type in t.get("description", "").lower()
        ] or failed_tasks_info[:3]

        research_context = ""
        research_sources = []

        if relevant_failures:
            for failure in relevant_failures[:2]:
                fail_desc = failure.get("description", "")[:80]
                fail_error = failure.get("error", "")[:80]

                query_prompt = f"""You are a {self.agent_type} developer.
A task FAILED during sprint with this context:
Task: {fail_desc}
Error/Rejection: {fail_error}

Generate ONE concise search query (max 8 keywords) to find a solution or best practice.
Output ONLY the query string, no explanations."""

                try:
                    query = await self.llm_client.generate(
                        system_prompt=f"You are a senior {self.agent_type} developer.",
                        prompt=query_prompt,
                    )
                    query = query.strip().strip('"').strip("'")[:100]
                    if "\n" in query:
                        query = query.split("\n")[0]

                    results = await self.perform_research(query)

                    if results and isinstance(results, list):
                        snippets = []
                        for r in results[:3]:
                            if isinstance(r, dict) and "title" in r:
                                title = r.get("title", "")
                                body = r.get("body", "")[:200]
                                href = r.get("href", "")
                                snippets.append(f"• {title}: {body}")
                                if href:
                                    research_sources.append(href)
                        if snippets:
                            research_context += (
                                f"\n\n📌 Web Research per '{fail_desc[:50]}':\n"
                                + "\n".join(snippets)
                            )
                except Exception as e:
                    import traceback

                    print(traceback.format_exc())
                    logger.warning(f"Web research during refinement failed: {e}")

        recent_work = {
            "completed": self.completed_tasks[-5:] if self.completed_tasks else [],
            "failed": [t.get("description", "")[:60] for t in relevant_failures[:3]],
        }

        research_section = ""
        if research_context:
            research_section = f"\nWeb research findings:\n{research_context[:1500]}\n"

        prompt = f"""As a {self.agent_type} agent, propose 2-3 concrete backlog items for the next sprint.

Your recent work:
- Completed: {json.dumps(recent_work["completed"])}
- Failed/Rejected: {json.dumps(recent_work["failed"])}

Current pending backlog context:
{pending_summary[:400]}
{research_section}
Respond ONLY with a JSON array:
[{{"description": "...", "priority": 1-3, "rationale": "why this is important"}}]"""

        try:
            proposals = await self.llm_client.generate_structured(
                system_prompt=f"You are a senior {self.agent_type} developer proposing data-driven backlog improvements.",
                prompt=prompt,
            )

            if not isinstance(proposals, list):
                proposals = [proposals] if isinstance(proposals, dict) else []

            await self.broker.publish(
                get_topics(self.project_id)["BACKLOG_REFINEMENT_PROPOSAL"],
                {
                    "sprint_id": sprint_id,
                    "project_id": self.project_id,
                    "agent_type": self.agent_type,
                    "agent_id": self.agent_id,
                    "proposals": proposals,
                    "research_sources": research_sources[:5],
                    "timestamp": time.time(),
                },
            )
            logger.info(
                f"✅ Agent {self.agent_id} ha pubblicato {len(proposals)} proposte di refinement per lo sprint {sprint_id}."
            )
        except Exception as e:
            import traceback

            print(traceback.format_exc())
            logger.error(f"Error generating backlog refinement proposals: {e}")

    async def _get_agile_context(self) -> str:
        try:
            retros = await self.memory.get_retrospectives(self.project_id)
            if not retros:
                return ""

            latest_retro = retros[0]
            feedbacks = latest_retro.get("feedbacks", [])
            agent_feedback = next(
                (f for f in feedbacks if f["agent_type"] == self.agent_type), None
            )

            if agent_feedback:
                return f"\n[LAST SPRINT FEEDBACK]: {agent_feedback['feedback']}\n"
        except Exception as e:
            import traceback

            print(traceback.format_exc())
            logger.error(f"Error fetching agile context: {e}")
        return ""

    async def _task_worker(self):
        """Worker che esegue i task dalla coda"""
        while self.running:
            try:
                try:
                    task = await asyncio.wait_for(self.tasks_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if not task:
                    continue

                task_id = task.get("task_id", "unknown")
                task_type = task.get("type", "unknown")

                # FIX: NON rimuovere da pending_task_ids qui — lo facciamo solo
                # a completamento/fallimento. Questo evita che un secondo messaggio
                # per lo stesso task_id venga accettato mentre è in esecuzione.

                logger.info(
                    f"▶️ Agent {self.agent_id} INIZIA task {task_id} ({task_type})"
                )
                logger.info(f"📝 Descrizione: {task.get('description', 'N/A')}")

                self.current_skill_content = None
                skill_loaded = False
                if self.skill_manager:
                    skill_name = task.get("skill") or self._detect_skill(task)
                    if skill_name:
                        skill_content = self.skill_manager.get_skill(skill_name)
                        if skill_content:
                            self.current_skill_content = skill_content
                            skill_loaded = True

                if skill_loaded:
                    logger.info(f"✓ Skill caricata per task {task_id}")

                self.current_task = task
                self.last_activity = time.time()

                await self.memory.update_task_status(
                    task_id, "in_progress", assigned_to=self.agent_id
                )

                await self.broker.publish(
                    get_topics(self.project_id)["TASKS_STARTED"],
                    {
                        "task_id": task_id,
                        "project_id": self.project_id,
                        "type": task_type,
                        "agent_id": self.agent_id,
                        "timestamp": time.time(),
                    },
                )

                success = False
                attempts = 0
                last_error = ""

                while attempts < MAX_RETRIES and not success:
                    attempts += 1
                    logger.info(
                        f"Agent {self.agent_id} executing task {task_id} (Attempt {attempts}/{MAX_RETRIES})"
                    )

                    try:
                        if attempts > 1:
                            if "metadata" not in task:
                                task["metadata"] = {}
                            task["metadata"]["last_error"] = last_error
                            task["metadata"]["is_retry"] = True

                        agile_context = await self._get_agile_context()

                        domain_intel = ""
                        top_knowledge = await self.memory.get_top_domain_knowledge(
                            self.agent_id, limit=3
                        )
                        if top_knowledge:
                            domain_intel = (
                                "\n\n### Domain Expertise (Learned Knowledge)\n"
                            )
                            for k in top_knowledge:
                                domain_intel += f"- **{k.get('domain', '').capitalize()} - {k.get('topic', '')}**: {k.get('synthesized_summary', '')}\n"
                                if k.get("key_points"):
                                    domain_intel += f"  Key points: {', '.join(k.get('key_points', [])[:3])}\n"

                        attached_docs_str = ""
                        attached_docs = await self.memory.get_agent_documents(
                            self.agent_type
                        )
                        if attached_docs:
                            attached_docs_str = (
                                "\n\n### Attached Documentation (CRITICAL CONTEXT)\n"
                            )
                            attached_docs_str += "The following documentations have been attached to you. Use them as ground truth:\n"
                            for idx, doc in enumerate(attached_docs):
                                attached_docs_str += f"\n--- Document {idx + 1}: {doc['source']} ({doc['doc_type']}) ---\n"
                                attached_docs_str += doc["content"] + "\n"

                        full_context = agile_context
                        if domain_intel:
                            full_context = (full_context or "") + domain_intel
                        if attached_docs_str:
                            full_context = (full_context or "") + attached_docs_str

                        if full_context:
                            if "metadata" not in task:
                                task["metadata"] = {}
                            task["_agile_context"] = full_context
                            logger.info(
                                f"Agile/Domain context injected for task {task_id}"
                            )

                        # FIX: aggiorna last_activity prima di execute per evitare
                        # che l'idle_checker segnali idle durante task lunghi
                        self.last_activity = time.time()

                        logger.info(f"DEBUG: Calling execute for task {task_id}")
                        result = await self.execute(task)
                        logger.info(f"DEBUG: Returned from execute for task {task_id}")

                        if (
                            isinstance(result, dict)
                            and result.get("status") == "failed"
                        ):
                            reason = result.get("reason", "Unknown failure")
                            logger.error(
                                f"Task {task_id} FAILED during execution: {reason}"
                            )

                            await self.broker.publish(
                                get_topics(self.project_id)["TASKS_FAILED"],
                                {
                                    "task_id": task_id,
                                    "project_id": self.project_id,
                                    "type": task_type,
                                    "agent_id": self.agent_id,
                                    "error": f"Execution failed: {reason}",
                                    "attempts": attempts,
                                    "timestamp": time.time(),
                                },
                            )
                            await self.memory.log_action(
                                agent=self.agent_id,
                                action=f"failed_{task_type}",
                                description=f"Fallito task {task_id}: {reason}",
                                project_id=self.project_id,
                                metadata={
                                    "task_id": task_id,
                                    "reason": reason,
                                    "status": "failed",
                                },
                            )
                            self.failed_tasks.append(task_id)
                            self.current_task = None
                            # FIX: rimuovi da pending solo a fine task (successo o fallimento)
                            self.pending_task_ids.discard(task_id)
                            break

                        success = True
                        self.completed_tasks.append(task_id)
                        self.current_task = None
                        # FIX: rimuovi da pending solo a completamento
                        self.pending_task_ids.discard(task_id)

                        logger.info(
                            f"DEBUG: Notifying completion to broker for {task_id}"
                        )
                        await self.broker.publish(
                            get_topics(self.project_id)["TASKS_COMPLETED"],
                            {
                                "task_id": task_id,
                                "project_id": self.project_id,
                                "type": task_type,
                                "agent_id": self.agent_id,
                                "result": result,
                                "attempts": attempts,
                                "timestamp": time.time(),
                            },
                        )

                        action_desc = (
                            f"Completato task {task_id}: {task.get('description', '')}"
                        )
                        if attempts > 1:
                            action_desc += f" (Riuscito al tentativo {attempts})"

                        logger.info(f"DEBUG: Calling log_action for task {task_id}")
                        await self.memory.log_action(
                            agent=self.agent_id,
                            action=f"completed_{task_type}",
                            description=action_desc,
                            project_id=self.project_id,
                            metadata={
                                "task_id": task_id,
                                "attempts": attempts,
                                "status": "success",
                            },
                        )
                        logger.info(
                            f"✅ Agent {self.agent_id} COMPLETATO task {task_id} con successo."
                        )

                    except Exception as e:
                        last_error = str(e)
                        logger.error(
                            f"Attempt {attempts} failed for agent {self.agent_id} on task {task_id}: {last_error}"
                        )
                        import traceback

                        logger.error(f"DEBUG Traceback:\n{traceback.format_exc()}")

                        if attempts >= MAX_RETRIES:
                            self.failed_tasks.append(task_id)
                            self.current_task = None
                            # FIX: rimuovi da pending a fallimento definitivo
                            self.pending_task_ids.discard(task_id)

                            await self.broker.publish(
                                get_topics(self.project_id)["TASKS_FAILED"],
                                {
                                    "task_id": task_id,
                                    "project_id": self.project_id,
                                    "type": task_type,
                                    "agent_id": self.agent_id,
                                    "error": last_error,
                                    "attempts": attempts,
                                    "timestamp": time.time(),
                                },
                            )
                        else:
                            await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error in task worker for {self.agent_id}: {e}")
                await asyncio.sleep(1)

    async def _heartbeat_worker(self):
        """
        Worker per heartbeat periodico.
        FIX: aggiorna last_activity ogni volta che c'è un task in corso,
        in modo che il reclaim dell'orchestratore non scatti per task lunghi
        (es. perform_research, chiamate LLM lente).
        """
        while self.running:
            try:
                has_task = self.current_task is not None

                # FIX: se c'è un task attivo, aggiorna last_activity ad ogni heartbeat
                # così il reclaim non vede mai un timeout mentre stiamo lavorando
                if has_task:
                    self.last_activity = time.time()

                status = "active" if has_task else "idle"
                await self.broker.send_heartbeat(
                    status=status,
                    metadata={
                        "completed_tasks": len(self.completed_tasks),
                        "failed_tasks": len(self.failed_tasks),
                        "current_task": (
                            self.current_task.get("task_id")
                            if self.current_task
                            else None
                        ),
                    },
                )
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.error(f"Error in heartbeat for {self.agent_id}: {e}")

    async def _idle_checker(self):
        """Controlla se l'agent è idle"""
        while self.running:
            try:
                idle_time = time.time() - self.last_activity

                # FIX: non segnalare idle se c'è un task in esecuzione
                if idle_time > MAX_IDLE_TIME and not self.current_task:
                    logger.info(f"Agent {self.agent_id} è ora idle")
                    await self.broker.report_idle()
                    self.last_activity = time.time()

                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Error in idle checker for {self.agent_id}: {e}")

    def _detect_skill(self, task: Dict) -> Optional[str]:
        if not self.skill_manager:
            return None
        description = task.get("description", "").lower()
        task_type = task.get("type", "").lower()
        search_text = f"{description} {task_type}"
        return self.skill_manager.find_skill_by_trigger(search_text)

    async def collect_retry_context(self, task: Dict) -> str:
        metadata = task.get("metadata", {})
        if not metadata.get("is_retry"):
            return ""

        last_error = metadata.get("last_error")
        if not last_error:
            return ""

        task_type = task.get("type", "")

        logger.info(
            f"Collecting retry context for task {task.get('task_id')} due to error: {last_error[:50]}..."
        )

        error_lines = str(last_error).split("\n")
        error_type = error_lines[0][:80] if error_lines else str(last_error)[:80]

        query = f"fix {error_type} in {task_type}"
        logger.info(f"Retry research query: {query}")

        research_results = await self.perform_research(query)

        context = ""
        if research_results and isinstance(research_results, list):
            context += (
                "\n\n--- 💡 AUTOMATED RESEARCH CONTEXT FOR ERROR RESOLUTION ---\n"
            )
            context += f"Last Error: {last_error}\n\nSearch Findings:\n"
            for res in research_results[:3]:
                if isinstance(res, dict) and "title" in res and "href" in res:
                    body = res.get("body", "")[:200]
                    context += f"- [{res.get('title')}]({res.get('href')}): {body}...\n"
            context += "\nUse these findings to fix the code and prevent the error from re-occurring.\n"

        return context

    def normalize_files(self, raw: Any) -> Dict[str, str]:
        if isinstance(raw, dict):
            result: Dict[str, str] = {}
            for k, v in raw.items():
                if isinstance(v, dict):
                    content = (
                        v.get("content") or v.get("code") or v.get("body") or str(v)
                    )
                    result[str(k)] = str(content)
                else:
                    result[str(k)] = str(v)
            return result
        if isinstance(raw, list):
            result: Dict[str, str] = {}
            for item in raw:
                if isinstance(item, dict):
                    path = (
                        item.get("path")
                        or item.get("filename")
                        or item.get("name")
                        or item.get("file")
                    )
                    content = (
                        item.get("content")
                        or item.get("code")
                        or item.get("body")
                        or ""
                    )
                    if path:
                        result[str(path)] = str(content)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    result[str(item[0])] = str(item[1])
            return result
        if isinstance(raw, str):
            logger.warning(
                f"[{self.agent_id}] LLM returned a plain string instead of a files dict — skipping file write."
            )
        else:
            logger.warning(
                f"[{self.agent_id}] Unexpected 'files' type: {type(raw)} — returning empty dict."
            )
        return {}

    async def get_auto_fix_instruction(self, task: Dict) -> str:
        metadata = task.get("metadata", {})
        if not metadata.get("is_retry"):
            return ""

        last_error = metadata.get("last_error", "Unknown error")
        retry_context = await self.collect_retry_context(task)

        return f"""
═══════════════════════════════════════════════════════════════
🚨 CRITICAL: THIS IS A RETRY AFTER FAILURE/REJECTION 🚨
═══════════════════════════════════════════════════════════════

The previous attempt was REJECTED or FAILED with this feedback/error:
{last_error}

{retry_context}

YOU MUST:
1. Identify the ROOT CAUSE of the failure above.
2. For REJECTION feedback: Address EVERY point mentioned by the reviewer.
3. For ERRORS: Implement a robust fix (e.g., add missing imports, fix logic, validate inputs).
4. Do NOT just regenerate the same code with minor changes.
5. Ensure the final result is complete, production-ready, and addresses all requirements.
═══════════════════════════════════════════════════════════════
"""

    async def perform_research(self, query: str) -> List[Dict]:
        """
        Esegue una ricerca web usando lo script utils/search_tool.py.
        FIX: aggiorna last_activity durante la ricerca per evitare che
        l'idle_checker segnali idle mentre aspettiamo il subprocess.
        """
        try:
            logger.info(f"Agent {self.agent_id} performing research: {query}")

            # FIX: tocca last_activity prima di aspettare il subprocess
            self.last_activity = time.time()

            system_root = Path(__file__).parent.parent.absolute()
            search_tool_path = system_root / "utils" / "search_tool.py"

            if not search_tool_path.exists():
                logger.error(f"Search tool not found at {search_tool_path}")
                return [{"error": "Search tool not found"}]

            cmd = [sys.executable, str(search_tool_path), query]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            # FIX: tocca last_activity anche dopo (la ricerca poteva durare secondi)
            self.last_activity = time.time()

            if process.returncode != 0:
                logger.error(f"Search tool failed: {stderr.decode()}")
                return [{"error": f"Search tool failed: {stderr.decode()}"}]

            results = json.loads(stdout.decode())

            if (
                results
                and not isinstance(results, list)
                or (
                    isinstance(results, list)
                    and len(results) > 0
                    and "error" not in results[0]
                )
            ):
                asyncio.create_task(
                    self._synthesize_and_store_knowledge(query, str(results))
                )

            return results
        except Exception as e:
            logger.error(f"Research call failed: {e}")
            return [{"error": str(e)}]

    async def _synthesize_and_store_knowledge(self, query_or_url: str, content: str):
        """Synthesizes research/docs and stores it in Domain Intelligence"""
        try:
            logger.info(f"🧠 Synthesizing domain knowledge for: {query_or_url[:50]}...")
            prompt = f"""
            Synthesize the following information to build Domain Intelligence.
            Source Context: {query_or_url}
            Raw Content: {content[:8000]}
            
            Format the output strictly as TOON/JSON with these keys:
            - domain: (string) broad domain
            - topic: (string) specific topic
            - synthesized_summary: (string) concise integrated conceptual summary
            - key_points: (list of strings) extracted principles and best practices
            - contradictions: (list of strings) any conflicts found
            """

            data = await self.llm_client.generate_structured(
                system_prompt="You are a Knowledge Merger Specialist. Extract and structure domain intelligence strictly in TOON/JSON format.",
                prompt=prompt,
            )

            domain = (data.get("domain") or "general").lower()
            topic = (data.get("topic") or "general").lower()
            summary = (
                data.get("synthesized_summary")
                or data.get("summary")
                or "No summary available"
            )
            key_points = data.get("key_points") or []
            contradictions = data.get("contradictions") or []

            if not summary or not summary.strip():
                logger.warning(
                    f"🧠 Knowledge synthesis skipped: LLM returned empty summary for '{topic}'"
                )
                return

            existing = await self.memory.get_domain_knowledge_by_topic(
                self.agent_id, topic
            )
            if existing:
                new_source_count = existing.get("source_count", 1) + 1
                new_confidence = min(1.0, existing.get("confidence_score", 0.5) + 0.1)

                merge_prompt = f"""
                Merge the old summary with new insights.
                Old Summary: {existing.get("synthesized_summary", "")}
                Old Key Points: {existing.get("key_points", [])}
                New Summary: {summary}
                New Key Points: {key_points}
                Return TOON/JSON with: 'synthesized_summary', 'key_points', 'contradictions'
                """
                m_data = await self.llm_client.generate_structured(
                    system_prompt="You are a Knowledge Merger Specialist. Output only TOON/JSON.",
                    prompt=merge_prompt,
                )

                summary = m_data.get("synthesized_summary", summary)
                key_points = m_data.get("key_points", key_points)
                contradictions = m_data.get("contradictions", contradictions)

                await self.memory.save_domain_knowledge(
                    id=existing["id"],
                    agent_id=self.agent_id,
                    domain=domain,
                    topic=topic,
                    summary=summary,
                    key_points=json.dumps(key_points)
                    if isinstance(key_points, list)
                    else key_points,
                    contradictions=json.dumps(contradictions)
                    if isinstance(contradictions, list)
                    else contradictions,
                    source_count=new_source_count,
                    confidence=new_confidence,
                )
                logger.info(f"🧠 Domain knowledge updated for topic: {topic}")
            else:
                import uuid

                await self.memory.save_domain_knowledge(
                    id=str(uuid.uuid4()),
                    agent_id=self.agent_id,
                    domain=domain,
                    topic=topic,
                    summary=summary,
                    key_points=json.dumps(key_points)
                    if isinstance(key_points, list)
                    else key_points,
                    contradictions=json.dumps(contradictions)
                    if isinstance(contradictions, list)
                    else contradictions,
                    source_count=1,
                    confidence=0.5,
                )
                logger.info(f"🧠 New domain knowledge created for topic: {topic}")

        except Exception as e:
            logger.error(f"Error in knowledge synthesis: {e}")

    async def read_web_page(self, url: str) -> Dict[str, Any]:
        try:
            logger.info(f"Agent {self.agent_id} reading web page: {url}")

            # FIX: aggiorna last_activity anche qui
            self.last_activity = time.time()

            system_root = Path(__file__).parent.parent.absolute()
            scraper_path = system_root / "utils" / "web_scraper.py"

            if not scraper_path.exists():
                logger.error(f"Web scraper not found at {scraper_path}")
                return {"error": "Web scraper tool not found"}

            cmd = [sys.executable, str(scraper_path), url]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            self.last_activity = time.time()

            if process.returncode != 0:
                logger.error(f"Web scraper failed: {stderr.decode()}")
                return {"error": f"Web scraper failed: {stderr.decode()}"}

            results = json.loads(stdout.decode())

            if results and "error" not in results:
                asyncio.create_task(
                    self._synthesize_and_store_knowledge(url, str(results))
                )

            return results
        except Exception as e:
            logger.error(f"Read web page call failed: {e}")
            return {"error": str(e)}

    async def execute(self, task: Dict) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement execute()")

    async def stop(self):
        self.running = False
        await self.broker.stop()
        logger.info(f"Agent {self.agent_id} stopped")

#!/usr/bin/env python3
"""
ScrumMasterAgent - Gestisce l'intero ciclo agile Scrum con supporto TOON.
"""

import asyncio
import logging
import time
import json
from typing import Dict, Any, List, Optional

from agents.base_agent import BaseAgent
from config import (
    get_topics,
    SPRINT_SIZE,
    BACKLOG_REFINEMENT_INTERVAL,
    RELEASE_SPRINT_INTERVAL,
)

logger = logging.getLogger(__name__)


class ScrumMasterAgent(BaseAgent):
    """
    Agente specializzato nella gestione del framework Scrum - TOON Ready.
    """

    def __init__(self, agent_id: str, memory, project_root: str, **kwargs):
        super().__init__(agent_id, "scrum_master", memory, project_root, **kwargs)
        self.sprint_task_count = 0
        self.active_sprint_id: Optional[int] = None
        self.agent_feedbacks: Dict[str, str] = {}
        self.refinement_proposals: List[Dict] = []
        self.pending_release_notes: Optional[str] = None
        self._is_ending_sprint: bool = False
        self.initial_retrospective: bool = False

    async def start(self):
        """Avvio dell'agente con sottoscrizioni"""
        self.running = True
        await self.broker.connect()

        # Custom Scrum Master Subscriptions
        await self.broker.subscribe(
            get_topics(self.project_id)["TASKS_COMPLETED"], self._on_task_completed
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["SCRUM_REPORT"], self._on_agent_feedback
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["BACKLOG_REFINEMENT_PROPOSAL"],
            self._on_refinement_proposal,
        )

        # Base Agent Subscriptions
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

        active_sprint = await self.memory.get_active_sprint(self.project_id)
        if active_sprint:
            self.active_sprint_id = active_sprint["sprint_id"]
            self.sprint_task_count = await self._get_completed_tasks_count_since(
                active_sprint["started_at"]
            )
            logger.info(
                f"🔄 Ripristinato Sprint activo ID: {self.active_sprint_id} con {self.sprint_task_count} task completati dal suo inizio."
            )
        else:
            await self._start_new_sprint()

        tasks = [self._heartbeat_worker(), self._task_worker(), self._idle_checker()]

        if self.initial_retrospective and self.active_sprint_id:
            logger.info(
                f"⚡ Progetto avviato con --resume. Lancio Retrospective immediata per lo Sprint {self.active_sprint_id}..."
            )
            # Ritardo di 10s per permettere agli altri agenti di connettersi e registrarsi al broker
            asyncio.create_task(
                self._trigger_retrospective_with_delay(self.active_sprint_id, delay=10)
            )

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _trigger_retrospective_with_delay(self, sprint_id: int, delay: int = 10):
        """Attende un breve ritardo prima di lanciare la retrospective (utile per il resume)"""
        await asyncio.sleep(delay)
        await self._trigger_retrospective(sprint_id)

    async def _get_local_sprint_num(self) -> int:
        """Restituisce il numero dello sprint per il progetto corrente (1-indexed)"""
        counter = await self.memory.get_sprint_counter(self.project_id)
        if not counter:
            return 1
        return counter.get("total_sprints_completed", 0) + 1

    async def _get_completed_tasks_count_since(self, started_at: str) -> int:
        """Query DB to count tasks completed during the active sprint"""
        import sqlite3

        conn = sqlite3.connect(self.memory.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM tasks 
            WHERE project_id = ? 
            AND status = 'completed'
            AND type NOT IN ('create_project', 'evolve_project', 'review_task', 'speaking_commit', 'scrum_improvement', 'backlog_item')
            AND completed_at >= ?
        """,
            (self.project_id, started_at),
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    async def _start_new_sprint(self):
        """Inizia un nuovo ciclo di sprint"""
        local_sprint_num = await self._get_local_sprint_num()
        self.active_sprint_id = await self.memory.create_sprint(
            self.project_id, sprint_number=local_sprint_num
        )
        self.sprint_task_count = 0
        self.agent_feedbacks = {}

        logger.info(
            f"🚀 Iniziato nuovo SPRINT ID (locale): {local_sprint_num} (DB ID: {self.active_sprint_id})"
        )

    async def _handle_scrum_ceremony(self, message: Dict):
        """Gestisce le cerimonie Scrum e intercetta la fine del progetto."""
        if message.get("type") == "project_completed":
            logger.info(
                "🏁 Ricevuto segnale PROJECT_COMPLETED dall'Orchestratore. Forza le cerimonie finali per lo sprint corrente..."
            )
            # Attendiamo che un eventuale _safe_end_sprint finisca
            while self._is_ending_sprint:
                await asyncio.sleep(1)

            self._is_ending_sprint = True
            try:
                if self.sprint_task_count >= 0:
                    sid = int(self.active_sprint_id) if self.active_sprint_id else 0
                    await self._end_sprint(sid, force_ceremonies=True)
            finally:
                self._is_ending_sprint = False
        else:
            await super()._handle_scrum_ceremony(message)

    async def _on_task_completed(self, message: Dict):
        # Filtra per progetto corrente
        if message.get("project_id") != self.project_id:
            return

        SYSTEM_TASK_TYPES = {
            "create_project",
            "evolve_project",
            "review_task",
            "speaking_commit",
            "scrum_improvement",
            "backlog_item",
        }
        task_type = message.get("type", "")
        if task_type in SYSTEM_TASK_TYPES:
            return

        self.sprint_task_count += 1
        local_sprint_num = await self._get_local_sprint_num()
        logger.info(
            f"📊 Sprint {local_sprint_num} Progress: {self.sprint_task_count}/{SPRINT_SIZE} tasks completed."
        )

        if self.sprint_task_count >= SPRINT_SIZE and not self._is_ending_sprint:
            # Crea un task per non bloccare l'event loop e non perdere task complessi
            asyncio.create_task(self._safe_end_sprint())

    async def _safe_end_sprint(self):
        self._is_ending_sprint = True
        try:
            while self.sprint_task_count >= SPRINT_SIZE:
                sprint_id_to_end = self.active_sprint_id

                # Iniziamo subito un nuovo sprint per raccogliere i nuovi task
                self.active_sprint_id = await self.memory.create_sprint(self.project_id)
                self.agent_feedbacks = {}

                local_sprint_num = await self._get_local_sprint_num()
                logger.info(
                    f"🚀 Iniziato nuovo SPRINT ID (locale): {local_sprint_num} (rimanenti in coda vecchio sprint: {self.sprint_task_count})"
                )

                await self._end_sprint(sprint_id_to_end)

                # Consumiamo i task dello sprint DOPO aver terminato il vecchio sprint
                # Questo assicura che i task completati durante l'esecuzione di _end_sprint
                # vengano conteggiati per il nuovo sprint.
                self.sprint_task_count -= SPRINT_SIZE
        finally:
            self._is_ending_sprint = False

    async def _end_sprint(self, sprint_id: int, force_ceremonies: bool = False):
        """Finalizza lo sprint corrente"""
        local_sprint_num = await self._get_local_sprint_num()
        logger.info(f"🏁 Sprint {local_sprint_num} (DB ID: {sprint_id}) completato.")

        await self._trigger_retrospective(sprint_id)

        total = await self.memory.increment_sprint_counter(self.project_id)
        if force_ceremonies or (total % BACKLOG_REFINEMENT_INTERVAL == 0):
            await self._trigger_backlog_refinement(sprint_id)

        if force_ceremonies or (total % RELEASE_SPRINT_INTERVAL == 0):
            await self._trigger_release(total, sprint_id)

    async def _trigger_retrospective(self, sprint_id: int):
        """Raccoglie feedback e genera report"""
        logger.info(f"🔍 Avvio Retrospective per Sprint {sprint_id}...")
        await self.broker.publish(
            get_topics(self.project_id)["SCRUM_CEREMONY"],
            {
                "type": "retrospective_request",
                "sprint_id": sprint_id,
                "project_id": self.project_id,
            },
        )
        logger.info(
            f"⏳ Attesa 90s per raccogliere feedback Retrospective (Sprint {sprint_id})..."
        )
        await asyncio.sleep(90)
        await self._finalize_retrospective(sprint_id)

    async def _on_agent_feedback(self, message: Dict):
        """Riceve feedback da un agente"""
        sprint_id = message.get("sprint_id")
        if not sprint_id:
            return

        agent_type = message.get("agent_type")
        feedback = message.get("feedback")
        sentiment = message.get("sentiment", "neutral")

        # Catch release notes from Architect
        if message.get("is_release_notes"):
            self.pending_release_notes = feedback
            return

        if agent_type and feedback:
            await self.memory.save_retrospective_feedback(
                sprint_id, agent_type, feedback, sentiment
            )
            self.agent_feedbacks[agent_type] = feedback

    async def _finalize_retrospective(self, sprint_id: int):
        """Sintetizza i feedback con output TOON"""
        feedbacks = await self.memory.get_sprint_retrospective(sprint_id)

        # Recupera task falliti per ridiscuterli
        pending_and_failed = await self.memory.get_pending_tasks(self.project_id)
        failed_tasks = [t for t in pending_and_failed if t.get("status") == "failed"]

        if not feedbacks and not failed_tasks:
            await self.memory.complete_sprint(sprint_id)
            return

        prompt = """Summarize agile retrospective feedbacks and address FAILED tasks.
Identify concrete technical improvements and decide the fate of each failed task.

CRITICAL: If the frontend agent reports missing backend routes or APIs, YOU MUST prioritize creating actions/tasks for the backend to implement those missing routes immediately, so the frontend can continue working in parallel.

For EACH failed task, decide if it should be:
1. "retry": Move back to 'pending' (potentially with higher priority if it blocks others).
2. "rework": Move to 'rework' status (a special status for fixing rejected/failed work).
3. "split": Create additional smaller action items to address the root cause, then this task will be handled accordingly.
4. "ignore": Keep as 'failed' if no longer relevant.

Output a summary, a list of selected actions, and a list of decisions for the failed tasks.

Feedbacks:
"""
        for f in feedbacks:
            prompt += f"- [{f['agent_type']}]: {f['feedback']}\n"

        if failed_tasks:
            prompt += "\nFailed Tasks to re-prioritize:\n"
            for t in failed_tasks:
                prompt += f"- ID: {t['task_id']}, Agent: {t['agent_type']}, Desc: {t['description']}\n"

        # Cerchiamo di ottenere output strutturato per gli Action Items
        try:
            prompt += "\nStructure your response as an object with: summary (string), actions (list of strings), failed_task_decisions (list of objects with 'task_id', 'decision', and 'reason')."
            data = await self.llm_client.generate_structured(
                system_prompt="You are an expert Scrum Master.", prompt=prompt
            )
        except Exception as e:
            logger.error(f"Errore retrospective LLM: {e}")
            data = {}

        summary = data.get("summary", "No summary available.")
        actions = data.get("actions", [])
        failed_task_decisions = data.get("failed_task_decisions", [])

        # Salva report
        retro_file = self.project_root / "memory" / "retrospective.md"
        retro_file.parent.mkdir(exist_ok=True, parents=True)
        content = f"\n\n# Retrospective Sprint {sprint_id}\n\n{summary}\n\n"

        if failed_task_decisions:
            content += "## Failed Task Decisions\n\n"
            for d in failed_task_decisions:
                content += f"- **{d.get('task_id')}**: {d.get('decision')} - {d.get('reason')}\n"
            content += "\n"

        content += "## Action Items\n\n"
        for a in actions:
            content += f"- [ACTION] {a}\n"
        with open(retro_file, "a") as f:
            f.write(content)

        # Processa decisioni per i task falliti
        for decision_obj in failed_task_decisions:
            tid = decision_obj.get("task_id")
            decision = decision_obj.get("decision", "").lower()
            reason = decision_obj.get("reason", "")

            if not tid:
                continue

            if decision == "retry":
                await self.memory.update_task(
                    tid, {"status": "pending", "priority": 10}
                )
                logger.info(f"🔄 Task {tid} ripristinato a PENDING per retry.")
            elif decision == "rework":
                await self.memory.update_task(tid, {"status": "rework"})
                logger.info(f"🛠️ Task {tid} spostato in REWORK.")
            elif decision == "split":
                # Il split è gestito dagli action items generati sopra
                await self.memory.update_task(
                    tid,
                    {
                        "status": "completed",
                        "metadata": json.dumps(
                            {
                                "reason": f"Split in multiple tasks during retro: {reason}"
                            }
                        ),
                    },
                )
                logger.info(
                    f"✂️ Task {tid} splittato e marcato completato via Action Items."
                )
            elif decision == "ignore":
                logger.info(f"🚫 Task {tid} ignorato come irrilevante.")

        # Crea task per Action Items
        for action in actions:
            agent_type = self._detect_agent_type(action)
            new_task = {
                "task_id": f"retro_{sprint_id}_{int(time.time())}_{abs(hash(action)) % 10000}",
                "project_id": self.project_id,
                "type": "scrum_improvement",
                "agent_type": agent_type,
                "description": f"[Agile Improvement] {action}",
                "priority": 10,
                "status": "pending",
                "metadata": json.dumps(
                    {"source": "retrospective", "sprint_id": sprint_id}
                ),
            }
            await self.memory.save_task(new_task)
            # Pubblica il nuovo task così l'orchestratore lo vede subito
            await self.broker.publish(
                get_topics(self.project_id)["TASKS_NEW"], new_task
            )

        await self.memory.complete_sprint(sprint_id)

    async def _trigger_backlog_refinement(self, sprint_id: int):
        """Cerimonia di refinement"""
        # FIX: Standardizza sprint_id come int
        sprint_id = int(sprint_id)
        # FIX: Pulisce proposte precedenti per evitare accumuli/leak di altri sprint
        self.refinement_proposals = []

        logger.info(f"🗂️ Avvio Backlog Refinement per lo Sprint {sprint_id}...")
        pending_tasks = await self.memory.get_pending_tasks(self.project_id)
        pending_summary = "\n".join(
            f"- [{t.get('agent_type')}] {t.get('description', '')[:80]}"
            for t in pending_tasks[:10]
        )

        await self.broker.publish(
            get_topics(self.project_id)["BACKLOG_REFINEMENT"],
            {
                "type": "backlog_refinement_request",
                "sprint_id": sprint_id,
                "project_id": self.project_id,
                "pending_tasks_summary": pending_summary,
                "timestamp": time.time(),
            },
        )
        logger.info(
            f"⏳ Attesa 90s per raccogliere proposte Backlog Refinement (Sprint {sprint_id})..."
        )
        await asyncio.sleep(90)
        await self._finalize_backlog_refinement(sprint_id)

    async def _on_refinement_proposal(self, message: Dict):
        """Riceve proposta"""
        if message.get("project_id") != self.project_id:
            return
        agent_type = message.get("agent_type")
        proposals = message.get("proposals", [])
        for p in proposals[:5]:  # aumentato da 3 a 5 per agente
            desc = p.get("description", "") if isinstance(p, dict) else str(p)
            if desc:
                self.refinement_proposals.append(
                    {
                        "agent_type": agent_type,
                        "description": desc,
                        "priority": p.get("priority", 1) if isinstance(p, dict) else 1,
                        "sprint_id": message.get("sprint_id", self.active_sprint_id),
                    }
                )

    async def _finalize_backlog_refinement(self, sprint_id: int):
        """Sintetizza proposte con output TOON"""
        if not self.refinement_proposals:
            return

        # Filtriamo le proposte per questo sprint specifico, o le usiamo tutte
        # (se _trigger_backlog_refinement pulisce self.refinement_proposals non e' safe per chiamate concorrenti,
        #  ma diamo per scontato che sia ok per ora)
        current_proposals = [
            p for p in self.refinement_proposals if p.get("sprint_id") == sprint_id
        ]

        proposals_text = "\n".join(
            f"- [{p['agent_type']}] P{p['priority']}: {p['description']}"
            for p in current_proposals
        )
        prompt = f"""Review these backlog refinement proposals. Select top 10 improvements.
Proposals:
{proposals_text}

Structure your response as an object with an 'items' key (list of objects with 'agent' and 'desc')."""

        data = await self.llm_client.generate_structured(
            system_prompt="You are an expert Scrum Master.", prompt=prompt
        )

        # AFTER
        items = []
        if data:
            logger.info(
                f"Backlog refinement collected {len(current_proposals)} proposals. LLM response keys: {list(data.keys())}"
            )
            # Robust key detection for TOON/JSON variations
            for key in [
                "items",
                "selected_items",
                "proposals",
                "actions",
                "backlog",
                "backlog_items",
            ]:
                val = data.get(key)
                if isinstance(val, list):
                    items = val
                    break
            else:
                # If no list found, check if the object itself is the list (some TOON parsers do this)
                if isinstance(data, list):
                    items = data

        # FIX: persisti le proposte raw nella tabella backlog_refinement_items
        # in modo che la dashboard /api/refinement le mostri
        for p in current_proposals:
            await self.memory.save_refinement_proposal(
                self.project_id,
                sprint_id,
                p["agent_type"],
                p["description"],
                p.get("priority", 1),
            )

        for i, item in enumerate(items[:10]):  # aumentato da 5 a 10
            agent_type = item.get("agent", "backend")
            description = item.get("desc", "")
            if description:
                new_task = {
                    "task_id": f"refinement_{sprint_id}_{int(time.time())}_{i}",
                    "project_id": self.project_id,
                    "type": "backlog_item",
                    "agent_type": self._detect_agent_type(
                        agent_type + " " + description
                    ),
                    "description": f"[Backlog] {description}",
                    "priority": 10,
                    "status": "pending",
                    "metadata": json.dumps(
                        {
                            "source": "backlog_refinement",
                            "sprint_id": sprint_id,
                            "published": False,
                        }
                    ),
                }
                await self.memory.save_task(new_task)
                # FIX: pubblica il task al broker così l'orchestratore lo riceve
                # e lo distribuisce agli agenti tramite _sync_external_tasks
                await self.broker.publish(
                    get_topics(self.project_id)["TASKS_NEW"], new_task
                )
                logger.info(
                    f"📋 Backlog item creato e pubblicato: {new_task['task_id']} → {new_task['agent_type']}"
                )

        await self.memory.accept_refinement_proposals(self.project_id, sprint_id)

        # Pulizia mem locale delle proposte processate in questo sprint
        self.refinement_proposals = [
            p for p in self.refinement_proposals if p.get("sprint_id") != sprint_id
        ]

    async def _trigger_release(self, total_sprints: int, sprint_id: int):
        """Crea una release"""
        release_number = total_sprints // RELEASE_SPRINT_INTERVAL
        version = f"v{release_number // 10}.{release_number % 10}"
        logger.info(f"🎉 Release {version}...")

        counter = await self.memory.get_sprint_counter(self.project_id)
        sprint_start = counter.get("current_release_sprint_start", 1)

        await self.broker.publish(
            get_topics(self.project_id)["SCRUM_CEREMONY"],
            {
                "type": "release_request",
                "version": version,
                "project_id": self.project_id,
                "sprint_start": sprint_start,
                "sprint_end": sprint_id,
            },
        )
        await asyncio.sleep(30)

        # Fallback release notes
        release_summary = self.pending_release_notes or f"Release {version} completed."
        release_id = await self.memory.create_release(
            self.project_id,
            version,
            sprint_start,
            sprint_id,
            release_summary,
        )

        (self.project_root / f"release_notes_{version}.md").write_text(
            f"# Release {version}\n\n{release_summary}"
        )

        await self.broker.publish(
            get_topics(self.project_id)["RELEASE_READY"],
            {
                "release_id": release_id,
                "version": version,
                "project_id": self.project_id,
            },
        )
        self.pending_release_notes = None

    def _detect_agent_type(self, text: str) -> str:
        """Euristica tipo agente"""
        t = text.lower()
        if any(k in t for k in ["frontend", "ui", "css", "html", "react"]):
            return "frontend"
        if any(k in t for k in ["database", "sql", "query", "schema"]):
            return "database"
        if any(k in t for k in ["test", "qa", "spec"]):
            return "testing"
        if any(k in t for k in ["architect", "design", "structure"]):
            return "architect"
        if any(k in t for k in ["deploy", "devops", "ci", "docker"]):
            return "devops"
        return "backend"

    async def execute(self, task: Dict) -> Dict[str, Any]:
        """Esegue task espliciti"""
        task_type = task.get("type")
        if task_type == "backlog_refinement":
            await self._trigger_backlog_refinement()
        elif task_type == "trigger_release":
            counter = await self.memory.get_sprint_counter(self.project_id)
            await self._trigger_release(counter.get("total_sprints_completed", 0))
        return {"status": "completed"}

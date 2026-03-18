#!/usr/bin/env python3
"""
Orchestrator Agent con FIX per distribuzione task
FIX applicati rispetto alla versione precedente:
  - _publish_ready_tasks: dipendenza "failed" = soddisfatta (non blocca a valle)
  - _handle_agent_idle:   stessa logica
  - _reclaim_orphaned_tasks: timeout differenziato per tipo task (commit/test → 300s)
  - _calculate_dependencies: pulizia dep fantasma già presente, mantenuta
  - _monitor_running guard: già presente, mantenuto
"""

import asyncio
import logging
from typing import Dict, List, Any
import uuid
import time
from pathlib import Path

from agents.base_agent import BaseAgent
from config import get_topics, REQUIRED_REVIEWS

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Orchestrator che coordina tutti gli agenti - FIXED"""

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
            agent_type="orchestrator",
            memory=memory,
            project_root=project_root,
            skill_manager=skill_manager,
            prompt_manager=prompt_manager,
        )

        self.all_tasks: Dict[str, Dict] = {}
        self.task_dependencies: Dict[str, List[str]] = {}
        self.agents_status: Dict[str, Dict] = {}

        self.REQUIRED_REVIEWS = REQUIRED_REVIEWS
        self.pending_reviews: Dict[str, Dict] = {}
        self.pending_commits: Dict[str, str] = {}

        self.completion_event = asyncio.Event()

        asyncio.create_task(self._subscribe_to_orchestrator_topics())

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize_llm_response(self, data: Any) -> Any:
        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                new_k = k.strip().strip('"').strip("'") if isinstance(k, str) else k
                new_dict[new_k] = self._normalize_llm_response(v)
            return new_dict
        elif isinstance(data, list):
            return [self._normalize_llm_response(item) for item in data]
        elif isinstance(data, str):
            val = data.strip().strip('"').strip("'")
            if val.endswith(","):
                val = val[:-1].strip().strip('"').strip("'")
            if (val.startswith("[") and val.endswith("]")) or (
                val.startswith("{") and val.endswith("}")
            ):
                try:
                    import json

                    return json.loads(val)
                except Exception:
                    pass
            return val
        return data

    def _ensure_metadata_dict(self, task: Dict):
        if not isinstance(task, dict):
            return
        metadata = task.get("metadata")
        if isinstance(metadata, str):
            try:
                import json

                task["metadata"] = json.loads(metadata)
                return
            except Exception:
                pass
            try:
                import ast

                parsed = ast.literal_eval(metadata)
                if isinstance(parsed, dict):
                    task["metadata"] = parsed
                    return
            except Exception:
                pass
            task["metadata"] = {}
        elif metadata is None:
            task["metadata"] = {}

    # ─────────────────────────────────────────────────────────────────────────
    # Subscriptions
    # ─────────────────────────────────────────────────────────────────────────

    async def _subscribe_to_orchestrator_topics(self):
        await asyncio.sleep(0.5)
        await self.broker.subscribe(
            get_topics(self.project_id)["TASKS_COMPLETED"], self._handle_task_completed
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["TASKS_STARTED"], self._handle_task_started
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["TASKS_FAILED"], self._handle_task_failed
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["AGENT_HEARTBEAT"], self._handle_heartbeat
        )
        await self.broker.subscribe(
            get_topics(self.project_id)["AGENT_IDLE"], self._handle_agent_idle
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Entry points
    # ─────────────────────────────────────────────────────────────────────────

    async def execute(self, task: Dict) -> Dict[str, Any]:
        task_type = task.get("type")
        if task_type == "create_project":
            return await self._orchestrate_project_creation(task)
        elif task_type == "evolve_project":
            return await self._orchestrate_project_evolution(task)
        else:
            logger.warning(f"Unknown orchestrator task type: {task_type}")
            return {"status": "unknown_type"}

    # ─────────────────────────────────────────────────────────────────────────
    # Project creation
    # ─────────────────────────────────────────────────────────────────────────

    async def _orchestrate_project_creation(self, task: Dict) -> Dict[str, Any]:
        logger.info("Inizio orchestrazione creazione progetto")

        prompt = task.get("prompt")
        spec = task.get("specification", {})

        if prompt:
            tasks = await self._decompose_project_with_llm(prompt, spec)
        else:
            tasks = self._decompose_project(spec)

        if not tasks:
            raise RuntimeError("LLM returned no tasks — retrying decomposition")

        impl_agent_types = {
            "backend",
            "frontend",
            "database",
            "devops",
            "testing",
            "qa",
        }
        has_impl_tasks = any(t.get("agent_type") in impl_agent_types for t in tasks)
        if not has_impl_tasks:
            logger.warning(
                "⚠️ LLM decomposition returned NO implementation tasks. Injecting hardcoded fallback tasks."
            )
            fallback = self._decompose_project(spec)
            fallback = [
                t
                for t in fallback
                if t.get("agent_type") not in {"researcher", "architect"}
            ]
            tasks.extend(fallback)

        if spec.get("frontend", True) and not any(
            t.get("agent_type") == "frontend" for t in tasks
        ):
            logger.warning(
                "⚠️ LLM decomposition omitted requested 'frontend' tasks. Injecting fallback."
            )
            tasks.append(
                {
                    "task_id": f"frontend_ui_{uuid.uuid4().hex[:8]}",
                    "type": "create_ui",
                    "agent_type": "frontend",
                    "description": "Create required frontend UI components",
                    "priority": 2,
                    "metadata": {},
                }
            )

        if spec.get("database", True) and not any(
            t.get("agent_type") == "database" for t in tasks
        ):
            logger.warning(
                "⚠️ LLM decomposition omitted requested 'database' tasks. Injecting fallback."
            )
            tasks.append(
                {
                    "task_id": f"db_schema_{uuid.uuid4().hex[:8]}",
                    "type": "design_schema",
                    "agent_type": "database",
                    "description": "Design necessary database schema",
                    "priority": 1,
                    "metadata": {},
                }
            )

        has_research = any(t["agent_type"] == "researcher" for t in tasks)
        if not has_research:
            research_task = {
                "task_id": f"research_tech_{uuid.uuid4().hex[:6]}",
                "type": "research_tech_stack",
                "agent_type": "researcher",
                "description": f"Research best tech stack and documentation for: {prompt or 'web project'}",
                "priority": 0,
                "metadata": {
                    "preferences": spec,
                    "tech_prefs": {k: v for k, v in spec.items() if isinstance(v, str)},
                },
            }
            tasks.insert(0, research_task)

        has_architect = any(t["agent_type"] == "architect" for t in tasks)
        if not has_architect:
            architect_task = {
                "task_id": f"design_arch_{uuid.uuid4().hex[:6]}",
                "type": "design_architecture",
                "agent_type": "architect",
                "description": f"Design complete technical architecture for the project: {prompt}",
                "priority": 0,
                "metadata": {},
            }
            insert_idx = 1 if any(t["agent_type"] == "researcher" for t in tasks) else 0
            tasks.insert(insert_idx, architect_task)

        architect_id = next(
            (t["task_id"] for t in tasks if t["agent_type"] == "architect"), None
        )
        research_id = next(
            (t["task_id"] for t in tasks if t["agent_type"] == "researcher"), None
        )

        for t in tasks:
            if (
                t.get("agent_type")
                in ["backend", "frontend", "database", "devops", "testing", "qa"]
                and t.get("type") != "research_tech_stack"
            ):
                if "depends_on" not in t:
                    t["depends_on"] = []
                if isinstance(t["depends_on"], str):
                    t["depends_on"] = [t["depends_on"]] if t["depends_on"] else []
                elif not isinstance(t["depends_on"], list):
                    t["depends_on"] = []
                if architect_id and architect_id not in t["depends_on"]:
                    t["depends_on"].append(architect_id)
                if research_id and research_id not in t["depends_on"]:
                    t["depends_on"].append(research_id)

        # Evita deadlock: researcher e architect non dipendono da nessuno
        for t in tasks:
            if t.get("agent_type") in ("researcher", "architect"):
                if t.get("depends_on"):
                    logger.warning(
                        f"⚠️ DEADLOCK PREVENTION: resetting depends_on={t['depends_on']} "
                        f"for root task {t['task_id']} ({t['agent_type']})"
                    )
                t["depends_on"] = []

        await self._calculate_dependencies(tasks)

        is_mvp = spec.get("mvp", False)

        for task_obj in tasks:
            task_id = task_obj["task_id"]
            agent_type = task_obj["agent_type"]

            if "metadata" not in task_obj or not isinstance(task_obj["metadata"], dict):
                task_obj["metadata"] = {}
            if is_mvp:
                task_obj["metadata"]["mvp"] = True
            task_obj["metadata"]["published"] = False

            self.all_tasks[task_id] = {
                **task_obj,
                "status": "pending",
                "assigned_at": None,
            }

            await self.memory.create_task(
                task_id=task_id,
                task_type=task_obj["type"],
                agent_type=agent_type,
                description=task_obj["description"],
                project_id=self.project_id,
                priority=task_obj.get("priority", 1),
                metadata=task_obj.get("metadata", {}),
                depends_on=task_obj.get("depends_on", []),
            )

        await self._publish_ready_tasks()
        asyncio.create_task(self._monitor_progress())

        return {
            "status": "orchestrating",
            "total_tasks": len(tasks),
            "tasks": [t["task_id"] for t in tasks],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Project evolution
    # ─────────────────────────────────────────────────────────────────────────

    async def _orchestrate_project_evolution(self, task: Dict) -> Dict[str, Any]:
        logger.info(f"🚀 Inizio evoluzione progetto '{self.project_id}'")
        self.completion_event.clear()

        prompt = task.get("prompt")
        spec = task.get("specification", {})

        existing_arch = ""
        for arch_path in [
            Path(self.project_root) / "architecture.md",
            Path(self.project_root) / "docs" / "architecture.md",
        ]:
            if arch_path.exists():
                with open(arch_path, "r") as f:
                    existing_arch = f.read()
                break

        evolution_prompt = f"""EVOLUTION REQUEST: {prompt}
        
EXISTING ARCHITECTURE:
{existing_arch}

Analyze the request and generate ONLY the NEW tasks (or modifications) needed.
DO NOT recreate existing infrastructure unless changes are needed.
Output MUST be a structured TOON list of tasks.

[
  {{
    "thought": "your reasoning",
    "task_id": "unique_id",
    "type": "ONE_OF_THE_ALLOWED_TYPES",
    "agent_type": "responsible_agent",
    "description": "Granular instructions",
    "priority": 10,
    "depends_on": [],
    "metadata": {{}}
  }}
]
"""

        new_tasks = await self._decompose_project_with_llm(evolution_prompt, spec)
        if not new_tasks:
            raise RuntimeError(
                "LLM returned no tasks — retrying evolution decomposition"
            )

        await self._calculate_dependencies(new_tasks)

        is_mvp = spec.get("mvp", False)

        for task_obj in new_tasks:
            task_id = task_obj["task_id"]
            if "metadata" not in task_obj or not isinstance(task_obj["metadata"], dict):
                task_obj["metadata"] = {}
            if is_mvp:
                task_obj["metadata"]["mvp"] = True
            task_obj["metadata"]["published"] = False

            self.all_tasks[task_id] = {
                **task_obj,
                "status": "pending",
                "assigned_at": None,
            }

            await self.memory.create_task(
                task_id=task_id,
                task_type=task_obj["type"],
                agent_type=task_obj["agent_type"],
                description=task_obj["description"],
                project_id=self.project_id,
                priority=task_obj.get("priority", 1),
                metadata=task_obj.get("metadata", {}),
                depends_on=task_obj.get("depends_on", []),
            )

        await self._publish_ready_tasks()
        asyncio.create_task(self._monitor_progress())

        return {
            "status": "evolving",
            "new_tasks_count": len(new_tasks),
            "tasks": [t["task_id"] for t in new_tasks],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # LLM decomposition
    # ─────────────────────────────────────────────────────────────────────────

    async def _decompose_project_with_llm(self, prompt: str, spec: Dict) -> List[Dict]:
        from core.toon import toon_decode

        system_prompt = """You are a software architect decomposing a project into ATOMIC tasks.

Agents available (ALLOWED task types):
- backend:  implement_api, implement_auth
- frontend: create_ui, integrate_api
- database: design_schema, create_migrations
- devops:   create_docker, setup_ci, create_startup_script
- testing:  write_tests
- qa:       write_e2e_tests, validate_project
- researcher: research_tech_stack, search_docs
- architect:  design_architecture

CRITICAL GRANULARITY RULES:
1. ONE task = ONE function / ONE endpoint / ONE table / ONE component — NEVER group multiple.
2. Do NOT create a task like "implement CRUD for products" — instead create 4 separate tasks:
   - "Implement GET /products endpoint"
   - "Implement POST /product endpoint"
   - "Implement PUT /product/{id} endpoint"
   - "Implement DELETE /product/{id} endpoint"
3. Maximum 12 tasks total. Prioritize the most essential features only.
4. Frontend MUST depend on backend tasks.
5. Use short descriptions (max 10 words each).

Respond in TOON tabular format:
thought: brief reasoning
tasks[0]{task_id,type,agent_type,description,priority,depends_on,metadata}:
  task_001,design_schema,database,Design products table schema,1,,{}
  task_002,implement_api,backend,Implement GET /products endpoint,2,task_001,{}
  task_003,implement_api,backend,Implement POST /product endpoint,2,task_001,{}"""

        user_content = f"Project: {prompt}\nComponents: backend={spec.get('backend')}, frontend={spec.get('frontend')}, database={spec.get('database')}"

        try:
            raw_response = await self.llm_client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=3000,
            )

            try:
                decoded = toon_decode(raw_response)
            except Exception as e:
                logger.warning(f"TOON decode failed ({e}), attempting JSON fallback")
                import json, re

                cleaned = re.sub(r"```(?:json)?\n?|```", "", raw_response).strip()
                try:
                    decoded = json.loads(cleaned)
                except Exception:
                    logger.error(
                        f"Both TOON and JSON decode failed. Raw: {raw_response[:300]}"
                    )
                    return []

            tasks = decoded

            if isinstance(tasks, dict):
                for key in [
                    "tasks",
                    "actions",
                    "project_tasks",
                    "items",
                    "backlog",
                    "steps",
                ]:
                    if key in tasks and isinstance(tasks[key], list):
                        tasks = tasks[key]
                        break
                else:
                    found = None
                    for k, v in tasks.items():
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            if any(
                                f in v[0]
                                for f in (
                                    "agent_type",
                                    "type",
                                    "description",
                                    "task_id",
                                )
                            ):
                                found = v
                                break
                    if found is not None:
                        tasks = found
                    elif any(
                        f in tasks for f in ("task_id", "agent_type", "description")
                    ):
                        tasks = [tasks]
                    else:
                        logger.warning(
                            f"No task list found in decoded TOON. Keys: {list(tasks.keys())}"
                        )
                        return []

            tasks = self._normalize_llm_response(tasks)

            if isinstance(tasks, dict):
                for key in [
                    "tasks",
                    "project_tasks",
                    "items",
                    "data",
                    "backlog",
                    "steps",
                ]:
                    if key in tasks and isinstance(tasks[key], list):
                        tasks = tasks[key]
                        break
                else:
                    potential_list = []
                    for k, v in tasks.items():
                        if isinstance(v, dict) and (
                            "agent_type" in v or "type" in v or "description" in v
                        ):
                            if "task_id" not in v:
                                v["task_id"] = k
                            potential_list.append(v)

                    if potential_list:
                        tasks = potential_list
                    elif (
                        "task_id" in tasks
                        or "description" in tasks
                        or "agent_type" in tasks
                    ):
                        tasks = [tasks]
                    elif "actions" in tasks and isinstance(tasks["actions"], list):
                        tasks = tasks["actions"]
                    else:
                        found = None
                        for k, v in tasks.items():
                            if isinstance(v, list) and v and isinstance(v[0], dict):
                                if any(
                                    field in v[0]
                                    for field in (
                                        "agent_type",
                                        "type",
                                        "description",
                                        "task_id",
                                    )
                                ):
                                    found = v
                                    break
                        if found is not None:
                            tasks = found
                        else:
                            logger.warning(
                                f"LLM returned a dict but no task list found: {list(tasks.keys())}"
                            )
                            return []

            if isinstance(tasks, list):
                cleaned_tasks = []
                allowed_agents = [
                    "backend",
                    "frontend",
                    "database",
                    "devops",
                    "testing",
                    "qa",
                    "researcher",
                    "architect",
                ]

                for i, t in enumerate(tasks):
                    if isinstance(t, str) and ":" in t:
                        try:
                            t = toon_decode(t)
                        except Exception:
                            pass

                    if not isinstance(t, dict):
                        logger.warning(f"Skipping non-dict task: {t}")
                        continue

                    import re

                    def clean_str(val):
                        if not isinstance(val, str):
                            return val
                        return re.sub(r"[,\.\s]+$", "", val).strip()

                    if "task_id" in t:
                        raw_tid = t["task_id"]
                        if isinstance(raw_tid, list):
                            raw_tid = (
                                raw_tid[0]
                                if raw_tid
                                else f"auto_{uuid.uuid4().hex[:6]}_{i}"
                            )
                        t["task_id"] = clean_str(str(raw_tid))
                    else:
                        t["task_id"] = f"auto_{uuid.uuid4().hex[:6]}_{i}"

                    if "agent_type" in t:
                        t["agent_type"] = clean_str(t["agent_type"]).lower()
                        if t["agent_type"] not in allowed_agents:
                            logger.warning(
                                f"Unknown agent type '{t['agent_type']}' → mapping to 'backend'"
                            )
                            t["agent_type"] = "backend"
                    else:
                        t["agent_type"] = "backend"

                    if "type" not in t or not t["type"]:
                        type_map = {
                            "backend": "implement_api",
                            "frontend": "create_ui",
                            "database": "design_schema",
                            "devops": "create_docker",
                            "researcher": "research_tech_stack",
                            "architect": "design_architecture",
                            "testing": "write_tests",
                            "qa": "validate_project",
                        }
                        t["type"] = type_map.get(t["agent_type"], "generic_task")

                    self._ensure_metadata_dict(t)

                    if "depends_on" not in t:
                        t["depends_on"] = []
                    elif isinstance(t["depends_on"], str):
                        t["depends_on"] = [t["depends_on"]] if t["depends_on"] else []

                    cleaned_tasks.append(t)

                logger.info(
                    f"cleaned_tasks count: {len(cleaned_tasks)} da {len(tasks)} raw"
                )
                return cleaned_tasks
            else:
                logger.warning(
                    f"LLM did not return a list of tasks (type: {type(tasks)})"
                )
                return []
        except Exception as e:
            logger.error(f"Error in LLM task decomposition: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Hardcoded decomposition fallback
    # ─────────────────────────────────────────────────────────────────────────

    def _decompose_project(self, spec: Dict) -> List[Dict]:
        tasks = []

        if spec.get("backend", True):
            tasks.append(
                {
                    "task_id": f"backend_api_{uuid.uuid4().hex[:8]}",
                    "type": "implement_api",
                    "agent_type": "backend",
                    "description": "Implement REST API with FastAPI",
                    "priority": 1,
                    "metadata": {},
                }
            )
            tasks.append(
                {
                    "task_id": f"backend_auth_{uuid.uuid4().hex[:8]}",
                    "type": "implement_auth",
                    "agent_type": "backend",
                    "description": "Implement JWT authentication",
                    "priority": 1,
                    "metadata": {},
                }
            )
            tasks.append(
                {
                    "task_id": f"backend_tests_{uuid.uuid4().hex[:8]}",
                    "type": "write_tests",
                    "agent_type": "testing",
                    "description": "Write backend unit tests",
                    "priority": 2,
                    "metadata": {"test_type": "unit", "target": "backend"},
                }
            )

        if spec.get("frontend", True):
            tasks.append(
                {
                    "task_id": f"frontend_ui_{uuid.uuid4().hex[:8]}",
                    "type": "create_ui",
                    "agent_type": "frontend",
                    "description": "Create React UI components",
                    "priority": 2,
                    "metadata": {},
                }
            )
            tasks.append(
                {
                    "task_id": f"frontend_api_integration_{uuid.uuid4().hex[:8]}",
                    "type": "integrate_api",
                    "agent_type": "frontend",
                    "description": "Integrate frontend with backend API",
                    "priority": 3,
                    "metadata": {},
                }
            )
            tasks.append(
                {
                    "task_id": f"frontend_tests_{uuid.uuid4().hex[:8]}",
                    "type": "write_tests",
                    "agent_type": "testing",
                    "description": "Write frontend unit tests",
                    "priority": 3,
                    "metadata": {"test_type": "unit", "target": "frontend"},
                }
            )

        if spec.get("database", True):
            tasks.append(
                {
                    "task_id": f"db_schema_{uuid.uuid4().hex[:8]}",
                    "type": "design_schema",
                    "agent_type": "database",
                    "description": "Design database schema",
                    "priority": 1,
                    "metadata": {},
                }
            )
            tasks.append(
                {
                    "task_id": f"db_migrations_{uuid.uuid4().hex[:8]}",
                    "type": "create_migrations",
                    "agent_type": "database",
                    "description": "Create database migrations",
                    "priority": 1,
                    "metadata": {},
                }
            )

        tasks.append(
            {
                "task_id": f"devops_docker_{uuid.uuid4().hex[:8]}",
                "type": "create_docker",
                "agent_type": "devops",
                "description": "Create Docker configuration",
                "priority": 4,
                "metadata": {},
            }
        )
        tasks.append(
            {
                "task_id": f"devops_ci_{uuid.uuid4().hex[:8]}",
                "type": "setup_ci",
                "agent_type": "devops",
                "description": "Setup CI/CD pipeline",
                "priority": 4,
                "metadata": {},
            }
        )
        tasks.append(
            {
                "task_id": f"qa_e2e_{uuid.uuid4().hex[:8]}",
                "type": "write_e2e_tests",
                "agent_type": "qa",
                "description": "Write end-to-end tests",
                "priority": 5,
                "metadata": {},
            }
        )
        tasks.append(
            {
                "task_id": f"qa_validation_{uuid.uuid4().hex[:8]}",
                "type": "validate_project",
                "agent_type": "qa",
                "description": "Validate entire project",
                "priority": 6,
                "metadata": {},
            }
        )

        return tasks

    # ─────────────────────────────────────────────────────────────────────────
    # Dependencies
    # ─────────────────────────────────────────────────────────────────────────

    async def _calculate_dependencies(self, tasks: List[Dict]):
        """Calcola dipendenze e rimuove quelle verso task inesistenti."""
        all_known_tasks = {**self.all_tasks}
        for t in tasks:
            all_known_tasks[t["task_id"]] = t

        for task in tasks:
            task_id = task["task_id"]

            if isinstance(task_id, list):
                task_id = task_id[0] if task_id else f"auto_{uuid.uuid4().hex[:6]}"
                task["task_id"] = task_id

            task["task_id"] = str(task_id).strip().strip('"').strip("'")
            task_id = task["task_id"]

            self.task_dependencies[task_id] = task.get("depends_on", [])

            if not self.task_dependencies[task_id]:
                if task["agent_type"] in ["backend", "frontend", "database"]:
                    arch_tasks = [
                        t["task_id"] for t in tasks if t["agent_type"] == "architect"
                    ]
                    if not arch_tasks:
                        arch_tasks = [
                            tid
                            for tid, td in self.all_tasks.items()
                            if td["agent_type"] == "architect"
                        ]
                    self.task_dependencies[task_id].extend(arch_tasks)

                if task["agent_type"] == "frontend":
                    backend_tasks = [
                        t["task_id"] for t in tasks if t["agent_type"] == "backend"
                    ]
                    backend_testing = [
                        t["task_id"]
                        for t in tasks
                        if t["agent_type"] == "testing"
                        and t.get("metadata", {}).get("target") == "backend"
                    ]
                    if not backend_tasks:
                        backend_tasks = [
                            tid
                            for tid, td in self.all_tasks.items()
                            if td["agent_type"] == "backend"
                        ]
                    if not backend_testing:
                        backend_testing = [
                            tid
                            for tid, td in self.all_tasks.items()
                            if td["agent_type"] == "testing"
                            and td.get("metadata", {}).get("target") == "backend"
                        ]
                    self.task_dependencies[task_id].extend(backend_tasks)
                    self.task_dependencies[task_id].extend(backend_testing)

                if task["agent_type"] == "backend":
                    db_tasks = [
                        t["task_id"] for t in tasks if t["agent_type"] == "database"
                    ]
                    if not db_tasks:
                        db_tasks = [
                            tid
                            for tid, td in self.all_tasks.items()
                            if td["agent_type"] == "database"
                        ]
                    self.task_dependencies[task_id].extend(db_tasks)

                if task["agent_type"] == "testing":
                    target = task.get("metadata", {}).get("target", "backend")
                    target_tasks = [
                        t["task_id"]
                        for t in tasks
                        if t["agent_type"] == target
                        and t["type"] != "research_tech_stack"
                    ]
                    if not target_tasks:
                        target_tasks = [
                            tid
                            for tid, td in self.all_tasks.items()
                            if td["agent_type"] == target
                        ]
                    self.task_dependencies[task_id].extend(target_tasks)

                if task["agent_type"] == "qa":
                    impl_tasks = [
                        t["task_id"]
                        for t in tasks
                        if t["agent_type"] in ["backend", "frontend"]
                        and t["type"] != "research_tech_stack"
                    ]
                    if not impl_tasks:
                        impl_tasks = [
                            tid
                            for tid, td in self.all_tasks.items()
                            if td["agent_type"] in ["backend", "frontend"]
                        ]
                    self.task_dependencies[task_id].extend(impl_tasks)

        # Rimuovi dep fantasma E dipendenze circolari su se stesso
        for tid in list(self.task_dependencies.keys()):
            original_deps = self.task_dependencies[tid]
            # 1. rimuovi dep verso task inesistenti
            valid_deps = [d for d in original_deps if d in all_known_tasks]
            removed_ghost = set(original_deps) - set(valid_deps)
            if removed_ghost:
                logger.warning(
                    f"⚠️ Task {tid}: rimosse dipendenze NON TROVATE: {removed_ghost}"
                )
            # 2. rimuovi dipendenza circolare su se stesso
            if tid in valid_deps:
                logger.warning(
                    f"⚠️ Task {tid}: rimosse dipendenze CIRCOLARI su se stesso"
                )
                valid_deps = [d for d in valid_deps if d != tid]
            self.task_dependencies[tid] = valid_deps

        logger.info(f"✓ Dipendenze calcolate per {len(tasks)} task")

    # ─────────────────────────────────────────────────────────────────────────
    # Task completion handling
    # ─────────────────────────────────────────────────────────────────────────

    QC_EXEMPT_TYPES = {
        "research_tech_stack",
        "search_docs",
        "design_architecture",
        "review_task",
        "speaking_commit",
        "create_project",
        "evolve_project",
    }

    async def _handle_task_completed(self, message: Dict):
        task_id = message.get("task_id")
        agent_id = message.get("agent_id")
        result = message.get("result", {})

        if task_id not in self.all_tasks:
            return

        task_obj = self.all_tasks[task_id]
        self._ensure_metadata_dict(task_obj)
        task_type = task_obj["type"]

        # 1. Task di REVISIONE
        if task_type == "review_task":
            target_id = task_obj.get("metadata", {}).get("target_task_id")
            approved = result.get("approved", False)

            task_obj["status"] = "completed"
            await self.memory.update_task_status(task_id, "completed")

            if target_id in self.pending_reviews:
                review_data = self.pending_reviews[target_id]
                review_data["reviewers"].append(agent_id)

                if approved:
                    review_data["approvals"] += 1
                    logger.info(
                        f"✓ Review APPROVATA ({review_data['approvals']}/{self.REQUIRED_REVIEWS}) per task {target_id}"
                    )
                else:
                    review_data["rejections"].append(
                        result.get("comments", "No comments")
                    )
                    logger.warning(f"✗ Review RIFIUTATA per task {target_id}")

                if len(review_data["reviewers"]) >= self.REQUIRED_REVIEWS:
                    if review_data["approvals"] >= self.REQUIRED_REVIEWS:
                        logger.info(
                            f"🚀 Task {target_id} superato revisioni! Avvio commit..."
                        )
                        files = self.pending_reviews.pop(target_id, {}).get(
                            "files", review_data["files"]
                        )
                        await self._initiate_speaking_commit(target_id, files)
                    else:
                        logger.error(f"⚠ Task {target_id} BOCCIATO nelle revisioni.")
                        self.pending_reviews.pop(target_id, None)
                        await self._handle_review_rejection(
                            target_id, review_data["rejections"]
                        )

            await self._publish_ready_tasks()
            return

        # 2. Task di COMMIT
        if task_type == "speaking_commit":
            task_obj["status"] = "completed"
            await self.memory.update_task_status(task_id, "completed")

            target_id = self.pending_commits.get(task_id)
            if target_id and target_id in self.all_tasks:
                self.all_tasks[target_id]["status"] = "completed"
                await self.memory.update_task_status(target_id, "completed")
                logger.info(f"🏁 Task {target_id} COMPLETATO E COMMITTATO!")

            await asyncio.sleep(0.3)
            await self._publish_ready_tasks()
            return

        # 3. Task QC-esenti
        if task_type in self.QC_EXEMPT_TYPES:
            task_obj["status"] = "completed"
            await self.memory.update_task_status(task_id, "completed")
            logger.info(f"Task completato (QC esente / {task_type}): {task_id}")
            await self._publish_ready_tasks()
            return

        # 4. Task di implementazione
        is_mvp = task_obj.get("metadata", {}).get("mvp", False)

        if is_mvp:
            logger.info(f"⚡ MVP MODE: Salto REVISIONE per task {task_id}.")
            task_obj["status"] = "completed"
            await self.memory.update_task_status(task_id, "completed")
            await self._publish_ready_tasks()
            return

        logger.info(
            f"🔍 Task {task_id} completato. Avvio REVISIONE (Richiesti {self.REQUIRED_REVIEWS} pareri)..."
        )
        task_obj["status"] = "under_review"
        await self.memory.update_task_status(task_id, "under_review")

        files_created = result.get("files_created", [])
        self.pending_reviews[task_id] = {
            "approvals": 0,
            "reviewers": [],
            "rejections": [],
            "files": files_created,
        }

        for i in range(self.REQUIRED_REVIEWS):
            review_agent_id = f"reviewer_{i + 1:03d}"
            review_task_id = f"review_{task_id}_{i + 1}"
            review_task = {
                "task_id": review_task_id,
                "type": "review_task",
                "agent_type": "reviewer",
                "assigned_to": review_agent_id,
                "description": f"Review execution of task {task_id}: {task_obj.get('description')}",
                "priority": task_obj.get("priority", 1) + 1,
                "metadata": {
                    "target_task_id": task_id,
                    "files": files_created,
                    "reviewer_index": i + 1,
                },
            }
            self.all_tasks[review_task_id] = {**review_task, "status": "pending"}
            await self.memory.create_task(
                task_id=review_task_id,
                task_type="review_task",
                agent_type="reviewer",
                description=review_task["description"],
                project_id=self.project_id,
                priority=review_task["priority"],
                metadata=review_task["metadata"],
            )
            await self.broker.publish(
                get_topics(self.project_id)["TASKS_NEW"], review_task
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Publish ready tasks
    # FIX PRINCIPALE: dipendenza "failed" = soddisfatta (non blocca a valle)
    # ─────────────────────────────────────────────────────────────────────────

    DEPS_SATISFIED_STATUSES = {"completed", "failed"}

    async def _publish_ready_tasks(self):
        logger.info("Verifico task pronti per la pubblicazione...")
        published_count = 0

        for tid, tdata in list(self.all_tasks.items()):
            self._ensure_metadata_dict(tdata)
            metadata = tdata["metadata"]
            status = tdata.get("status")

            if status not in ("pending", "rework"):
                continue

            if metadata.get("published", False):
                continue

            deps = self.task_dependencies.get(tid, [])

            # FIX: "failed" conta come soddisfatto — un task upstream fallito
            # non deve bloccare per sempre i task a valle.
            deps_status = {
                dtid: self.all_tasks[dtid].get("status", "unknown")
                for dtid in deps
                if dtid in self.all_tasks
            }

            deps_met = all(
                s in self.DEPS_SATISFIED_STATUSES for s in deps_status.values()
            )

            if not deps_met:
                not_done = {
                    d: s
                    for d, s in deps_status.items()
                    if s not in self.DEPS_SATISFIED_STATUSES
                }
                logger.info(
                    f"  ⏳ Task {tid} ({tdata.get('agent_type')}) in attesa di: {not_done}"
                )
                continue

            # FIX: log se alcune dipendenze erano fallite (info utile)
            failed_deps = [d for d, s in deps_status.items() if s == "failed"]
            if failed_deps:
                logger.warning(
                    f"  ⚠️ Task {tid} parte con dipendenze FALLITE: {failed_deps} — prosegue comunque"
                )

            logger.info(f"🚀 Task pronto: {tid} (Dipendenze OK)")

            tdata["metadata"]["published"] = True
            tdata["assigned_at"] = time.time()

            await self.broker.publish(get_topics(self.project_id)["TASKS_NEW"], tdata)
            published_count += 1
            logger.info(f"📤 Pubblicato task '{tid}' al broker ({tdata['agent_type']})")
            await asyncio.sleep(0.1)

        if published_count > 0:
            logger.info(f"✓ Pubblicati {published_count} nuovi task pronti.")

    # ─────────────────────────────────────────────────────────────────────────
    # Commit
    # ─────────────────────────────────────────────────────────────────────────

    async def _initiate_speaking_commit(self, target_id: str, files: List[str]):
        target_task = self.all_tasks.get(target_id, {})
        commit_task_id = f"commit_{target_id}"

        commit_task = {
            "task_id": commit_task_id,
            "type": "speaking_commit",
            "agent_type": "devops",
            "description": f"Generate speaking commit for {target_id}",
            "priority": 10,
            "metadata": {
                "description": target_task.get("description", ""),
                "files": files,
                "target_task_id": target_id,
            },
        }

        self.pending_commits[commit_task_id] = target_id
        self.all_tasks[commit_task_id] = {**commit_task, "status": "pending"}

        await self.memory.create_task(
            task_id=commit_task_id,
            task_type="speaking_commit",
            agent_type="devops",
            description=commit_task["description"],
            project_id=self.project_id,
            priority=10,
            metadata=commit_task["metadata"],
        )

        await self.broker.publish(get_topics(self.project_id)["TASKS_NEW"], commit_task)
        logger.info(f"📝 Task di commit creato per {target_id} → {commit_task_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # Review rejection
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_review_rejection(self, target_id: str, rejections: List[str]):
        task_obj = self.all_tasks.get(target_id)
        if not task_obj:
            return

        if "metadata" not in task_obj:
            task_obj["metadata"] = {}

        review_rejection_count = (
            task_obj["metadata"].get("review_rejection_count", 0) + 1
        )
        task_obj["metadata"]["review_rejection_count"] = review_rejection_count

        MAX_REVIEW_REJECTIONS = 5
        if review_rejection_count >= MAX_REVIEW_REJECTIONS:
            logger.error(
                f"❌ Task {target_id} rifiutato {review_rejection_count} volte. PERMANENTLY FAILED."
            )
            task_obj["status"] = "failed"
            await self.memory.update_task(
                target_id, {"status": "failed", "metadata": task_obj["metadata"]}
            )
            await self.broker.publish(
                get_topics(self.project_id)["TASKS_FAILED"],
                {
                    "task_id": target_id,
                    "agent_id": "orchestrator",
                    "error": f"Task rejected {review_rejection_count} times by reviewers",
                    "rejections": rejections,
                    "timestamp": time.time(),
                },
            )
            await self._propagate_failure(target_id)
            self.pending_reviews.pop(target_id, None)
            return

        feedback = "\n".join([f"Reviewer Rejection:\n{r}" for r in rejections])
        task_obj["metadata"]["last_error"] = (
            f"REJECTION FEEDBACK (Attempt {review_rejection_count}):\n{feedback}"
        )
        task_obj["metadata"]["is_retry"] = True
        task_obj["metadata"]["published"] = False
        task_obj["status"] = "rework"

        await self.memory.update_task(
            target_id, {"status": "rework", "metadata": task_obj["metadata"]}
        )
        await self.broker.publish(get_topics(self.project_id)["TASKS_NEW"], task_obj)

        logger.warning(
            f"🔄 Task {target_id} rispedito per FIX (Review rejection #{review_rejection_count})."
        )
        logger.warning(f"📝 FEEDBACK DETTAGLIATO PER {target_id}:\n{feedback}")
        self.pending_reviews.pop(target_id, None)

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_task_started(self, message: Dict):
        task_id = message.get("task_id")
        agent_id = message.get("agent_id")

        if task_id in self.all_tasks:
            tdata = self.all_tasks[task_id]
            if tdata["status"] in ["pending", "rework", "under_review", "failed"]:
                tdata["status"] = "in_progress"
                tdata["assigned_to"] = agent_id
                logger.info(f"📶 Task {task_id} INIZIATO da {agent_id}")

    async def _handle_task_failed(self, message: Dict):
        task_id = message.get("task_id")
        if task_id not in self.all_tasks:
            return

        task_obj = self.all_tasks[task_id]

        if task_obj.get("type") == "review_task":
            target_id = task_obj.get("metadata", {}).get("target_task_id")
            logger.warning(
                f"⚠ Review task {task_id} CRASHED for target {target_id}. Retrying..."
            )
            task_obj["status"] = "pending"
            if not task_obj.get("metadata"):
                task_obj["metadata"] = {}
            task_obj["metadata"]["published"] = False
            await self.memory.update_task(
                task_id, {"status": "pending", "metadata": task_obj["metadata"]}
            )
            await self.broker.publish(
                get_topics(self.project_id)["TASKS_NEW"], task_obj
            )
            return

        task_obj["status"] = "failed"
        await self.memory.update_task_status(task_id, "failed")
        logger.error(f"Task fallito: {task_id}")

        # FIX: pubblica i task a valle anche quando un dep fallisce —
        # _publish_ready_tasks ora tratta "failed" come soddisfatto
        await self._publish_ready_tasks()
        await self._propagate_failure(task_id)

    async def _propagate_failure(self, failed_task_id: str):
        logger.warning(f"Propagazione fallimento da {failed_task_id}...")
        dependents = [
            tid
            for tid, deps in self.task_dependencies.items()
            if failed_task_id in deps
        ]

        for dep_id in dependents:
            dep_task = self.all_tasks.get(dep_id)
            if dep_task and dep_task["status"] not in ["failed", "completed"]:
                # FIX: NON propaghiamo più il fallimento a cascata — lasciamo che
                # _publish_ready_tasks decida se il task può partire lo stesso.
                # Propaghiamo solo se TUTTE le dipendenze sono fallite.
                deps_of_dep = self.task_dependencies.get(dep_id, [])
                all_failed = all(
                    self.all_tasks.get(d, {}).get("status") == "failed"
                    for d in deps_of_dep
                    if d in self.all_tasks
                )
                if all_failed and deps_of_dep:
                    logger.error(
                        f"⚠️ Task {dep_id} BLOCCATO: tutte le dipendenze sono fallite."
                    )
                    dep_task["status"] = "failed"
                    dep_task["metadata"]["blocked_by"] = failed_task_id
                    await self.memory.update_task(
                        dep_id, {"status": "failed", "metadata": dep_task["metadata"]}
                    )
                    await self._propagate_failure(dep_id)
                else:
                    logger.info(
                        f"ℹ️ Task {dep_id} ha dep fallita ({failed_task_id}) ma altre ancora attive — aspetta _publish"
                    )

    async def _handle_heartbeat(self, message: Dict):
        agent_id = message.get("agent_id")
        if agent_id != self.agent_id:
            self.agents_status[agent_id] = message

    async def _handle_agent_idle(self, message: Dict):
        agent_id = message.get("agent_id")
        agent_type = message.get("agent_type") or (
            agent_id.split("_")[0] if agent_id and "_" in agent_id else None
        )

        if not agent_type:
            return

        logger.info(f"Agent {agent_id} ({agent_type}) è idle, cerco task da assegnare")

        ready_tasks = []
        for tid, tdata in list(self.all_tasks.items()):
            if (
                tdata.get("status") in ("pending", "rework")
                and tdata.get("agent_type") == agent_type
            ):
                deps = self.task_dependencies.get(tid, [])
                # FIX: "failed" conta come soddisfatto anche qui
                deps_met = all(
                    self.all_tasks[dtid].get("status") in self.DEPS_SATISFIED_STATUSES
                    for dtid in deps
                    if dtid in self.all_tasks
                )
                if deps_met:
                    ready_tasks.append(tdata)

        if ready_tasks:
            ready_tasks.sort(key=lambda x: x.get("priority", 1))
            task_to_assign = ready_tasks[0]

            task_to_assign["assigned_to"] = agent_id
            task_to_assign["status"] = "assigned"
            task_to_assign["assigned_at"] = time.time()

            await self.memory.update_task_status(
                task_to_assign["task_id"], "assigned", assigned_to=agent_id
            )
            await self.broker.publish(
                get_topics(self.project_id)["TASKS_ASSIGNED"],
                {**task_to_assign, "assigned_to": agent_id},
            )
            logger.info(
                f"✓ Assegnato task {task_to_assign['task_id']} a agente idle {agent_id}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Monitor
    # ─────────────────────────────────────────────────────────────────────────

    async def _monitor_progress(self):
        if getattr(self, "_monitor_running", False):
            logger.warning("⚠️ _monitor_progress già in esecuzione, skip.")
            return
        self._monitor_running = True

        logger.info("🔍 Avvio monitoraggio progresso...")
        # Attesa iniziale per permettere a tutti gli agenti di iscriversi ai topic MQTT/Kafka
        await asyncio.sleep(5)

        last_reclaim = time.time()
        last_publish = time.time()

        try:
            while self.running:
                now = time.time()

                if now - last_reclaim > 30:
                    await self._reclaim_orphaned_tasks()
                    last_reclaim = now

                if now - last_publish > 10:
                    await self._publish_ready_tasks()
                    last_publish = now

                completed = sum(
                    1 for t in self.all_tasks.values() if t.get("status") == "completed"
                )
                failed = sum(
                    1 for t in self.all_tasks.values() if t.get("status") == "failed"
                )
                total = len(self.all_tasks)

                if total > 0:
                    logger.info(f"Progress: {completed}/{total} tasks completed")
                    if failed > 0:
                        logger.info(f"Progress: {failed} tasks failed/blocked")

                    if (completed + failed) < total:
                        incomplete = [
                            tid
                            for tid, tdata in self.all_tasks.items()
                            if tdata.get("status") not in ["completed", "failed"]
                        ]
                        if len(incomplete) <= 5:
                            logger.info(f"Tasks rimanenti: {incomplete}")
                        else:
                            logger.info(f"Tasks rimanenti: {len(incomplete)}")

                if total > 0 and (completed + failed) == total:
                    if failed > 0:
                        logger.warning(
                            f"⚠️ Orchestrazione terminata con {failed} fallimenti."
                        )
                    else:
                        logger.info("✓ Tutti i task completati!")

                    # Permette allo Scrum Master di eseguire Retrospective e Refinement finali prima dello spegnimento
                    logger.info(
                        "Segnalo al Scrum Master di finalizzare le cerimonie..."
                    )
                    await self.broker.publish(
                        get_topics(self.project_id)["SCRUM_CEREMONY"],
                        {
                            "type": "project_completed",
                            "project_id": self.project_id,
                        },
                    )

                    logger.info(
                        "Attesa di 300s per permettere al Scrum Master di completare (Retro, Refinement, Releases)..."
                    )
                    await asyncio.sleep(300)

                    # ── Post-ceremony secondary sync ──────────────────────────
                    # Lo ScrumMaster ha potuto creare nuovi task (backlog_item,
                    # scrum_improvement) nel DB durante le cerimonie.
                    # Li sincronizziamo ora e li distribuiamo prima di chiudere.
                    logger.info("🔄 Post-ceremony sync: carico nuovi task da DB...")
                    await self._sync_external_tasks()
                    await self._publish_ready_tasks()

                    # Ri-verifica: ci sono nuovi task ancora in attesa?
                    new_pending = sum(
                        1
                        for t in self.all_tasks.values()
                        if t.get("status")
                        in (
                            "pending",
                            "rework",
                            "in_progress",
                            "assigned",
                            "under_review",
                        )
                    )

                    if new_pending > 0:
                        logger.info(
                            f"🆕 {new_pending} nuovi task dal ScrumMaster rilevati — "
                            f"continuo il monitoraggio..."
                        )
                        # Resetta i contatori locali e continua il loop normale
                        last_reclaim = time.time()
                        last_publish = time.time()
                        await asyncio.sleep(5)
                        continue

                    logger.info(
                        "✅ Nessun nuovo task pendente. Sistema pronto per la chiusura."
                    )
                    self.completion_event.set()
                    break

                await self._sync_external_tasks()
                await asyncio.sleep(5)
        finally:
            self._monitor_running = False

    async def _sync_external_tasks(self):
        try:
            db_tasks = await self.memory.get_all_tasks(self.project_id)
            new_sync_count = 0
            update_sync_count = 0

            for task_obj in db_tasks:
                tid = task_obj["task_id"]
                if tid not in self.all_tasks:
                    self.all_tasks[tid] = task_obj
                    if tid not in self.task_dependencies:
                        self.task_dependencies[tid] = []
                    new_sync_count += 1
                else:
                    local = self.all_tasks[tid]
                    db_status = task_obj.get("status", local.get("status"))
                    changed = False

                    if local["status"] != db_status:
                        logger.info(
                            f"🔄 Sincronizzato stato task {tid}: {local['status']} -> {db_status}"
                        )
                        local["status"] = db_status
                        changed = True

                    # FIX: sincronizza anche metadata e assigned_to
                    local["metadata"] = task_obj.get(
                        "metadata", local.get("metadata", {})
                    )
                    db_assigned = task_obj.get("assigned_to")
                    if db_assigned and local.get("assigned_to") != db_assigned:
                        local["assigned_to"] = db_assigned
                        changed = True

                    if changed:
                        update_sync_count += 1

            if new_sync_count > 0 or update_sync_count > 0:
                logger.info(
                    f"✓ Sincronizzati {new_sync_count} nuovi e {update_sync_count} aggiornati task."
                )
                await self._publish_ready_tasks()
        except Exception as e:
            logger.error(f"Error syncing external tasks: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Reclaim orphaned tasks
    # FIX: timeout differenziato per tipo task
    # ─────────────────────────────────────────────────────────────────────────

    # Task "pesanti" che hanno bisogno di più tempo prima di essere reclamati
    _LONG_RUNNING_TYPES = {
        "speaking_commit",
        "write_tests",
        "write_e2e_tests",
        "implement_api",
        "implement_auth",
        "create_ui",
        "integrate_api",
        "design_schema",
        "create_migrations",
        "create_docker",
        "setup_ci",
    }

    async def _reclaim_orphaned_tasks(self):
        logger.info("🕵️ Controllo task orfani o bloccati...")
        now = time.time()

        for tid, tdata in list(self.all_tasks.items()):
            status = tdata.get("status")

            # FIX: non toccare mai task già completati/in review/failed
            if status not in ["in_progress", "assigned"]:
                continue

            agent_id = tdata.get("assigned_to")

            if not agent_id:
                logger.warning(
                    f"Reclaiming task {tid}: no agent assigned despite status {status}"
                )
                tdata["status"] = "pending"
                await self.memory.update_task_status(tid, "pending")
                if tdata.get("metadata"):
                    tdata["metadata"]["published"] = False
                continue

            # FIX: prima di reclamare, rileggi lo stato dal DB —
            # potrebbe essere già completed/under_review ma non ancora
            # propagato in memoria locale.
            try:
                db_task = await self.memory.get_task(tid)
                if db_task:
                    db_status = db_task.get("status", status)
                    if db_status != status:
                        logger.info(
                            f"🔄 Reclaim skip: task {tid} DB status={db_status} vs local={status}, aggiorno locale"
                        )
                        tdata["status"] = db_status
                        tdata["metadata"] = db_task.get(
                            "metadata", tdata.get("metadata", {})
                        )
                        # Se nel DB è completed/under_review, pubblica i task a valle
                        if db_status in ("completed", "under_review", "failed"):
                            await self._publish_ready_tasks()
                        continue
            except Exception as e:
                logger.warning(
                    f"Impossibile leggere task {tid} dal DB durante reclaim: {e}"
                )

            agent_status = self.agents_status.get(agent_id)
            reclaim = False
            reason = ""

            if not agent_status:
                reclaim = True
                reason = f"agent {agent_id} unknown or disconnected"
            else:
                last_heartbeat = agent_status.get("timestamp", 0)
                if now - last_heartbeat > 120:
                    reclaim = True
                    reason = f"agent {agent_id} heartbeat timeout"
                elif agent_status.get("status") == "idle" and status == "in_progress":
                    reclaim = True
                    reason = (
                        f"agent {agent_id} reports idle but task {tid} is in_progress"
                    )

            assigned_at = tdata.get("assigned_at", 0)

            # Timeout differenziato per tipo task
            task_type = tdata.get("type", "")
            min_grace = 300 if task_type in self._LONG_RUNNING_TYPES else 120
            if now - assigned_at < min_grace:
                continue

            if reclaim:
                logger.warning(f"♻️ RECUPERO TASK {tid}: {reason}. Riportato a PENDING.")
                tdata["status"] = "pending"
                tdata["assigned_to"] = None
                if not tdata.get("metadata"):
                    tdata["metadata"] = {}
                tdata["metadata"]["published"] = False
                await self.memory.update_task(
                    tid,
                    {
                        "status": "pending",
                        "metadata": tdata["metadata"],
                        "assigned_to": None,
                    },
                )
                await self._publish_ready_tasks()

    # ─────────────────────────────────────────────────────────────────────────
    # Resume
    # ─────────────────────────────────────────────────────────────────────────

    async def resume_tasks(self) -> int:
        logger.info(f"🔄 Ripristino stato progetto '{self.project_id}' dal database...")

        all_project_tasks = await self.memory.get_all_tasks(project_id=self.project_id)

        if not all_project_tasks:
            logger.info("Nessun task trovato in precedenza per questo progetto.")
            return 0

        logger.info(
            f"📊 Trovati {len(all_project_tasks)} task totali. Ricostruzione grafo..."
        )

        for task_obj in all_project_tasks:
            self._ensure_metadata_dict(task_obj)
            task_id = task_obj["task_id"]
            self.all_tasks[task_id] = task_obj
            if task_obj["status"] == "in_progress":
                self.all_tasks[task_id]["status"] = "pending"
                if not self.all_tasks[task_id].get("metadata"):
                    self.all_tasks[task_id]["metadata"] = {}
                self.all_tasks[task_id]["metadata"]["published"] = False
                await self.memory.update_task_status(task_id, "pending")
            if self.all_tasks[task_id].get("metadata") is None:
                self.all_tasks[task_id]["metadata"] = {}

        await self._calculate_dependencies(list(self.all_tasks.values()))

        for t_id, t_obj in list(self.all_tasks.items()):
            if t_obj["status"] == "under_review":
                r_tasks = [
                    rt
                    for rt in self.all_tasks.values()
                    if rt.get("type") == "review_task"
                    and rt.get("metadata", {}).get("target_task_id") == t_id
                ]
                if r_tasks:
                    files_created = r_tasks[0].get("metadata", {}).get("files", [])
                    self.pending_reviews[t_id] = {
                        "approvals": 0,
                        "reviewers": [],
                        "rejections": [],
                        "files": files_created,
                    }
                    for rt in r_tasks:
                        rt_id = rt["task_id"]
                        if rt["status"] != "pending":
                            rt["status"] = "pending"
                            if not rt.get("metadata"):
                                rt["metadata"] = {}
                            rt["metadata"]["published"] = False
                            await self.memory.update_task_status(rt_id, "pending")
            elif t_obj["type"] == "speaking_commit":
                target_id = t_obj.get("metadata", {}).get("target_task_id")
                if target_id:
                    self.pending_commits[t_id] = target_id

        pending_count = sum(
            1
            for t in self.all_tasks.values()
            if t["status"] in ["pending", "rework", "failed", "under_review"]
        )

        if pending_count > 0:
            logger.info(f"🚀 Ripresa esecuzione: {pending_count} task rimanenti.")
            await self._publish_ready_tasks()
        else:
            logger.info("✅ Tutti i task risultano già completati nel database.")
            self.completion_event.set()

        asyncio.create_task(self._monitor_progress())
        return pending_count

#!/usr/bin/env python3
"""
Memory System - Simplified
"""

import sqlite3
import logging
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

from config import DB_PATH, MEMORY_DIR

logger = logging.getLogger(__name__)


class MemorySystem:
    """Sistema di memoria persistente"""

    def __init__(self):
        self.db_path = DB_PATH
        self.memory_dir = MEMORY_DIR
        self.memory_dir.mkdir(exist_ok=True, parents=True)

    async def initialize(self):
        """Inizializza il database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Project memory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                project_id TEXT,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                description TEXT,
                file_modified TEXT,
                commit_hash TEXT,
                metadata TEXT
            )
        """)

        # 2. Check for legacy 'tasks' table and migrate if 'agent' exists
        cursor.execute("PRAGMA table_info(tasks)")
        columns = {column[1]: column for column in cursor.fetchall()}

        if columns and "agent" in columns:
            logger.warning(
                "Rilevata colonna legacy 'agent' nella tabella 'tasks'. Migrazione in corso..."
            )
            cursor.execute("ALTER TABLE tasks RENAME TO tasks_old")
            cursor.execute("""
                CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    type TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    description TEXT,
                    priority INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT,
                    depends_on TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            # Trasferisce i dati provando a mappare agent -> agent_type
            cursor.execute("""
                INSERT INTO tasks (task_id, type, agent_type, description, priority, status, metadata, created_at, completed_at)
                SELECT task_id, type, agent, description, priority, status, metadata, created_at, completed_at FROM tasks_old
            """)
            cursor.execute("DROP TABLE tasks_old")
            logger.info("✓ Migrazione tabella 'tasks' completata")
        else:
            # Crea la tabella se non esiste con il nuovo schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    type TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    description TEXT,
                    priority INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT,
                    depends_on TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

        # Check for missing columns in existing tables (project_id migration)
        for table in ["tasks", "project_memory"]:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [c[1] for c in cursor.fetchall()]
            if "project_id" not in cols:
                logger.info(f"Aggiunta colonna 'project_id' a tabella {table}")
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN project_id TEXT DEFAULT 'default_project'"
                )

        # Check for missing columns in existing (but not necessarily legacy) 'tasks' table
        cursor.execute("PRAGMA table_info(tasks)")
        current_columns = [column[1] for column in cursor.fetchall()]

        needed_columns = {
            "type": "TEXT NOT NULL DEFAULT 'generic'",
            "agent_type": "TEXT NOT NULL DEFAULT 'unknown'",
            "assigned_to": "TEXT",
            "depends_on": "TEXT",
            "metadata": "TEXT",
        }

        for col, col_def in needed_columns.items():
            if col not in current_columns:
                logger.info(f"Aggiunta colonna '{col}' alla tabella 'tasks'")
                cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col} {col_def}")

        # Bugs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bugs (
                bug_id TEXT PRIMARY KEY,
                severity TEXT,
                description TEXT,
                reporter_agent TEXT,
                assigned_agent TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)

        # Architecture decisions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS architecture_decisions (
                decision_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                rationale TEXT,
                decided_by TEXT,
                alternatives TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Scrum - Sprints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sprints (
                sprint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                sprint_number INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active', -- 'active', 'completed'
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Migration for sprint_number
        cursor.execute("PRAGMA table_info(sprints)")
        sprint_cols = [c[1] for c in cursor.fetchall()]
        if "sprint_number" not in sprint_cols:
            logger.info("Aggiunta colonna 'sprint_number' alla tabella 'sprints'")
            cursor.execute(
                "ALTER TABLE sprints ADD COLUMN sprint_number INTEGER DEFAULT 1"
            )

        # Scrum - Retrospectives
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS retrospectives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sprint_id INTEGER NOT NULL,
                agent_type TEXT NOT NULL,
                feedback TEXT,
                sentiment TEXT, -- 'positive', 'neutral', 'negative'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sprint_id) REFERENCES sprints(sprint_id)
            )
        """)

        # Scrum - Releases (ogni 8 sprint)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS releases (
                release_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                version TEXT NOT NULL,          -- es. v1.0, v1.1
                sprint_start INTEGER NOT NULL,  -- sprint_id di inizio
                sprint_end INTEGER NOT NULL,    -- sprint_id di fine
                summary TEXT,                  -- release notes generate dall'LLM
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Scrum - Backlog Refinement Proposals
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backlog_refinement_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                sprint_id INTEGER NOT NULL,
                proposed_by TEXT NOT NULL,      -- agent_type
                description TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                accepted INTEGER DEFAULT 0,     -- 0=pending,1=accepted,2=rejected
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sprint_id) REFERENCES sprints(sprint_id)
            )
        """)

        # Sprint counter (per tracking release cycle)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sprint_counters (
                project_id TEXT PRIMARY KEY,
                total_sprints_completed INTEGER DEFAULT 0,
                current_release_sprint_start INTEGER DEFAULT 1
            )
        """)

        # Agent Prompts (NEW)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_prompts (
                agent_type TEXT PRIMARY KEY,
                system_prompt TEXT NOT NULL,
                task_templates TEXT, -- JSON dictionary of task_type -> template
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Domain Knowledge
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_domain_knowledge (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                domain TEXT,
                topic TEXT,
                synthesized_summary TEXT NOT NULL,
                key_points TEXT,
                contradictions TEXT,
                source_count INTEGER DEFAULT 1,
                confidence_score REAL DEFAULT 0.5,
                embedding TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Token Usage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                agent_id TEXT NOT NULL,
                project_id TEXT,
                model TEXT,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                is_toon BOOLEAN DEFAULT 0,
                saved_tokens INTEGER DEFAULT 0
            )
        """)

        # Migration for existing token_usage table
        cursor.execute("PRAGMA table_info(token_usage)")
        token_usage_cols = [c[1] for c in cursor.fetchall()]
        if "is_toon" not in token_usage_cols:
            logger.info("Aggiunta colonna 'is_toon' a tabella token_usage")
            cursor.execute(
                "ALTER TABLE token_usage ADD COLUMN is_toon BOOLEAN DEFAULT 0"
            )
        if "saved_tokens" not in token_usage_cols:
            logger.info("Aggiunta colonna 'saved_tokens' a tabella token_usage")
            cursor.execute(
                "ALTER TABLE token_usage ADD COLUMN saved_tokens INTEGER DEFAULT 0"
            )

        # Agent Documents (RAG/Knowledge)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_documents (
                id TEXT PRIMARY KEY,
                agent_type TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Config (generic key-value store for versioning, flags, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

        logger.info(f"Memory system initialized at {self.db_path}")

    async def log_action(
        self,
        agent: str,
        action: str,
        description: str,
        project_id: str = "default_project",
        file_modified: str = None,
        commit_hash: str = None,
        metadata: Dict = None,
    ):
        """Log un'azione nel database con project_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO project_memory 
            (timestamp, project_id, agent, action, description, file_modified, commit_hash, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.now().isoformat(),
                project_id,
                agent,
                action,
                description,
                file_modified,
                commit_hash,
                json.dumps(metadata) if metadata else None,
            ),
        )

        conn.commit()
        conn.close()

    async def create_task(
        self,
        task_id: str,
        task_type: str,
        agent_type: str,
        description: str,
        project_id: str = "default_project",
        priority: int = 1,
        metadata: Dict = None,
        depends_on: List[str] = None,
    ):
        """Crea o aggiorna un task nel database con project_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO tasks (task_id, project_id, type, agent_type, description, priority, metadata, depends_on, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                project_id,
                task_type,
                agent_type,
                description,
                priority,
                json.dumps(metadata) if metadata else None,
                json.dumps(depends_on) if depends_on else None,
                "pending",
            ),
        )

        conn.commit()
        conn.close()

    async def get_task(self, task_id: str) -> Optional[Dict]:
        """Ottieni un singolo task per ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            task = dict(row)
            if task.get("metadata"):
                try:
                    task["metadata"] = json.loads(task["metadata"])
                except Exception:
                    task["metadata"] = {}
            return task
        return None

    async def update_task_status(
        self, task_id: str, status: str, assigned_to: str = None
    ):
        """Aggiorna lo stato di un task con supporto opzionale per l'assegnatario"""
        updates = {"status": status}
        if status in ["completed", "failed"]:
            updates["completed_at"] = datetime.now().isoformat()
        if assigned_to:
            updates["assigned_to"] = assigned_to

        await self.update_task(task_id, updates)

    async def update_task(self, task_id: str, updates: Dict[str, Any]):
        """Aggiorna campi arbitrari di un task nel database"""
        if not updates:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Prepare parts of the query
        fields = []
        values = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            if key == "metadata" and isinstance(value, dict):
                values.append(json.dumps(value))
            else:
                values.append(value)

        values.append(task_id)
        query = f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?"

        try:
            cursor.execute(query, tuple(values))
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
        finally:
            conn.close()

    async def get_all_tasks(self, project_id: str = None) -> List[Dict]:
        """Ottieni tutti i task, opzionalmente filtrati per progetto"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if project_id:
            cursor.execute(
                """
                SELECT * FROM tasks WHERE project_id = ?
                ORDER BY created_at ASC
            """,
                (project_id,),
            )
        else:
            cursor.execute("""
                SELECT * FROM tasks 
                ORDER BY created_at ASC
            """)

        rows = cursor.fetchall()
        tasks = []
        for row in rows:
            task = dict(row)
            if task.get("metadata"):
                try:
                    task["metadata"] = json.loads(task["metadata"])
                except Exception:
                    task["metadata"] = {}
            if task.get("depends_on"):
                try:
                    task["depends_on"] = json.loads(task["depends_on"])
                except Exception:
                    task["depends_on"] = []
            else:
                task["depends_on"] = []
            tasks.append(task)

        conn.close()
        return tasks

    async def has_tasks(self, project_id: str) -> bool:
        """Verifica se esistono task per un dato progetto"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id = ?", (project_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    async def get_pending_tasks(self, project_id: str = None) -> List[Dict]:
        """Ottieni task non completati (pending o failed)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if project_id:
            cursor.execute(
                """
                SELECT * FROM tasks WHERE status IN ('pending', 'failed') AND project_id = ?
                ORDER BY priority DESC, created_at ASC
            """,
                (project_id,),
            )
        else:
            cursor.execute("""
                SELECT * FROM tasks WHERE status IN ('pending', 'failed')
                ORDER BY priority DESC, created_at ASC
            """)

        rows = cursor.fetchall()
        tasks = []
        for row in rows:
            task = dict(row)
            if task.get("metadata"):
                try:
                    task["metadata"] = json.loads(task["metadata"])
                except Exception:
                    task["metadata"] = {}
            if task.get("depends_on"):
                try:
                    task["depends_on"] = json.loads(task["depends_on"])
                except Exception:
                    task["depends_on"] = []
            else:
                task["depends_on"] = []
            tasks.append(task)

        conn.close()
        return tasks

    async def get_recent_actions(
        self, limit: int = 20, project_id: str = None
    ) -> List[Dict]:
        """Ottieni azioni recenti, opzionalmente filtrate per progetto"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if project_id:
            cursor.execute(
                """
                SELECT * FROM project_memory WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (project_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM project_memory
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

        actions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return actions

    async def get_projects(self) -> List[str]:
        """Ritorna la lista di ID progetto unici per la dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT project_id FROM tasks UNION SELECT DISTINCT project_id FROM project_memory"
        )
        projects = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        return projects

    async def clear_project_data(self, project_id: str):
        logger.info(f"Wiping data for project: {project_id}")
        conn = sqlite3.connect(self.db_path)  # isolation_level default
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            cursor.execute(
                "DELETE FROM project_memory WHERE project_id = ?", (project_id,)
            )
            cursor.execute(
                "SELECT sprint_id FROM sprints WHERE project_id = ?", (project_id,)
            )
            sprints = cursor.fetchall()
            for (s_id,) in sprints:
                cursor.execute(
                    "DELETE FROM retrospectives WHERE sprint_id = ?", (s_id,)
                )
            cursor.execute("DELETE FROM sprints WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM releases WHERE project_id = ?", (project_id,))
            cursor.execute(
                "DELETE FROM backlog_refinement_items WHERE project_id = ?",
                (project_id,),
            )
            cursor.execute(
                "DELETE FROM sprint_counters WHERE project_id = ?", (project_id,)
            )
            # Clear retrospective.md if it exists
            retro_file = self.memory_dir / "retrospective.md"
            if retro_file.exists():
                logger.info(f"Clearing retrospective.md")
                retro_file.unlink()

            cursor.execute(
                "DELETE FROM token_usage WHERE project_id = ?", (project_id,)
            )
            cursor.execute(
                "DELETE FROM sqlite_sequence WHERE name IN ('sprints', 'retrospectives', 'backlog_refinement_items', 'releases')"
            )
            conn.commit()
            logger.info(f"✓ Data for project {project_id} wiped successfully.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Error wiping project data: {e}")
        finally:
            conn.close()

    async def save_architecture_decision(
        self,
        decision_id: str,
        title: str,
        description: str,
        rationale: str,
        decided_by: str,
        alternatives: str = None,
    ):
        """Salva una decisione architetturale"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO architecture_decisions
            (decision_id, title, description, rationale, decided_by, alternatives)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (decision_id, title, description, rationale, decided_by, alternatives),
        )

        conn.commit()
        conn.close()

    async def add_retrospective(self, title: str, content: str):
        """Aggiungi retrospettiva"""
        retro_file = self.memory_dir / "retrospective.md"

        entry = f"\n\n## {title} - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{content}\n"

        with open(retro_file, "a") as f:
            f.write(entry)

    async def save_agent_prompt(
        self, agent_type: str, system_prompt: str, task_templates: Dict = None
    ):
        """Salva o aggiorna un prompt per un tipo di agente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO agent_prompts (agent_type, system_prompt, task_templates, last_updated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                agent_type,
                system_prompt,
                json.dumps(task_templates) if task_templates else None,
            ),
        )

        conn.commit()
        conn.close()

    async def get_agent_prompt(self, agent_type: str) -> Optional[Dict]:
        """Ottiene il prompt salvato per un agente"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM agent_prompts WHERE agent_type = ?", (agent_type,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            data = dict(row)
            if data.get("task_templates"):
                data["task_templates"] = json.loads(data["task_templates"])
            return data
        return None

    async def update_agent_prompt(self, agent_type: str, new_prompt: str):
        """Aggiorna il system prompt di un agente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Inserisce o aggiorna
        cursor.execute(
            """
            INSERT INTO agent_prompts (agent_type, system_prompt, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(agent_type) DO UPDATE SET
                system_prompt=excluded.system_prompt,
                last_updated=CURRENT_TIMESTAMP
            """,
            (agent_type, new_prompt),
        )
        conn.commit()
        conn.close()

    # --- TOKEN USAGE METHODS ---

    async def log_token_usage(
        self,
        agent_id: str,
        project_id: Optional[str],
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost: float,
        is_toon: bool = False,
        saved_tokens: int = 0,
    ):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO token_usage 
            (agent_id, project_id, model, prompt_tokens, completion_tokens, total_tokens, cost, is_toon, saved_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                project_id,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cost,
                1 if is_toon else 0,
                saved_tokens,
            ),
        )
        conn.commit()
        conn.close()

    async def get_agent_stats(self, project_id: Optional[str] = None) -> List[Dict]:
        """Restituisce le statistiche aggiornate di token/costi per gli agenti, inclusi i prompt"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Filtro per progetto
        where_clause = "WHERE project_id = ?" if project_id else ""
        params = (project_id,) if project_id else ()

        cursor.execute(
            f"""
            SELECT 
                agent_id, 
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as grand_total_tokens,
                SUM(cost) as total_cost,
                SUM(saved_tokens) as total_saved_tokens,
                COUNT(IIF(is_toon = 1, 1, NULL)) as toon_calls_count
            FROM token_usage

            {where_clause}
            GROUP BY agent_id
        """,
            params,
        )

        stats = cursor.fetchall()

        # Combiniamo con i system prompt attuali
        cursor.execute("SELECT agent_type, system_prompt FROM agent_prompts")
        prompts = {r["agent_type"]: r["system_prompt"] for r in cursor.fetchall()}

        # Normalizziamo le stats per agente, ritornando tutte le chiavi che la dashboard aspetta
        results = []
        for row in stats:
            data = dict(row)
            agent_id = data["agent_id"]
            # Di solito gli agent id sono "architect", "backend", o "architect_001"
            agent_type = agent_id.split("_")[0]
            data["system_prompt"] = prompts.get(agent_type, "")

            # Fetch document count (cursor must still be open)
            cursor.execute(
                "SELECT COUNT(*) FROM agent_documents WHERE agent_type = ?",
                (agent_type,),
            )
            data["doc_count"] = cursor.fetchone()[0]

            results.append(data)

        conn.close()
        return results

    # --- AGENT DOCUMENTS METHODS ---

    async def add_agent_document(
        self, agent_type: str, doc_type: str, source: str, content: str
    ) -> str:
        """Aggiunge un documento al contesto permanente di un agente"""
        import uuid

        doc_id = str(uuid.uuid4())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_documents (id, agent_type, doc_type, source, content)
            VALUES (?, ?, ?, ?, ?)
        """,
            (doc_id, agent_type, doc_type, source, content),
        )
        conn.commit()
        conn.close()
        return doc_id

    async def get_agent_documents(self, agent_type: str) -> List[Dict]:
        """Recupera tutti i documenti associati a un tipo di agente"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM agent_documents WHERE agent_type = ? ORDER BY created_at DESC",
            (agent_type,),
        )
        docs = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return docs

    async def delete_agent_document(self, doc_id: str):
        """Elimina un documento dal contesto permanente di un agente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM agent_documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()

    # --- DOMAIN INTELLIGENCE METHODS ---

    async def get_domain_knowledge_by_topic(
        self, agent_id: str, topic: str
    ) -> Optional[Dict]:
        """Ottiene la domain knowledge per uno specifico topic e agente"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM agent_domain_knowledge WHERE agent_id = ? AND topic = ?",
            (agent_id, topic),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            data = dict(row)
            if data.get("key_points"):
                data["key_points"] = json.loads(data["key_points"])
            if data.get("contradictions"):
                data["contradictions"] = json.loads(data["contradictions"])
            return data
        return None

    async def save_domain_knowledge(
        self,
        id: str,
        agent_id: str,
        domain: str,
        topic: str,
        summary: str,
        key_points: List[str],
        contradictions: List[str],
        source_count: int,
        confidence: float,
    ):
        """Salva o aggiorna la domain knowledge"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO agent_domain_knowledge 
            (id, agent_id, domain, topic, synthesized_summary, key_points, contradictions, source_count, confidence_score, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                id,
                agent_id,
                domain,
                topic,
                summary,
                json.dumps(key_points),
                json.dumps(contradictions),
                source_count,
                confidence,
            ),
        )

        conn.commit()
        conn.close()

    async def get_top_domain_knowledge(
        self, agent_id: str, limit: int = 5
    ) -> List[Dict]:
        """Ottiene i topic più rilevanti/confidenti dell'agente"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Ordiniamo per confidence_score * log(source_count) se usiamo formula, o semplificato:
        cursor.execute(
            """
            SELECT * FROM agent_domain_knowledge 
            WHERE agent_id = ? 
            ORDER BY (confidence_score * source_count) DESC 
            LIMIT ?
            """,
            (agent_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            data = dict(row)
            if data.get("key_points"):
                data["key_points"] = json.loads(data["key_points"])
            if data.get("contradictions"):
                data["contradictions"] = json.loads(data["contradictions"])
            results.append(data)

        return results

    # --- SCRUM METHODS ---

    async def create_sprint(self, project_id: str, sprint_number: int = 1) -> int:
        """Crea un nuovo sprint nel database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sprints (project_id, sprint_number, status, started_at) VALUES (?, ?, 'active', ?)",
            (project_id, sprint_number, datetime.now().isoformat()),
        )
        sprint_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return sprint_id

    async def get_active_sprint(self, project_id: str) -> Optional[Dict]:
        """Ottiene l'attuale sprint attivo"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sprints WHERE project_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
            (project_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    async def complete_sprint(self, sprint_id: int):
        """Marca uno sprint come completato"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sprints SET status = 'completed', completed_at = ? WHERE sprint_id = ?",
            (datetime.now().isoformat(), sprint_id),
        )
        conn.commit()
        conn.close()

    async def save_retrospective_feedback(
        self, sprint_id: int, agent_type: str, feedback: str, sentiment: str = "neutral"
    ):
        """Salva il feedback di un agente per una retrospective"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO retrospectives (sprint_id, agent_type, feedback, sentiment) VALUES (?, ?, ?, ?)",
            (sprint_id, agent_type, feedback, sentiment),
        )
        conn.commit()
        conn.close()

    async def get_sprint_retrospective(self, sprint_id: int) -> List[Dict]:
        """Ottiene tutti i feedback per uno specifico sprint"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM retrospectives WHERE sprint_id = ? ORDER BY created_at ASC",
            (sprint_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    async def get_retrospectives(self, project_id: Optional[str] = None) -> List[Dict]:
        """Ottiene la cronologia delle retrospective con statistiche sui task"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM sprints WHERE status = 'completed'"
        params = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY completed_at DESC"

        cursor.execute(query, params)
        sprints = [dict(row) for row in cursor.fetchall()]

        result = []
        for sprint in sprints:
            fbs = await self.get_sprint_retrospective(sprint["sprint_id"])

            # Calcola statistiche dello sprint basate sul tempo
            cursor.execute(
                """
                SELECT 
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM tasks 
                WHERE project_id = ? 
                AND completed_at >= ? AND completed_at <= ?
                AND type NOT IN ('create_project', 'evolve_project', 'review_task', 'speaking_commit', 'scrum_improvement', 'backlog_item')
            """,
                (sprint["project_id"], sprint["started_at"], sprint["completed_at"]),
            )

            stats_row = cursor.fetchone()
            stats = {
                "completed_tasks": stats_row[0] or 0,
                "failed_tasks": stats_row[1] or 0,
                "total_tasks": (stats_row[0] or 0) + (stats_row[1] or 0),
            }

            result.append({"sprint": sprint, "feedbacks": fbs, "stats": stats})

        conn.close()
        return result

    # --- SPRINT COUNTER METHODS ---

    async def increment_sprint_counter(self, project_id: str) -> int:
        """Incrementa il contatore degli sprint completati e restituisce il totale"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sprint_counters (project_id, total_sprints_completed, current_release_sprint_start)
            VALUES (?, 1, 1)
            ON CONFLICT(project_id) DO UPDATE SET total_sprints_completed = total_sprints_completed + 1
        """,
            (project_id,),
        )
        conn.commit()
        cursor.execute(
            "SELECT total_sprints_completed FROM sprint_counters WHERE project_id = ?",
            (project_id,),
        )
        total = cursor.fetchone()[0]
        conn.close()
        return total

    async def get_sprint_counter(self, project_id: str) -> Dict:
        """Restituisce il contatore sprint del progetto"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sprint_counters WHERE project_id = ?", (project_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return {
            "project_id": project_id,
            "total_sprints_completed": 0,
            "current_release_sprint_start": 1,
        }

    # --- RELEASE METHODS ---

    async def create_release(
        self,
        project_id: str,
        version: str,
        sprint_start: int,
        sprint_end: int,
        summary: str,
    ) -> int:
        """Salva una nuova Release e resetta il contatore di inizio sprint release"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO releases (project_id, version, sprint_start, sprint_end, summary)
            VALUES (?, ?, ?, ?, ?)
        """,
            (project_id, version, sprint_start, sprint_end, summary),
        )
        release_id = cursor.lastrowid
        # Reset sprint start per prossima release
        cursor.execute(
            """
            UPDATE sprint_counters SET current_release_sprint_start = ?
            WHERE project_id = ?
        """,
            (sprint_end + 1, project_id),
        )
        conn.commit()
        conn.close()
        return release_id

    async def get_releases(self, project_id: str) -> List[Dict]:
        """Recupera tutte le release di un progetto"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM releases WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- BACKLOG REFINEMENT METHODS ---

    async def save_refinement_proposal(
        self,
        project_id: str,
        sprint_id: int,
        proposed_by: str,
        description: str,
        priority: int = 1,
    ) -> int:
        """Salva una proposta di refinement da un agente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO backlog_refinement_items
            (project_id, sprint_id, proposed_by, description, priority)
            VALUES (?, ?, ?, ?, ?)
        """,
            (project_id, sprint_id, proposed_by, description, priority),
        )
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return item_id

    async def get_refinement_proposals(
        self, project_id: str, sprint_id: int = None
    ) -> List[Dict]:
        """Recupera le proposte di refinement"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if sprint_id:
            cursor.execute(
                """
                SELECT b.*, s.sprint_number 
                FROM backlog_refinement_items b
                LEFT JOIN sprints s ON b.sprint_id = s.sprint_id
                WHERE b.project_id = ? AND b.sprint_id = ? 
                ORDER BY b.priority DESC
            """,
                (project_id, sprint_id),
            )
        else:
            cursor.execute(
                """
                SELECT b.*, s.sprint_number 
                FROM backlog_refinement_items b
                LEFT JOIN sprints s ON b.sprint_id = s.sprint_id
                WHERE b.project_id = ? 
                ORDER BY b.created_at DESC LIMIT 50
            """,
                (project_id,),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    async def accept_refinement_proposals(self, project_id: str, sprint_id: int):
        """Marca le proposte di questo sprint come accepted"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE backlog_refinement_items SET accepted = 1 WHERE project_id = ? AND sprint_id = ? AND accepted = 0",
            (project_id, sprint_id),
        )
        conn.commit()
        conn.close()

    # --- CONFIG METHODS ---

    async def get_config(self, key: str) -> Optional[str]:
        """Legge un valore dalla tabella config"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    async def set_config(self, key: str, value: str):
        """Scrive o aggiorna un valore nella tabella config"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        conn.commit()
        conn.close()

    async def clear_agent_prompts(self):
        """Cancella tutti i prompt agenti dal DB e resetta la versione prompt"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM agent_prompts")
        cursor.execute("DELETE FROM config WHERE key = 'prompt_version'")
        conn.commit()
        conn.close()
        logger.info("✓ Tutti i prompt agenti eliminati dal DB")

    # --- UTILITY ---

    async def save_task(self, task: Dict):
        """Salva un task nel database (usato per action items e refinement proposals)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        depends_on_val = task.get("depends_on")
        if isinstance(depends_on_val, list):
            depends_on_val = json.dumps(depends_on_val)
        cursor.execute(
            """
            INSERT OR IGNORE INTO tasks (task_id, project_id, type, agent_type, description, priority, status, metadata, depends_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task.get("task_id"),
                task.get("project_id"),
                task.get("type", "generic"),
                task.get("agent_type", "backend"),
                task.get("description", ""),
                task.get("priority", 1),
                task.get("status", "pending"),
                task.get("metadata")
                if isinstance(task.get("metadata"), str)
                else json.dumps(task.get("metadata", {})),
                depends_on_val,
            ),
        )
        conn.commit()
        conn.close()

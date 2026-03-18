#!/usr/bin/env python3
"""
Main entry point
"""

from config import MQTT_PORT
from config import MQTT_BROKER
import asyncio
import logging
import sys
from pathlib import Path
import argparse
import uuid

sys.path.insert(0, str(Path(__file__).parent))

from config import WORKSPACE_ROOT, MEMORY_DIR, USE_UNIVERSAL_AGENTS, get_topics
from agents.orchestrator_agent import OrchestratorAgent
from agents.backend_agent import BackendAgent
from agents.frontend_agent import FrontendAgent
from agents.database_agent import DatabaseAgent
from agents.devops_agent import DevOpsAgent
from agents.qa_agent import QAAgent
from agents.testing_agent import TestingAgent
from agents.researcher_agent import ResearcherAgent
from agents.architect_agent import PlannerArchitectAgent
from agents.scrum_master_agent import ScrumMasterAgent
from agents.universal_agent import UniversalAgent
from core.prompt_manager import PromptManager
from core.skills import SkillManager
from core.memory import MemorySystem

# Definizione colori ANSI
COLORS = {
    "orchestrator": "\033[96m",  # Cyan
    "backend": "\033[94m",  # Blue
    "frontend": "\033[95m",  # Magenta
    "database": "\033[32m",  # Green
    "devops": "\033[92m",  # Light Green
    "qa": "\033[38;5;214m",  # Orange
    "testing": "\033[97m",  # White
    "researcher": "\033[93m",  # Yellow
    "architect": "\033[38;5;208m",  # Orange-ish
    "scrum_master": "\033[95m",  # Light Magenta
    "ERROR": "\033[91m",  # Red
    "INFO": "\033[93m",  # Yellow
    "RESET": "\033[0m",
}


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        level_color = COLORS.get(record.levelname, COLORS["RESET"])
        name = record.name.lower()
        agent_color = COLORS["RESET"]
        for key, value in COLORS.items():
            if key in name:
                agent_color = value
                break
        original_levelname = record.levelname
        record.levelname = f"{level_color}{original_levelname}{agent_color}"
        formatted = super().format(record)
        result = f"{agent_color}{formatted}{COLORS['RESET']}"
        record.levelname = original_levelname
        return result


console_handler = logging.StreamHandler()
console_handler.setFormatter(
    ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, logging.FileHandler(MEMORY_DIR / "system.log")],
)

logger = logging.getLogger(__name__)


class MultiAgentSystem:
    """Sistema Multi-Agente"""

    def __init__(self, project_name: str = "default_project"):
        self.project_name = project_name
        self.project_root = WORKSPACE_ROOT / project_name
        self.project_root.mkdir(exist_ok=True, parents=True)

        self.memory = MemorySystem()
        self.prompt_manager = PromptManager(self.memory)
        self.skill_manager = SkillManager()
        self.agents = []

        logger.info(f"Inizializzato Multi-Agent System per progetto: {project_name}")
        logger.info(f"Project root: {self.project_root}")

    async def _reset_message_brokers(self):
        """Pulisce Kafka e Redis per il progetto corrente al reset"""
        from config import get_topics

        topics = get_topics(self.project_name)

        # --- KAFKA ---
        try:
            from aiokafka.admin import AIOKafkaAdminClient

            admin = AIOKafkaAdminClient(bootstrap_servers="localhost:9092")
            await asyncio.wait_for(admin.start(), timeout=5.0)

            existing = await admin.list_topics()
            to_delete = [t for t in topics.values() if t in existing]
            if to_delete:
                await admin.delete_topics(to_delete)
                logger.info(
                    f"✓ Kafka: eliminati {len(to_delete)} topic per {self.project_name}"
                )
            else:
                logger.info(
                    f"ℹ Kafka: nessun topic da eliminare per {self.project_name}"
                )

            await admin.close()
        except Exception as e:
            logger.warning(f"Kafka reset fallito: {e}")

        await asyncio.sleep(2)

        # --- REDIS ---
        try:
            import redis

            r = redis.from_url("redis://localhost:6379/0")
            deleted = 0
            for key in r.scan_iter(f"*{self.project_name}*"):
                r.delete(key)
                deleted += 1
            logger.info(f"✓ Redis: {deleted} chiavi eliminate per {self.project_name}")
        except Exception as e:
            logger.warning(f"Redis cleanup fallito: {e}")

        # --- MQTT: elimina retained messages ---
        try:
            import aiomqtt

            async with aiomqtt.Client(MQTT_BROKER, port=MQTT_PORT) as client:
                topics_list = get_topics(self.project_name)
                for topic in topics_list.values():
                    await client.publish(topic, payload=None, retain=True)
                logger.info(
                    f"✓ MQTT: retained messages eliminati per {self.project_name}"
                )
        except Exception as e:
            logger.warning(f"MQTT reset fallito: {e}")

    async def clean_agents(self):
        """Rimuove tutti i dati degli agenti e resetta i prompt nel DB"""
        logger.info("🧹 Pulizia agenti in corso...")

        await self.memory.initialize()

        # 1. Cancella tutti i prompt dal DB
        await self.memory.clear_agent_prompts()
        logger.info("✓ Prompt agenti eliminati dal DB")

        # 2. Flush Redis cache prompt
        try:
            import redis
            from config import REDIS_URL

            r = redis.from_url(REDIS_URL, decode_responses=True)
            deleted = 0
            for key in r.scan_iter("prompts:*"):
                r.delete(key)
                deleted += 1
            r.delete("prompt_version")
            logger.info(f"✓ Redis: {deleted} chiavi prompt eliminate")
        except Exception as e:
            logger.warning(f"Redis flush fallito: {e}")

        # 3. Re-inizializza i prompt con la configurazione corrente (USE_TOON aware)
        await self.prompt_manager.initialize_default_prompts(force=True)
        logger.info("✓ Prompt re-inizializzati con configurazione corrente")

        logger.info("✅ Clean agenti completato")

    async def initialize(self, reset: bool = False):
        """Inizializza il sistema"""
        logger.info("Inizializzazione sistema...")

        await self.memory.initialize()
        logger.info("✓ Sistema di memoria inizializzato")

        is_new_folder = not any(self.project_root.iterdir()) or (
            len(list(self.project_root.iterdir())) == 1
            and (self.project_root / ".git").exists()
        )

        if reset or is_new_folder:
            if reset:
                logger.info(
                    f"⚠ Flag --reset rilevato. Pulizia totale (Database + File) per {self.project_name}..."
                )
                import shutil

                for item in self.project_root.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                logger.info(f"✓ File del progetto {self.project_name} eliminati.")

                await self.memory.clear_project_data(self.project_name)
                await self._reset_message_brokers()
                await asyncio.sleep(0.5)
                logger.info(f"✓ Progetto {self.project_name} azzerato nel database.")
            else:
                logger.info(
                    f"ℹ Cartella progetto vuota o mancante. Ripristino stato database per {self.project_name}..."
                )
                await self.memory.clear_project_data(self.project_name)
                await asyncio.sleep(0.5)
                logger.info(f"✓ Progetto {self.project_name} azzerato nel database.")

        await self.prompt_manager.initialize_default_prompts()
        logger.info("✓ Prompt Manager inizializzato")

        self.skill_manager.initialize(WORKSPACE_ROOT)
        logger.info("✓ Skill Manager inizializzato")

        await self._create_agents()
        logger.info(f"✓ {len(self.agents)} agenti creati")

        self._init_git()

    def _init_git(self):
        """Inizializza Git repository"""
        import subprocess

        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            try:
                subprocess.run(["git", "init"], cwd=self.project_root, check=True)
                subprocess.run(
                    ["git", "config", "user.email", "agent@devagent.ai"],
                    cwd=self.project_root,
                    check=True,
                )
                subprocess.run(
                    ["git", "config", "user.name", "Hypnonyx"],
                    cwd=self.project_root,
                    check=True,
                )
                logger.info("✓ Git repository initialized")
            except Exception as e:
                import traceback

                logger.warning(f"Git init failed: {e} {traceback.format_exc()}")

    async def _create_agents(self):
        """Crea tutti gli agenti del sistema"""
        self.orchestrator = OrchestratorAgent(
            agent_id="orchestrator_001",
            memory=self.memory,
            project_root=str(self.project_root),
            skill_manager=self.skill_manager,
            prompt_manager=self.prompt_manager,
        )
        self.agents.append(self.orchestrator)

        roles = {
            "backend": (BackendAgent, "backend_001"),
            "frontend": (FrontendAgent, "frontend_001"),
            "database": (DatabaseAgent, "database_001"),
            "devops": (DevOpsAgent, "devops_001"),
            "qa": (QAAgent, "qa_001"),
            "testing": (TestingAgent, "testing_001"),
        }

        for role, (AgentClass, agent_id) in roles.items():
            if USE_UNIVERSAL_AGENTS:
                logger.info(f"Using UniversalAgent for role: {role}")
                agent = UniversalAgent(
                    agent_id=agent_id,
                    agent_type=role,
                    memory=self.memory,
                    project_root=str(self.project_root),
                    skill_manager=self.skill_manager,
                    prompt_manager=self.prompt_manager,
                )
            else:
                agent = AgentClass(
                    agent_id=agent_id,
                    memory=self.memory,
                    project_root=str(self.project_root),
                    skill_manager=self.skill_manager,
                    prompt_manager=self.prompt_manager,
                )
            self.agents.append(agent)

        self.architect = PlannerArchitectAgent(
            agent_id="architect_001",
            memory=self.memory,
            project_root=str(self.project_root),
            skill_manager=self.skill_manager,
            prompt_manager=self.prompt_manager,
        )
        self.agents.append(self.architect)

        from agents.reviewer_agent import ReviewerAgent

        for i in range(1, 4):
            reviewer_agent = ReviewerAgent(
                agent_id=f"reviewer_{i:03d}",
                memory=self.memory,
                project_root=str(self.project_root),
                skill_manager=self.skill_manager,
                prompt_manager=self.prompt_manager,
            )
            self.agents.append(reviewer_agent)

        researcher_agent = ResearcherAgent(
            agent_id="researcher_001",
            memory=self.memory,
            project_root=str(self.project_root),
            skill_manager=self.skill_manager,
            prompt_manager=self.prompt_manager,
        )
        self.agents.append(researcher_agent)

        scrum_master_agent = ScrumMasterAgent(
            agent_id="scrum_master_001",
            memory=self.memory,
            project_root=str(self.project_root),
            skill_manager=self.skill_manager,
            prompt_manager=self.prompt_manager,
        )
        self.agents.append(scrum_master_agent)

    async def create_project(self, specification: dict, prompt: str = None):
        """Crea un progetto completo"""
        logger.info("=" * 60)
        logger.info("AVVIO CREAZIONE PROGETTO")
        logger.info("=" * 60)

        create_task = {
            "task_id": f"create_project_{uuid.uuid4().hex[:4]}",
            "type": "create_project",
            "description": prompt or "Create complete project",
            "prompt": prompt,
            "specification": {
                "project_id": self.project_name,
                "backend": specification.get("backend", True),
                "frontend": specification.get("frontend", True),
                "database": specification.get("database", True),
                "mvp": specification.get("mvp", False),
            },
        }

        await self.orchestrator.tasks_queue.put(create_task)
        logger.info(
            f"Task di creazione progetto assegnato all'orchestratore. Prompt: {prompt[:50] if prompt else 'N/A'}..."
        )

    async def evolve_project(self, specification: dict, prompt: str):
        """Evolve un progetto esistente"""
        logger.info("=" * 60)
        logger.info("AVVIO EVOLUZIONE PROGETTO")
        logger.info("=" * 60)

        evolve_task = {
            "task_id": f"evolve_project_{uuid.uuid4().hex[:4]}",
            "type": "evolve_project",
            "description": f"Evolution: {prompt}",
            "prompt": prompt,
            "specification": {
                "project_id": self.project_name,
                "backend": specification.get("backend", True),
                "frontend": specification.get("frontend", True),
                "database": specification.get("database", True),
                "mvp": specification.get("mvp", False),
            },
        }

        self.orchestrator.completion_event.clear()
        await self.orchestrator.tasks_queue.put(evolve_task)
        logger.info(
            f"Task di evoluzione assegnato all'orchestratore. Prompt: {prompt[:50]}..."
        )

    async def start(
        self,
        specification: dict,
        duration: int = 60,
        prompt: str = None,
        reset: bool = False,
    ):
        """Avvia il sistema multi-agente"""
        await self.initialize(reset=reset)

        logger.info("Avvio tutti gli agenti...")
        agent_tasks = [asyncio.create_task(agent.start()) for agent in self.agents]

        should_resume = specification.get("resume", False)
        should_update = specification.get("update", False)

        if not reset and not should_resume and not should_update:
            if await self.memory.has_tasks(self.project_name):
                should_resume = True

        if should_resume:
            from agents.scrum_master_agent import ScrumMasterAgent

            for agent in self.agents:
                if isinstance(agent, ScrumMasterAgent):
                    agent.initial_retrospective = True
                    logger.info(
                        f"📍 Scrum Master '{agent.agent_id}' configurato per Retrospective iniziale (modalità RESUME attivata)."
                    )
                    break

        resumed_count = 0
        if should_resume or should_update:
            resumed_count = await self.orchestrator.resume_tasks()

        if should_update:
            await self.evolve_project(specification, prompt=prompt)
        elif not should_resume:
            await self.create_project(specification, prompt=prompt)
        elif resumed_count > 0:
            logger.info(
                f"ℹ️ Sistema avviato in modalità RESUME: {resumed_count} task caricati."
            )
        else:
            logger.info(
                "ℹ️ Sistema avviato in modalità RESUME: Tutti i task risultano già completati."
            )

        await asyncio.sleep(2)

        logger.info("=" * 60)
        logger.info("SISTEMA MULTI-AGENTE ATTIVO")
        logger.info("=" * 60)
        logger.info(f"Agenti attivi: {len(self.agents)}")
        logger.info(f"Project root: {self.project_root}")
        logger.info(f"Memory DB: {self.memory.db_path}")
        logger.info(f"Sistema si fermerà dopo {duration} secondi")
        logger.info("=" * 60)

        completion_task = asyncio.create_task(self.orchestrator.completion_event.wait())

        try:
            done, pending = await asyncio.wait(
                [completion_task, *agent_tasks],
                timeout=duration,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if completion_task in done:
                logger.info("✅ Progetto completato! Arresto anticipato del sistema.")
            elif any(t in done for t in agent_tasks):
                logger.warning("⚠ Uno o più agenti si sono fermati inaspettatamente.")
            else:
                logger.info(f"⏰ Raggiunta durata massima di {duration} secondi.")

        except Exception as e:
            import traceback

            logger.error(f"Errore durante l'attesa del sistema: {e}")
            logger.error(traceback.format_exc())
        finally:
            if not completion_task.done():
                completion_task.cancel()
            for t in agent_tasks:
                if not t.done():
                    t.cancel()
            if agent_tasks:
                await asyncio.gather(*agent_tasks, return_exceptions=True)
            await self.stop()

    async def stop(self):
        """Ferma tutti gli agenti"""
        logger.info("Fermando tutti gli agenti...")

        for agent in self.agents:
            await agent.stop()

        completed = sum(len(a.completed_tasks) for a in self.agents)
        failed = sum(len(a.failed_tasks) for a in self.agents)

        await self.memory.add_retrospective(
            title="Session Complete",
            content=f"Sistema fermato.\n"
            f"- Agenti attivi: {len(self.agents)}\n"
            f"- Tasks completati: {completed}\n"
            f"- Tasks falliti: {failed}\n",
        )

        logger.info("=" * 60)
        logger.info("RIEPILOGO FINALE")
        logger.info("=" * 60)
        logger.info(f"Tasks completati: {completed}")
        logger.info(f"Tasks falliti: {failed}")
        logger.info(f"Progetto creato in: {self.project_root}")
        logger.info("=" * 60)
        logger.info("✓ Sistema fermato correttamente")


def check_dependencies():
    import subprocess
    import sys
    from pathlib import Path

    requirements_file = Path(__file__).parent / "requirements.txt"
    if not requirements_file.exists():
        logger.warning(
            "File requirements.txt non trovato. Salto il controllo dipendenze."
        )
        return

    logger.info("🔍 Controllo dipendenze in corso...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "check"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("✓ Tutte le dipendenze sono soddisfatte.")
    except subprocess.CalledProcessError:
        logger.warning(
            "⚠ Alcune dipendenze mancano o sono incompatibili. Installazione automatica..."
        )
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
            )
            logger.info("✓ Dipendenze installate con successo.")
        except Exception as e:
            import traceback

            logger.error(f"❌ Errore durante l'installazione delle dipendenze: {e}")
            logger.error(traceback.format_exc())


async def main():
    check_dependencies()

    parser = argparse.ArgumentParser(description="Hypnonyx Multi-Agent System")
    parser.add_argument(
        "--project", type=str, default="demo_project", help="Nome del progetto"
    )
    parser.add_argument("--no-backend", action="store_true")
    parser.add_argument("--no-frontend", action="store_true")
    parser.add_argument("--no-database", action="store_true")
    parser.add_argument("--backend", type=str, default=None)
    parser.add_argument("--frontend", type=str, default=None)
    parser.add_argument("--database", type=str, default=None)
    parser.add_argument("--prompt", type=str, default=None)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--mvp", action="store_true")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Elimina i dati del progetto e ricomincia da zero",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Resetta i prompt agenti nel DB (USE_TOON aware)",
    )

    args = parser.parse_args()

    # ── Early exit: clean agents only ────────────────────────────────────────
    if args.clean:
        system = MultiAgentSystem(project_name=args.project)
        await system.clean_agents()
        return

    # ── Normal flow ───────────────────────────────────────────────────────────
    specification = {
        "backend": args.backend if args.backend else (not args.no_backend),
        "frontend": args.frontend if args.frontend else (not args.no_frontend),
        "database": args.database if args.database else (not args.no_database),
        "resume": args.resume,
        "update": args.update,
        "mvp": args.mvp,
    }

    current_prompt = (
        args.prompt
        or "Create a standard web application with FastAPI, React and SQLite"
    )

    system = MultiAgentSystem(project_name=args.project)

    try:
        await system.start(
            specification,
            duration=args.duration,
            prompt=current_prompt,
            reset=args.reset,
        )
    except KeyboardInterrupt:
        logger.info("\nInterruzione richiesta dall'utente")
        await system.stop()
    except Exception as e:
        import traceback

        logger.error(f"Errore critico: {e}")
        logger.error(traceback.format_exc())
        await system.stop()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSistema interrotto")
        sys.exit(0)

#!/usr/bin/env python3
"""
Demo script che mostra le capacità del sistema multi-agente
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import MultiAgentSystem


async def demo_simple_api():
    """Demo: Crea una semplice API REST"""
    print("\n" + "=" * 70)
    print("📚 DEMO 1: Creazione API REST Semplice")
    print("=" * 70)
    print("""
Questo demo crea:
- Backend API con FastAPI
- Endpoint CRUD per gestione items
- Sistema di autenticazione JWT
- Unit tests per backend
- Documentazione automatica
""")

    input("Premi INVIO per iniziare...")

    system = MultiAgentSystem(project_name="simple_api")

    spec = {"backend": True, "frontend": False, "database": True}

    # Avvia per 30 secondi poi ferma
    try:
        await asyncio.wait_for(system.start(spec), timeout=30)
    except asyncio.TimeoutError:
        print("\n✓ Demo completato - sistema fermato")
        await system.stop()


async def demo_fullstack_app():
    """Demo: Crea una applicazione full-stack"""
    print("\n" + "=" * 70)
    print("📚 DEMO 2: Applicazione Full-Stack Completa")
    print("=" * 70)
    print("""
Questo demo crea:
- Backend API con FastAPI
- Frontend React con Vite
- Database SQLite con migrazioni
- Sistema di autenticazione
- Docker + docker-compose
- GitHub Actions CI/CD
- Test E2E completi
- Documentazione completa
""")

    input("Premi INVIO per iniziare...")

    system = MultiAgentSystem(project_name="fullstack_app")

    spec = {"backend": True, "frontend": True, "database": True}

    try:
        await asyncio.wait_for(system.start(spec), timeout=60)
    except asyncio.TimeoutError:
        print("\n✓ Demo completato - sistema fermato")
        await system.stop()


async def demo_agent_collaboration():
    """Demo: Mostra collaborazione tra agenti"""
    print("\n" + "=" * 70)
    print("📚 DEMO 3: Collaborazione tra Agenti")
    print("=" * 70)
    print("""
Questo demo mostra:
- Orchestratore che assegna task
- Agenti che lavorano in parallelo
- Sistema anti-idle (agenti si aiutano)
- Comunicazione tramite message broker
- Commit Git automatici
- Memoria persistente
""")

    input("Premi INVIO per iniziare...")

    system = MultiAgentSystem(project_name="collab_demo")
    await system.initialize()

    # Aggiungi task manualmente per mostrare collaborazione
    print("\n📤 Assegnando task agli agenti...")

    tasks = [
        {
            "task_id": "backend_001",
            "type": "implement_api",
            "agent_type": "backend",
            "description": "Create REST API",
        },
        {
            "task_id": "frontend_001",
            "type": "create_ui",
            "agent_type": "frontend",
            "description": "Create React UI",
        },
        {
            "task_id": "database_001",
            "type": "design_schema",
            "agent_type": "database",
            "description": "Design database schema",
        },
    ]

    for task in tasks:
        await system.orchestrator.broker.publish("tasks.new", task)
        print(f"  ✓ Task {task['task_id']} assigned to {task['agent_type']}")

    print("\n👀 Monitoraggio esecuzione task...")
    print("(Il sistema si fermerà automaticamente dopo 45 secondi)\n")

    # Avvia sistema per 45 secondi
    try:
        await asyncio.wait_for(
            asyncio.gather(*[agent.start() for agent in system.agents]), timeout=45
        )
    except asyncio.TimeoutError:
        print("\n✓ Demo completato")
        await system.stop()

    # Mostra statistiche
    print("\n📊 Statistiche finali:")
    print(f"  - Agenti attivi: {len(system.agents)}")
    print(
        f"  - Task completati totali: {sum(len(a.completed_tasks) for a in system.agents)}"
    )

    # Mostra azioni dal database
    recent_actions = await system.memory.get_recent_actions(limit=10)
    print(f"\n📝 Ultime {len(recent_actions)} azioni:")
    for action in recent_actions:
        print(f"  - [{action['agent']}] {action['action']}: {action['description']}")


async def demo_memory_system():
    """Demo: Sistema di memoria persistente"""
    print("\n" + "=" * 70)
    print("📚 DEMO 4: Sistema di Memoria Persistente")
    print("=" * 70)
    print("""
Questo demo mostra:
- Database SQLite per tracciare tutto
- File Markdown per documentazione
- Decisioni architetturali salvate
- Storico commit Git
- Query sul database
""")

    input("Premi INVIO per iniziare...")

    from core.memory import MemorySystem
    import sqlite3

    memory = MemorySystem()
    await memory.initialize()

    # Simula alcune azioni
    print("\n📝 Simulando azioni degli agenti...")

    actions = [
        ("backend_001", "implement_api", "Created REST API endpoints"),
        ("frontend_001", "create_ui", "Created React components"),
        ("database_001", "design_schema", "Designed database schema"),
        ("devops_001", "create_dockerfile", "Created Docker configuration"),
        ("qa_001", "write_e2e_tests", "Created E2E test suite"),
    ]

    for agent, action, desc in actions:
        await memory.log_action(
            agent=agent,
            action=action,
            description=desc,
            commit_hash=f"abc{hash(agent + action) % 1000:03d}",
        )
        print(f"  ✓ {agent}: {desc}")

    # Salva decisione architetturale
    print("\n🏗️ Salvando decisione architetturale...")
    await memory.save_architecture_decision(
        decision_id="arch_demo_001",
        title="Scelta framework frontend",
        description="Deciso di usare React con Vite per sviluppo rapido",
        rationale="React ha ecosystem maturo, Vite offre HMR veloce",
        decided_by="orchestrator",
        alternatives="Vue.js, Angular, Svelte",
    )
    print("  ✓ Decisione salvata")

    # Query database
    print("\n🔍 Query database:")

    conn = sqlite3.connect(memory.db_path)
    cursor = conn.cursor()

    # Azioni per agente
    cursor.execute("""
        SELECT agent, COUNT(*) as count
        FROM project_memory
        GROUP BY agent
        ORDER BY count DESC
    """)

    print("\n  Azioni per agente:")
    for row in cursor.fetchall():
        print(f"    - {row[0]}: {row[1]} azioni")

    # Decisioni architetturali
    cursor.execute("SELECT title, decided_by FROM architecture_decisions")
    print("\n  Decisioni architetturali:")
    for row in cursor.fetchall():
        print(f"    - {row[0]} (by {row[1]})")

    conn.close()

    print("\n📄 File di memoria creati:")
    for md_file in memory.memory_dir.glob("*.md"):
        print(f"  - {md_file.name}")


async def main_menu():
    """Menu principale dei demo"""
    demos = [
        ("API REST Semplice (30s)", demo_simple_api),
        ("Applicazione Full-Stack (60s)", demo_fullstack_app),
        ("Collaborazione Agenti (45s)", demo_agent_collaboration),
        ("Sistema di Memoria", demo_memory_system),
    ]

    while True:
        print("\n" + "=" * 70)
        print("🤖 Hypnonyx Multi-Agent System - Demo Menu")
        print("=" * 70)
        print("\nSeleziona un demo:\n")

        for i, (name, _) in enumerate(demos, 1):
            print(f"  {i}. {name}")

        print(f"\n  0. Esci")

        try:
            choice = input("\nScelta: ").strip()

            if choice == "0":
                print("\nGrazie per aver provato Hypnonyx! 👋")
                break

            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(demos):
                _, demo_func = demos[choice_idx]
                await demo_func()

                input("\n\nPremi INVIO per tornare al menu...")
            else:
                print("\n❌ Scelta non valida")

        except ValueError:
            print("\n❌ Inserisci un numero")
        except KeyboardInterrupt:
            print("\n\n👋 Arrivederci!")
            break
        except Exception as e:
            import traceback

            print(f"\n❌ Errore: {e} {traceback.format_exc()}")
            input("\nPremi INVIO per continuare...")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║       🤖  Hypnonyx Multi-Agent System - Interactive Demo  🤖        ║
║                                                                      ║
║  Sistema multi-agente autonomo per sviluppo software completo       ║
║  con orchestratore, comunicazione MQTT/Kafka, memoria persistente   ║
║  e automazione Git                                                   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    try:
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrotto")
        sys.exit(0)

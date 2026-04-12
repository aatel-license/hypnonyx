# hypnonyx
![Alt text](https://github.com/aatel-license/hypnonyx/blob/main/image.png "hypnonyx")
Hypnonyx is an AI agent designed to operate in Swarm mode, following Agile and Scrum principles. Tireless, it was “born” from the sleepless nights of its developers, optimizing code collaboratively and autonomously. Hypnonyx can coordinate multiple instances of itself to maximize productivity and software quality.

# 🤖 Hypnonyx Multi-Agent System


Sistema multi-agente autonomo per lo sviluppo software completo con orchestratore centrale, comunicazione tramite message broker, memoria persistente e Git automation.

## 🎯 Caratteristiche

### **7 Agenti Specializzati**

1. **Orchestrator Agent** - Coordina tutti gli agenti, assegna task, monitora progresso
2. **Backend Developer Agent** - Implementa API, business logic, autenticazione
3. **Frontend Developer Agent** - Crea UI, integra con backend
4. **Database Administrator Agent** - Progetta schema, crea migrazioni
5. **DevOps Engineer Agent** - Docker, CI/CD, deployment
6. **QA Agent** - Test end-to-end, validazione, bug reporting
7. **Testing Agent** - Unit tests, integration tests, coverage analysis

### **Sistema di Comunicazione**

- **MQTT** o **Kafka** per comunicazione asincrona tra agenti (OPZIONALE)
- **Falla in-memory** automatico se broker non disponibile
- Topics dedicati: `tasks.new`, `tasks.completed`, `bugs.reported`, `agent.heartbeat`, etc.
- **Funziona out-of-the-box senza configurazione!** 🎯

### **💻 Dashboard & Monitoraggio** 🆕

- **Dashboard Web Interattiva**: Visualizza lo stato dei task in tempo reale.
- **Kanban Board**: Traccia il progresso di ogni agente.
- **Dettagli Rejection**: Visualizza feedback dei reviewer e motivi di bocciatura direttamente sulle card.
- **Activity Log**: Stream live di tutte le azioni di sistema.

### **🔄 Evoluzione e Persistence** 🆕

- **Auto-Resume**: Riprende esattamente da dove si era fermato dopo un'interruzione (Ctrl+C).
- **Project Evolution**: Permette di aggiornare progetti esistenti con nuovi prompt (`--update`).
- **Modalità MVP**: Sviluppo ultra-rapido senza Auth e senza il ciclo di review (`--mvp`).

### **Sistema di Skills Dinamiche** 🆕

- **Caricamento dinamico** di best practices e linee guida
- **Skills di default**: backend-api, frontend-react, testing-best-practices
- **Auto-detection**: Skills attivate automaticamente in base al task
- **Custom skills**: Crea le tue skills in `.claude/`
- **Metadata YAML**: Specifica agent types, triggers, dependencies
- Vedi [SKILLS_GUIDE.md](SKILLS_GUIDE.md) per dettagli completi

### **Memoria Persistente**

- **Database SQLite** per tracciare:
  - Azioni degli agenti (chi, cosa, quando, commit hash)
  - Task e loro stato
  - Bug reports
  - Decisioni architetturali
- **File Markdown** in `/memory/`:
  - `global_memory.md` - Memoria globale
  - `decisions.md` - Log decisioni
  - `architecture.md` - Documentazione architettura
  - `retrospective.md` - Retrospettive

### **Git Automation**

- Commit automatici dopo ogni task completato
- Messaggi di commit strutturati (`feat:`, `fix:`, `refactor:`, etc.)
- Branch per agente: `agent/backend/backend_001`
- Storicizzazione completa

### **Anti-Idle System**

- Quando un agente è idle (>30 secondi senza task):
  - Segnala disponibilità
  - Cerca task da altri agenti sovraccarichi
  - Offre aiuto ad agenti in difficoltà
- L'orchestratore redistribuisce automaticamente i task

## 📁 Struttura del Progetto

```
hypnonyx/
├── main.py                 # Entrypoint principale
├── config.py              # Configurazione globale
├── requirements.txt       # Dipendenze Python
│
├── core/
│   ├── memory.py          # Sistema di memoria persistente
│   └── message_broker.py  # Comunicazione MQTT/Kafka
│
├── agents/
│   ├── base_agent.py      # Classe base per agenti
│   ├── orchestrator_agent.py
│   ├── backend_agent.py
│   ├── frontend_agent.py
│   ├── database_agent.py
│   ├── devops_agent.py
│   ├── qa_agent.py
│   └── testing_agent.py
│
├── memory/                # File di memoria
│   ├── project_memory.db
│   ├── global_memory.md
│   ├── decisions.md
│   ├── architecture.md
│   └── retrospective.md
│
├── docs/                  # Documentazione generata
│
└── projects/              # Progetti creati dagli agenti
    └── <project_name>/
        ├── backend/
        ├── frontend/
        ├── database/
        ├── tests/
        └── devops/
```

## 🚀 Quick Start

### Prerequisiti

**1. LM Studio** (richiesto):

- Scarica: https://lmstudio.ai/
- Scarica modello: **DeepSeek Coder 6.7B** (consigliato)
- Avvia server locale
- Guida completa: [LM_STUDIO_SETUP.md](LM_STUDIO_SETUP.md)

**2. Python 3.10+** e **Git**

### 1. Installazione

```bash
# Clona il repository
git clone <repo-url>
cd hypnonyx

# Installa dipendenze
pip install -r requirements.txt
```

### 2. Configurazione (Opzionale)

Crea un file `.env`:

```env
# LLM Configuration
LM_STUDIO_URL=http://localhost:1234/v1/chat/completions
MODEL_NAME=mistral
TEMPERATURE=0.3

# Message Broker
USE_MQTT=true
MQTT_BROKER=localhost
MQTT_PORT=1883

# Git
GIT_AUTO_COMMIT=true
GIT_BRANCH_PREFIX=agent
```

### 3. Avvio Sistema

```bash
# Specifica tecnologia specifica
python main.py --project my_app --backend fastapi --frontend react --database postgres

# 🔄 Riprendi progetto esistente (Auto-detect o manuale)
python main.py --project ecommerce --resume

# 🚀 Modalità MVP (Veloce, No Auth, No Review)
python main.py --project startup_idea --prompt "Landing page per AI" --mvp

# 🛠️ Evolvi un progetto esistente
python main.py --project ecommerce --update --prompt "Aggiungi carrello e checkout"

# 🗑️ Reset completo
python main.py --project test_app --reset
```

### 4. Dashboard (Reale-Time)

```bash
# Avvia la dashboard web
./dashboard.sh
# Apri http://localhost:5000
```

### 4. Setup MQTT (Opzionale ma Consigliato)

```bash
# Con Docker
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto

# O installa localmente
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients

# macOS
brew install mosquitto
brew services start mosquitto
```

## 🔧 Come Funziona

### Workflow di Creazione Progetto

1. **Orchestrator** riceve richiesta di creazione progetto
2. **Decomposizione** in task atomici (API, UI, DB, tests, CI/CD, etc.)
3. **Calcolo dipendenze** (DB → Backend → Frontend)
4. **Distribuzione task** ai vari agenti tramite message broker
5. **Esecuzione parallela** con monitoraggio
6. **Auto-commit** Git dopo ogni task
7. **Log persistente** su database e markdown

### Comunicazione tra Agenti

```python
# Agent A pubblica un task
await broker.publish( get_topics(self.project_id)["TASKS_NEW"], {
    "task_id": "backend_api_001",
    "type": "implement_api",
    "agent_type": "backend",
    "description": "Implement REST API"
})

# Agent B (backend) riceve e esegue
# Quando completa:
await broker.publish( get_topics(self.project_id)["TASKS_COMPLETED"], {
    "task_id": "backend_api_001",
    "result": {"status": "completed"}
})

# Orchestrator monitora e sblocca task dipendenti
```

### Sistema Anti-Idle

```python
# Ogni 5 secondi ogni agente invia heartbeat
await broker.send_heartbeat(status="active" | "idle")

# Se idle >30s:
await broker.report_idle()

# Orchestrator assegna nuovo task
await broker.publish( get_topics(self.project_id)["TASKS_ASSIGNED"], {
    "task_id": "help_backend_001",
    "assigned_to": "testing_001"
})
```

### Memoria e Git

Ogni azione viene tracciata:

```sql
INSERT INTO project_memory (
    timestamp, agent, action, file_modified,
    commit_hash, description
) VALUES (
    '2025-02-14T10:30:00',
    'backend_001',
    'implemented_api',
    'backend/api.py',
    'abc123',
    'Created REST API with FastAPI'
);
```

## 📊 Monitoraggio

### Log in Tempo Reale

```bash
# Log del sistema
tail -f memory/system.log

# Memoria globale
cat memory/global_memory.md

# Decisioni architetturali
cat memory/decisions.md

# Task completati
sqlite3 memory/project_memory.db "SELECT * FROM project_memory ORDER BY timestamp DESC LIMIT 10;"
```

### Database Queries

```sql
-- Azioni recenti
SELECT agent, action, description, timestamp
FROM project_memory
ORDER BY timestamp DESC LIMIT 20;

-- Task per agente
SELECT agent, COUNT(*) as task_count, status
FROM tasks
GROUP BY agent, status;

-- Bug aperti
SELECT bug_id, severity, description, reporter_agent
FROM bugs
WHERE status = 'open'
ORDER BY severity DESC;
```

## 🔌 Estensioni

### Aggiungere un Nuovo Agente

```python
from agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    def __init__(self, agent_id: str, memory: MemorySystem, project_root: str):
        super().__init__(
            agent_id=agent_id,
            agent_type="custom",
            memory=memory,
            project_root=project_root
        )

    async def execute(self, task: Dict) -> Any:
        # Implementa logica specifica
        if task.get("type") == "my_task":
            # Do something
            return {"status": "completed"}

    async def can_help(self, task: Dict) -> bool:
        # Decide se può aiutare
        return task.get("type") in ["my_task", "related_task"]
```

### Aggiungere Nuovi Topic

Modifica `config.py`:

```python
 get_topics(self.project_id) = {
    # ... existing topics ...
    "MY_NEW_TOPIC": "my.new.topic"
}
```

## 🐛 Troubleshooting

### Sistema Funziona Senza MQTT/Kafka!

Il sistema usa **fallback in-memory automatico** - non serve configurare nulla!

Se vedi errori MQTT, puoi ignorarli o disabilitare esplicitamente:

```bash
# Nel file .env
USE_MQTT=false
USE_KAFKA=false
```

### Altri Problemi Comuni

Vedi [TROUBLESHOOTING.md](TROUBLESHOOTING.md) per la guida completa con soluzioni a:

- Errori MQTT/Kafka
- Module not found
- Git errors
- Database locked
- Performance issues

### Test Rapido

```bash
python test_system.py
```

## 📖 Esempi

### Progetto Full-Stack

```bash
python main.py --project ecommerce
```

Genera:

- Backend API con FastAPI
- Frontend React con Vite
- Database SQLite con schema
- Docker + docker-compose
- GitHub Actions CI/CD
- Test E2E, unit, integration
- Documentazione completa

### Solo Backend API

```bash
python main.py --project api_service --no-frontend --no-database
```

### Custom Configuration

```python
# custom_project.py
import asyncio
from main import MultiAgentSystem

async def main():
    system = MultiAgentSystem("custom_app")

    spec = {
        "backend": True,
        "frontend": True,
        "database": True,
        "custom_features": ["auth", "realtime", "caching"]
    }

    await system.start(spec)

asyncio.run(main())
```

## 📝 License

READ License https://github.com/aatel-license/hypnonyx/blob/main/LICENSE.md

## 🤝 Contributing

Contributi benvenuti! Apri una PR o issue.

## 📬 Contact

Per domande o supporto, apri una issue su GitHub.

---

**Built with ❤️ by the Hypnonyx Multi-Agent System**

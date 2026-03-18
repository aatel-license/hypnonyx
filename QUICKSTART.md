# 🚀 Quick Start Guide - Hypnonyx Multi-Agent System

## Installazione Rapida (5 minuti)

### Prerequisiti

**LM Studio** (necessario per generare codice):

1. Scarica da https://lmstudio.ai/
2. Scarica un modello (consigliato: **DeepSeek Coder 6.7B**)
3. Avvia il server locale (tab "Local Server" → "Start Server")

Vedi [LM_STUDIO_SETUP.md](LM_STUDIO_SETUP.md) per guida dettagliata.

### Setup Hypnonyx

```bash
# 1. Setup automatico
./setup.sh

# 2. Attiva virtual environment
source venv/bin/activate  # Linux/macOS
# oppure
.\venv\Scripts\activate  # Windows

# 3. Test del sistema
python test_system.py

# 4. Esegui demo interattivo
python demo.py
```

## Primo Progetto (1 minuto)

```bash
# Crea un'applicazione full-stack completa
python main.py --project my_first_app

# Output in: projects/my_first_app/
# - backend/     → API REST con FastAPI
# - frontend/    → React app con Vite
# - database/    → Schema SQLite + migrazioni
# - tests/       → Unit, integration, E2E tests
# - devops/      → Docker + CI/CD
# - docs/        → Documentazione auto-generata
```

## Comandi Essenziali

### Skills Management 🆕

```bash
# Le skills vengono cercate in:
# 1. $HOME/.claude/
# 2. .claude/ (root del progetto)

# Creare una skill custom globale
mkdir -p ~/.claude/my-skill
cat > ~/.claude/my-skill/SKILL.md << 'EOF'
---
description: "My global custom skill"
agent_types: ["backend"]
triggers: ["custom", "special"]
---

# My Custom Skill
Your guidelines here...
EOF

# Le skills vengono caricate automaticamente al riavvio!
```

### Creare Progetti

```bash
# Full-stack (default)
python main.py --project ecommerce

# Solo backend
python main.py --project api_service --no-frontend --no-database

# Solo frontend
python main.py --project dashboard --no-backend --no-database

# Backend + Database (no frontend)
python main.py --project data_api --no-frontend

# 🚀 Modalità MVP (Prototipazione Rapida)
# - Salta le review (quorum 3 agents)
# - Salta autenticazione
# - Backend con dati mock
python main.py --project prototype --prompt "App per note" --mvp

# 🔄 Evoluzione Progetto
# - Analizza architettura attuale
# - Genera solo i nuovi task necessari
python main.py --project existing_app --update --prompt "Aggiungi dashboard admin"
```

### Monitorare il Sistema

```bash
# Dashboard Web (Consigliato)
./dashboard.sh  # Avvia su http://localhost:5000

# Log real-time
tail -f memory/system.log

# Memoria globale
cat memory/global_memory.md

# Azioni recenti (SQL)
sqlite3 memory/project_memory.db "SELECT agent, action, description FROM project_memory ORDER BY timestamp DESC LIMIT 10"

# Task completati
sqlite3 memory/project_memory.db "SELECT * FROM tasks WHERE status='completed'"
```

### Setup MQTT (Opzionale)

```bash
# Docker (raccomandato)
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto

# Verifica
mosquitto_sub -t '#' -v
```

## Struttura Output

```
projects/my_first_app/
├── backend/
│   ├── api.py              # REST API con FastAPI
│   ├── auth.py             # JWT authentication
│   ├── business_logic.py   # Business logic
│   ├── requirements.txt    # Python deps
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # React app
│   │   ├── App.css        # Styles
│   │   └── api.js         # API client
│   ├── package.json
│   └── Dockerfile
│
├── database/
│   ├── schema.sql         # DB schema
│   ├── migrations/        # SQL migrations
│   └── run_migrations.py
│
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/             # End-to-end tests
│
├── devops/
│
├── docs/
│   ├── backend.md        # Backend documentation
│   ├── frontend.md       # Frontend documentation
│   ├── database_changes.md
│   ├── devops.md
│   ├── qa_reports.md
│   └── testing.md
│
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions
│
└── .git/                 # Git repo con commit automatici
```

## Esempi di Uso

### 1. E-commerce API

```bash
python main.py --project ecommerce_api
cd projects/ecommerce_api/backend
uvicorn api:app --reload
# API disponibile su http://localhost:8000
```

### 2. Dashboard React

```bash
python main.py --project analytics_dashboard
cd projects/analytics_dashboard/frontend
npm install
npm run dev
# Dashboard su http://localhost:3000
```

### 3. Data Pipeline

```bash
python main.py --project data_pipeline --no-frontend
# Crea backend + database per data processing
```

## Architettura Agenti

### Gli Agenti e i Loro Compiti

1. **Orchestrator** → Coordina, assegna task, monitora
2. **Backend** → API, business logic, auth
3. **Frontend** → UI, components, API integration
4. **Database** → Schema, migrations, optimization
5. **DevOps** → Docker, CI/CD, deployment
6. **QA** → E2E tests, validation, bugs
7. **Testing** → Unit tests, integration, coverage

### Come Comunicano

```
┌─────────────┐
│Orchestrator │ ──┐
└─────────────┘   │
                  │ MQTT/Kafka
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐    ┌───▼───┐    ┌───▼───┐
│Backend│    │Frontend│   │Database│
└───┬───┘    └───┬───┘    └───┬───┘
    │            │            │
    └────────────┴────────────┘
         Message Broker
```

### Sistema Anti-Idle

```python
# Ogni 30 secondi:
if agent.is_idle:
    # Cerca task da altri agenti
    # Offre aiuto
    # Scrive test
    # Fa code review
```

## Troubleshooting Rapido

### Errore: MQTT non connesso

```bash
# Installa MQTT
sudo apt-get install mosquitto  # Ubuntu
brew install mosquitto           # macOS

# Il sistema usa fallback in-memory se MQTT non disponibile
```

### Errore: Module not found

```bash
# Reinstalla dipendenze
pip install -r requirements.txt
```

### Errore: Git not initialized

```bash
cd projects/your_project
git init
git config user.email "agent@devagent.ai"
git config user.name "Hypnonyx"
```

### Performance lente

```bash
# Riduci agenti (modifica main.py)
# Commenta agenti non necessari
# self.agents.append(testing_agent)  # <- commenta
```

## Personalizzazione

### Aggiungere un Agente Custom

Crea `agents/my_agent.py`:

```python
from agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, agent_id, memory, project_root):
        super().__init__(agent_id, "my_type", memory, project_root)

    async def execute(self, task):
        # Tua logica qui
        return {"status": "completed"}
```

Aggiungi a `main.py`:

```python
from agents.my_agent import MyAgent

# In _create_agents()
my_agent = MyAgent("my_001", self.memory, str(self.project_root))
self.agents.append(my_agent)
```

### Modificare Task del Progetto

Edita `agents/orchestrator_agent.py` → `_decompose_project()`:

```python
# Aggiungi nuovi task
tasks.append({
    "task_id": f"my_task_{uuid.uuid4().hex[:8]}",
    "type": "my_custom_task",
    "agent_type": "my_type",
    "description": "My custom task",
    "priority": 3
})
```

## Best Practices

1. **Usa Git**: Ogni progetto ha Git auto-inizializzato
2. **Monitora Log**: Segui `memory/system.log` in real-time
3. **Review Commits**: Gli agenti fanno commit, tu fai review
4. **Test Prima**: Esegui `test_system.py` dopo modifiche
5. **Backup Memory**: Il DB è in `memory/project_memory.db`

## Links Utili

- **Documentazione Completa**: `README.md`
- **Demo Interattivo**: `python demo.py`
- **Test Sistema**: `python test_system.py`
- **Config**: `.env`

## Support

Per problemi o domande:

1. Controlla `memory/system.log`
2. Esegui `python test_system.py`
3. Verifica `.env` configuration
4. Apri issue su GitHub

---

**Pronto? Inizia ora!**

```bash
python main.py --project awesome_app
```

🎉 Il tuo primo progetto verrà creato in ~30 secondi!

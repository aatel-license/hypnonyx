# hypnonyx
![Alt text](https://github.com/aatel-license/hypnonyx/blob/main/image.png "hypnonyx")
Hypnonyx is an AI agent designed to operate in Swarm mode, following Agile and Scrum principles. Tireless, it was "born" from the sleepless nights of its developers, optimizing code collaboratively and autonomously. Hypnonyx can coordinate multiple instances of itself to maximize productivity and software quality.

# 🤖 Hypnonyx Multi-Agent System

Autonomous multi-agent system for complete software development, featuring a central orchestrator, communication via message broker, persistent memory, and Git automation.

## 🎯 Features

### **7 Specialized Agents**

1. **Orchestrator Agent** – Coordinates all agents, assigns tasks, monitors progress
2. **Backend Developer Agent** – Implements APIs, business logic, authentication
3. **Frontend Developer Agent** – Creates UI, integrates with backend
4. **Database Administrator Agent** – Designs schema, creates migrations
5. **DevOps Engineer Agent** – Docker, CI/CD, deployment
6. **QA Agent** – End-to-end testing, validation, bug reporting
7. **Testing Agent** – Unit tests, integration tests, coverage analysis

### **Communication System**

- **MQTT** or **Kafka** for asynchronous communication between agents (OPTIONAL)
- Automatic **in-memory fallback** if broker is unavailable
- Dedicated topics: `tasks.new`, `tasks.completed`, `bugs.reported`, `agent.heartbeat`, etc.
- **Works out-of-the-box with no configuration required!** 🎯

### **💻 Dashboard & Monitoring** 🆕

- **Interactive Web Dashboard**: Displays task status in real time.
- **Kanban Board**: Tracks each agent's progress.
- **Rejection Details**: Shows reviewer feedback and rejection reasons directly on cards.
- **Activity Log**: Live stream of all system actions.

### **🔄 Evolution & Persistence** 🆕

- **Auto-Resume**: Picks up exactly where it left off after an interruption (Ctrl+C).
- **Project Evolution**: Allows updating existing projects with new prompts (`--update`).
- **MVP Mode**: Ultra-fast development without Auth and without the review cycle (`--mvp`).

### **Dynamic Skills System** 🆕

- **Dynamic loading** of best practices and guidelines
- **Default skills**: backend-api, frontend-react, testing-best-practices
- **Auto-detection**: Skills activated automatically based on the task
- **Custom skills**: Create your own skills in `.claude/`
- **YAML Metadata**: Specify agent types, triggers, dependencies
- See [SKILLS_GUIDE.md](SKILLS_GUIDE.md) for full details

### **Persistent Memory**

- **SQLite database** for tracking:
  - Agent actions (who, what, when, commit hash)
  - Tasks and their status
  - Bug reports
  - Architectural decisions
- **Markdown files** in `/memory/`:
  - `global_memory.md` – Global memory
  - `decisions.md` – Decision log
  - `architecture.md` – Architecture documentation
  - `retrospective.md` – Retrospectives

### **Git Automation**

- Automatic commits after each completed task
- Structured commit messages (`feat:`, `fix:`, `refactor:`, etc.)
- Per-agent branches: `agent/backend/backend_001`
- Complete history tracking

### **Anti-Idle System**

- When an agent is idle (>30 seconds without a task):
  - Reports availability
  - Looks for tasks from overloaded agents
  - Offers help to struggling agents
- The orchestrator automatically redistributes tasks

## 📁 Project Structure

```
hypnonyx/
├── main.py                 # Main entrypoint
├── config.py              # Global configuration
├── requirements.txt       # Python dependencies
│
├── core/
│   ├── memory.py          # Persistent memory system
│   └── message_broker.py  # MQTT/Kafka communication
│
├── agents/
│   ├── base_agent.py      # Base class for agents
│   ├── orchestrator_agent.py
│   ├── backend_agent.py
│   ├── frontend_agent.py
│   ├── database_agent.py
│   ├── devops_agent.py
│   ├── qa_agent.py
│   └── testing_agent.py
│
├── memory/                # Memory files
│   ├── project_memory.db
│   ├── global_memory.md
│   ├── decisions.md
│   ├── architecture.md
│   └── retrospective.md
│
├── docs/                  # Generated documentation
│
└── projects/              # Projects created by agents
    └── <project_name>/
        ├── backend/
        ├── frontend/
        ├── database/
        ├── tests/
        └── devops/
```

## 🚀 Quick Start

### Prerequisites

**1. LM Studio** (required):

- Download: https://lmstudio.ai/
- Download model: **DeepSeek Coder 6.7B** (recommended)
- Start local server
- Full guide: [LM_STUDIO_SETUP.md](LM_STUDIO_SETUP.md)

**2. Python 3.10+** and **Git**

### 1. Installation

```bash
# Clone the repository
git clone <repo-url>
cd hypnonyx

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (Optional)

Create a `.env` file:

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

### 3. Start the System

```bash
# Specify a specific technology stack
python main.py --project my_app --backend fastapi --frontend react --database postgres

# 🔄 Resume an existing project (auto-detect or manual)
python main.py --project ecommerce --resume

# 🚀 MVP Mode (Fast, No Auth, No Review)
python main.py --project startup_idea --prompt "Landing page for AI" --mvp

# 🛠️ Evolve an existing project
python main.py --project ecommerce --update --prompt "Add cart and checkout"

# 🗑️ Full reset
python main.py --project test_app --reset
```

### 4. Dashboard (Real-Time)

```bash
# Start the web dashboard
./dashboard.sh
# Open http://localhost:5000
```

### 4. MQTT Setup (Optional but Recommended)

```bash
# With Docker
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto

# Or install locally
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients

# macOS
brew install mosquitto
brew services start mosquitto
```

## 🔧 How It Works

### Project Creation Workflow

1. **Orchestrator** receives project creation request
2. **Decomposition** into atomic tasks (API, UI, DB, tests, CI/CD, etc.)
3. **Dependency calculation** (DB → Backend → Frontend)
4. **Task distribution** to various agents via message broker
5. **Parallel execution** with monitoring
6. **Auto-commit** to Git after each task
7. **Persistent logging** to database and markdown

### Agent Communication

```python
# Agent A publishes a task
await broker.publish( get_topics(self.project_id)["TASKS_NEW"], {
    "task_id": "backend_api_001",
    "type": "implement_api",
    "agent_type": "backend",
    "description": "Implement REST API"
})

# Agent B (backend) receives and executes
# When complete:
await broker.publish( get_topics(self.project_id)["TASKS_COMPLETED"], {
    "task_id": "backend_api_001",
    "result": {"status": "completed"}
})

# Orchestrator monitors and unblocks dependent tasks
```

### Anti-Idle System

```python
# Every 5 seconds each agent sends a heartbeat
await broker.send_heartbeat(status="active" | "idle")

# If idle >30s:
await broker.report_idle()

# Orchestrator assigns a new task
await broker.publish( get_topics(self.project_id)["TASKS_ASSIGNED"], {
    "task_id": "help_backend_001",
    "assigned_to": "testing_001"
})
```

### Memory & Git

Every action is tracked:

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

## 📊 Monitoring

### Real-Time Logs

```bash
# System log
tail -f memory/system.log

# Global memory
cat memory/global_memory.md

# Architectural decisions
cat memory/decisions.md

# Completed tasks
sqlite3 memory/project_memory.db "SELECT * FROM project_memory ORDER BY timestamp DESC LIMIT 10;"
```

### Database Queries

```sql
-- Recent actions
SELECT agent, action, description, timestamp
FROM project_memory
ORDER BY timestamp DESC LIMIT 20;

-- Tasks per agent
SELECT agent, COUNT(*) as task_count, status
FROM tasks
GROUP BY agent, status;

-- Open bugs
SELECT bug_id, severity, description, reporter_agent
FROM bugs
WHERE status = 'open'
ORDER BY severity DESC;
```

## 🔌 Extensions

### Adding a New Agent

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
        # Implement specific logic
        if task.get("type") == "my_task":
            # Do something
            return {"status": "completed"}

    async def can_help(self, task: Dict) -> bool:
        # Decide if it can help
        return task.get("type") in ["my_task", "related_task"]
```

### Adding New Topics

Edit `config.py`:

```python
get_topics(self.project_id) = {
    # ... existing topics ...
    "MY_NEW_TOPIC": "my.new.topic"
}
```

## 🐛 Troubleshooting

### System Works Without MQTT/Kafka!

The system uses an **automatic in-memory fallback** – no configuration needed!

If you see MQTT errors, you can ignore them or explicitly disable them:

```bash
# In the .env file
USE_MQTT=false
USE_KAFKA=false
```

### Other Common Issues

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the complete guide with solutions for:

- MQTT/Kafka errors
- Module not found
- Git errors
- Database locked
- Performance issues

### Quick Test

```bash
python test_system.py
```

## 📖 Examples

### Full-Stack Project

```bash
python main.py --project ecommerce
```

Generates:

- Backend API with FastAPI
- React frontend with Vite
- SQLite database with schema
- Docker + docker-compose
- GitHub Actions CI/CD
- E2E, unit, and integration tests
- Complete documentation

### Backend API Only

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

Contributions are welcome! Open a PR or issue.

## 📬 Contact

For questions or support, open an issue on GitHub.

---

**Built with ❤️ by the Hypnonyx Multi-Agent System**
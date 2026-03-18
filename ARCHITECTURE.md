# System Overview & Architecture: Hypnonyx Multi-Agent

Hypnonyx Multi-Agent is a sophisticated platform that automates software development using specialized AI agents. It follows an Agile-inspired workflow (Scrum) to decompose, execute, and verify tasks.

## 🏗️ System Architecture

The system is built on a **Modular Multi-Agent Architecture** where specialized agents communicate via a unified message broker.

```mermaid
graph TD
    User([User Request]) --> MAS[Multi-Agent System]
    
    subgraph "Orchestration & Planning"
        Orchestrator[Orchestrator Agent]
        Architect[Architect Agent]
        ScrumMaster[Scrum Master Agent]
    end
    
    subgraph "Execution Agents"
        Backend[Backend Agent]
        Frontend[Frontend Agent]
        Database[Database Agent]
        DevOps[DevOps Agent]
        Researcher[Researcher Agent]
    end
    
    subgraph "Quality & Verification"
        QA[QA Agent]
        Testing[Testing Agent]
        Reviewer[Reviewer Agent]
    end
    
    subgraph "Communication & State"
        Broker{Message Broker<br/>Kafka / MQTT}
        Redis[(Redis Cache)]
        SQLite[(SQLite Memory)]
    end
    
    subgraph "Observability"
        Dashboard[Kanban Dashboard]
        OpenSearch[(OpenSearch + Dashboards)]
        FluentBit[Fluent Bit]
    end

    MAS --> Orchestrator
    Orchestrator <--> Broker
    Execution Agents <--> Broker
    Quality & Verification <--> Broker
    ScrumMaster <--> Broker
    Dashboard <--> SQLite
    Dashboard <--> Broker
```

## 🤖 Agent Roles

| Agent | Responsibility |
| :--- | :--- |
| **Orchestrator** | Manages the project lifecycle, task assignment, and progress monitoring. |
| **Architect** | Decomposes high-level requirements into technical specifications and tasks. |
| **Scrum Master** | Orchestrates Agile ceremonies (Retrospectives, Backlog Refinement) and tracks sprints. |
| **Backend** | Implements server-side logic, APIs, and business modules. |
| **Frontend** | Build UI components, styling, and client-side interactions. |
| **Database** | Manages schema design, migrations, and query optimization. |
| **DevOps** | Handles CI/CD, Docker configurations, and infrastructure setup. |
| **Researcher** | Performs Web/Code searches to provide context and solutions for complex problems. |
| **Reviewer** | Audits code changes and provides feedback or approval. |
| **QA / Testing** | Writes and executes unit/integration tests to ensure code quality. |

## 🛠️ Infrastructure (Docker Services)

The system relies on several containerized services defined in `docker-compose.yml`:

- **Redis**: Used for high-speed caching and volatile state persistence.
- **Mosquitto (MQTT)**: The primary lightweight message broker for real-time agent communication.
- **Kafka**: A high-throughput alternative broker for distributed task handling.
- **OpenSearch Stack**:
    - **OpenSearch**: Stores logs, agent actions, and performance metrics.
    - **Dashboards**: Visualization tool for monitoring system health and agent activity.
    - **Fluent Bit**: Seamlessly forwards system and agent logs to OpenSearch.

## 📊 Kanban Dashboard

The integrated dashboard (`/dashboard`) provides a real-time view of the development process:

1.  **Kanban Board**: Tracks tasks from `Pending` to `Completed`.
2.  **Live Action Logs**: Shows what each agent is doing at any given moment.
3.  **Real-time Updates**: Powered by **FastAPI** and **WebSockets**, giving instant feedback on progress.
4.  **Agile Tracking**: Visualizes Sprint progress and Backlog Refinement items.

## 🔄 Workflow

1.  **Initialization**: User provides a prompt (e.g., "Build an e-commerce API").
2.  **Decomposition**: The **Architect** creates a TOON/JSON task list.
3.  **Execution**: The **Orchestrator** assigns tasks to appropriate agents (Backend, Database, etc.).
4.  **Verification**: The **Reviewer** and **Testing** agents validate the work.
5.  **Ceremonies**: Every $N$ tasks, the **Scrum Master** runs a **Retrospective** to improve the process and a **Backlog Refinement** to plan next steps.
6.  **Evolution**: The system can evolve existing projects by analyzing current architecture and adding new features iteratively.

# 🏗️ Architettura di Sistema: Hypnonyx Multi-Agent

Questo documento descrive l'architettura tecnica di `Hypnonyx`, spiegando come gli agenti collaborano, come avviene la comunicazione e come vengono gestiti i dati e l'interfaccia di monitoraggio.

## 📊 Diagramma Architetturale (Mermaid)

```mermaid
graph TD
    %% Entry Point e User Interaction
    User([Utente / CLI]) --> Main[main.py / Orchestrator]

    %% Communication Layer
    subgraph Communication [Livello di Comunicazione]
        Broker{Message Broker}
        MQTT[MQTT / Mosquitto]
        Kafka[Apache Kafka]
        InMemory[In-Memory Fallback]

        Broker --- MQTT
        Broker --- Kafka
        Broker --- InMemory
    end

    %% Multi-Agent System
    subgraph Agents [Sistema Multi-Agente]
        Main <--> Broker

        Architect[Architect Agent] <--> Broker
        Backend[Backend Agent] <--> Broker
        Frontend[Frontend Agent] <--> Broker
        DBA[Database Agent] <--> Broker
        DevOps[DevOps Agent] <--> Broker
        QA[QA/Testing Agents] <--> Broker
        Researcher[Researcher Agent] <--> Broker
        Reviewer[Reviewer Agent] <--> Broker
    end

    %% Core Services
    subgraph Core [Servizi Core & Risorse]
        LLM[LLM Client<br/>LM Studio / Local LLM]
        SQLite[(Memoria SQLite<br/>Tasks & Logs)]
        Prompts[Prompt Manager<br/>Redis + SQLite]
        Skills[Skill Manager<br/>Best Practices]

        Agents -.-> LLM
        Agents -.-> SQLite
        Agents -.-> Prompts
        Agents -.-> Skills
    end

    %% Monitoring Layer
    subgraph Monitoring [Monitoraggio & Dashboard]
        DashServer[Dashboard Server<br/>FastAPI]
        WebSocket((WebSocket<br/>Real-Time))
        DashUI[Dashboard Web<br/>Glassmorphism UI]

        SQLite <--> DashServer
        Broker <--> DashServer
        DashServer <--> WebSocket
        WebSocket <--> DashUI
    end

    %% Output
    subgraph Output [Generazione Progetto]
        Git[Git Automation<br/>Commits & Branches]
        ProjectFiles[Codice Sorgente<br/>/projects/...]

        Reviewer -.-> Git
        Agents --> ProjectFiles
    end

    %% Styling
    style Communication fill:#f9f,stroke:#333,stroke-width:2px
    style Agents fill:#bbf,stroke:#333,stroke-width:2px
    style Core fill:#dfd,stroke:#333,stroke-width:2px
    style Monitoring fill:#ffd,stroke:#333,stroke-width:2px
    style User fill:#f96,stroke:#333,stroke-width:2px
```

## 📐 Schema Stile PlantUML

```plantuml
@startuml
!theme black-knight
skinparam backgroundColor #1a1a1a
skinparam ArrowColor #3498db
skinparam PackageBackgroundColor #2c3e50
skinparam PackageBorderColor #555
skinparam ActorBorderColor #3498db
skinparam ComponentBackgroundColor #34495e
skinparam ComponentBorderColor #7f8c8d
skinparam ComponentFontColor #ecf0f1

actor "User / CLI" as user

package "Orchestration & Logic" {
  component [main.py] as main
  component [OrchestratorAgent] as orchestrator
}

package "Communication Layer" {
  queue "Message Broker" as broker
  database "Redis (Cache)" as redis
}

package "Agent Swarm" {
  component [ArchitectAgent] as architect
  component [BackendAgent] as backend
  component [FrontendAgent] as frontend
  component [DBAgent] as dba
  component [DevOpsAgent] as devops
  component [QAAgent] as qa
  component [ResearcherAgent] as researcher
  component [ReviewerAgent] as reviewer
}

package "Core Engine" {
  component [LLMClient] as llm
  database "SQLite (Memory DB)" as sqlite
  component [PromptManager] as prompt_mgr
  component [SkillManager] as skill_mgr
}

user --> main
main --> orchestrator
orchestrator <..> broker
architect <..> broker
backend <..> broker
frontend <..> broker
dba <..> broker
devops <..> broker
qa <..> broker
researcher <..> broker
reviewer <..> broker

orchestrator ..> llm
orchestrator ..> sqlite
agents ..> llm : JSON requests
@enduml
```

## 🖋️ Schema Visuale (Box-Drawing Style)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          USER / CLI INTERFACE (main.py)                     │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MESSAGE BROKER (Central Hub)                        │
│             (MQTT / Kafka / In-Memory Fallback System)                      │
└───────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬───┘
        │          │          │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼          ▼          ▼
 ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
 │  ARCHI-  ││ BACKEND  ││ FRONTEND ││ DATABASE ││ DEVOPS   ││ RESEARCH ││ REVIEWER │
 │   TECT   ││  AGENT   ││  AGENT   ││  AGENT   ││  AGENT   ││  AGENT   ││  AGENT   │
 └────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘
      │           │           │           │           │           │           │
      └───────────┴───────────┼───────────┴───────────┴───────────┴───────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CORE ENGINE & RESOURCES                            │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│    LLM CLIENT        │    MEMORY SYSTEM     │      PROMPT MANAGER           │
│ (LM Studio / API)    │ (SQLite / Markdown)  │     (Redis + SQLite)          │
└──────────┬───────────┴──────────┬───────────┴────────────┬──────────────────┘
           │                      │                        │
           ▼                      ▼                        ▼
┌──────────────────────┐┌──────────────────────┐┌─────────────────────────────┐
│   PROJECT OUTPUT     ││  DASHBOARD SERVER    ││      SKILL SYSTEM           │
│ (/projects/code)     ││ (FastAPI + WS)       ││   (.agent/workflows)        │
└──────────────────────┘└──────────┬───────────┘└─────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WEB MONITORING INTERFACE                             │
│                      (Kanban Board + Real-time Logs)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🧩 Descrizione dei Componenti

### 1. Orchestrator & Agents

Il cuore del sistema è un'architettura basata su agenti specializzati:

- **Orchestrator**: Riceve l'input dell'utente, decompone il progetto in task atomici e monitora lo stato globale.
- **Agenti Operativi**: (Backend, Frontend, DB, etc.) eseguono i task assegnati comunicando via broker.
- **Reviewer Agent**: Agisce come "gatekeeper", validando il lavoro degli altri agenzie e fornendo feedback per ri-esecuzioni (retry).

### 2. Message Broker (MQTT / Kafka)

Gli agenti comunicano in modo asincrono tramite topic:

- `tasks.new`: Notifica di nuovi task disponibili.
- `tasks.assigned`: Conferma di presa in carico.
- `tasks.completed`: Risultato dell'esecuzione.
- `agent.heartbeat`: Monitoraggio dello stato di salute degli agenti.
- _Fallback_: Se nessun broker esterno è configurato, il sistema utilizza una coda in-memory.

### 3. Core Engine

- **LLM Client**: Gestisce le chiamate al modello linguistico (default: LM Studio) con logica di retry e parsing JSON robusto.
- **Memory System**: Utilizza SQLite per i dati strutturati (Task, Logs, Bug) e file Markdown per la memoria storica e le decisioni.
- **Prompt Manager**: Gestisce la versione dei prompt degli agenti, permettendo aggiornamenti dinamici senza riavviare il codice.

### 4. Dashboard & Monitoring

Un server FastAPI dedicato espone API per la dashboard:

- **WebSocket**: Notifica istantaneamente il frontend di ogni cambio di stato.
- **Kanban UI**: Permette una visualizzazione chiara dei task in `Pending`, `In Progress`, `Review` e `Completed`.

### 5. Git & Persistence

Ogni volta che un agente completa un task con successo, il sistema effettua automaticamente un commit Git con un messaggio strutturato, garantendo la tracciabilità completa di ogni riga di codice generata.

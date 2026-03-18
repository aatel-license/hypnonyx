# 🎯 Sistema di Skills - Guida Completa

Il sistema di skills permette agli agenti di caricare dinamicamente best practices e linee guida per eseguire task specifici.

## 📚 Cos'è una Skill?

Una **skill** è un documento markdown che contiene:

- Best practices per un compito specifico
- Esempi di codice
- Linee guida architetturali
- Pattern da seguire

### **Globali ($HOME)**

```
$HOME/
└── .claude/
    ├── backend-api/
    │   └── SKILL.md
    └── common-patterns/
        └── SKILL.md
```

### **Workspace Root (Veloar Context)**

```
hypnonyx/  (Root del sistema)
├── .claude/         (Skills condivise per tutti i progetti)
│   └── frontend-react/
│       └── SKILL.md
├── projects/
│   └── my_project/
└── main.py
```

## ✨ Skills di Default

Il sistema crea automaticamente 3 skills di base:

### 1. `backend-api`

Best practices per sviluppo API REST:

- Design RESTful
- Validazione input
- Gestione errori
- Security patterns
- Testing

### 2. `frontend-react`

Best practices per React:

- Component structure
- State management
- Performance optimization
- Code examples

### 3. `testing-best-practices`

Strategie di testing:

- Unit tests
- Integration tests
- E2E tests
- Coverage analysis

### Metodo 1: Manualmente (Globali)

Crea la directory e il file nella tua HOME:

```bash
mkdir -p ~/.claude/my-skill
nano ~/.claude/my-skill/SKILL.md
```

### Metodo 2: Nella Root del Sistema

```bash
mkdir -p .claude/my-skill
nano .claude/my-skill/SKILL.md
```

### Metodo 2: Programmaticamente

````python
from core.skills import SkillManager

manager = SkillManager()
manager.initialize()

manager.create_skill(
    "database-optimization",
    """# Database Optimization Skill

## Indexing Best Practices
- Create indexes on foreign keys
- Index frequently queried columns
- Avoid over-indexing

## Query Optimization
- Use EXPLAIN to analyze queries
- Avoid SELECT *
- Use prepared statements

## Example
```sql
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_order_user ON orders(user_id);
````

""",
metadata={
"description": "Database optimization techniques",
"agent_types": ["database", "backend"],
"triggers": ["optimize", "performance", "index"],
"dependencies": []
}
)

````

## 📝 Formato Skill con Metadata

Le skills possono includere metadata YAML all'inizio:

```markdown
---
description: "API security best practices"
agent_types: ["backend"]
triggers: ["security", "auth", "jwt"]
dependencies: []
---

# API Security Skill

## Authentication
- Use JWT tokens
- Implement refresh tokens
...
````

### Campi Metadata

- **description**: Breve descrizione della skill
- **agent_types**: Lista di agenti che possono usare questa skill
  - `backend`, `frontend`, `database`, `devops`, `qa`, `testing`
  - Se vuoto, tutti gli agenti possono usarla
- **triggers**: Keywords che attivano automaticamente questa skill
- **dependencies**: Altre skills richieste

## 🎬 Come gli Agenti Usano le Skills

### 1. Caricamento Automatico per Tipo

```python
# Gli agenti caricano automaticamente skills rilevanti
# Backend agent → carica skills con agent_types: ["backend"]
```

### 2. Trigger Automatici

```python
# Task con description: "create REST API with authentication"
# → Skill "backend-api" viene auto-caricata (trigger: "api", "rest")
```

### 3. Skill Esplicita

```python
# Specifica skill nel task
task = {
    "task_id": "impl_001",
    "type": "implement_feature",
    "description": "Implement user authentication",
    "skill": "backend-api"  # ← Specifica esplicitamente
}
```

## 💡 Esempi Pratici

### Esempio 1: Skill per Testing

````markdown
# Testing Best Practices Skill

## Test Structure

### AAA Pattern

- **Arrange**: Setup test data
- **Act**: Execute the action
- **Assert**: Verify results

## Example: Backend Unit Test

```python
def test_create_user():
    # Arrange
    user_data = {"name": "John", "email": "john@example.com"}

    # Act
    response = client.post("/users", json=user_data)

    # Assert
    assert response.status_code == 201
    assert response.json()["name"] == "John"
```
````

## Coverage Goals

- Aim for >80% coverage
- Focus on critical paths
- Test edge cases

````

### Esempio 2: Skill per Docker

```markdown
---
description: "Docker and containerization best practices"
agent_types: ["devops"]
triggers: ["docker", "container", "dockerfile"]
---

# Docker Best Practices Skill

## Dockerfile Optimization

### Multi-stage Builds
```dockerfile
# Build stage
FROM node:18 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM node:18-alpine
WORKDIR /app
COPY --from=build /app/dist ./dist
CMD ["node", "dist/main.js"]
````

### Best Practices

- Use specific base image versions
- Minimize layers
- Use .dockerignore
- Don't run as root

````

### Esempio 3: Skill per Security

```markdown
---
description: "Security best practices for web applications"
agent_types: ["backend", "frontend", "devops"]
triggers: ["security", "auth", "vulnerability"]
---

# Security Best Practices Skill

## Input Validation
- Always validate user input
- Use parameterized queries
- Sanitize HTML output

## Authentication
- Use bcrypt for passwords (min 10 rounds)
- Implement rate limiting
- Use HTTPS only

## Example: Password Hashing
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
````

````

## 🔍 Query e Debug Skills

### Lista Skills Disponibili

```python
from core.skills import SkillManager

manager = SkillManager()
manager.initialize()

print("Skills disponibili:")
for skill_name in manager.list_skills():
    print(f"  - {skill_name}")
````

### Vedere Contenuto Skill

```python
skill_content = manager.get_skill("backend-api")
print(skill_content)
```

### Trovare Skill per Trigger

```python
# Trova skill che matchano "api security"
skill_name = manager.find_skill_by_trigger("api security")
print(f"Skill trovata: {skill_name}")
```

### Skills per Tipo Agente

```python
# Ottieni tutte le skills per backend
backend_skills = manager.get_skills_for_agent("backend")
print(f"Backend ha {len(backend_skills)} skills")
```

## 🎯 Best Practices per Scrivere Skills

### 1. Sii Specifico

❌ "Write good code"
✅ "Use Pydantic for input validation in FastAPI endpoints"

### 2. Include Esempi

Sempre includere esempi di codice funzionanti

### 3. Organizza per Sezioni

```markdown
# Skill Name

## Overview

Brief description

## Best Practices

Bullet points

## Examples

Code samples

## Common Pitfalls

What to avoid
```

### 4. Usa Trigger Appropriati

```yaml
triggers: ["api", "rest", "endpoint", "fastapi"]
```

### 5. Specifica Agent Types

```yaml
agent_types: ["backend"]  # Solo backend agents
# oppure
agent_types: []  # Tutti gli agents
```

## 🔄 Workflow con Skills

```
1. Task creato
   ↓
2. Agent riceve task
   ↓
3. Agent cerca skill appropriata:
   - Skill esplicita nel task?
   - Trigger match nel description?
   - Skills per il suo agent_type?
   ↓
4. Skill caricata e applicata
   ↓
5. Agent esegue task seguendo la skill
   ↓
6. Log: skill usata sì/no
```

## 📊 Monitoraggio Usage Skills

```sql
-- Query per vedere quante volte le skills sono state usate
SELECT
    metadata,
    COUNT(*) as usage_count
FROM project_memory
WHERE metadata LIKE '%"used_skill": true%'
GROUP BY metadata;
```

## 🚀 Tips Avanzati

### Skill Composte

Crea skills che referenziano altre:

```yaml
dependencies: ["backend-api", "testing-best-practices"]
```

### Skill per Progetti Specifici

Crea skills custom per il tuo dominio:

- `ecommerce-patterns.md`
- `fintech-compliance.md`
- `gaming-optimization.md`

### Versionare Skills

Committa le skills nel Git del progetto:

```bash
git add .claude/
git commit -m "Add custom skills for project"
```

## 🎓 Esempi Completi

### Skill: GraphQL API

````markdown
---
description: "GraphQL API development with best practices"
agent_types: ["backend"]
triggers: ["graphql", "gql", "apollo"]
---

# GraphQL API Development Skill

## Schema Design

### Types

```graphql
type User {
  id: ID!
  name: String!
  email: String!
  posts: [Post!]!
}

type Post {
  id: ID!
  title: String!
  content: String!
  author: User!
}
```
````

### Queries and Mutations

```graphql
type Query {
  user(id: ID!): User
  users: [User!]!
}

type Mutation {
  createUser(name: String!, email: String!): User!
}
```

## Resolver Implementation (Python + Strawberry)

```python
import strawberry
from typing import List

@strawberry.type
class User:
    id: int
    name: str
    email: str

@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: int) -> User:
        # Implementation
        return get_user_by_id(id)

    @strawberry.field
    def users(self) -> List[User]:
        return get_all_users()
```

## Best Practices

- Use DataLoader for N+1 prevention
- Implement pagination
- Add proper error handling
- Use fragments for reusability

```

---

**Le skills rendono il sistema intelligente e adattivo! 🚀**
```

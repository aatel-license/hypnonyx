"""
Sistema di Skills Dinamiche per Hypnonyx Multi-Agent System

Permette agli agenti di caricare e utilizzare skills dalla directory .claude/
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
import yaml
import json

logger = logging.getLogger(__name__)


class SkillManager:
    """Gestisce il caricamento e l'utilizzo di skills dinamiche da percorsi multipli"""

    def __init__(self, skills_dirs: Optional[List[str]] = None):
        self.skills_dirs: List[Path] = (
            [Path(d) for d in skills_dirs] if skills_dirs else []
        )
        self.skills: Dict[str, Dict] = {}
        self.skills_cache: Dict[str, str] = {}

    def initialize(self, workspace_root: Optional[Path] = None):
        """Inizializza il sistema di skills cercando in percorsi globali e locali"""
        self.skills_dirs = []

        # 1. $HOME/.claude
        home_claude = Path.home() / ".claude"
        if home_claude.exists():
            self.skills_dirs.append(home_claude)

        # 2. Workspace Root .claude
        if workspace_root:
            ws_claude = workspace_root / ".claude"
            if ws_claude.exists():
                self.skills_dirs.append(ws_claude)

        # Log dei percorsi trovati
        for d in self.skills_dirs:
            logger.info(f"Skill search path: {d}")

        # Carica skills esistenti da tutti i percorsi
        self.load_all_skills()

    def load_all_skills(self):
        """Carica tutte le skills disponibili da tutti i directory configurati"""
        self.skills = {}
        self.skills_cache = {}

        for s_dir in self.skills_dirs:
            if not s_dir.exists():
                continue

            for skill_dir in s_dir.iterdir():
                if skill_dir.is_dir():
                    skill_name = skill_dir.name
                    # Evitiamo di sovrascrivere se già caricata da un percorso a priorità maggiore
                    if skill_name not in self.skills:
                        self._load_skill(skill_name, s_dir)

        logger.info(f"Caricate {len(self.skills)} skills totali")

    def _load_skill(
        self, skill_name: str, base_dir: Optional[Path] = None
    ) -> Optional[Dict]:
        """Carica una singola skill da un percorso specifico o da quelli noti"""
        if base_dir:
            skill_path = base_dir / skill_name / "SKILL.md"
        else:
            # Cerca tra i percorsi noti
            skill_path = None
            for s_dir in self.skills_dirs:
                temp_path = s_dir / skill_name / "SKILL.md"
                if temp_path.exists():
                    skill_path = temp_path
                    break

        if not skill_path or not skill_path.exists():
            logger.warning(f"Skill file non trovato per: {skill_name}")
            return None

        try:
            content = skill_path.read_text(encoding="utf-8")
            self.skills_cache[skill_name] = content

            # Parse metadata se presente
            metadata = self._parse_skill_metadata(content)
            self.skills[skill_name] = {
                "name": skill_name,
                "path": str(skill_path),
                "content": content,
                "metadata": metadata,
            }

            logger.info(f"✓ Skill caricata: {skill_name} da {skill_path.parent}")
            return self.skills[skill_name]

        except Exception as e:
            logger.error(f"Errore caricamento skill {skill_name}: {e}")
            return None

    def _parse_skill_metadata(self, content: str) -> Dict:
        """Estrae metadata dalla skill (se presente)"""
        metadata = {
            "description": "",
            "agent_types": [],
            "triggers": [],
            "dependencies": [],
        }

        # Cerca blocco metadata YAML (se presente)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    yaml_content = parts[1].strip()
                    metadata.update(yaml.safe_load(yaml_content))
                except:
                    pass

        return metadata

    def get_skill(self, skill_name: str) -> Optional[str]:
        """Ottiene il contenuto di una skill"""
        if skill_name in self.skills_cache:
            return self.skills_cache[skill_name]

        # Prova a caricarla
        skill = self._load_skill(skill_name)
        return skill["content"] if skill else None

    def list_skills(self) -> List[str]:
        """Lista tutte le skills disponibili"""
        return list(self.skills.keys())

    def get_skills_for_agent(self, agent_type: str) -> List[Dict]:
        """Ottiene le skills rilevanti per un tipo di agente"""
        relevant = []

        for skill_name, skill_data in self.skills.items():
            metadata = skill_data.get("metadata", {})
            agent_types = metadata.get("agent_types", [])

            # Se non specificato, la skill è per tutti
            if not agent_types or agent_type in agent_types:
                relevant.append(skill_data)

        return relevant

    def create_skill(
        self, skill_name: str, content: str, metadata: Optional[Dict] = None
    ):
        """Crea una nuova skill"""
        skill_dir = self.skills_dir / skill_name
        skill_dir.mkdir(exist_ok=True, parents=True)

        skill_file = skill_dir / "SKILL.md"

        # Aggiungi metadata se presente
        if metadata:
            yaml_header = "---\n"
            yaml_header += yaml.dump(metadata, default_flow_style=False)
            yaml_header += "---\n\n"
            content = yaml_header + content

        skill_file.write_text(content, encoding="utf-8")

        # Ricarica la skill
        self._load_skill(skill_name)

        logger.info(f"✓ Skill creata: {skill_name}")

    def apply_skill_to_prompt(self, skill_name: str, base_prompt: str) -> str:
        """Applica una skill a un prompt"""
        skill_content = self.get_skill(skill_name)

        if not skill_content:
            logger.warning(f"Skill non trovata: {skill_name}")
            return base_prompt

        # Combina skill e prompt
        enhanced_prompt = f"""
# Skill: {skill_name}

{skill_content}

---

# Task

{base_prompt}
"""

        return enhanced_prompt

    def find_skill_by_trigger(self, text: str) -> Optional[str]:
        """Trova una skill basandosi su trigger keywords"""
        text_lower = text.lower()

        for skill_name, skill_data in self.skills.items():
            metadata = skill_data.get("metadata", {})
            triggers = metadata.get("triggers", [])

            for trigger in triggers:
                if trigger.lower() in text_lower:
                    return skill_name

        return None


# Integrazione con gli agenti
class SkillAwareAgent:
    """Mixin per agenti che supportano skills"""

    def __init__(self, *args, skill_manager: Optional[SkillManager] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.skill_manager = skill_manager or SkillManager()
        self.active_skills: List[str] = []

    async def load_skill_for_task(self, task: Dict) -> Optional[str]:
        """Carica la skill appropriata per un task"""
        task_description = task.get("description", "")
        task_type = task.get("type", "")

        # Cerca skill esplicita
        requested_skill = task.get("skill")
        if requested_skill:
            return self.skill_manager.get_skill(requested_skill)

        # Cerca per trigger
        skill_name = self.skill_manager.find_skill_by_trigger(task_description)
        if skill_name:
            logger.info(
                f"Skill auto-rilevata: {skill_name} per task {task.get('task_id')}"
            )
            return self.skill_manager.get_skill(skill_name)

        # Cerca skills per il tipo di agente
        agent_skills = self.skill_manager.get_skills_for_agent(self.agent_type)

        # Usa la prima skill rilevante
        if agent_skills:
            return agent_skills[0]["content"]

        return None

    def enhance_prompt_with_skill(
        self, prompt: str, skill_content: Optional[str]
    ) -> str:
        """Arricchisce un prompt con il contenuto di una skill"""
        if not skill_content:
            return prompt

        return f"""
<skill_context>
{skill_content}
</skill_context>

<task>
{prompt}
</task>

Please follow the guidelines in the skill_context while completing the task.
"""


def create_default_skills(skills_dir: Path):
    """Crea alcune skills di default"""
    manager = SkillManager(str(skills_dir))

    # Skill per backend API
    manager.create_skill(
        "backend-api",
        """# Backend API Development Skill

## Best Practices

### API Design
- Use RESTful conventions
- Proper HTTP methods (GET, POST, PUT, DELETE)
- Meaningful endpoint names
- Versioning (e.g., /api/v1/)
- Proper status codes

### Code Structure
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    description: str

@app.post("/api/v1/items")
async def create_item(item: Item):
    # Implementation
    return {"id": 1, **item.dict()}
```

### Security
- Input validation with Pydantic
- Authentication/Authorization
- Rate limiting
- CORS configuration
- SQL injection prevention

### Testing
- Write unit tests for each endpoint
- Test edge cases
- Use fixtures for test data
""",
        metadata={
            "description": "Best practices for backend API development",
            "agent_types": ["backend"],
            "triggers": ["api", "endpoint", "rest", "backend"],
            "dependencies": [],
        },
    )

    # Skill per frontend React
    manager.create_skill(
        "frontend-react",
        """# React Frontend Development Skill

## Best Practices

### Component Structure
- Functional components with hooks
- Props validation with PropTypes or TypeScript
- Separation of concerns (presentational vs container)

### State Management
- useState for local state
- useContext for shared state
- React Query for server state

### Code Example
```jsx
import { useState, useEffect } from 'react'
import axios from 'axios'

function ItemList() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchItems()
  }, [])

  const fetchItems = async () => {
    try {
      const response = await axios.get('/api/v1/items')
      setItems(response.data)
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div>Loading...</div>

  return (
    <div>
      {items.map(item => (
        <div key={item.id}>{item.name}</div>
      ))}
    </div>
  )
}
```

### Performance
- Use React.memo for expensive components
- Lazy loading with React.lazy
- Code splitting
- Virtual scrolling for long lists
""",
        metadata={
            "description": "React development best practices",
            "agent_types": ["frontend"],
            "triggers": ["react", "ui", "component", "frontend"],
            "dependencies": [],
        },
    )

    # Skill per testing
    manager.create_skill(
        "testing-best-practices",
        """# Testing Best Practices Skill

## Test Structure

### Unit Tests
- Test individual functions/methods
- Mock external dependencies
- Aim for >80% coverage

### Integration Tests
- Test component interactions
- Use test database
- Test API endpoints

### E2E Tests
- Test complete user workflows
- Use realistic data
- Test critical paths

## Example: Backend Unit Test
```python
import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_create_item():
    response = client.post(
        "/api/v1/items",
        json={"name": "Test", "description": "Test desc"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test"
    assert "id" in data
```

## Coverage Analysis
- Use pytest-cov for Python
- Use Jest for JavaScript
- Aim for high coverage but focus on critical code
""",
        metadata={
            "description": "Testing best practices and patterns",
            "agent_types": ["testing", "qa"],
            "triggers": ["test", "testing", "coverage", "pytest"],
            "dependencies": [],
        },
    )

    logger.info("✓ Skills di default create")


if __name__ == "__main__":
    # Test del sistema di skills
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        skills_path = Path(tmpdir) / ".claude"

        # Crea skills di default
        create_default_skills(skills_path)

        # Testa il manager
        manager = SkillManager(str(skills_path))
        manager.initialize()

        print(f"Skills disponibili: {manager.list_skills()}")

        # Testa get skill
        skill = manager.get_skill("backend-api")
        if skill:
            print(f"\n✓ Skill 'backend-api' caricata ({len(skill)} chars)")

        # Testa ricerca per trigger
        found = manager.find_skill_by_trigger("create a REST api")
        print(f"\n✓ Skill trovata per trigger 'REST api': {found}")

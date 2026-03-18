from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
)
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import sys
import json
import hashlib
from pathlib import Path
from typing import Optional, Set

# Aggiungi la radice del progetto al path per importare core
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory import MemorySystem

app = FastAPI(title="Hypnonyx Kanban Dashboard")

# CORS per sviluppo locale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = MemorySystem()


# Gestione WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()


# Background task per il Real-time
async def monitor_changes():
    """Monitora il database per cambiamenti e notifica via WebSocket"""
    last_hash = ""
    while True:
        try:
            # Calcola un hash veloce dello stato corrente dei task e log
            tasks = await memory.get_all_tasks()
            logs = await memory.get_recent_actions(limit=5)

            state = json.dumps({"tasks": tasks, "logs": logs}, default=str)
            current_hash = hashlib.md5(state.encode()).hexdigest()

            if current_hash != last_hash:
                last_hash = current_hash
                await manager.broadcast(json.dumps({"type": "update_ready"}))

            await asyncio.sleep(0.5)  # Check ogni 500ms
        except Exception:
            await asyncio.sleep(2)


@app.on_event("startup")
async def startup():
    await memory.initialize()
    asyncio.create_task(monitor_changes())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/projects")
async def get_projects():
    try:
        projects = await memory.get_projects()
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    try:
        await memory.clear_project_data(project_id)
        return {
            "status": "success",
            "message": f"Project {project_id} data wiped from database",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks")
async def get_tasks(project_id: Optional[str] = Query(None)):
    try:
        tasks = await memory.get_all_tasks(project_id=project_id)
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/retrospectives")
async def get_retrospectives(project_id: Optional[str] = Query(None)):
    try:
        return await memory.get_retrospectives(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/releases")
async def get_releases(project_id: Optional[str] = Query(None)):
    """Restituisce la lista delle release del progetto"""
    try:
        if not project_id:
            projects = await memory.get_projects()
            project_id = projects[0] if projects else None
        if not project_id:
            return []
        return await memory.get_releases(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/refinement")
async def get_refinement_proposals(
    project_id: Optional[str] = Query(None), sprint_id: Optional[int] = Query(None)
):
    """Restituisce le proposte di Backlog Refinement"""
    try:
        if not project_id:
            projects = await memory.get_projects()
            project_id = projects[0] if projects else None
        if not project_id:
            return []
        return await memory.get_refinement_proposals(project_id, sprint_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sprint-counter")
async def get_sprint_counter(project_id: Optional[str] = Query(None)):
    """Restituisce il contatore sprint (totale completati, release cycle progress)"""
    try:
        if not project_id:
            projects = await memory.get_projects()
            project_id = projects[0] if projects else None
        if not project_id:
            return {"total_sprints_completed": 0, "current_release_sprint_start": 1}
        from config import RELEASE_SPRINT_INTERVAL

        counter = await memory.get_sprint_counter(project_id)
        total = counter.get("total_sprints_completed", 0)
        counter["sprints_to_next_release"] = RELEASE_SPRINT_INTERVAL - (
            total % RELEASE_SPRINT_INTERVAL
        )
        counter["release_progress_pct"] = int(
            (total % RELEASE_SPRINT_INTERVAL) / RELEASE_SPRINT_INTERVAL * 100
        )
        return counter
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs")
async def get_logs(project_id: Optional[str] = Query(None), limit: int = 50):
    try:
        logs = await memory.get_recent_actions(limit=limit, project_id=project_id)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status(project_id: Optional[str] = Query(None)):
    """Restituisce uno stato sintetico degli agenti basato sui log recenti"""
    try:
        logs = await memory.get_recent_actions(limit=100, project_id=project_id)
        agents = {}
        for log in logs:
            name = log["agent"]
            if name not in agents:
                agents[name] = {
                    "last_action": log["action"],
                    "timestamp": log["timestamp"],
                    "description": log["description"],
                }
        return agents
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents")
async def get_agents(project_id: Optional[str] = Query(None)):
    """Restituisce le statistiche e i prompt correnti degli agenti"""
    try:
        stats = await memory.get_agent_stats(project_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PromptUpdate(BaseModel):
    system_prompt: str


class DocInput(BaseModel):
    doc_type: str
    source: str
    content: str


@app.post("/api/agents/{agent_type}/prompt")
async def update_agent_prompt(agent_type: str, update: PromptUpdate):
    """Aggiorna il system prompt di un agente"""
    try:
        await memory.update_agent_prompt(agent_type, update.system_prompt)
        return {"status": "success", "message": f"Prompt for {agent_type} updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- AGENT DOCUMENTS API ---


@app.get("/api/agents/{agent_type}/docs")
async def get_agent_docs(agent_type: str):
    """Ottieni la lista dei documenti per un agente"""
    try:
        return await memory.get_agent_documents(agent_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_type}/docs")
async def add_agent_doc(agent_type: str, doc: DocInput):
    """Aggiunge un documento (es. URL parsato dal frontend o testo)"""
    try:
        content = doc.content
        if doc.doc_type == "url" and not content.strip():
            # Scrape the URL and extract visible text
            try:
                import aiohttp
                from bs4 import BeautifulSoup

                async with aiohttp.ClientSession(
                    headers={"User-Agent": "Mozilla/5.0 Hypnonyx-Bot/1.0"}
                ) as session:
                    async with session.get(
                        doc.source, timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        resp.raise_for_status()
                        html = await resp.text(errors="replace")
                        soup = BeautifulSoup(html, "html.parser")
                        # Remove script/style noise
                        for tag in soup(["script", "style", "nav", "footer"]):
                            tag.decompose()
                        content = soup.get_text(separator="\n", strip=True)
                        content = content[:50000]  # cap at ~50k chars
            except Exception as scrape_err:
                raise HTTPException(
                    status_code=422,
                    detail=f"Impossibile scrapare l'URL: {scrape_err}",
                )

        doc_id = await memory.add_agent_document(
            agent_type, doc.doc_type, doc.source, content
        )
        return {"status": "success", "id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/docs/{doc_id}")
async def delete_agent_doc(doc_id: str):
    """Elimina un documento"""
    try:
        await memory.delete_agent_document(doc_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_type}/docs/upload")
async def upload_agent_doc(agent_type: str, file: UploadFile = File(...)):
    """Carica e parsa un PDF, DOCX o TXT al volo dalla UI"""
    try:
        raw_bytes = await file.read()
        text_content = ""
        fname = file.filename.lower()

        if fname.endswith(".pdf"):
            import PyPDF2
            import io

            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
                for page in pdf_reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text_content += extracted + "\n"
            except Exception as pdf_err:
                raise HTTPException(
                    status_code=422, detail=f"Errore lettura PDF: {pdf_err}"
                )
        elif fname.endswith(".docx"):
            import io
            from docx import Document as DocxDocument

            try:
                doc_obj = DocxDocument(io.BytesIO(raw_bytes))
                text_content = "\n".join(
                    p.text for p in doc_obj.paragraphs if p.text.strip()
                )
            except Exception as docx_err:
                raise HTTPException(
                    status_code=422, detail=f"Errore lettura DOCX: {docx_err}"
                )
        else:
            try:
                text_content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text_content = raw_bytes.decode("latin-1", errors="replace")

        if not text_content.strip():
            raise HTTPException(
                status_code=422, detail="Il file non contiene testo estraibile."
            )

        doc_type = (
            "pdf"
            if fname.endswith(".pdf")
            else ("docx" if fname.endswith(".docx") else "text")
        )
        doc_id = await memory.add_agent_document(
            agent_type, doc_type, file.filename, text_content
        )
        return {"status": "success", "id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Servire i file statici
static_path = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

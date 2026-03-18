# 🔧 Troubleshooting Guide

## Problemi Comuni e Soluzioni

### 1. Errore MQTT Connection

**Errore:**

```
ERROR - Errore connessione MQTT: 'Client' object has no attribute...
```

**Soluzione:**
Il sistema usa **fallback in-memory** automaticamente. MQTT è opzionale!

```bash
# Opzione 1: Disabilita MQTT (già fatto di default)
# Nel file .env:
USE_MQTT=false

# Opzione 2: Installa e avvia MQTT broker
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto

# Opzione 3: Ignora - il sistema funziona senza MQTT!
```

### 2. AttributeError: '\_fallback_queues'

**Errore:**

```
AttributeError: 'MessageBroker' object has no attribute '_fallback_queues'
```

**Soluzione:**
Questo errore è stato **fixato nella v2.1**. Aggiorna il codice o scarica l'ultima versione.

### 3. Module Not Found

**Errore:**

```
ModuleNotFoundError: No module named 'X'
```

**Soluzione:**

```bash
# Reinstalla dipendenze
pip install -r requirements.txt

# O con virtualenv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Git Errors

**Errore:**

```
GitCommandError: 'git' not found
```

**Soluzione:**

```bash
# Installa Git
sudo apt-get install git  # Ubuntu/Debian
brew install git           # macOS

# Inizializza Git nel progetto
cd projects/your_project
git init
git config user.email "agent@devagent.ai"
git config user.name "Hypnonyx"
```

### 5. Database Locked o UNIQUE Constraint

**Errore:**

```
sqlite3.OperationalError: database is locked
# oppure
sqlite3.IntegrityError: UNIQUE constraint failed
```

**Soluzione:**

```bash
# Opzione 1: Reset database
python db_utils.py reset

# Opzione 2: Rimuovi manualmente
rm memory/project_memory.db

# Opzione 3: Pulisci vecchi dati
python db_utils.py clean 7

# Il database verrà ricreato automaticamente al prossimo avvio
```

### 6. Port Already in Use

**Errore:**

```
OSError: [Errno 48] Address already in use
```

**Soluzione:**

```bash
# Trova processo che usa la porta (es. 8000)
lsof -i :8000

# Killalo
kill -9 <PID>
```

## Configurazione Messaggi Broker

### Senza Broker (Default - Raccomandato per iniziare)

```env
USE_MQTT=false
USE_KAFKA=false
```

Il sistema usa **in-memory fallback** - funziona perfettamente!

### Con MQTT (Opzionale)

```bash
# 1. Installa MQTT
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto

# 2. Abilita nel .env
USE_MQTT=true
MQTT_BROKER=localhost
MQTT_PORT=1883

# 3. Testa connessione
mosquitto_sub -t '#' -v
```

### Con Kafka (Avanzato)

```bash
# 1. Installa Kafka con Docker
docker-compose up -d kafka zookeeper

# 2. Abilita nel .env
USE_KAFKA=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# 3. Testa
kafka-console-consumer --bootstrap-server localhost:9092 --topic test
```

## Logs e Debug

### Database Management

```bash
# Statistiche database
python db_utils.py stats

# Resetta database (se corrotto)
python db_utils.py reset

# Pulisci dati vecchi
python db_utils.py clean 30  # Rimuovi >30 giorni

# Vedi azioni recenti
python db_utils.py actions 50
```

### Controllare i Log

```bash
# Log in tempo reale
tail -f memory/system.log

# Ultimi 50 errori
grep ERROR memory/system.log | tail -50

# Log specifico agente
grep "backend_001" memory/system.log
```

### Aumentare Verbosity

```python
# In main.py, cambia:
logging.basicConfig(level=logging.DEBUG)  # Invece di INFO
```

### Query Database

```bash
# Apri database
sqlite3 memory/project_memory.db

# Query utili
SELECT * FROM project_memory ORDER BY timestamp DESC LIMIT 10;
SELECT agent, COUNT(*) FROM project_memory GROUP BY agent;
SELECT * FROM tasks WHERE status='failed';
SELECT * FROM bugs WHERE status='open';
```

## Performance

### Sistema Lento

```bash
# 1. Riduci agenti attivi
# In main.py, commenta agenti non necessari

# 2. Aumenta timeout
# In config.py:
EXEC_TIMEOUT = 120  # Invece di 60

# 3. Disabilita Git auto-commit
GIT_AUTO_COMMIT=false
```

### Troppa Memoria

```bash
# 1. Limita history nel database
sqlite3 memory/project_memory.db "DELETE FROM project_memory WHERE timestamp < date('now', '-7 days')"

# 2. Pulisci progetti vecchi
rm -rf projects/old_project
```

## 7. Project Evolution & MVP Mode

### 🔄 Project Evolution (`--update`)

**Problema: Il sistema non trova il progetto da aggiornare**

- Assicurati che il nome fornito a `--project` corrisponda esattamente a una cartella in `projects/`.
- La cartella deve contenere il file `docs/architecture.md` per permettere al sistema di capire lo stato attuale.

**Problema: I nuovi task non vengono aggiunti**

- Verifica i log (`memory/system.log`). L'orchestratore deve loggare "🚀 Inizio evoluzione progetto".
- Se non accade, controlla di aver usato correttamente il flag `--update`.

### 🚀 Modalità MVP (`--mvp`)

**Problema: Vorrei l'autenticazione ma non viene generata**

- La modalità MVP è **hardcoded** per saltare l'autenticazione. Se serve Auth, non usare il flag `--mvp`.

**Problema: Il backend non salva i dati**

- In modalità MVP, il BackendAgent è istruito a usare "mock data" se più veloce. Controlla il codice generato in `backend/` per vedere se usa un DB reale o liste in-memory.

## Testing

### Test Sistema

```bash
# Test completo
python test_system.py

# Test specifico
python -c "from core.memory import MemorySystem; import asyncio; asyncio.run(MemorySystem().initialize())"
```

### Test Agente Singolo

```python
# test_single_agent.py
import asyncio
from core.memory import MemorySystem
from agents.backend_agent import BackendAgent

async def test():
    memory = MemorySystem()
    await memory.initialize()

    agent = BackendAgent("test_001", memory, "test_project")

    task = {
        "task_id": "test",
        "type": "implement_api",
        "description": "Test"
    }

    result = await agent.execute(task)
    print(f"Result: {result}")

asyncio.run(test())
```

## FAQ

### Q: Il sistema funziona senza MQTT?

**A:** Sì! Usa fallback in-memory automaticamente. MQTT è solo per distribuire su più macchine.

### Q: Posso usare API key diversa da Anthropic?

**A:** Sì, configura LM_STUDIO_URL nel .env per usare modelli locali o altri provider compatibili.

### Q: Come fermo il sistema?

**A:** `Ctrl+C` o manda SIGTERM: `kill <PID>`

### Q: I file vengono sovrascritti?

**A:** No, ogni esecuzione crea un progetto nuovo o aggiorna quello esistente in modo sicuro.

### Q: Posso customizzare gli agenti?

**A:** Sì! Modifica i file in `agents/` o crea nuovi agenti estendendo `BaseAgent`.

### Q: Le skills sono obbligatorie?

**A:** No, sono opzionali. Gli agenti funzionano anche senza skills.

## Supporto

### Se il problema persiste:

1. **Controlla log**: `tail -f memory/system.log`
2. **Testa componenti**: `python test_system.py`
3. **Verifica config**: `cat .env`
4. **Pulisci e reinstalla**:
   ```bash
   rm -rf venv
   ./setup.sh
   ```

### Segnala Bug

Se trovi un bug:

1. Copia l'errore da `memory/system.log`
2. Includi la tua configurazione (`.env`)
3. Descrivi i passi per riprodurlo
4. Apri una issue su GitHub

## Note sulla Versione

### v2.2 (Current)

- ✅ **Project Evolution**: Supporto per aggiornamenti incrementali (`--update`).
- ✅ **Auto-Resume**: Ripristino automatico e ricostruzione del grafo dei task.
- ✅ **MVP Mode**: Sviluppo rapido senza review e senza Auth (`--mvp`).
- ✅ **Dashboard v2**: Kanban cliccabili con log di rejection dettagliati.

### v2.1

- ✅ Fix MQTT connection errors
- ✅ Fix `_fallback_queues` initialization
- ✅ MQTT disabilitato di default (fallback in-memory)
- ✅ Migliore gestione errori
- ✅ Skills system completo

### v2.0

- Skills dinamiche
- Auto-detection skills
- Metadata YAML

### v1.0

- Sistema base multi-agente
- MQTT/Kafka support
- Memoria persistente

---

**Il sistema ora è stabile e funziona out-of-the-box!** 🎉

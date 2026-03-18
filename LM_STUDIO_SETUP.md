# 🤖 LM Studio Setup Guide

Il sistema usa **LM Studio** o qualsiasi API compatibile con OpenAI per generare codice.

## 🚀 Quick Setup (5 minuti)

### 1. Installa LM Studio

```bash
# Scarica da: https://lmstudio.ai/
# Disponibile per Windows, macOS, Linux
```

### 2. Scarica un Modello

In LM Studio:
1. Vai alla tab "Discover"
2. Cerca e scarica uno di questi modelli consigliati:
   - **DeepSeek Coder 6.7B** (raccomandato per coding)
   - **CodeLlama 13B**
   - **Mistral 7B** (versatile)
   - **Qwen 2.5 Coder** (ottimo per code)

### 3. Avvia il Server

In LM Studio:
1. Vai alla tab "Local Server"
2. Carica il modello
3. Clicca "Start Server"
4. Il server partirà su `http://localhost:1234`

### 4. Configura Hypnonyx

```bash
# Nel file .env
LM_STUDIO_URL=http://localhost:1234/v1/chat/completions
MODEL_NAME=local-model  # O il nome esatto del tuo modello
TEMPERATURE=0.3
```

### 5. Test

```bash
python main.py --project test_project
```

## 🎯 Modelli Consigliati per Coding

### Top Choice: DeepSeek Coder
```
Nome: deepseek-coder-6.7b-instruct
Dimensione: ~4GB
Qualità: ⭐⭐⭐⭐⭐
Velocità: ⭐⭐⭐⭐
```

### Alternative:

**CodeLlama 13B**
- Migliore qualità ma più lento
- Richiede ~8GB RAM

**Mistral 7B**
- Versatile, buon compromesso
- ~4GB RAM

**Qwen 2.5 Coder**
- Ottimo per Python
- ~4GB RAM

## ⚙️ Configurazione Avanzata

### Ottimizza Performance

In LM Studio → Settings:
```
Context Length: 4096 (minimo) / 8192 (consigliato)
GPU Offload: Max (se hai GPU)
CPU Threads: Auto
```

### Usa API Esterna (OpenAI, Azure, etc.)

```bash
# Nel .env
LM_STUDIO_URL=https://api.openai.com/v1/chat/completions
MODEL_NAME=gpt-4
# Aggiungi API key se necessaria
```

### Ollama (Alternativa a LM Studio)

```bash
# Installa Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Scarica modello
ollama pull deepseek-coder

# Avvia
ollama serve

# Configura
LM_STUDIO_URL=http://localhost:11434/v1/chat/completions
MODEL_NAME=deepseek-coder
```

## 🔧 Troubleshooting

### Errore: Connection Refused

```bash
# Verifica che LM Studio server sia attivo
curl http://localhost:1234/v1/models

# Se non risponde:
# 1. Apri LM Studio
# 2. Tab "Local Server"
# 3. "Start Server"
```

### Risposte Lente

```bash
# Opzioni:
# 1. Usa modello più piccolo (6-7B invece di 13B)
# 2. Aumenta GPU offload in LM Studio
# 3. Riduci context length a 2048
```

### Codice di Bassa Qualità

```bash
# 1. Usa modello migliore (DeepSeek Coder, CodeLlama)
# 2. Aumenta temperature a 0.5 per più creatività
# 3. Verifica che le skills siano caricate
```

### Out of Memory

```bash
# 1. Chiudi applicazioni non necessarie
# 2. Usa modello più piccolo
# 3. Riduci context length
# 4. In config.py, riduci MAX_TOKENS
```

## 📊 Requisiti Hardware

### Minimi
- RAM: 8GB
- Storage: 10GB
- CPU: Quad-core

### Consigliati
- RAM: 16GB+
- Storage: 20GB
- GPU: NVIDIA RTX (8GB VRAM)

### Con GPU
- Velocità: ~10-50 tokens/sec
- Esperienza fluida

### Solo CPU
- Velocità: ~2-10 tokens/sec
- Funziona ma più lento

## 🎨 Modelli per Use Case Specifici

### Solo Backend API
- **DeepSeek Coder 6.7B**
- Context: 4096 tokens
- RAM: 8GB

### Full-Stack (Backend + Frontend)
- **CodeLlama 13B** o **DeepSeek Coder 13B**
- Context: 8192 tokens
- RAM: 16GB

### Con Test Completi
- **DeepSeek Coder 33B** (se hai GPU)
- Context: 16384 tokens
- RAM: 24GB + GPU

## 💡 Tips per Migliori Risultati

### 1. Usa Skills Appropriate
Le skills guidano l'LLM. Assicurati siano caricate:
```bash
ls projects/my_project/.claude/
```

### 2. Prompt Chiari nei Task
Quando crei task custom, sii specifico:
```python
task = {
    "description": "Create REST API with JWT auth and rate limiting"
    # ✅ Specifico
}
```

### 3. Iterazione
Il sistema farà fix automatici se i test falliscono.

### 4. Monitora Log
```bash
tail -f memory/system.log | grep LLM
```

## 🔗 Alternative a LM Studio

### 1. Ollama (CLI-based)
```bash
ollama pull deepseek-coder
ollama serve
```

### 2. llama.cpp (Low-level)
```bash
./server -m model.gguf -c 4096
```

### 3. Cloud APIs
- OpenAI GPT-4
- Azure OpenAI
- Anthropic Claude (richiede modifiche)

## 📚 Risorse

- LM Studio: https://lmstudio.ai/
- Ollama: https://ollama.com/
- Model Hub: https://huggingface.co/models
- DeepSeek: https://github.com/deepseek-ai

## ✅ Checklist Pre-Avvio

- [ ] LM Studio installato
- [ ] Modello scaricato (DeepSeek Coder consigliato)
- [ ] Server avviato (http://localhost:1234)
- [ ] .env configurato
- [ ] Test: `curl http://localhost:1234/v1/models`

---

**Ora sei pronto per generare progetti completi con AI! 🚀**

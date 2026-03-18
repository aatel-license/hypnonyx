import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# DIRECTORIES
# ============================================================
BASE_DIR = Path(__file__).parent
WORKSPACE_ROOT = BASE_DIR / "projects"
MEMORY_DIR = BASE_DIR / "memory"
DOCS_DIR = BASE_DIR / "docs"
DB_PATH = MEMORY_DIR / "project_memory.db"

# Create directories
for dir_path in [WORKSPACE_ROOT, MEMORY_DIR, DOCS_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)

# ============================================================
# LLM CONFIGURATION
# ============================================================
# LM Studio or OpenAI-compatible API
LM_STUDIO_URL = os.getenv(
    "LM_STUDIO_URL", "http://192.168.1.10:1234/v1/chat/completions"
)
LM_STUDIO_MODEL_NAME = os.getenv("LM_STUDIO_MODEL_NAME", "local-model")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
LLM_STUDIO_KEY = os.getenv("LLM_STUDIO_KEY", "")
REQUEST_PER_MINUTE = int(os.getenv("REQUEST_PER_MINUTE", "20"))
USE_MULTI_PROVIDER = os.getenv("USE_MULTI_PROVIDER", "true").lower() == "true"
USE_TOON = os.getenv("USETOON", "true").lower() == "true"
ALLOWED_LLM_PROFILES = [
    p.strip()
    for p in os.getenv("ACTIVE_LLM_PROFILES", "default,sambanova,lm_studio").split(",")
    if p.strip()
]

# LLM Profiles (New Multi-Client Support)
LLM_PROFILES = {
    "default": {
        "api_url": LM_STUDIO_URL,
        "model": LM_STUDIO_MODEL_NAME,
        "api_key": LLM_STUDIO_KEY,
        "rpm": REQUEST_PER_MINUTE,
    },
    "sambanova": {
        "api_url": os.getenv(
            "SAMBANOVA_URL", "https://api.sambanova.ai/v1/chat/completions"
        ),
        "model": os.getenv("SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct"),
        "api_key": os.getenv("SAMBANOVA_KEY", LLM_STUDIO_KEY),
        "rpm": int(os.getenv("SAMBANOVA_RPM", "12")),
    },
    "anthropic": {
        "api_url": os.getenv("ANTHROPIC_URL", "https://api.anthropic.com/v1/messages"),
        "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620"),
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "rpm": int(os.getenv("ANTHROPIC_RPM", "5")),
    },
    "openrouter": {
        "api_url": os.getenv(
            "OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"
        ),
        "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-405b"),
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "rpm": int(os.getenv("OPENROUTER_RPM", "10")),
    },
    "google_ai_studio": {
        "api_url": os.getenv(
            "GOOGLE_AI_STUDIO_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        ),
        "model": os.getenv("GOOGLE_AI_STUDIO_MODEL", "gemini-1.5-pro"),
        "api_key": os.getenv("GOOGLE_AI_STUDIO_API_KEY", ""),
        "rpm": int(os.getenv("GOOGLE_AI_STUDIO_RPM", "15")),
    },
    "groq": {
        "api_url": os.getenv(
            "GROQ_URL", "https://api.groq.com/openai/v1/chat/completions"
        ),
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "api_key": os.getenv("GROQ_API_KEY", ""),
        "rpm": int(os.getenv("GROQ_RPM", "30")),
    },
    "mistral": {
        "api_url": os.getenv(
            "MISTRAL_URL", "https://api.mistral.ai/v1/chat/completions"
        ),
        "model": os.getenv("MISTRAL_MODEL", "mistral-large-latest"),
        "api_key": os.getenv("MISTRAL_API_KEY", ""),
        "rpm": int(os.getenv("MISTRAL_RPM", "5")),
    },
    "codestral": {
        "api_url": os.getenv(
            "CODESTRAL_URL", "https://codestral.mistral.ai/v1/chat/completions"
        ),
        "model": os.getenv("CODESTRAL_MODEL", "codestral-latest"),
        "api_key": os.getenv("CODESTRAL_API_KEY", ""),
        "rpm": int(os.getenv("CODESTRAL_RPM", "5")),
    },
    "cerebras": {
        "api_url": os.getenv(
            "CEREBRAS_URL", "https://api.cerebras.ai/v1/chat/completions"
        ),
        "model": os.getenv("CEREBRAS_MODEL", "llama3.1-70b"),
        "api_key": os.getenv("CEREBRAS_API_KEY", ""),
        "rpm": int(os.getenv("CEREBRAS_RPM", "30")),
    },
    "fireworks": {
        "api_url": os.getenv(
            "FIREWORKS_URL", "https://api.fireworks.ai/inference/v1/chat/completions"
        ),
        "model": os.getenv(
            "FIREWORKS_MODEL", "accounts/fireworks/models/llama-v3p1-70b-instruct"
        ),
        "api_key": os.getenv("FIREWORKS_API_KEY", ""),
        "rpm": int(os.getenv("FIREWORKS_RPM", "10")),
    },
    "nebius": {
        "api_url": os.getenv(
            "NEBIUS_URL", "https://api.studio.nebius.ai/v1/chat/completions"
        ),
        "model": os.getenv("NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct"),
        "api_key": os.getenv("NEBIUS_API_KEY", ""),
        "rpm": int(os.getenv("NEBIUS_RPM", "10")),
    },
    "hyperbolic": {
        "api_url": os.getenv(
            "HYPERBOLIC_URL", "https://api.hyperbolic.xyz/v1/chat/completions"
        ),
        "model": os.getenv(
            "HYPERBOLIC_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct"
        ),
        "api_key": os.getenv("HYPERBOLIC_API_KEY", ""),
        "rpm": int(os.getenv("HYPERBOLIC_RPM", "10")),
    },
    "together": {
        "api_url": os.getenv(
            "TOGETHER_URL", "https://api.together.xyz/v1/chat/completions"
        ),
        "model": os.getenv(
            "TOGETHER_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
        ),
        "api_key": os.getenv("TOGETHER_API_KEY", ""),
        "rpm": int(os.getenv("TOGETHER_RPM", "10")),
    },
    "nvidia_nim": {
        "api_url": os.getenv(
            "NVIDIA_NIM_URL", "https://integrate.api.nvidia.com/v1/chat/completions"
        ),
        "model": os.getenv("NVIDIA_NIM_MODEL", "meta/llama-3.1-70b-instruct"),
        "api_key": os.getenv("NVIDIA_NIM_API_KEY", ""),
        "rpm": int(os.getenv("NVIDIA_NIM_RPM", "5")),
    },
    "huggingface": {
        "api_url": os.getenv(
            "HF_URL", "https://api-inference.huggingface.co/v1/chat/completions"
        ),
        "model": os.getenv("HF_MODEL", "meta-llama/Meta-Llama-3-70B-Instruct"),
        "api_key": os.getenv("HF_API_KEY", ""),
        "rpm": int(os.getenv("HF_RPM", "5")),
    },
    "github": {
        "api_url": os.getenv(
            "GITHUB_URL", "https://models.inference.ai.azure.com/chat/completions"
        ),
        "model": os.getenv("GITHUB_MODEL", "gpt-4o"),
        "api_key": os.getenv("GITHUB_API_KEY", ""),
        "rpm": int(os.getenv("GITHUB_RPM", "5")),
    },
    "cohere": {
        "api_url": os.getenv("COHERE_URL", "https://api.cohere.ai/v1/chat/completions"),
        "model": os.getenv("COHERE_MODEL", "command-r-plus"),
        "api_key": os.getenv("COHERE_API_KEY", ""),
        "rpm": int(os.getenv("COHERE_RPM", "10")),
    },
    "novita": {
        "api_url": os.getenv("NOVITA_URL", "https://api.novita.ai/v1/chat/completions"),
        "model": os.getenv("NOVITA_MODEL", "meta-llama/llama-3.1-70b-instruct"),
        "api_key": os.getenv("NOVITA_API_KEY", ""),
        "rpm": int(os.getenv("NOVITA_RPM", "10")),
    },
    "upstage": {
        "api_url": os.getenv(
            "UPSTAGE_URL", "https://api.upstage.ai/v1/solar/chat/completions"
        ),
        "model": os.getenv("UPSTAGE_MODEL", "solar-1-mini-chat"),
        "api_key": os.getenv("UPSTAGE_API_KEY", ""),
        "rpm": int(os.getenv("UPSTAGE_RPM", "5")),
    },
    "scaleway": {
        "api_url": os.getenv(
            "SCALEWAY_URL", "https://api.scaleway.ai/v1/chat/completions"
        ),
        "model": os.getenv("SCALEWAY_MODEL", "llama-3.1-70b-instruct"),
        "api_key": os.getenv("SCALEWAY_API_KEY", ""),
        "rpm": int(os.getenv("SCALEWAY_RPM", "5")),
    },
    "aliyun": {
        "api_url": os.getenv(
            "ALIYUN_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        ),
        "model": os.getenv("ALIYUN_MODEL", "qwen-plus"),
        "api_key": os.getenv("ALIYUN_API_KEY", ""),
        "rpm": int(os.getenv("ALIYUN_RPM", "10")),
    },
    "vercel": {
        "api_url": os.getenv("VERCEL_URL", ""),
        "model": os.getenv("VERCEL_MODEL", ""),
        "api_key": os.getenv("VERCEL_API_KEY", ""),
        "rpm": int(os.getenv("VERCEL_RPM", "10")),
    },
    "cloudflare": {
        "api_url": os.getenv("CLOUDFLARE_URL", ""),
        "model": os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3.1-70b-instruct"),
        "api_key": os.getenv("CLOUDFLARE_API_KEY", ""),
        "rpm": int(os.getenv("CLOUDFLARE_RPM", "10")),
    },
    "vertex_ai": {
        "api_url": os.getenv("VERTEX_AI_URL", ""),
        "model": os.getenv("VERTEX_AI_MODEL", "gemini-1.5-pro"),
        "api_key": os.getenv("VERTEX_AI_API_KEY", ""),
        "rpm": int(os.getenv("VERTEX_AI_RPM", "10")),
    },
    "baseten": {
        "api_url": os.getenv("BASETEN_URL", ""),
        "model": os.getenv("BASETEN_MODEL", ""),
        "api_key": os.getenv("BASETEN_API_KEY", ""),
        "rpm": int(os.getenv("BASETEN_RPM", "10")),
    },
    "ai21": {
        "api_url": os.getenv(
            "AI21_URL", "https://api.ai21.com/studio/v1/chat/completions"
        ),
        "model": os.getenv("AI21_MODEL", "jamba-1-5-large"),
        "api_key": os.getenv("AI21_API_KEY", ""),
        "rpm": int(os.getenv("AI21_RPM", "10")),
    },
    "nlp_cloud": {
        "api_url": os.getenv(
            "NLP_CLOUD_URL", "https://api.nlpcloud.io/v1/chat/completions"
        ),
        "model": os.getenv("NLP_CLOUD_MODEL", "finetuned-llama-3-70b"),
        "api_key": os.getenv("NLP_CLOUD_API_KEY", ""),
        "rpm": int(os.getenv("NLP_CLOUD_RPM", "10")),
    },
    "modal": {
        "api_url": os.getenv("MODAL_URL", ""),
        "model": os.getenv("MODAL_MODEL", ""),
        "api_key": os.getenv("MODAL_API_KEY", ""),
        "rpm": int(os.getenv("MODAL_RPM", "10")),
    },
    "inference_net": {
        "api_url": os.getenv(
            "INFERENCE_NET_URL", "https://api.inference.net/v1/chat/completions"
        ),
        "model": os.getenv("INFERENCE_NET_MODEL", "meta-llama/llama-3.1-70b"),
        "api_key": os.getenv("INFERENCE_NET_API_KEY", ""),
        "rpm": int(os.getenv("INFERENCE_NET_RPM", "10")),
    },
    "lm_studio": {
        "api_url": os.getenv(
            "LOCAL_LLM_URL", "http://localhost:1234/v1/chat/completions"
        ),
        "model": os.getenv("LOCAL_LLM_MODEL", "local-model"),
        "api_key": "",
        "rpm": 60,
    },
}

# Role-based mapping
AGENT_LLM_MAPPING = {
    "backend": os.getenv("AGENT_BACKEND_LLM", "default"),
    "frontend": os.getenv("AGENT_FRONTEND_LLM", "default"),
    "orchestrator": os.getenv("AGENT_ORCHESTRATOR_LLM", "default"),
    "architect": os.getenv("AGENT_ARCHITECT_LLM", "default"),
    "scrum_master": os.getenv("AGENT_SCRUM_LLM", "default"),
    "database": os.getenv("AGENT_DATABASE_LLM", "default"),
    "devops": os.getenv("AGENT_DEVOPS_LLM", "default"),
    "qa": os.getenv("AGENT_QA_LLM", "default"),
    "researcher": os.getenv("AGENT_RESEARCHER_LLM", "default"),
    "reviewer": os.getenv("AGENT_REVIEWER_LLM", "default"),
    "testing": os.getenv("AGENT_TESTING_LLM", "default"),
    "universal": os.getenv("AGENT_UNIVERSAL_LLM", "default"),
}

# Situation-based mapping
SITUATION_LLM_MAPPING = {
    "retrospective": os.getenv("SITUATION_RETRO_LLM", "lm_studio"),
    "research": os.getenv("SITUATION_RESEARCH_LLM", "default"),
}


# ============================================================
# MESSAGE BROKER CONFIGURATION
# ============================================================
USE_KAFKA = os.getenv("USE_KAFKA", "false").lower() == "true"
USE_MQTT = os.getenv("USE_MQTT", "false").lower() == "true"  # Disabilitato di default

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# MQTT settings
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Redis settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ============================================================
# AGENT CONFIGURATION
# ============================================================
MAX_IDLE_TIME = int(os.getenv("MAX_IDLE_TIME", "30"))  # seconds
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "5"))  # seconds
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))

# ============================================================
# EXECUTION CONFIGURATION
# ============================================================
EXEC_TIMEOUT = int(os.getenv("EXEC_TIMEOUT", "60"))
MAX_JSON_RETRY = int(os.getenv("MAX_JSON_RETRY", "3"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
REQUIRED_REVIEWS = int(os.getenv("REQUIRED_REVIEWS", "1"))

# ============================================================
# TOPICS FOR MESSAGE BROKER
# # ============================================================
# TOPICS = {
#     "TASKS_NEW": "tasks.new",
#     "TASKS_ASSIGNED": "tasks.assigned",
#     "TASKS_COMPLETED": "tasks.completed",
#     "TASKS_STARTED": "tasks.started",
#     "TASKS_FAILED": "tasks.failed",
#     "BUGS_REPORTED": "bugs.reported",
#     "DEPLOY_READY": "deploy.ready",
#     "TESTS_FAILED": "tests.failed",
#     "AGENT_HEARTBEAT": "agent.heartbeat",
#     "AGENT_IDLE": "agent.idle",
#     "HELP_REQUEST": "help.request",
#     "SCRUM_CEREMONY": "scrum.ceremony",
#     "SCRUM_REPORT": "scrum.report",
#     "BACKLOG_REFINEMENT": "scrum.backlog.refinement",
#     "BACKLOG_REFINEMENT_PROPOSAL": "scrum.backlog.proposal",
#     "RELEASE_READY": "scrum.release.ready",
# }


def get_topics(project_id: str) -> dict:
    return {
        "TASKS_NEW": f"tasks.{project_id}.new",
        "TASKS_ASSIGNED": f"tasks.{project_id}.assigned",
        "TASKS_COMPLETED": f"tasks.{project_id}.completed",
        "TASKS_STARTED": f"tasks.{project_id}.started",
        "TASKS_FAILED": f"tasks.{project_id}.failed",
        "BUGS_REPORTED": f"bugs.{project_id}.reported",
        "DEPLOY_READY": f"deploy.{project_id}.ready",
        "TESTS_FAILED": f"tests.{project_id}.failed",
        "AGENT_HEARTBEAT": f"agent.{project_id}.heartbeat",
        "AGENT_IDLE": f"agent.{project_id}.idle",
        "HELP_REQUEST": f"help.{project_id}.request",
        "SCRUM_CEREMONY": f"scrum.{project_id}.ceremony",
        "SCRUM_REPORT": f"scrum.{project_id}.report",
        "BACKLOG_REFINEMENT": f"scrum.{project_id}.backlog.refinement",
        "BACKLOG_REFINEMENT_PROPOSAL": f"scrum.{project_id}.backlog.proposal",
        "RELEASE_READY": f"scrum.{project_id}.release.ready",
    }


# Sprint configuration
SPRINT_SIZE = int(
    os.getenv("SPRINT_SIZE", "2")
)  # Task per sprint (ogni 2 task = 1 sprint → retro + backlog refinement)
BACKLOG_REFINEMENT_INTERVAL = int(
    os.getenv("BACKLOG_REFINEMENT_INTERVAL", "1")
)  # Ogni N sprint
RELEASE_SPRINT_INTERVAL = int(
    os.getenv("RELEASE_SPRINT_INTERVAL", "1")
)  # Sprint per Release

# ============================================================
# GIT CONFIGURATION
# ============================================================
GIT_AUTO_COMMIT = os.getenv("GIT_AUTO_COMMIT", "true").lower() == "true"
GIT_BRANCH_PREFIX = os.getenv("GIT_BRANCH_PREFIX", "agent")

USE_UNIVERSAL_AGENTS = os.getenv("USE_UNIVERSAL_AGENTS", "false").lower() == "true"

# ============================================================
# IGNORE PATTERNS
# ============================================================
IGNORE_DIRS = {"venv", "node_modules", ".git", "__pycache__", ".pytest_cache", ".idea"}

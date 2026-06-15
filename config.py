"""
Jarvis AI Assistant — Configuration
All constants and tunable parameters live here. Values that a user might
reasonably want to change without editing code are read from the environment
(see .env.example); everything else has a sensible default below.
"""

import os

from dotenv import load_dotenv

# Load variables from a local .env file if present (never commit it).
load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a truthy environment variable ('1', 'true', 'yes', 'on')."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ─── LLM (Ollama) ─────────────────────────────────────────────────────────────
# Jarvis talks to a local Ollama server through its OpenAI-compatible API.
# Override any of these in your .env file.
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.5"))
OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "256"))
# CPU threads Ollama uses for generation. 0 = let Ollama auto-detect (usually
# the best choice — it picks your physical core count).
OLLAMA_NUM_THREADS: int = int(os.getenv("OLLAMA_NUM_THREADS", "0"))

# ─── LLM provider (pluggable) ─────────────────────────────────────────────────
# "ollama"            → local llama3.2 via Ollama (default, no API key).
# "openai_compatible" → any OpenAI-compatible endpoint (OpenAI, Gemini's
#                       OpenAI endpoint, a Claude gateway, ZedaPod, ...).
#                       Configure LLM_BASE_URL / LLM_API_KEY / LLM_MODEL.
# brain.py reads only the resolved LLM_* values below, so switching providers
# is an .env change with no code edits.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

if LLM_PROVIDER == "openai_compatible":
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    IS_OLLAMA: bool = False
else:  # default: ollama
    LLM_PROVIDER = "ollama"
    LLM_BASE_URL = OLLAMA_BASE_URL
    LLM_API_KEY = "ollama"  # required by the client, ignored by Ollama
    LLM_MODEL = OLLAMA_MODEL
    IS_OLLAMA = True

# ─── Web server ───────────────────────────────────────────────────────────────
# The assistant is served as a local web app. Bind to loopback ONLY — it can
# touch local apps and files, so it must never be exposed to the network.
WEB_HOST: str = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT: int = int(os.getenv("WEB_PORT", "8765"))

# ─── File workspace ───────────────────────────────────────────────────────────
# Sandbox directory the file tools and uploads are confined to.
WORKSPACE_DIR: str = os.getenv(
    "WORKSPACE_DIR", os.path.join(os.path.dirname(__file__), "workspace")
)
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))  # 20 MB
MAX_FILE_READ_CHARS: int = int(os.getenv("MAX_FILE_READ_CHARS", "20000"))

# ─── Web access (fetch + search tools) ────────────────────────────────────────
FETCH_MAX_CHARS: int = int(os.getenv("FETCH_MAX_CHARS", "6000"))
WEB_SEARCH_MAX_RESULTS: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
MAX_FETCHES_PER_TURN: int = int(os.getenv("MAX_FETCHES_PER_TURN", "3"))
HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "15"))

# ─── Agent loop ───────────────────────────────────────────────────────────────
# Maximum number of tool-calling rounds in a single turn before Jarvis is forced
# to answer with whatever it has. Prevents infinite tool loops.
MAX_TOOL_ROUNDS: int = int(os.getenv("MAX_TOOL_ROUNDS", "5"))

# ─── Safety ───────────────────────────────────────────────────────────────────
# Tools that can run arbitrary code or drive the keyboard are DISABLED unless the
# user explicitly opts in. See the "Safety & Security" section of the README.
ALLOW_DANGEROUS_TOOLS: bool = _env_bool("ALLOW_DANGEROUS_TOOLS", False)

# ─── Wake Word ────────────────────────────────────────────────────────────────
# Phrases that count as "Hey Jarvis" (Google STT mis-hears the name often).
WAKE_WORD_ALTERNATIVES: list[str] = [
    "hey jarvis",
    "jarvis",
    "hey jervis",
    "hey jarvi",
    "jervis",
]

# ─── Memory ───────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "jarvis_memory.db"),
)
# Number of recent messages replayed to the LLM each turn.
CONTEXT_WINDOW: int = int(os.getenv("CONTEXT_WINDOW", "10"))

# ─── Voice / Audio ────────────────────────────────────────────────────────────
TTS_VOICE: str = os.getenv("TTS_VOICE", "en-US-GuyNeural")  # edge-tts voice
TTS_RATE: str = os.getenv("TTS_RATE", "+10%")  # speech speed
LISTEN_TIMEOUT: int = int(os.getenv("LISTEN_TIMEOUT", "8"))  # s to wait for speech
LISTEN_PHRASE_LIMIT: int = int(os.getenv("LISTEN_PHRASE_LIMIT", "15"))  # max s per utterance
ENERGY_THRESHOLD: int = int(os.getenv("ENERGY_THRESHOLD", "300"))  # mic sensitivity

# ─── System Prompt (Jarvis Personality) ───────────────────────────────────────
SYSTEM_PROMPT: str = """You are Jarvis, a concise, helpful, and slightly witty \
desktop AI assistant running locally on the user's computer.

Guidelines:
• Be helpful, direct, and efficient. No fluff.
• When a tool returns information (such as the current time or a stored fact), \
state that information directly and clearly in your reply so the user can read \
and hear it.
• When the user asks you to perform an action (open an app, search the web, \
remember something), use the tools provided — do not just describe what you \
would do.
• You may chain several tool calls in one turn to complete multi-step tasks.
• If a request is ambiguous, ask a brief clarifying question.
• Keep responses spoken-length: 1-3 sentences unless the user asks for detail.
• Address the user in a warm, friendly tone."""

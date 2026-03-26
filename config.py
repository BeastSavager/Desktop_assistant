"""
Jarvis AI Assistant — Configuration
All constants, API keys, and tunable parameters live here.
"""

import os
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()

# ─── LLM (Ollama) ─────────────────────────────────────────────────────────────
# Set to your preferred Ollama model (llama3.1 is recommended for tool calling)
OLLAMA_MODEL: str = "llama3.1"                 # model used for reasoning
OLLAMA_BASE_URL: str = "http://localhost:11434/v1" # Ollama OpenAI-compatible endpoint
OLLAMA_TEMPERATURE: float = 0.7              # creativity dial
OLLAMA_MAX_TOKENS: int = 1024                # max response length

# ─── Wake Word ────────────────────────────────────────────────────────────────
WAKE_WORD: str = "Hey"
WAKE_WORD_ALTERNATIVES: list[str] = [
    "hey coco", "coco", "hey koko",          # common mis-hearings
    "hey cocoa", "hey coko",
]

# ─── Memory ───────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.path.join(os.path.dirname(__file__), "jarvis_memory.db")
CONTEXT_WINDOW: int = 20                     # last N messages sent to LLM

# ─── Voice / Audio ────────────────────────────────────────────────────────────
TTS_VOICE: str = "en-US-GuyNeural"           # edge-tts voice (male, natural)
TTS_RATE: str = "+10%"                       # speech speed adjustment
LISTEN_TIMEOUT: int = 8                      # seconds to wait for speech
LISTEN_PHRASE_LIMIT: int = 15                # max seconds per utterance
ENERGY_THRESHOLD: int = 31                # mic sensitivity (lower = more sensitive)

# ─── System Prompt (Jarvis Personality) ───────────────────────────────────────
SYSTEM_PROMPT: str = """You are Coco, a highly intelligent, concise, and slightly \
witty desktop AI assistant.

Guidelines:
• Be helpful, direct, and efficient. No fluff.
• Add a touch of dry humour when appropriate, but never at the user's expense.
• When the user asks you to perform an action (open apps, search the web, etc.), \
use the tools provided — do NOT just describe what you would do.
• If a request is ambiguous, ask a brief clarifying question.
• Keep responses spoken-length: 1-3 sentences unless the user explicitly asks for detail.
• Address the user in a warm, friendly tone.
• You can handle multi-step tasks by chaining tool calls.
• Always prefer action over explanation when tools are available."""

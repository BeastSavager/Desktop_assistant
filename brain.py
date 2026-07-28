"""
Jarvis AI Assistant — Brain Module
LLM reasoning and a real multi-round tool-calling loop.

Jarvis talks to an OpenAI-compatible chat endpoint. By default that is a local
Ollama server (``llama3.2``); set ``LLM_PROVIDER=openai_compatible`` plus the
``LLM_*`` env vars to use any cloud endpoint instead — no code change needed.

Each turn runs an agentic loop: the model may request tool calls, we execute them
and feed the results back as plain text (small local models consume OpenAI
``tool``-role messages unreliably), and let the model decide whether it needs more
tools or is ready to answer — preserving the full conversation and system prompt.

``stream_turn`` is the core generator: it yields ``tool`` / ``tool_result`` /
``final`` events so the web UI can show live tool activity. ``think`` is a thin
wrapper that drains it and returns the final text.
"""

import json
import logging
from collections.abc import Iterator

from openai import OpenAI

from config import (
    IS_OLLAMA,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    MAX_TOOL_ROUNDS,
    OLLAMA_MAX_TOKENS,
    OLLAMA_NUM_THREADS,
    OLLAMA_TEMPERATURE,
    SYSTEM_PROMPT,
)
from memory import MemoryManager
from tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger("jarvis.brain")

# Shown to the user when the model returns nothing usable, so Jarvis never
# appears frozen.
FALLBACK_REPLY = "I couldn't generate a response. Could you try again?"

# Appended after tool results so the (often small) model answers with the data.
_RESULTS_INSTRUCTION = (
    "\n\nUsing these results, reply to my original request directly and "
    "concisely, stating the actual information. Only call another tool if you "
    "genuinely need more data."
)


class JarvisBrain:
    """Wraps the LLM client, conversation context, and the tool-execution loop."""

    def __init__(self, memory: MemoryManager):
        self.client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY or "none")
        self.memory = memory
        self.max_tool_rounds = MAX_TOOL_ROUNDS
        self.model_override = None
        self.temperature_override = None

    def get_model(self) -> str:
        return self.model_override or LLM_MODEL

    def _is_simple_greeting(self, text: str) -> bool:
        clean = text.strip().lower().replace("jarvis", "").replace("assistant", "").strip(",.!? ")
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "yo", "greetings", "hi there", "hello there"}
        return clean in greetings

    # ── public API ────────────────────────────────────────────────────────

    def warmup(self) -> None:
        """
        Pre-load the model into memory so the first real reply is fast.

        Ollama loads the (multi-GB) model on the first request, which is the main
        reason the first message feels slow. Calling this at startup pays that
        cost up front; keep_alive=-1 then keeps the model resident.
        """
        if not IS_OLLAMA:
            return
        try:
            self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
                extra_body={"keep_alive": -1},
            )
            logger.info("Model '%s' warmed up and resident.", LLM_MODEL)
        except Exception as e:  # noqa: BLE001 - Ollama may not be up yet
            logger.warning("Warmup skipped (model will load on first request): %s", e)

    def think(self, user_message: str) -> str:
        """Run one full agent turn and return Jarvis's reply text."""
        reply = FALLBACK_REPLY
        for event in self.stream_turn(user_message):
            if event["type"] == "final":
                reply = event["text"]
        return reply

    def stream_turn(self, user_message: str) -> Iterator[dict]:
        """
        Run one agent turn, yielding events as they happen:

          {"type": "tool", "name": ...}                  — a tool is about to run
          {"type": "tool_result", "name": ..., "result": ...}
          {"type": "final", "text": ...}                 — the final reply

        Tool results are stored to memory implicitly via the conversation; only
        the user message and the final reply are persisted as chat history.
        """
        self.memory.add_message("user", user_message)
        messages = self._build_messages()

        reply = ""
        for round_num in range(self.max_tool_rounds):
            # On the final allowed round, drop the tools so the model is forced
            # to produce a textual answer instead of requesting more calls.
            is_last_round = round_num == self.max_tool_rounds - 1
            is_greeting = round_num == 0 and self._is_simple_greeting(user_message)
            with_tools = not is_last_round and not is_greeting
            try:
                response = self._chat(messages, with_tools=with_tools)
            except Exception as e:  # noqa: BLE001
                logger.error("LLM request failed: %s", e)
                reply = f"I'm having trouble connecting to my brain. Error: {e}"
                break

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)

            if not tool_calls:
                reply = (message.content or "").strip()
                break

            # Run the requested tools, emitting live events, then feed the
            # results back as plain text for the next round.
            round_results: list[str] = []
            for tool_call in tool_calls:
                yield {"type": "tool", "name": tool_call.function.name}
                result = self._run_tool_call(tool_call)
                yield {
                    "type": "tool_result",
                    "name": tool_call.function.name,
                    "result": result,
                }
                round_results.append(f"{tool_call.function.name}: {result}")

            if message.content:
                messages.append({"role": "assistant", "content": message.content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Results from the tools you just used:\n"
                        + "\n".join(f"- {r}" for r in round_results)
                        + _RESULTS_INSTRUCTION
                    ),
                }
            )
        else:
            logger.warning("Tool loop hit max rounds (%d) without a reply.", self.max_tool_rounds)

        # ── Empty-response fallback ─────────────────────────────────────────
        if not reply or not reply.strip():
            logger.warning("Model returned an empty reply for: %r", user_message)
            reply = FALLBACK_REPLY

        logger.info("Reply: %s", reply)
        self.memory.add_message("assistant", reply)
        yield {"type": "final", "text": reply}

    # ── private helpers ───────────────────────────────────────────────────

    def _chat(self, messages: list[dict], with_tools: bool):
        """Single chat-completion call against the configured provider."""
        model = self.model_override or LLM_MODEL
        temp = self.temperature_override if self.temperature_override is not None else OLLAMA_TEMPERATURE
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": OLLAMA_MAX_TOKENS,
        }
        # keep_alive / num_thread are Ollama-specific; don't send them to clouds.
        if IS_OLLAMA:
            extra: dict = {"keep_alive": -1}  # keep the model resident in RAM
            if OLLAMA_NUM_THREADS > 0:
                extra["options"] = {"num_thread": OLLAMA_NUM_THREADS}
            kwargs["extra_body"] = extra
        if with_tools and TOOL_SCHEMAS:
            kwargs["tools"] = TOOL_SCHEMAS
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def _run_tool_call(self, tool_call) -> str:
        """Parse arguments, execute a single tool call, and return its result."""
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        logger.info("Tool call: %s(%s)", name, args)
        result = execute_tool(name, args, memory=self.memory)
        logger.info("Tool result: %s", result)
        return result

    def _build_messages(self) -> list[dict]:
        """Assemble the system prompt followed by recent conversation history."""
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.memory.get_recent_messages())
        return messages

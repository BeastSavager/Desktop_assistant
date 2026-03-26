"""
Jarvis AI Assistant — Brain Module
LLM reasoning, function/tool calling, and multi-step agent logic.
Uses OpenAI ChatCompletion with tool_calls support.
"""

import json
import logging
from typing import Optional

from openai import OpenAI

from config import (
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MAX_TOKENS,
    OLLAMA_TEMPERATURE,
    SYSTEM_PROMPT,
)
from memory import MemoryManager
from tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger("jarvis.brain")


class JarvisBrain:
    """Wraps the OpenAI API, conversation context, and tool execution loop."""

    def __init__(self, memory: MemoryManager):
        # We use the OpenAI python package but point it to local Ollama
        self.client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama" # Required by the client, but unused by Ollama
        )
        self.memory = memory
        self.max_tool_rounds = 5  # safety cap for chained tool calls

    # ── public API ────────────────────────────────────────────────────────

    def think(self, user_message: str) -> str:
        """
        Full agent turn:
          1. Build messages (system + history + new user message)
          2. Call LLM
          3. If LLM requests tool calls → execute → feed results back → repeat
          4. Return final text response
        """
        # Store user message
        self.memory.add_message("user", user_message)

        # Build message list
        messages = self._build_messages()

        # Agent loop: LLM may request tools repeatedly
        for _ in range(self.max_tool_rounds):
            try:
                response = self.client.chat.completions.create(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=OLLAMA_TEMPERATURE,
                    max_tokens=OLLAMA_MAX_TOKENS,
                )
            except Exception as e:
                error_msg = f"I'm having trouble connecting to my brain. Error: {e}"
                logger.error("OpenAI API error: %s", e)
                return error_msg

            choice = response.choices[0]
            assistant_message = choice.message

            # If there are tool calls, execute them
            if assistant_message.tool_calls:
                # Append the assistant message (with tool_calls) to messages
                messages.append(assistant_message)

                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    logger.info("Tool call: %s(%s)", tool_name, tool_args)
                    result = execute_tool(tool_name, tool_args)
                    logger.info("Tool result: %s", result)

                    # Feed tool result back to the conversation
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result),
                        }
                    )
                # Loop back to let the LLM process tool results
                continue

            # No tool calls — we have the final text response
            reply = assistant_message.content or ""
            self.memory.add_message("assistant", reply)
            return reply

        # Exceeded max tool rounds
        fallback = "I seem to be stuck in a loop. Let me try a simpler approach."
        self.memory.add_message("assistant", fallback)
        return fallback

    # ── private helpers ───────────────────────────────────────────────────

    def _build_messages(self) -> list[dict]:
        """Assemble the system prompt + recent conversation history."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.memory.get_recent_messages())
        return messages

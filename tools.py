"""
Jarvis AI Assistant — Tool System
Each tool is a callable + an OpenAI function-calling JSON schema.
The LLM decides which tool to invoke; `execute_tool` dispatches the call.
"""

import os
import subprocess
import webbrowser
from datetime import datetime
from typing import Any

# Optional: pyautogui for keyboard/mouse automation
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
#  Tool Implementations
# ═══════════════════════════════════════════════════════════════════════════════

def open_chrome(url: str = "") -> str:
    """Open Google Chrome, optionally navigating to a URL."""
    try:
        if url:
            webbrowser.get("C:/Program Files/Google/Chrome/Application/chrome.exe %s").open(url)
            return f"Opened Chrome at {url}"
        else:
            # Try common Chrome paths on Windows
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    subprocess.Popen([path])
                    return "Chrome opened."
            # Fallback: use webbrowser
            webbrowser.open("https://www.google.com")
            return "Opened default browser."
    except Exception as e:
        return f"Failed to open Chrome: {e}"


def open_vs_code(path: str = "") -> str:
    """Open Visual Studio Code, optionally at a given path."""
    try:
        cmd = ["code"]
        if path:
            cmd.append(path)
        subprocess.Popen(cmd, shell=True)
        return f"VS Code opened{' at ' + path if path else ''}."
    except Exception as e:
        return f"Failed to open VS Code: {e}"


def get_time() -> str:
    """Return the current date and time."""
    now = datetime.now()
    return now.strftime("It's %I:%M %p on %A, %B %d, %Y.")


def search_web(query: str) -> str:
    """Search the web for a query by opening Google in the browser."""
    try:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return f"Searching the web for: {query}"
    except Exception as e:
        return f"Failed to search: {e}"


def open_file(path: str) -> str:
    """Open a file or folder with the OS default application."""
    try:
        if not os.path.exists(path):
            return f"Path not found: {path}"
        os.startfile(path)  # Windows-specific
        return f"Opened: {path}"
    except Exception as e:
        return f"Failed to open file: {e}"


def shutdown_pc() -> str:
    """Simulated PC shutdown (safe mock — does NOT actually shut down)."""
    return (
        "⚠️  Shutdown command received. This is a MOCK action — "
        "the PC will NOT actually shut down. "
        "To enable real shutdown, modify this function."
    )


def type_text(text: str) -> str:
    """Type text using the keyboard (requires pyautogui)."""
    if not PYAUTOGUI_AVAILABLE:
        return "pyautogui is not installed. Cannot type text."
    try:
        pyautogui.typewrite(text, interval=0.03)
        return f"Typed: {text}"
    except Exception as e:
        return f"Failed to type text: {e}"


def press_key(key: str) -> str:
    """Press a keyboard key (e.g., 'enter', 'esc', 'tab')."""
    if not PYAUTOGUI_AVAILABLE:
        return "pyautogui is not installed. Cannot press key."
    try:
        pyautogui.press(key)
        return f"Pressed key: {key}"
    except Exception as e:
        return f"Failed to press key: {e}"


def run_system_command(command: str) -> str:
    """Run a system/shell command and return the output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output if output else "Command executed (no output)."
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Failed to run command: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
#  OpenAI Function-Calling Schemas
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_chrome",
            "description": "Open the Google Chrome browser, optionally navigating to a specific URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Optional URL to open. Leave empty to open Chrome's homepage.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_vs_code",
            "description": "Open Visual Studio Code editor, optionally at a specific file or folder path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional file or folder path to open in VS Code.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for a given query by opening Google search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_file",
            "description": "Open a file or folder using the default OS application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file or folder to open.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shutdown_pc",
            "description": "Shut down the computer. (Currently a safe mock — will not actually shut down.)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type a string of text on the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to type.",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a single keyboard key (e.g. 'enter', 'esc', 'tab', 'space').",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key to press.",
                    }
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_system_command",
            "description": "Run a system shell command and return the output. Use with caution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
#  Tool Dispatcher
# ═══════════════════════════════════════════════════════════════════════════════

_TOOL_MAP: dict[str, callable] = {
    "open_chrome": open_chrome,
    "open_vs_code": open_vs_code,
    "get_time": get_time,
    "search_web": search_web,
    "open_file": open_file,
    "shutdown_pc": shutdown_pc,
    "type_text": type_text,
    "press_key": press_key,
    "run_system_command": run_system_command,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """
    Dispatch a tool call by name with the given arguments.
    Returns the tool's string result or an error message.
    """
    func = _TOOL_MAP.get(name)
    if func is None:
        return f"Unknown tool: {name}"
    try:
        return func(**arguments)
    except TypeError as e:
        return f"Tool '{name}' received bad arguments: {e}"
    except Exception as e:
        return f"Tool '{name}' failed: {e}"

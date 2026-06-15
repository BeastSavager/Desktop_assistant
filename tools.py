"""
Jarvis AI Assistant — Tool System
Each tool is a plain Python callable plus an OpenAI-style function-calling JSON
schema. The LLM decides which tool to invoke; ``execute_tool`` dispatches it.

Tools fall into three groups:
  • safe         — open apps/files, search the web, tell the time
  • memory       — store/recall long-term facts (injected with the MemoryManager)
  • dangerous    — run shell commands, drive the keyboard. DISABLED unless the
                   user sets ALLOW_DANGEROUS_TOOLS=true (see config / README).
"""

import logging
import os
import shutil
import subprocess
import sys
import webbrowser
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from config import (
    ALLOW_DANGEROUS_TOOLS,
    FETCH_MAX_CHARS,
    HTTP_TIMEOUT,
    MAX_FILE_READ_CHARS,
    WEB_SEARCH_MAX_RESULTS,
    WORKSPACE_DIR,
)

if TYPE_CHECKING:  # avoid a hard import cycle; only needed for typing
    from memory import MemoryManager

logger = logging.getLogger("jarvis.tools")

# Optional: pyautogui for keyboard automation (dangerous tools only).
try:
    import pyautogui

    PYAUTOGUI_AVAILABLE = True
except Exception:  # pragma: no cover - import side effects vary by platform
    PYAUTOGUI_AVAILABLE = False

_IS_WINDOWS = sys.platform.startswith("win")
_DANGEROUS_DISABLED_MSG = (
    "That tool is disabled for safety. Set ALLOW_DANGEROUS_TOOLS=true in your "
    ".env file to enable shell and keyboard control."
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Safe tools
# ═══════════════════════════════════════════════════════════════════════════════


def _normalize_url(url: str) -> str:
    """Add an https:// scheme if the user passed a bare domain."""
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
    return url


def _find_chrome() -> str | None:
    """Locate the Chrome executable across platforms, or return None."""
    candidates: list[str] = []
    if _IS_WINDOWS:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    elif sys.platform == "darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:  # linux / other
        candidates = []

    for name in ("chrome", "google-chrome", "google-chrome-stable", "chromium"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def open_chrome(url: str = "") -> str:
    """
    Open Google Chrome, optionally navigating to a URL.

    Falls back to the system default browser if Chrome cannot be found, and
    returns a human-readable message describing what happened.
    """
    target = _normalize_url(url) if url else ""
    chrome = _find_chrome()

    try:
        if chrome:
            args = [chrome, target] if target else [chrome]
            subprocess.Popen(args)
            return f"Opened Chrome{f' at {target}' if target else ''}."

        # Chrome not installed — fall back to the default browser.
        if target:
            webbrowser.open(target)
            return f"Chrome not found; opened {target} in your default browser."
        webbrowser.open("https://www.google.com")
        return "Chrome not found; opened Google in your default browser."
    except Exception as e:  # noqa: BLE001 - report any launch failure to the user
        logger.error("open_chrome failed: %s", e)
        return f"Failed to open the browser: {e}"


def open_vs_code(path: str = "") -> str:
    """Open Visual Studio Code, optionally at a given file or folder path."""
    if shutil.which("code") is None:
        return "VS Code ('code' command) is not on your PATH."
    try:
        cmd = ["code"]
        if path:
            cmd.append(path)
        # shell=True is required on Windows because `code` is a .cmd shim.
        subprocess.Popen(cmd, shell=_IS_WINDOWS)
        return f"Opened VS Code{f' at {path}' if path else ''}."
    except Exception as e:  # noqa: BLE001
        logger.error("open_vs_code failed: %s", e)
        return f"Failed to open VS Code: {e}"


def get_time() -> str:
    """Return the current date and time."""
    return datetime.now().strftime("It's %I:%M %p on %A, %B %d, %Y.")


def search_web(query: str) -> str:
    """Search the web for a query by opening Google in the default browser."""
    from urllib.parse import quote_plus

    try:
        webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
        return f"Searching the web for: {query}"
    except Exception as e:  # noqa: BLE001
        logger.error("search_web failed: %s", e)
        return f"Failed to search: {e}"


def open_file(path: str) -> str:
    """Open a file or folder with the OS default application (cross-platform)."""
    if not os.path.exists(path):
        return f"Path not found: {path}"
    try:
        if _IS_WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]  # Windows only
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return f"Opened: {path}"
    except Exception as e:  # noqa: BLE001
        logger.error("open_file failed: %s", e)
        return f"Failed to open file: {e}"


def shutdown_pc() -> str:
    """Mock PC shutdown — intentionally does NOT shut anything down."""
    return (
        "Shutdown command received. This is a mock action — the PC will NOT "
        "actually shut down. Enabling real shutdown is left to the user."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Memory tools (require the MemoryManager, injected by the brain)
# ═══════════════════════════════════════════════════════════════════════════════


def remember_fact(memory: "MemoryManager", key: str, value: str) -> str:
    """Persist a fact (key → value) the user wants Jarvis to remember."""
    memory.store_fact(key, value)
    return f"Got it — I'll remember that {key} is {value}."


def recall_fact(memory: "MemoryManager", key: str) -> str:
    """Look up a previously stored fact by key."""
    value = memory.get_fact(key)
    if value is None:
        return f"I don't have anything stored for '{key}'."
    return f"{key}: {value}"


def search_history(memory: "MemoryManager", query: str) -> str:
    """Keyword-search past conversation for anything matching the query."""
    matches = memory.search_memory(query)
    if not matches:
        return f"I found nothing in our history about '{query}'."
    lines = [f"{m['role']}: {m['content']}" for m in matches]
    return "Here is what I found:\n" + "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  Web access tools (real internet: read pages + search snippets)
# ═══════════════════════════════════════════════════════════════════════════════


def open_in_browser(url: str) -> str:
    """Open a URL in the user's default browser (just opens a tab)."""
    try:
        webbrowser.open(_normalize_url(url))
        return f"Opened {url} in your browser."
    except Exception as e:  # noqa: BLE001
        return f"Failed to open URL: {e}"


def fetch_url(url: str) -> str:
    """
    Download a web page and return its main readable text (truncated).

    Use this to actually *read* a page's content rather than just opening it.
    """
    import httpx
    from bs4 import BeautifulSoup

    target = _normalize_url(url)
    try:
        resp = httpx.get(
            target,
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (JarvisAssistant)"},
        )
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return f"Failed to fetch {target}: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    if not text:
        return f"Fetched {target} but found no readable text."
    if len(text) > FETCH_MAX_CHARS:
        text = text[:FETCH_MAX_CHARS] + " …[truncated]"
    return f"Content of {target}:\n{text}"


def web_search(query: str) -> str:
    """Search the web and return result titles, snippets, and links to read."""
    try:
        from ddgs import DDGS
    except Exception:  # noqa: BLE001 - package optional
        return "Web search is unavailable (the 'ddgs' package is not installed)."

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=WEB_SEARCH_MAX_RESULTS))
    except Exception as e:  # noqa: BLE001
        return f"Web search failed: {e}"

    if not results:
        return f"No web results found for '{query}'."

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "(no title)")
        body = r.get("body", "")
        href = r.get("href", "")
        lines.append(f"{i}. {title}\n   {body}\n   {href}")
    return f"Web results for '{query}':\n" + "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  File workspace tools (sandboxed to WORKSPACE_DIR)
# ═══════════════════════════════════════════════════════════════════════════════


def _workspace_root() -> Path:
    root = Path(WORKSPACE_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(name: str) -> Path:
    """
    Resolve ``name`` inside the workspace, rejecting path traversal.

    Raises ValueError if the resolved path escapes the workspace root.
    """
    root = _workspace_root()
    candidate = (root / name).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("path escapes the workspace")
    return candidate


def _extract_text(path: Path) -> str:
    """Extract readable text from common file types (txt/md/csv/json/pdf/docx)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix == ".docx":
        import docx

        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)
    # txt, md, csv, json, and anything else readable as UTF-8 text
    return path.read_text(encoding="utf-8", errors="replace")


def list_files() -> str:
    """List files available in the workspace."""
    root = _workspace_root()
    files = sorted(p.name for p in root.iterdir() if p.is_file())
    if not files:
        return "The workspace is empty."
    return "Files in the workspace:\n" + "\n".join(f"- {f}" for f in files)


def read_file(name: str) -> str:
    """Read a workspace file's text content (handles pdf/docx/txt/md/csv/json)."""
    try:
        path = _safe_path(name)
    except ValueError as e:
        return f"Refused: {e}."
    if not path.exists() or not path.is_file():
        return f"File not found in workspace: {name}"
    try:
        text = _extract_text(path)
    except Exception as e:  # noqa: BLE001
        return f"Failed to read '{name}': {e}"
    if len(text) > MAX_FILE_READ_CHARS:
        text = text[:MAX_FILE_READ_CHARS] + " …[truncated]"
    return text or f"'{name}' contains no extractable text."


def write_file(name: str, content: str) -> str:
    """Create or overwrite a text file in the workspace."""
    try:
        path = _safe_path(name)
    except ValueError as e:
        return f"Refused: {e}."
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return f"Failed to write '{name}': {e}"
    return f"Wrote {len(content)} characters to {name}."


def append_file(name: str, content: str) -> str:
    """Append text to a workspace file (creates it if missing)."""
    try:
        path = _safe_path(name)
    except ValueError as e:
        return f"Refused: {e}."
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(content)
    except Exception as e:  # noqa: BLE001
        return f"Failed to append to '{name}': {e}"
    return f"Appended {len(content)} characters to {name}."


def summarize_file(name: str) -> str:
    """Return a workspace file's text so it can be summarized by the assistant."""
    text = read_file(name)
    return f"Here is the content of '{name}' to summarize:\n{text}"


def search_in_files(query: str) -> str:
    """Case-insensitive search for a string across workspace files."""
    root = _workspace_root()
    needle = query.lower()
    hits: list[str] = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        try:
            text = _extract_text(path)
        except Exception:  # noqa: BLE001 - skip unreadable files
            continue
        if needle in text.lower():
            idx = text.lower().find(needle)
            snippet = text[max(0, idx - 40) : idx + 60].replace("\n", " ")
            hits.append(f"- {path.name}: …{snippet.strip()}…")
    if not hits:
        return f"No workspace files contain '{query}'."
    return f"Matches for '{query}':\n" + "\n".join(hits)


# ═══════════════════════════════════════════════════════════════════════════════
#  Dangerous tools (gated behind ALLOW_DANGEROUS_TOOLS)
# ═══════════════════════════════════════════════════════════════════════════════


def type_text(text: str) -> str:
    """Type text via the keyboard (requires pyautogui; dangerous)."""
    if not ALLOW_DANGEROUS_TOOLS:
        return _DANGEROUS_DISABLED_MSG
    if not PYAUTOGUI_AVAILABLE:
        return "pyautogui is not installed; cannot type text."
    try:
        pyautogui.typewrite(text, interval=0.03)
        return f"Typed: {text}"
    except Exception as e:  # noqa: BLE001
        return f"Failed to type text: {e}"


def press_key(key: str) -> str:
    """Press a keyboard key (requires pyautogui; dangerous)."""
    if not ALLOW_DANGEROUS_TOOLS:
        return _DANGEROUS_DISABLED_MSG
    if not PYAUTOGUI_AVAILABLE:
        return "pyautogui is not installed; cannot press key."
    try:
        pyautogui.press(key)
        return f"Pressed key: {key}"
    except Exception as e:  # noqa: BLE001
        return f"Failed to press key: {e}"


def run_system_command(command: str) -> str:
    """Run a shell command and return its output (dangerous)."""
    if not ALLOW_DANGEROUS_TOOLS:
        return _DANGEROUS_DISABLED_MSG
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip() or result.stderr.strip()
        return output or "Command executed (no output)."
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:  # noqa: BLE001
        return f"Failed to run command: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
#  Function-calling schemas
# ═══════════════════════════════════════════════════════════════════════════════

_SAFE_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_chrome",
            "description": "Open the Google Chrome browser, optionally at a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Optional URL to open. Leave empty for Chrome's homepage.",
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
            "description": "Open Visual Studio Code, optionally at a file or folder path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional file or folder path to open.",
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
            "description": "Search the web for a query by opening Google search.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The search query."}},
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
                        "description": "Absolute path to the file or folder.",
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
            "description": "Shut down the computer (currently a safe mock — does nothing).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Store a fact the user wants you to remember long-term.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Short label for the fact, e.g. 'favourite colour'.",
                    },
                    "value": {"type": "string", "description": "The value to store."},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_fact",
            "description": "Retrieve a previously stored fact by its key.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The label of the fact to recall."}
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_history",
            "description": "Keyword-search the past conversation for something that was said.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Words to search for in history."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and get result titles, snippets, and links to read.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The search query."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Download a web page and read its main text. Use after web_search to read a result.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "The URL to read."}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_in_browser",
            "description": "Open a URL in the user's default browser (just opens a tab).",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "The URL to open."}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List the files in the user's file workspace.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a workspace file's text (txt, md, csv, json, pdf, docx).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "File name in the workspace."}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a text file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "File name in the workspace."},
                    "content": {"type": "string", "description": "Text to write."},
                },
                "required": ["name", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Append text to a workspace file (creates it if missing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "File name in the workspace."},
                    "content": {"type": "string", "description": "Text to append."},
                },
                "required": ["name", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_file",
            "description": "Fetch a workspace file's content so you can summarize it for the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "File name in the workspace."}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Search for a string across all workspace files.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Text to search for."}},
                "required": ["query"],
            },
        },
    },
]

_DANGEROUS_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type a string of text on the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "The text to type."}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a single keyboard key (e.g. 'enter', 'esc', 'tab').",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "The key to press."}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_system_command",
            "description": "Run a system shell command and return its output. Use with caution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."}
                },
                "required": ["command"],
            },
        },
    },
]

# Only advertise dangerous tools to the model when they are actually enabled.
TOOL_SCHEMAS: list[dict[str, Any]] = (
    _SAFE_SCHEMAS + _DANGEROUS_SCHEMAS if ALLOW_DANGEROUS_TOOLS else list(_SAFE_SCHEMAS)
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Dispatcher
# ═══════════════════════════════════════════════════════════════════════════════

_TOOL_MAP: dict[str, Callable[..., str]] = {
    "open_chrome": open_chrome,
    "open_vs_code": open_vs_code,
    "get_time": get_time,
    "search_web": search_web,
    "open_file": open_file,
    "shutdown_pc": shutdown_pc,
    "remember_fact": remember_fact,
    "recall_fact": recall_fact,
    "search_history": search_history,
    "web_search": web_search,
    "fetch_url": fetch_url,
    "open_in_browser": open_in_browser,
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "append_file": append_file,
    "summarize_file": summarize_file,
    "search_in_files": search_in_files,
    "type_text": type_text,
    "press_key": press_key,
    "run_system_command": run_system_command,
}

# Tools that need the MemoryManager injected as their first argument.
_MEMORY_TOOLS: frozenset[str] = frozenset({"remember_fact", "recall_fact", "search_history"})


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    memory: "MemoryManager | None" = None,
) -> str:
    """
    Dispatch a tool call by name with the given arguments.

    Memory-backed tools receive ``memory`` as their first argument. Returns the
    tool's string result, or a human-readable error message on failure.
    """
    func = _TOOL_MAP.get(name)
    if func is None:
        return f"Unknown tool: {name}"

    args = dict(arguments or {})
    try:
        if name in _MEMORY_TOOLS:
            if memory is None:
                return f"Tool '{name}' needs memory but none was available."
            return func(memory, **args)
        return func(**args)
    except TypeError as e:
        return f"Tool '{name}' received bad arguments: {e}"
    except Exception as e:  # noqa: BLE001
        logger.error("Tool '%s' failed: %s", name, e)
        return f"Tool '{name}' failed: {e}"

"""
Jarvis AI Assistant — Main Entry Point
Supports two modes:
  • python main.py          → launches the PyQt5 GUI
  • python main.py --cli    → runs in terminal (no GUI)
"""

import argparse
import logging
import signal
import sys

from brain import JarvisBrain
from memory import MemoryManager
from voice import listen, speak
from wakeword import WakeWordDetector

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-18s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis.main")


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI Mode — simple terminal loop
# ═══════════════════════════════════════════════════════════════════════════════


def run_cli() -> None:
    """Run Jarvis in the terminal with voice I/O."""
    logger.info("Starting Jarvis in CLI mode…")

    memory = MemoryManager()
    brain = JarvisBrain(memory)
    wake = WakeWordDetector()

    # Graceful shutdown on Ctrl+C
    def _shutdown(sig, frame):
        print("\n👋  Shutting down Jarvis. Goodbye!")
        wake.stop()
        memory.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)

    speak("Jarvis online. How can I help you?")
    print('\n🟢  Jarvis is running.  Say "Hey Jarvis" to wake me up.')
    print("    Press Ctrl+C to quit.\n")

    while True:
        try:
            # ── Wait for wake word ────────────────────────────────────
            print("💤  Idle — waiting for wake word…")
            command_text = wake.wait_for_wake_word()

            if command_text:
                user_text = command_text
            else:
                # ── Listen for command ────────────────────────────────────
                print("🎙️  Listening…")
                user_text = listen()
                if not user_text:
                    print("   (didn't catch that)\n")
                    continue

            print(f"🧑 You: {user_text}")

            # ── Think ─────────────────────────────────────────────────
            print("🧠  Thinking…")
            response = brain.think(user_text)
            print(f"🤖 Jarvis: {response}")

            # ── Speak ─────────────────────────────────────────────────
            print("🔊  Speaking…\n")
            speak(response)

        except KeyboardInterrupt:
            _shutdown(None, None)
        except Exception as e:
            logger.error("Unexpected error in main loop: %s", e)
            print(f"⚠️  Error: {e}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  Text Mode — type instead of talk (useful for testing without a mic)
# ═══════════════════════════════════════════════════════════════════════════════


def run_text() -> None:
    """Run Jarvis with typed input and text output (no mic/speaker needed)."""
    logger.info("Starting Jarvis in text mode…")

    memory = MemoryManager()
    brain = JarvisBrain(memory)

    print("\n🟢  Jarvis text mode. Type your message and press Enter.")
    print('    Type "quit" or "exit" to stop.\n')

    while True:
        try:
            user_text = input("🧑 You: ").strip()
            if not user_text:
                continue
            if user_text.lower() in ("quit", "exit", "bye"):
                print("👋  Goodbye!")
                break

            print("🧠  Thinking…")
            response = brain.think(user_text)
            print(f"🤖 Jarvis: {response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\n👋  Goodbye!")
            break
        except Exception as e:
            logger.error("Error: %s", e)
            print(f"⚠️  Error: {e}\n")

    memory.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis AI Assistant")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (terminal with voice)")
    parser.add_argument(
        "--text", action="store_true", help="Run in text mode (no mic/speaker needed)"
    )
    args = parser.parse_args()

    if args.cli:
        run_cli()
    elif args.text:
        run_text()
    else:
        # Default: launch the PyQt5 GUI
        try:
            from ui import launch_gui

            launch_gui()
        except ImportError as e:
            logger.warning("PyQt5 not available (%s). Falling back to CLI mode.", e)
            run_cli()


if __name__ == "__main__":
    main()

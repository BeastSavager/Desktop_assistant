"""
Jarvis AI Assistant — Desktop UI
PyQt5 dark-themed interface with state indicators and chat history.
"""

import logging
import sys
from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon, QPalette, QLinearGradient
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
    QGraphicsDropShadowEffect,
)

from brain import JarvisBrain
from memory import MemoryManager
from voice import listen, speak
from wakeword import WakeWordDetector

logger = logging.getLogger("jarvis.ui")


# ═══════════════════════════════════════════════════════════════════════════════
#  Worker Thread — runs the agent loop off the main Qt thread
# ═══════════════════════════════════════════════════════════════════════════════

class JarvisWorker(QThread):
    """Background worker that runs the wake-word → listen → think → speak loop."""

    state_changed = pyqtSignal(str)         # "idle" | "listening" | "thinking" | "speaking"
    new_message = pyqtSignal(str, str)       # (role, content)
    error_occurred = pyqtSignal(str)

    def __init__(self, brain: JarvisBrain, wake_detector: WakeWordDetector):
        super().__init__()
        self.brain = brain
        self.wake_detector = wake_detector
        self._running = True
        self._wake_word_enabled = True

    def run(self) -> None:
        while self._running:
            try:
                # ── Wake word phase ───────────────────────────────────
                if self._wake_word_enabled:
                    self.state_changed.emit("idle")
                    if not self.wake_detector.listen_for_wake_word(timeout=3):
                        continue
                    # Play a small acknowledgement
                    self.state_changed.emit("listening")
                else:
                    self.state_changed.emit("listening")

                # ── Listen phase ──────────────────────────────────────
                self.state_changed.emit("listening")
                user_text = listen()
                if not user_text:
                    continue

                self.new_message.emit("user", user_text)

                # ── Think phase ───────────────────────────────────────
                self.state_changed.emit("thinking")
                response = self.brain.think(user_text)

                self.new_message.emit("assistant", response)

                # ── Speak phase ───────────────────────────────────────
                self.state_changed.emit("speaking")
                speak(response)

            except Exception as e:
                logger.error("Worker error: %s", e)
                self.error_occurred.emit(str(e))

    def stop(self) -> None:
        self._running = False
        self.wake_detector.stop()

    def set_wake_word_enabled(self, enabled: bool) -> None:
        self._wake_word_enabled = enabled
        if enabled:
            self.wake_detector.start()
        else:
            self.wake_detector.stop()


# ═══════════════════════════════════════════════════════════════════════════════
#  Stylesheet
# ═══════════════════════════════════════════════════════════════════════════════

DARK_STYLESHEET = """
QMainWindow {
    background-color: #0d1117;
}

QWidget#centralWidget {
    background-color: #0d1117;
}

QLabel#titleLabel {
    color: #58a6ff;
    font-size: 28px;
    font-weight: bold;
    padding: 10px;
}

QLabel#stateLabel {
    font-size: 16px;
    font-weight: bold;
    padding: 8px 16px;
    border-radius: 12px;
    min-width: 140px;
    qproperty-alignment: AlignCenter;
}

QTextEdit#chatHistory {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 16px;
    font-size: 14px;
    font-family: 'Segoe UI', 'Consolas', monospace;
    selection-background-color: #1f6feb;
}

QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #58a6ff;
    color: #58a6ff;
}

QPushButton:pressed {
    background-color: #1f6feb;
    color: white;
}

QPushButton#startBtn {
    background-color: #238636;
    border-color: #2ea043;
    color: white;
}

QPushButton#startBtn:hover {
    background-color: #2ea043;
}

QPushButton#stopBtn {
    background-color: #da3633;
    border-color: #f85149;
    color: white;
}

QPushButton#stopBtn:hover {
    background-color: #f85149;
}

QPushButton#clearBtn {
    background-color: #6e40c9;
    border-color: #8b5cf6;
    color: white;
}

QPushButton#clearBtn:hover {
    background-color: #8b5cf6;
}

QFrame#headerFrame {
    background-color: #161b22;
    border-bottom: 2px solid #1f6feb;
    padding: 8px;
}

QFrame#statusFrame {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 8px;
}
"""

STATE_STYLES = {
    "idle": "background-color: #1c2128; color: #8b949e; border: 2px solid #30363d;",
    "listening": "background-color: #0d2818; color: #3fb950; border: 2px solid #238636;",
    "thinking": "background-color: #1c1507; color: #d29922; border: 2px solid #9e6a03;",
    "speaking": "background-color: #0c2d6b; color: #58a6ff; border: 2px solid #1f6feb;",
}

STATE_ICONS = {
    "idle": "💤",
    "listening": "🎙️",
    "thinking": "🧠",
    "speaking": "🔊",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════════════════════

class JarvisWindow(QMainWindow):
    """Main application window for Jarvis."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coco AI Assistant")
        self.setMinimumSize(700, 550)
        self.resize(850, 650)
        self.setStyleSheet(DARK_STYLESHEET)

        # ── Core modules ──────────────────────────────────────────────
        self.memory = MemoryManager()
        self.brain = JarvisBrain(self.memory)
        self.wake_detector = WakeWordDetector()
        self.worker: Optional[JarvisWorker] = None

        # ── Build UI ──────────────────────────────────────────────────
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 16, 20, 20)
        main_layout.setSpacing(16)

        # ── Header ────────────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)

        title = QLabel("⚡ COCO")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.state_label = QLabel("💤  IDLE")
        self.state_label.setObjectName("stateLabel")
        self.state_label.setStyleSheet(STATE_STYLES["idle"])
        header_layout.addWidget(self.state_label)

        main_layout.addWidget(header)

        # ── Chat history ──────────────────────────────────────────────
        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chatHistory")
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText(
            "Chat history will appear here…\n\n"
            'Press "Start Listening" to begin, or say "Hey COCO".'
        )
        main_layout.addWidget(self.chat_display, stretch=1)

        # ── Buttons ───────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.start_btn = QPushButton("▶  Start Listening")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self._start_listening)

        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.clicked.connect(self._stop_listening)
        self.stop_btn.setEnabled(False)

        self.clear_btn = QPushButton("🗑  Clear Chat")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self._clear_chat)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clear_btn)
        main_layout.addLayout(btn_layout)

    # ── Slots ─────────────────────────────────────────────────────────

    def _start_listening(self) -> None:
        if self.worker and self.worker.isRunning():
            return

        self.worker = JarvisWorker(self.brain, self.wake_detector)
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.new_message.connect(self._on_new_message)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._append_system('Coco is now listening. Say "Hey Coco" to begin.')

    def _stop_listening(self) -> None:
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)
            self.worker = None

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._on_state_changed("idle")
        self._append_system("Coco stopped.")

    def _clear_chat(self) -> None:
        self.chat_display.clear()
        self.memory.clear_short_term()

    def _on_state_changed(self, state: str) -> None:
        icon = STATE_ICONS.get(state, "")
        label = state.upper()
        self.state_label.setText(f"{icon}  {label}")
        self.state_label.setStyleSheet(STATE_STYLES.get(state, STATE_STYLES["idle"]))

    def _on_new_message(self, role: str, content: str) -> None:
        if role == "user":
            self._append_chat("🧑 You", content, "#3fb950")
        else:
            self._append_chat("🤖 Coco", content, "#58a6ff")

    def _on_error(self, error: str) -> None:
        self._append_system(f"⚠️ Error: {error}")

    # ── Chat formatting helpers ───────────────────────────────────────

    def _append_chat(self, sender: str, text: str, color: str) -> None:
        self.chat_display.append(
            f'<p style="margin:8px 0;">'
            f'<span style="color:{color}; font-weight:bold;">{sender}:</span> '
            f'<span style="color:#c9d1d9;">{text}</span>'
            f"</p>"
        )
        self._scroll_to_bottom()

    def _append_system(self, text: str) -> None:
        self.chat_display.append(
            f'<p style="margin:6px 0; color:#8b949e; font-style:italic;">'
            f"ℹ️  {text}</p>"
        )
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        sb = self.chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── Cleanup ───────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._stop_listening()
        self.memory.close()
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry helper
# ═══════════════════════════════════════════════════════════════════════════════

def launch_gui() -> None:
    """Launch the Jarvis GUI application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Force dark palette as a fallback
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0d1117"))
    palette.setColor(QPalette.WindowText, QColor("#c9d1d9"))
    palette.setColor(QPalette.Base, QColor("#161b22"))
    palette.setColor(QPalette.AlternateBase, QColor("#21262d"))
    palette.setColor(QPalette.Text, QColor("#c9d1d9"))
    palette.setColor(QPalette.Button, QColor("#21262d"))
    palette.setColor(QPalette.ButtonText, QColor("#c9d1d9"))
    palette.setColor(QPalette.Highlight, QColor("#1f6feb"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = JarvisWindow()
    window.show()
    sys.exit(app.exec_())

"""
Jarvis AI Assistant — Desktop UI
PyQt5 dark-themed interface with state indicators, hybrid voice/text input,
and custom styled chat bubble cards.
"""

import logging
import sys

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from brain import JarvisBrain
from memory import MemoryManager
from voice import listen, speak
from wakeword import WakeWordDetector

logger = logging.getLogger("jarvis.ui")


# ═══════════════════════════════════════════════════════════════════════════════
#  Worker Threads
# ═══════════════════════════════════════════════════════════════════════════════


class JarvisWorker(QThread):
    """Background worker that runs the wake-word → listen → think → speak loop."""

    state_changed = pyqtSignal(str)  # "idle" | "listening" | "thinking" | "speaking"
    new_message = pyqtSignal(str, str)  # (role, content)
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
                user_text = ""
                if self._wake_word_enabled:
                    self.state_changed.emit("idle")
                    detected, remaining = self.wake_detector.listen_for_wake_word(timeout=3)
                    if not self._running:
                        break
                    if not detected:
                        continue
                    if remaining:
                        user_text = remaining
                    else:
                        self.state_changed.emit("listening")
                else:
                    self.state_changed.emit("listening")

                # ── Listen phase ──────────────────────────────────────
                if not user_text:
                    if not self._running:
                        break
                    self.state_changed.emit("listening")
                    user_text = listen()
                    if not user_text:
                        continue

                if not self._running:
                    break
                self.new_message.emit("user", user_text)

                # ── Think phase ───────────────────────────────────────
                self.state_changed.emit("thinking")
                response = self.brain.think(user_text)

                if not self._running:
                    break
                self.new_message.emit("assistant", response)

                # ── Speak phase ───────────────────────────────────────
                self.state_changed.emit("speaking")
                speak(response)

            except Exception as e:
                logger.error("Voice worker error: %s", e)
                if self._running:
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


class JarvisTextWorker(QThread):
    """Background worker to process a manual text input (bypasses voice loop)."""

    state_changed = pyqtSignal(str)  # "idle" | "listening" | "thinking" | "speaking"
    new_message = pyqtSignal(str, str)  # (role, content)
    finished_query = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, brain: JarvisBrain, text: str):
        super().__init__()
        self.brain = brain
        self.text = text

    def run(self) -> None:
        try:
            self.new_message.emit("user", self.text)
            self.state_changed.emit("thinking")
            response = self.brain.think(self.text)
            self.new_message.emit("assistant", response)
            self.state_changed.emit("speaking")
            speak(response)
        except Exception as e:
            logger.error("Text worker error: %s", e)
            self.error_occurred.emit(str(e))
        finally:
            self.finished_query.emit()


# ═══════════════════════════════════════════════════════════════════════════════
#  UI Custom Cards and Bubbles
# ═══════════════════════════════════════════════════════════════════════════════


class ChatBubble(QFrame):
    """A styled message bubble with user vs assistant alignments and custom borders."""

    def __init__(self, sender: str, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("chatBubble")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self.sender_label = QLabel(sender)
        self.sender_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; text-transform: uppercase; letter-spacing: 1.1px; "
            "color: "
            + ("#00F2FE" if is_user else "#a855f7")
            + "; background: transparent; border: none;"
        )

        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text_label.setStyleSheet(
            "font-size: 14px; color: #e2e8f0; background: transparent; border: none;"
        )

        layout.addWidget(self.sender_label)
        layout.addWidget(self.text_label)

        # Style bubble cards by targeting specific object name to prevent styling child labels
        if is_user:
            self.setStyleSheet("""
                QFrame#chatBubble {
                    background-color: #0b253a;
                    border: 1.5px solid #00f2fe;
                    border-radius: 16px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#chatBubble {
                    background-color: #160f26;
                    border: 1.5px solid #a855f7;
                    border-radius: 16px;
                }
            """)


class SystemMessage(QWidget):
    """A centered, italicized info card for logging events and errors."""

    def __init__(self, text: str, is_error: bool = False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 6, 20, 6)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        if is_error:
            self.label.setStyleSheet(
                "color: #ff4a4a; font-weight: bold; font-size: 12px; background: transparent; border: none;"
            )
        else:
            self.label.setStyleSheet(
                "color: #64748b; font-style: italic; font-size: 12px; background: transparent; border: none;"
            )
        self.label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.label)


class SuggestionCard(QPushButton):
    """A clickable card representing a quick query suggestion."""

    def __init__(self, title: str, query: str, callback, parent=None):
        super().__init__(parent)
        self.query = query
        self.callback = callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #ffffff; background: transparent; border: none;"
        )

        self.sub_label = QLabel("Click to run command")
        self.sub_label.setStyleSheet(
            "font-size: 11px; color: #64748b; background: transparent; border: none;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.sub_label)

        self.clicked.connect(self._on_click)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(75)

        self.setStyleSheet("""
            QPushButton {
                background-color: #111827;
                border: 1.5px solid #1f2937;
                border-radius: 12px;
                text-align: left;
                min-width: 170px;
                max-width: 240px;
            }
            QPushButton:hover {
                border-color: #00f2fe;
                background-color: #1f2937;
            }
        """)

    def _on_click(self):
        self.callback(self.query)


# ═══════════════════════════════════════════════════════════════════════════════
#  Stylesheet
# ═══════════════════════════════════════════════════════════════════════════════

DARK_STYLESHEET = """
QMainWindow {
    background-color: #0a0e17;
}

QWidget#centralWidget {
    background-color: #0a0e17;
}

QFrame#headerFrame {
    background-color: transparent;
    border-bottom: 1.5px solid #1f2937;
    padding: 4px;
}

QLabel#titleLabel {
    color: #ffffff;
    font-size: 20px;
    font-weight: bold;
    font-family: 'Outfit', 'Segoe UI', sans-serif;
    letter-spacing: 2px;
}

QScrollArea#chatScrollArea {
    background-color: transparent;
    border: none;
}

QWidget#scrollContent {
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #1e293b;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #334155;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

QLineEdit#textInput {
    background-color: #111827;
    color: #e2e8f0;
    border: 1.5px solid #1f2937;
    border-radius: 20px;
    padding: 10px 18px;
    font-size: 14px;
    font-family: 'Segoe UI', sans-serif;
}

QLineEdit#textInput:focus {
    border-color: #00f2fe;
}

QPushButton#clearBtn {
    background-color: transparent;
    color: #64748b;
    border: none;
    font-size: 12px;
    font-weight: bold;
    padding: 6px 12px;
    min-width: 80px;
}

QPushButton#clearBtn:hover {
    color: #a855f7;
}

QPushButton#sendBtn {
    background-color: #0b1f30;
    border: 1.5px solid #00f2fe;
    color: #00f2fe;
    min-width: 60px;
    padding: 10px 14px;
    border-radius: 20px;
    font-weight: bold;
}

QPushButton#sendBtn:hover {
    background-color: #00f2fe;
    color: #080b11;
}
"""

BUTTON_STYLES = {
    "inactive": "background-color: #111827; border: 1.5px solid #1f2937; color: #94a3b8; border-radius: 20px; padding: 10px 18px; font-weight: bold;",
    "listening": "background-color: #092b18; border: 1.5px solid #10b981; color: #10b981; border-radius: 20px; padding: 10px 18px; font-weight: bold;",
    "thinking": "background-color: #3b2e0f; border: 1.5px solid #f59e0b; color: #f59e0b; border-radius: 20px; padding: 10px 18px; font-weight: bold;",
    "speaking": "background-color: #0b1f30; border: 1.5px solid #00f2fe; color: #00f2fe; border-radius: 20px; padding: 10px 18px; font-weight: bold;",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════════════════════


class JarvisWindow(QMainWindow):
    """Main application window for Jarvis."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis AI Assistant")
        self.setMinimumSize(700, 600)
        self.resize(800, 680)
        self.setStyleSheet(DARK_STYLESHEET)

        # ── Core modules ──────────────────────────────────────────────
        self.memory = MemoryManager()
        self.brain = JarvisBrain(self.memory)
        self.wake_detector = WakeWordDetector()
        self.worker: JarvisWorker | None = None
        self.text_worker: JarvisTextWorker | None = None
        self._voice_was_running = False

        # ── Build UI ──────────────────────────────────────────────────
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 6)

        title = QLabel("⚡ JARVIS")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Status dot & indicator text
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(10, 10)
        self.status_dot.setStyleSheet("border-radius: 5px; background-color: #64748b;")

        self.status_text = QLabel("Voice Inactive")
        self.status_text.setStyleSheet(
            "color: #64748b; font-size: 12px; font-family: 'Segoe UI'; font-weight: bold;"
        )

        header_layout.addWidget(self.status_dot)
        header_layout.addWidget(self.status_text)

        header_layout.addSpacing(16)

        # Small clear chat link
        self.clear_btn = QPushButton("Clear history")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_chat)
        header_layout.addWidget(self.clear_btn)

        main_layout.addWidget(header)

        # ── Chat history (Scrollable Area) ────────────────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("chatScrollArea")
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scrollContent")

        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(14)

        # ── Welcome Panel (Suggestions) ───────────────────────────────
        self.welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_widget)
        welcome_layout.setContentsMargins(0, 40, 0, 40)
        welcome_layout.setSpacing(24)

        welcome_title = QLabel("How can I help you today?")
        welcome_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")
        welcome_title.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(welcome_title)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)
        cards_layout.setAlignment(Qt.AlignCenter)

        card_time = SuggestionCard(
            "🕒 Get current time", "what is the time right now", self._submit_suggestion
        )
        card_chrome = SuggestionCard(
            "🌐 Open Chrome", "open chrome browser", self._submit_suggestion
        )
        card_code = SuggestionCard(
            "💻 Open VS Code", "open visual studio code", self._submit_suggestion
        )

        cards_layout.addWidget(card_time)
        cards_layout.addWidget(card_chrome)
        cards_layout.addWidget(card_code)
        welcome_layout.addLayout(cards_layout)

        self.scroll_layout.addWidget(self.welcome_widget)

        # Stretch spacer keeps messages pushed down
        self.scroll_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # ── Floating Input Bar ────────────────────────────────────────
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        # Voice Toggle Button
        self.voice_btn = QPushButton("🎙️ Start Voice")
        self.voice_btn.setObjectName("voiceBtn")
        self.voice_btn.setStyleSheet(BUTTON_STYLES["inactive"])
        self.voice_btn.setCursor(Qt.PointingHandCursor)
        self.voice_btn.clicked.connect(self._toggle_voice)

        self.text_input = QLineEdit()
        self.text_input.setObjectName("textInput")
        self.text_input.setPlaceholderText("Ask Jarvis anything…")
        self.text_input.returnPressed.connect(self._submit_text)

        self.send_btn = QPushButton("➔")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._submit_text)

        input_layout.addWidget(self.voice_btn)
        input_layout.addWidget(self.text_input, stretch=1)
        input_layout.addWidget(self.send_btn)
        main_layout.addLayout(input_layout)

    # ── Slots ─────────────────────────────────────────────────────────

    def _toggle_voice(self) -> None:
        if self.worker and self.worker.isRunning():
            self._stop_listening()
        else:
            self._start_listening()

    def _terminate_voice_worker(self) -> None:
        """
        Stop the voice worker and block until its thread has fully exited.

        This guarantees the microphone is released before any new worker (voice
        or text) starts, preventing the concurrent-mic race that PyAudio cannot
        handle. We wait with a timeout slightly longer than the worst-case
        in-flight ``listen()`` call so the UI never hangs indefinitely.
        """
        if self.worker is None:
            return
        self.worker.stop()
        if self.worker.isRunning():
            self.worker.wait(12000)  # ms; covers LISTEN_TIMEOUT + phrase limit
        self.worker.deleteLater()
        self.worker = None

    def _start_listening(self) -> None:
        if self.worker and self.worker.isRunning():
            return

        # Ensure any prior worker is fully torn down before re-acquiring the mic.
        self._terminate_voice_worker()
        # The detector may have been disabled by a previous stop(); re-arm it.
        self.wake_detector.start()

        self.worker = JarvisWorker(self.brain, self.wake_detector)
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.new_message.connect(self._on_new_message)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

        # Update initial states
        self.status_dot.setStyleSheet("border-radius: 5px; background-color: #10B981;")
        self.status_text.setText("Listening (Hey Jarvis)...")
        self.status_text.setStyleSheet("color: #10B981; font-weight: bold;")
        self.voice_btn.setStyleSheet(BUTTON_STYLES["listening"])
        self.voice_btn.setText("🎙️ Stop Voice")

    def _stop_listening(self) -> None:
        self._terminate_voice_worker()

        self.status_dot.setStyleSheet("border-radius: 5px; background-color: #64748b;")
        self.status_text.setText("Voice Inactive")
        self.status_text.setStyleSheet("color: #64748b; font-weight: bold;")
        self.voice_btn.setStyleSheet(BUTTON_STYLES["inactive"])
        self.voice_btn.setText("🎙️ Start Voice")

    def _submit_suggestion(self, query: str) -> None:
        self.text_input.setText(query)
        self._submit_text()

    def _submit_text(self) -> None:
        text = self.text_input.text().strip()
        if not text:
            return

        self.text_input.clear()

        # Hide suggestions if they are still visible
        if self.welcome_widget.isVisible():
            self.welcome_widget.hide()

        # Pause the voice loop if active and wait for the mic to be released
        # before the text worker runs, to prevent microphone clashes.
        self._voice_was_running = bool(self.worker and self.worker.isRunning())
        self._terminate_voice_worker()

        # Lock controls during think/speak phase
        self.voice_btn.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.text_input.setEnabled(False)

        # Run text submission in background text worker thread
        self.text_worker = JarvisTextWorker(self.brain, text)
        self.text_worker.state_changed.connect(self._on_state_changed)
        self.text_worker.new_message.connect(self._on_new_message)
        self.text_worker.error_occurred.connect(self._on_error)
        self.text_worker.finished_query.connect(self._on_text_query_finished)
        self.text_worker.start()

    def _on_text_query_finished(self) -> None:
        self.text_worker = None
        self.voice_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.text_input.setEnabled(True)
        self.text_input.setFocus()

        # Restore voice detector if it was running previously
        if self._voice_was_running:
            self._start_listening()
        else:
            self.status_dot.setStyleSheet("border-radius: 5px; background-color: #64748b;")
            self.status_text.setText("Voice Inactive")
            self.status_text.setStyleSheet("color: #64748b; font-weight: bold;")
            self.voice_btn.setStyleSheet(BUTTON_STYLES["inactive"])
            self.voice_btn.setText("🎙️ Start Voice")

    def _clear_chat(self) -> None:
        self.memory.clear_short_term()

        # Remove all message widgets/layouts in scrollarea except the suggestions welcome widget & trailing spacer
        while self.scroll_layout.count() > 2:
            item = self.scroll_layout.takeAt(1)  # keep index 0 (welcome_widget)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                layout = item.layout()
                if layout is not None:
                    while layout.count():
                        sub_item = layout.takeAt(0)
                        sub_widget = sub_item.widget()
                        if sub_widget is not None:
                            sub_widget.deleteLater()

        self.welcome_widget.show()

    def _on_state_changed(self, state: str) -> None:
        # Dynamic status indicator dot changes
        if state == "idle":
            self.status_dot.setStyleSheet("border-radius: 5px; background-color: #64748b;")
            self.status_text.setText(
                "Voice Active (Hey Jarvis)" if self.worker else "Voice Inactive"
            )
            self.status_text.setStyleSheet("color: #64748b; font-weight: bold;")
            self.voice_btn.setStyleSheet(
                BUTTON_STYLES["inactive"] if not self.worker else BUTTON_STYLES["listening"]
            )
            self.voice_btn.setText("🎙️ Start Voice" if not self.worker else "🎙️ Stop Voice")
        elif state == "listening":
            self.status_dot.setStyleSheet("border-radius: 5px; background-color: #10B981;")
            self.status_text.setText("Listening...")
            self.status_text.setStyleSheet("color: #10B981; font-weight: bold;")
            self.voice_btn.setStyleSheet(BUTTON_STYLES["listening"])
            self.voice_btn.setText("🎙️ Stop Voice")
        elif state == "thinking":
            self.status_dot.setStyleSheet("border-radius: 5px; background-color: #F59E0B;")
            self.status_text.setText("Thinking...")
            self.status_text.setStyleSheet("color: #F59E0B; font-weight: bold;")
            self.voice_btn.setStyleSheet(BUTTON_STYLES["thinking"])
            self.voice_btn.setText("🧠 Thinking...")
        elif state == "speaking":
            self.status_dot.setStyleSheet("border-radius: 5px; background-color: #06B6D4;")
            self.status_text.setText("Speaking...")
            self.status_text.setStyleSheet("color: #06B6D4; font-weight: bold;")
            self.voice_btn.setStyleSheet(BUTTON_STYLES["speaking"])
            self.voice_btn.setText("🔊 Speaking...")

    def _on_new_message(self, role: str, content: str) -> None:
        if self.welcome_widget.isVisible():
            self.welcome_widget.hide()

        if role == "user":
            self._append_chat("🧑 You", content, is_user=True)
        else:
            self._append_chat("🤖 Jarvis", content, is_user=False)

    def _on_error(self, error: str) -> None:
        self._append_system(f"⚠️ Error: {error}")

    # ── Chat formatting helpers ───────────────────────────────────────

    def _append_chat(self, sender: str, text: str, is_user: bool) -> None:
        bubble = ChatBubble(sender, text, is_user)
        bubble.setMaximumWidth(550)

        # Wrap inside QHBoxLayout for left/right alignment
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)

        if is_user:
            h_layout.addStretch(1)
            h_layout.addWidget(bubble)
        else:
            h_layout.addWidget(bubble)
            h_layout.addStretch(1)

        # Insert layout right before the last stretch spacer
        self.scroll_layout.insertLayout(self.scroll_layout.count() - 1, h_layout)

        # Scroll to bottom after layout updates
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _append_system(self, text: str) -> None:
        if self.welcome_widget.isVisible():
            self.welcome_widget.hide()

        sys_widget = SystemMessage(text, is_error=False)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, sys_widget)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        sb = self.scroll_area.verticalScrollBar()
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
    palette.setColor(QPalette.Window, QColor("#0a0e17"))
    palette.setColor(QPalette.WindowText, QColor("#e2e8f0"))
    palette.setColor(QPalette.Base, QColor("#111827"))
    palette.setColor(QPalette.AlternateBase, QColor("#1e293b"))
    palette.setColor(QPalette.Text, QColor("#e2e8f0"))
    palette.setColor(QPalette.Button, QColor("#111827"))
    palette.setColor(QPalette.ButtonText, QColor("#e2e8f0"))
    palette.setColor(QPalette.Highlight, QColor("#00f2fe"))
    palette.setColor(QPalette.HighlightedText, QColor("#080b11"))
    app.setPalette(palette)

    window = JarvisWindow()
    window.show()
    sys.exit(app.exec_())

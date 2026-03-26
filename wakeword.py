"""
Jarvis AI Assistant — Wake Word Detector
Listens continuously for "Hey Jarvis" using SpeechRecognition.
Lightweight, no external API dependency beyond Google STT.
"""

import logging
from typing import Optional

import speech_recognition as sr

from config import WAKE_WORD_ALTERNATIVES, ENERGY_THRESHOLD

logger = logging.getLogger("jarvis.wakeword")


class WakeWordDetector:
    """Continuously listens for the wake word and returns True when detected."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_threshold = True
        self._active = True

    def listen_for_wake_word(self, timeout: int = 3) -> bool:
        """
        Listen for a short burst of audio and check for the wake word.
        Returns True if wake word detected, False otherwise.
        """
        if not self._active:
            return False

        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=3
                )
        except sr.WaitTimeoutError:
            return False
        except OSError as e:
            logger.error("Microphone error during wake word detection: %s", e)
            return False

        try:
            text = self.recognizer.recognize_google(audio).lower().strip()
            logger.debug("Wake word heard: '%s'", text)

            for phrase in WAKE_WORD_ALTERNATIVES:
                if phrase in text:
                    logger.info("✅ Wake word detected!")
                    return True
            return False

        except sr.UnknownValueError:
            return False
        except sr.RequestError as e:
            logger.error("Wake word STT error: %s", e)
            return False

    def wait_for_wake_word(self) -> None:
        """Block until the wake word is detected."""
        logger.info("Waiting for wake word…")
        while self._active:
            if self.listen_for_wake_word():
                return

    def stop(self) -> None:
        """Stop the detector loop."""
        self._active = False

    def start(self) -> None:
        """Re-enable the detector."""
        self._active = True

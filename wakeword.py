"""
Jarvis AI Assistant — Wake Word Detector
Listens continuously for "Hey Jarvis" using SpeechRecognition.
Lightweight, no external API dependency beyond Google STT.
"""

import logging

import speech_recognition as sr

from config import ENERGY_THRESHOLD, WAKE_WORD_ALTERNATIVES
from voice import mic_lock

logger = logging.getLogger("jarvis.wakeword")


class WakeWordDetector:
    """Continuously listens for the wake word and returns True when detected."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_threshold = True
        self._active = True

    def listen_for_wake_word(self, timeout: int = 3) -> tuple[bool, str]:
        """
        Listen for a short burst of audio and check for the wake word.
        Returns (detected: bool, remaining_text: str).
        """
        if not self._active:
            return False, ""

        try:
            with mic_lock, sr.Microphone() as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=4)
        except sr.WaitTimeoutError:
            return False, ""
        except OSError as e:
            logger.error("Microphone error during wake word detection: %s", e)
            return False, ""

        try:
            text = self.recognizer.recognize_google(audio).lower().strip()
            logger.debug("Wake word heard: '%s'", text)

            for phrase in WAKE_WORD_ALTERNATIVES:
                if phrase in text:
                    logger.info("✅ Wake word detected: '%s'", text)
                    # Extract everything after the wake word
                    idx = text.find(phrase)
                    remaining = text[idx + len(phrase) :].strip()
                    remaining = remaining.lstrip(",.?! ").strip()
                    return True, remaining
            return False, ""

        except sr.UnknownValueError:
            return False, ""
        except sr.RequestError as e:
            logger.error("Wake word STT error: %s", e)
            return False, ""

    def wait_for_wake_word(self) -> str:
        """Block until the wake word is detected and return any remaining command text."""
        logger.info("Waiting for wake word…")
        while self._active:
            detected, remaining = self.listen_for_wake_word()
            if detected:
                return remaining
        return ""

    def stop(self) -> None:
        """Stop the detector loop."""
        self._active = False

    def start(self) -> None:
        """Re-enable the detector."""
        self._active = True

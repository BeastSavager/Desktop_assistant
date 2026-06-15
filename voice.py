"""
Jarvis AI Assistant — Voice Module
Speech-to-text (via SpeechRecognition / Google STT) and
text-to-speech (via edge-tts + pygame for playback).
"""

import asyncio
import logging
import os
import tempfile
import threading

import speech_recognition as sr

from config import (
    ENERGY_THRESHOLD,
    LISTEN_PHRASE_LIMIT,
    LISTEN_TIMEOUT,
    TTS_RATE,
    TTS_VOICE,
)

logger = logging.getLogger("jarvis.voice")

# ═══════════════════════════════════════════════════════════════════════════════
#  Speech-to-Text
# ═══════════════════════════════════════════════════════════════════════════════

_recognizer = sr.Recognizer()
_recognizer.energy_threshold = ENERGY_THRESHOLD
_recognizer.dynamic_energy_threshold = True

# Shared across the assistant: only one thread may hold the microphone at a time.
# Both listen() and the wake-word detector acquire this before opening the mic,
# which prevents the PyAudio "device already in use" race between workers.
mic_lock = threading.Lock()


def listen(timeout: int | None = None, phrase_limit: int | None = None) -> str | None:
    """
    Listen to the microphone and return transcribed text.
    Returns None if nothing was heard or an error occurred.
    """
    timeout = timeout or LISTEN_TIMEOUT
    phrase_limit = phrase_limit or LISTEN_PHRASE_LIMIT

    try:
        with mic_lock, sr.Microphone() as source:
            logger.info("Listening…")
            audio = _recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
    except sr.WaitTimeoutError:
        logger.debug("Listen timed out — no speech detected.")
        return None
    except OSError as e:
        logger.error("Microphone error: %s", e)
        return None

    # Transcribe with Google Speech Recognition (free, no key needed)
    try:
        text = _recognizer.recognize_google(audio)
        logger.info("Heard: %s", text)
        return text
    except sr.UnknownValueError:
        logger.debug("Could not understand audio.")
        return None
    except sr.RequestError as e:
        logger.error("STT service error: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Text-to-Speech  (edge-tts → temp mp3 → pygame playback)
# ═══════════════════════════════════════════════════════════════════════════════

_tts_lock = threading.Lock()
_pygame_initialized = False


def _ensure_pygame() -> None:
    """Lazy-init pygame mixer exactly once."""
    global _pygame_initialized
    if not _pygame_initialized:
        try:
            import pygame

            pygame.mixer.init()
            _pygame_initialized = True
        except Exception as e:
            logger.error("pygame mixer init failed: %s", e)


async def _generate_speech(text: str, output_path: str) -> None:
    """Use edge-tts to generate an mp3 file from text."""
    import edge_tts

    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
    await communicate.save(output_path)


def speak(text: str) -> None:
    """
    Convert text to speech and play it.
    Thread-safe; blocks until playback finishes.
    """
    if not text or not text.strip():
        return

    _ensure_pygame()

    with _tts_lock:
        tmp_path = None
        try:
            import pygame

            # Generate speech audio to a temp file
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(tmp_fd)

            asyncio.run(_generate_speech(text, tmp_path))

            # Play the audio
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)

        except Exception as e:
            logger.error("TTS playback error: %s", e)
        finally:
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


def speak_async(text: str) -> threading.Thread:
    """Non-blocking speak: runs TTS in a background thread. Returns the thread."""
    t = threading.Thread(target=speak, args=(text,), daemon=True)
    t.start()
    return t

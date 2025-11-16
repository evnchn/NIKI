"""
Text-to-Speech Module

This module provides text-to-speech functionality for the NIKI Photo Booth.
Uses Google Text-to-Speech (gTTS) to generate MP3 files and NiceGUI for playback.
Files are stored in the 'tts/' directory and served as media files.

The emotion parameter is currently accepted but not used in speech generation.
"""

import os
import uuid

from gtts import gTTS
from nicegui import app, ui

# Directory for storing TTS audio files
_TTS_DIR = "tts"
os.makedirs(_TTS_DIR, exist_ok=True)

# Path to the most recently generated TTS file
latest_tts_path = None


def generate_tts(text: str, emotion: str | None = None) -> str:
    """
    Generate TTS audio file from text and register with NiceGUI.

    Creates an MP3 file using gTTS, saves it to the TTS directory,
    and registers it as a media file for web serving.

    Args:
        text: Text to convert to speech
        emotion: Emotion parameter (currently unused)

    Returns:
        str: Media URL path for the generated audio file

    Side effect: Updates module-level latest_tts_path
    """
    global latest_tts_path

    # Generate unique filename
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(_TTS_DIR, filename)

    # Generate and save TTS audio
    tts = gTTS(text)
    tts.save(filepath)

    # Register with NiceGUI media files
    media_path = f"/tts/{filename}"
    try:
        app.add_media_file(url_path=media_path, local_file=filepath)
    except Exception:
        # Ignore if media file already registered
        pass

    latest_tts_path = media_path
    return media_path


def play_tts(text: str, emotion: str | None = None) -> None:
    """
    Generate TTS audio and play it via JavaScript.

    Combines generation and playback in a single call for convenience.

    Args:
        text: Text to speak
        emotion: Emotion parameter (currently unused)
    """
    media_path = generate_tts(text, emotion)
    ui.run_javascript(f"window.currentAudio = new Audio('{media_path}'); window.currentAudio.play();")

"""Text-to-speech helpers extracted from main.py for reuse and testing.

This module uses gTTS to render speech to mp3 files under `tts/` and
registers them with NiceGUI's media files so the frontend can play them.
"""

import os
import uuid

from gtts import gTTS
from nicegui import app, ui

_TTS_DIR = 'tts'
os.makedirs(_TTS_DIR, exist_ok=True)

# last generated path (URL path served by NiceGUI)
latest_tts_path = None


def generate_tts(text: str, emotion: str | None = None) -> str:
    """Generate TTS mp3 from `text`, register it with NiceGUI and return the media path.

    Side effect: updates module-level `latest_tts_path`.
    """
    global latest_tts_path
    filename = f'{uuid.uuid4()}.mp3'
    filepath = os.path.join(_TTS_DIR, filename)
    tts = gTTS(text)
    tts.save(filepath)
    media_path = f'/tts/{filename}'
    try:
        app.add_media_file(url_path=media_path, local_file=filepath)
    except Exception:
        # In some NiceGUI setups add_media_file may be called multiple times; ignore if it fails
        pass
    latest_tts_path = media_path
    return media_path


def play_tts(text: str, emotion: str | None = None) -> None:
    """Generate and play TTS via NiceGUI's `ui.run_javascript`.

    Keeps the same simple behavior as the original implementation.
    """
    media_path = generate_tts(text, emotion)
    ui.run_javascript(
        f"window.currentAudio = new Audio('{media_path}'); window.currentAudio.play();"
    )

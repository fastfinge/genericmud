"""Pick the best available self-voice backend for the platform.

Windows: accessible_output2 (routes to the running screen reader — NVDA speaks in the
user's own voice/settings) > SAPI5. macOS: the built-in ``say``. Linux: speech-dispatcher
(``spd-say``, the same engine Orca drives). Console print is the last resort everywhere.
Constructed on the thread that uses it (SAPI is COM, apartment-bound).
"""

from __future__ import annotations

import sys

from genericmud.voice.backends.base import VoiceBackend


class PrintBackend(VoiceBackend):
    def speak(self, text: str) -> None:
        # A PyInstaller ``--windowed`` process has no stdout. This backend is the
        # last resort when native speech is unavailable, so it must degrade to
        # silence instead of crashing every UI announcement.
        if sys.stdout is None:
            return
        try:
            print("SPEAK:", text)
        except (OSError, ValueError):
            return

    def stop(self) -> None:
        pass


def make_voice_backend() -> VoiceBackend:
    # accessible_output2 routes to the running screen reader (NVDA → the user's own
    # voice) and bundles the controller DLLs, so it's preferred over raw SAPI.
    try:
        from genericmud.voice.backends.ao2 import Ao2Backend

        return Ao2Backend()
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            from genericmud.voice.backends.sapi import SapiBackend

            return SapiBackend()
        except Exception:  # pywin32 / SAPI unavailable
            pass
    elif sys.platform == "darwin":
        try:
            from genericmud.voice.backends.subprocess_tts import MacSayBackend

            return MacSayBackend()
        except Exception:  # `say` missing (unheard of on macOS)
            pass
    elif sys.platform.startswith("linux"):
        try:
            from genericmud.voice.backends.subprocess_tts import SpeechDispatcherBackend

            return SpeechDispatcherBackend()
        except Exception:  # speech-dispatcher not installed
            pass
    return PrintBackend()

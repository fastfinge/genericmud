"""Cross-platform self-voice backend selection and the queued subprocess TTS backend."""

from __future__ import annotations

import sys
import time

import pytest

from genericmud.voice import factory
from genericmud.voice.backends import subprocess_tts
from genericmud.voice.backends.subprocess_tts import (
    MacSayBackend,
    QueuedTtsBackend,
    SpeechDispatcherBackend,
)


def test_factory_picks_say_on_macos(monkeypatch):
    monkeypatch.setattr(factory.sys, "platform", "darwin")
    monkeypatch.setattr(subprocess_tts.shutil, "which", lambda _cmd: "/usr/bin/say")
    backend = factory.make_voice_backend()
    try:
        assert isinstance(backend, MacSayBackend)
    finally:
        backend.close()


def test_factory_picks_speech_dispatcher_on_linux(monkeypatch):
    monkeypatch.setattr(factory.sys, "platform", "linux")
    monkeypatch.setattr(subprocess_tts.shutil, "which", lambda _cmd: "/usr/bin/spd-say")
    backend = factory.make_voice_backend()
    try:
        assert isinstance(backend, SpeechDispatcherBackend)
    finally:
        backend.close()


def test_factory_falls_back_to_print_when_no_tts(monkeypatch):
    # No screen reader, no platform TTS on PATH: degrade to the silent print backend
    # rather than crash the app's first announcement.
    monkeypatch.setattr(factory.sys, "platform", "linux")
    monkeypatch.setattr(subprocess_tts.shutil, "which", lambda _cmd: None)
    assert isinstance(factory.make_voice_backend(), factory.PrintBackend)


def test_queued_backend_requires_the_command_on_path(monkeypatch):
    monkeypatch.setattr(subprocess_tts.shutil, "which", lambda _cmd: None)
    with pytest.raises(RuntimeError):
        QueuedTtsBackend(["definitely-not-a-real-tts"])


def test_queued_backend_speaks_serially_and_stop_drains(monkeypatch):
    # Use a benign real command so the worker actually spawns and waits, exercising the
    # queue/subprocess path without needing an audio device.
    monkeypatch.setattr(subprocess_tts.shutil, "which", lambda _cmd: "/usr/bin/true")
    backend = QueuedTtsBackend(["true"])
    try:
        backend.speak("one")
        backend.speak("two")
        backend.speak("")  # empty text is ignored, not queued
        backend.stop()  # must not raise; drains the queue and terminates any current proc
        time.sleep(0.05)
    finally:
        backend.close()


def test_cancel_command_runs_on_stop(monkeypatch):
    monkeypatch.setattr(subprocess_tts.shutil, "which", lambda _cmd: "/usr/bin/true")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess_tts.subprocess, "run",
        lambda cmd, **_kw: calls.append(cmd),
    )
    backend = QueuedTtsBackend(["true"], cancel_command=["spd-say", "-C"])
    try:
        backend.stop()
        assert ["spd-say", "-C"] in calls  # the daemon-cancel ran
    finally:
        backend.close()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell command for the smoke test")
def test_queued_backend_actually_runs_the_command(monkeypatch, tmp_path):
    # Prove the worker runs the command with the text as the final argv element.
    marker = tmp_path / "spoken.txt"
    script = tmp_path / "fake_tts.sh"
    script.write_text(f'#!/bin/sh\nprintf "%s\\n" "$1" >> "{marker}"\n', encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setattr(subprocess_tts.shutil, "which", lambda _cmd: str(script))
    backend = QueuedTtsBackend([str(script)])
    try:
        backend.speak("hello world")
        for _ in range(100):
            if marker.exists() and marker.read_text().strip():
                break
            time.sleep(0.02)
        assert marker.read_text().strip() == "hello world"
    finally:
        backend.close()

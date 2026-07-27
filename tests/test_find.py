"""The engine half of Find: a FIND message searches the scrollback and reports back."""

from __future__ import annotations

from genericmud.app import EngineApp
from genericmud.bridge import protocol
from genericmud.config.keymap import load_keymap
from genericmud.protocol.telnet import DataReceived
from genericmud.voice.router import VoiceRouter
from tests.helpers import RecordingBackend


def _app(*lines: str) -> tuple[EngineApp, RecordingBackend, list[dict]]:
    backend = RecordingBackend()
    posted: list[dict] = []
    app = EngineApp(
        VoiceRouter(backend, clock=lambda: 0.0),
        send=lambda text: None,
        post=posted.append,
        keymap=load_keymap("vipmud"),
    )
    for text in lines:
        app.on_telnet_event(DataReceived(text.encode() + b"\r\n"))
    posted.clear()  # only care about what the search posts
    return app, backend, posted


def _results(posted: list[dict]) -> list[dict]:
    return [m for m in posted if m["type"] == protocol.FIND_RESULT]


def test_find_reports_the_matching_line_and_speaks_it():
    app, backend, posted = _app("a quiet road", "a dragon roars", "a quiet road again")
    app.on_ws_message(protocol.find("dragon"))
    assert _results(posted) == [{"type": protocol.FIND_RESULT, "text": "a dragon roars",
                                 "found": True}]
    assert "a dragon roars" in backend.spoken


def test_a_miss_is_reported_as_not_found_and_said_aloud():
    app, backend, posted = _app("a quiet road")
    app.on_ws_message(protocol.find("griffin"))
    assert _results(posted) == [{"type": protocol.FIND_RESULT, "text": "", "found": False}]
    assert "not found: griffin" in backend.spoken


def test_find_searches_backwards_by_default_and_forwards_when_asked():
    app, _backend, posted = _app("old dragon", "middle", "new dragon")
    app.on_ws_message(protocol.find("dragon"))  # from the newest line, going back
    assert _results(posted)[-1]["text"] == "old dragon"
    app.on_ws_message(protocol.find("dragon", forward=True))
    assert _results(posted)[-1]["text"] == "new dragon"


def test_repeating_a_find_walks_through_the_matches():
    app, _backend, posted = _app("first dragon", "second dragon", "third dragon", "tail")
    for _ in range(3):
        app.on_ws_message(protocol.find("dragon"))
    assert [m["text"] for m in _results(posted)] == [
        "third dragon", "second dragon", "first dragon",
    ]


def test_case_sensitive_find_skips_the_wrong_case():
    app, _backend, posted = _app("a dragon roars", "a Dragon sleeps", "tail")
    app.on_ws_message(protocol.find("dragon", case_sensitive=True))
    assert _results(posted)[-1]["text"] == "a dragon roars"


def test_case_insensitive_find_takes_the_nearest_either_way():
    app, _backend, posted = _app("a dragon roars", "a Dragon sleeps", "tail")
    app.on_ws_message(protocol.find("dragon"))
    assert _results(posted)[-1]["text"] == "a Dragon sleeps"


def test_find_on_an_empty_buffer_is_a_miss_not_a_crash():
    app, _backend, posted = _app()
    app.on_ws_message(protocol.find("anything"))
    assert _results(posted) == [{"type": protocol.FIND_RESULT, "text": "", "found": False}]

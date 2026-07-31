"""Session logging: the SessionLogger file primitive + the app log:toggle key."""

from __future__ import annotations

from genericmud.app import EngineApp
from genericmud.config.keymap import load_keymap
from genericmud.protocol.telnet import DataReceived
from genericmud.session.log import SessionLogger
from genericmud.voice.router import VoiceRouter
from tests.helpers import RecordingBackend


def test_session_logger_writes_then_appends(tmp_path):
    path = tmp_path / "logs" / "s.log"  # parent dir created on start
    logger = SessionLogger(path)
    logger.start()
    logger.log("line one")
    logger.log("line two")
    logger.stop()
    assert path.read_text(encoding="utf-8") == "line one\nline two\n"
    assert not logger.active

    reopened = SessionLogger(path)
    reopened.start()
    reopened.log("line three")
    reopened.stop()
    assert path.read_text(encoding="utf-8").splitlines() == ["line one", "line two", "line three"]


def _app(tmp_path):
    backend = RecordingBackend()
    voice = VoiceRouter(backend, clock=lambda: 0.0)
    sent: list[str] = []
    posted: list[dict] = []
    app = EngineApp(
        voice, send=sent.append, post=posted.append,
        keymap=load_keymap("vipmud"), name="gw", log_dir=tmp_path,
    )
    return app, backend, sent, posted


def test_log_toggle_captures_output_and_commands_then_stops(tmp_path):
    app, backend, _sent, _posted = _app(tmp_path)
    app._handle_key("alt+shift+l")  # log:toggle on
    assert app.logger is not None and app.logger.active
    path = app.logger.path
    assert path.name.startswith("gw-")  # named after the session

    app.on_telnet_event(DataReceived(b"You see a dragon\r\n"))
    app.on_ws_message({"type": "input", "text": "kill dragon"})
    app._handle_key("alt+shift+l")  # toggle off
    assert app.logger is None
    assert any("logging" in spoken for spoken in backend.spoken)

    text = path.read_text(encoding="utf-8")
    assert "You see a dragon" in text  # incoming output logged
    assert "> kill dragon" in text  # sent command logged

    app.on_telnet_event(DataReceived(b"after stop\r\n"))
    assert "after stop" not in path.read_text(encoding="utf-8")  # nothing after stop


def test_log_write_failure_stops_logging_without_dropping_the_line(tmp_path):
    # A failed write (disk full, media removed) must not abort _emit_line -- that runs
    # before speak/append, so a raised OSError silenced and dropped every later line.
    app, backend, _sent, posted = _app(tmp_path)
    app._handle_key("alt+shift+l")  # logging on

    class _Boom:
        active = True

        def log(self, _text):
            return False  # simulate a write fault that auto-stopped logging

    app.logger = _Boom()
    app.on_telnet_event(DataReceived(b"A goblin hits you\r\n"))
    # The line still reached speech and the buffer; only logging stopped.
    assert any("goblin" in spoken for spoken in backend.spoken)
    assert app.buffer.lines()[-1].plain_text == "A goblin hits you"
    assert any("logging stopped" in spoken.lower() for spoken in backend.spoken)


def test_session_logger_auto_stops_on_write_error(tmp_path):
    logger = SessionLogger(tmp_path / "s.log")
    logger.start()
    logger._handle.close()  # make the next write raise ValueError/OSError on a closed file
    assert logger.log("x") is False
    assert not logger.active  # auto-stopped

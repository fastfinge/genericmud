"""Tests for the static frontend server (serves the real frontend dir)."""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from genericmud.bridge.static_server import serve_static
from genericmud.resources import resource_root


def _get(base: str, path: str):
    return urllib.request.urlopen(base + path, timeout=5)


def test_serves_index_and_modules_with_correct_mime():
    server = serve_static(str(resource_root() / "frontend"), port=0)
    try:
        _host, port = server.server_address
        base = f"http://127.0.0.1:{port}"

        with _get(base, "/index.html") as response:
            assert response.status == 200
            assert "text/html" in response.headers.get("Content-Type", "")
            assert "genericMud" in response.read().decode("utf-8")

        # ES modules must be served with a JS MIME type or the browser rejects them.
        with _get(base, "/src/app.js") as response:
            assert response.status == 200
            assert "javascript" in response.headers.get("Content-Type", "")
    finally:
        server.shutdown()


def test_missing_file_is_404():
    server = serve_static(str(resource_root() / "frontend"), port=0)
    try:
        _host, port = server.server_address
        try:
            _get(f"http://127.0.0.1:{port}", "/nope.html")
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as error:
            assert error.code == 404
    finally:
        server.shutdown()


def test_serves_sound_from_sound_root(tmp_path):
    sounds = tmp_path / "snd"
    sounds.mkdir()
    (sounds / "hit.ogg").write_bytes(b"OGGDATA")
    server = serve_static(str(resource_root() / "frontend"), port=0, sound_root=str(sounds))
    try:
        _host, port = server.server_address
        with _get(f"http://127.0.0.1:{port}", "/sounds/hit.ogg") as response:
            assert response.status == 200
            assert response.read() == b"OGGDATA"
    finally:
        server.shutdown()


def test_symlink_outside_root_is_not_served(tmp_path):
    sounds = tmp_path / "snd"
    sounds.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"SECRET")
    try:
        (sounds / "escape.ogg").symlink_to(secret)  # a symlink pointing outside the sound root
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not creatable on this platform/privilege level")
    server = serve_static(str(resource_root() / "frontend"), port=0, sound_root=str(sounds))
    try:
        _host, port = server.server_address
        base = f"http://127.0.0.1:{port}"
        try:
            with _get(base, "/sounds/escape.ogg") as response:
                body = response.read()
            assert b"SECRET" not in body  # contained: the symlink target is never followed out
        except urllib.error.HTTPError as error:
            assert error.code in (403, 404)
    finally:
        server.shutdown()


def test_null_byte_in_sounds_url_does_not_crash_the_request(tmp_path):
    # A "%00" used to reach os.path.realpath, which raises ValueError and reset the
    # connection. It must now resolve cleanly (the NUL segment is dropped) with a normal
    # HTTP response, and the server must stay alive for the next request.
    (tmp_path / "ok.wav").write_bytes(b"RIFF")
    server = serve_static(str(resource_root() / "frontend"), port=0, sound_root=str(tmp_path))
    try:
        _host, port = server.server_address
        try:
            with _get(f"http://127.0.0.1:{port}", "/sounds/%00.wav") as response:
                assert response.status == 200  # a clean response, not a reset connection
        except urllib.error.HTTPError as error:
            assert error.code in (403, 404)  # a clean refusal is fine too -- just not a crash
        # The server survived and still serves a real file.
        with _get(f"http://127.0.0.1:{port}", "/sounds/ok.wav") as response:
            assert response.status == 200
    finally:
        server.shutdown()

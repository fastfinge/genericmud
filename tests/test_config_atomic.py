"""Atomic config writes never expose a partial replacement."""

from __future__ import annotations

import pytest

from genericmud.config import atomic


def test_atomic_write_replaces_the_target(tmp_path):
    target = tmp_path / "state.toml"
    target.write_text("old", encoding="utf-8")
    atomic.atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_failed_replace_preserves_the_old_file_and_cleans_up(tmp_path, monkeypatch):
    target = tmp_path / "state.toml"
    target.write_text("old", encoding="utf-8")

    def fail_replace(_source, _target):
        raise OSError("locked")

    monkeypatch.setattr(atomic.os, "replace", fail_replace)
    with pytest.raises(OSError, match="locked"):
        atomic.atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [target]

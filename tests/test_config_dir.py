"""config_dir() is portable (beside the exe) when frozen, ~/.genericmud from source."""

from __future__ import annotations

import sys
from pathlib import Path

from genericmud.config.worlds import config_dir


def test_config_dir_is_beside_the_exe_when_frozen(monkeypatch, tmp_path):
    exe = tmp_path / "app" / "genericMud.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    assert config_dir() == exe.parent / "genericmud-data"


def test_config_dir_uses_application_support_for_a_frozen_mac_app(monkeypatch, tmp_path):
    # A .app bundle is read-only, so config must NOT go beside the executable.
    exe = tmp_path / "genericMud.app" / "Contents" / "MacOS" / "genericMud"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert config_dir() == Path.home() / "Library" / "Application Support" / "genericMud"


def test_config_dir_is_home_from_source(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert config_dir() == Path.home() / ".genericmud"

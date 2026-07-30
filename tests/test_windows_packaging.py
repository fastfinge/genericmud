"""Windows artifacts stay GUI-subsystem builds without a companion terminal."""

from __future__ import annotations

from pathlib import Path


def test_windows_builds_use_the_windowed_subsystem():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "build_windows.bat").read_text(encoding="utf-8").lower()
    workflow = (root / ".github/workflows/build-windows.yml").read_text(encoding="utf-8").lower()

    for source in (build_script, workflow):
        assert "--windowed" in source
        assert "--console" not in source

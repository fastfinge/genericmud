"""Build-blind structural checks for the native wx world flows."""

from __future__ import annotations

import ast
from pathlib import Path


def test_new_world_and_saved_connect_use_distinct_dialogs_and_commands():
    source = (
        Path(__file__).resolve().parents[1] / "genericmud/ui/wx_app.py"
    ).read_text(encoding="utf-8")
    classes = {
        node.name
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef)
    }

    assert {"WorldDialog", "ConnectDialog"} <= classes
    assert '"&New World...\\tCtrl+N"' in source
    assert '"&Connect to Saved World...\\tCtrl+O"' in source


def test_find_shortcuts_remain_scoped_to_the_output_control():
    source = (
        Path(__file__).resolve().parents[1] / "genericmud/ui/wx_app.py"
    ).read_text(encoding="utf-8")
    assert "self.output.Bind(wx.EVT_KEY_DOWN, self._on_output_key)" in source
    assert '"&Find in Output...\\tCtrl+F"' not in source

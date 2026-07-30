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


def test_find_caret_mapping_stays_in_native_units():
    # Insertion-point units and GetValue() offsets disagree on Windows (a line break
    # is two native characters, one in the string), so the caret sync must convert
    # through the control's own line functions, never position by string offset.
    source = (
        Path(__file__).resolve().parents[1] / "genericmud/ui/wx_app.py"
    ).read_text(encoding="utf-8")
    assert "find_offset" not in source
    assert "self.output.PositionToXY(self.output.GetInsertionPoint())" in source
    assert "self.output.XYToPosition(0, line)" in source

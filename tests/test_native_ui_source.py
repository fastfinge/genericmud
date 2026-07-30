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


def test_output_caret_survives_appends_while_find_dialog_is_open():
    # While the modal Find dialog holds focus, arriving output must not yank the
    # underlying insertion point: _keep_caret_on_focus promises the search runs from
    # the reader's position, so the flush has to anchor whenever that flag is set,
    # not only while the output itself has focus.
    source = (
        Path(__file__).resolve().parents[1] / "genericmud/ui/wx_app.py"
    ).read_text(encoding="utf-8")
    assert "preserve = self.output.HasFocus() or self._keep_caret_on_focus" in source


def test_history_recall_parks_and_restores_the_unsent_draft():
    # Up parks the live edit line; Down past the newest entry restores it instead of
    # blanking the field (silent data loss for a blind typist).
    source = (
        Path(__file__).resolve().parents[1] / "genericmud/ui/wx_app.py"
    ).read_text(encoding="utf-8")
    assert "self._history_draft = self.input.GetValue()" in source
    assert "else self._history_draft" in source

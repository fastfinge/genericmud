"""Tests for keeping a review caret in place across output appends and trims."""

from __future__ import annotations

from genericmud.ui.scrollback import anchor_after_append


def test_plain_append_leaves_the_anchor_alone():
    # Nothing trimmed off the front, so the reader's offset still points at the same text.
    assert anchor_after_append(anchor=500, removed=0, last_position=4000) == 500


def test_trim_shifts_the_anchor_down_by_the_removed_count():
    # The oldest 200 characters went; the reader's place moved down with the text.
    assert anchor_after_append(anchor=500, removed=200, last_position=3800) == 300


def test_anchor_inside_the_trimmed_region_lands_at_the_top():
    # The reader was parked in text that has since been dropped: clamp, don't go negative.
    assert anchor_after_append(anchor=50, removed=200, last_position=3800) == 0


def test_anchor_past_the_end_is_clamped_into_the_control():
    assert anchor_after_append(anchor=9000, removed=0, last_position=4000) == 4000


def test_everything_trimmed_leaves_the_anchor_at_zero():
    assert anchor_after_append(anchor=500, removed=4000, last_position=0) == 0

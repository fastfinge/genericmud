"""Tests for the output control's reading position: keeping a place, and finding one."""

from __future__ import annotations

from genericmud.ui.scrollback import FindState, anchor_after_append, find_offset


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


# --- find ---

TEXT = "a dragon roars\nthe Dragon sleeps\na dragon waits\n"
FIRST = TEXT.index("dragon")  # 2
MIDDLE = TEXT.index("Dragon")  # the capitalised one
LAST = TEXT.rindex("dragon")


def test_find_forward_starts_past_the_caret():
    assert find_offset(TEXT, "dragon", 0, forward=True, case_sensitive=False) == FIRST


def test_new_find_includes_the_direction_edge():
    assert (
        find_offset(
            TEXT,
            "dragon",
            MIDDLE,
            forward=True,
            case_sensitive=False,
            from_edge=True,
        )
        == FIRST
    )
    assert (
        find_offset(
            TEXT,
            "dragon",
            MIDDLE,
            forward=False,
            case_sensitive=False,
            from_edge=True,
        )
        == LAST
    )


def test_repeating_a_forward_find_walks_to_the_next_match():
    # Sitting on a match and searching again must move on, not sit still.
    second = find_offset(TEXT, "dragon", FIRST, forward=True, case_sensitive=False)
    assert second == MIDDLE
    assert find_offset(TEXT, "dragon", second, forward=True, case_sensitive=False) == LAST


def test_find_backward_starts_before_the_caret():
    assert find_offset(TEXT, "dragon", LAST, forward=False, case_sensitive=False) == MIDDLE


def test_case_sensitive_find_skips_the_wrong_case():
    # "Dragon" is between them, and must be passed over when case matters.
    assert find_offset(TEXT, "dragon", FIRST, forward=True, case_sensitive=True) == LAST


def test_case_sensitive_find_matches_the_exact_case():
    assert find_offset(TEXT, "Dragon", 0, forward=True, case_sensitive=True) == MIDDLE


def test_no_match_returns_none_rather_than_wrapping():
    assert find_offset(TEXT, "dragon", LAST, forward=True, case_sensitive=False) is None
    assert find_offset(TEXT, "griffin", 0, forward=True, case_sensitive=False) is None


def test_empty_needle_never_matches():
    assert find_offset(TEXT, "", 0, forward=True, case_sensitive=False) is None


def test_negative_caret_is_treated_as_the_start():
    assert find_offset(TEXT, "dragon", -50, forward=True, case_sensitive=False) == FIRST


def test_find_state_defaults_to_a_backwards_case_insensitive_search():
    state = FindState()
    assert state.term == ""
    assert state.forward is False
    assert state.case_sensitive is False

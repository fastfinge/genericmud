"""Keeping a reader's place in the output control while new MUD text arrives.

The output control is append-only and trimmed from the top, and both operations move
text out from under someone who has tabbed in and is arrowing back through it: wx's
``AppendText`` drags the caret to the end, and dropping the oldest lines shifts every
surviving offset down. This module holds that offset arithmetic, kept free of wx so it
can be tested on a machine that can't run the Windows UI.
"""

from __future__ import annotations


def anchor_after_append(anchor: int, removed: int, last_position: int) -> int:
    """Where a caret parked at ``anchor`` belongs after an append plus a top trim.

    ``removed`` is the character count dropped off the front, which shifts every
    surviving offset down by exactly that much. The result is clamped into the control,
    so a reader whose place was itself trimmed away lands at the top of what's left
    rather than at a stale offset.
    """
    return max(0, min(anchor - removed, last_position))

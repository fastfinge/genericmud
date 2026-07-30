"""Reading position in the output control: keeping a place, and finding a new one.

Two jobs, both pure so they can be tested on a machine that can't run the Windows UI.

The output control is append-only and trimmed from the top, and both operations move
text out from under someone who has tabbed in and is arrowing back through it: wx's
``AppendText`` drags the caret to the end, and dropping the oldest lines shifts every
surviving offset down. :func:`anchor_after_append` is that offset arithmetic.

:func:`find_line` backs the Find keys, locating the engine's matched line among the
control's lines so the caret can follow the scrollback search onto the same line.
Everything here works in whole lines, never raw character offsets: on Windows the
native control counts a line break as two characters while ``GetValue()`` renders it
as one, so a string offset walks off the caret's actual position by one character per
preceding line.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


def anchor_after_append(anchor: int, removed: int, last_position: int) -> int:
    """Where a caret parked at ``anchor`` belongs after an append plus a top trim.

    ``removed`` is the character count dropped off the front, which shifts every
    surviving offset down by exactly that much. The result is clamped into the control,
    so a reader whose place was itself trimmed away lands at the top of what's left
    rather than at a stale offset.
    """
    return max(0, min(anchor - removed, last_position))


def find_line(
    lines: Sequence[str],
    needle_line: str,
    current: int,
    *,
    forward: bool,
    from_edge: bool = False,
) -> int | None:
    """Index of the line equal to ``needle_line``, or None if it isn't among ``lines``.

    The engine matched a whole scrollback line, so only a control line equal to it
    counts; a longer line merely containing the text must not capture the caret.
    ``current`` is the caret's line. Repeated searches begin strictly past it so they
    advance. ``from_edge`` is for a newly-submitted dialog search: it takes the first
    (forward) or last (backward) occurrence, matching the engine cursor's reset.
    """
    if not needle_line:
        return None
    if from_edge:
        indices = range(len(lines)) if forward else range(len(lines) - 1, -1, -1)
    elif forward:
        indices = range(max(current + 1, 0), len(lines))
    else:
        indices = range(min(current, len(lines)) - 1, -1, -1)
    for i in indices:
        if lines[i] == needle_line:
            return i
    return None


@dataclass
class FindState:
    """The last search, so the dialog reopens with it and F3 can repeat it.

    Backwards by default: the output is history, and the interesting thing is nearly
    always behind you.
    """

    term: str = ""
    forward: bool = False
    case_sensitive: bool = False

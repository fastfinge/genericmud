"""Reading position in the output control: keeping a place, and finding a new one.

Two jobs, both pure so they can be tested on a machine that can't run the Windows UI.

The output control is append-only and trimmed from the top, and both operations move
text out from under someone who has tabbed in and is arrowing back through it: wx's
``AppendText`` drags the caret to the end, and dropping the oldest lines shifts every
surviving offset down. :func:`anchor_after_append` is that offset arithmetic.

:func:`find_offset` backs the Find keys, locating a match in the control's text so the
caret can follow the engine's scrollback search onto the same line.
"""

from __future__ import annotations

from dataclasses import dataclass


def anchor_after_append(anchor: int, removed: int, last_position: int) -> int:
    """Where a caret parked at ``anchor`` belongs after an append plus a top trim.

    ``removed`` is the character count dropped off the front, which shifts every
    surviving offset down by exactly that much. The result is clamped into the control,
    so a reader whose place was itself trimmed away lands at the top of what's left
    rather than at a stale offset.
    """
    return max(0, min(anchor - removed, last_position))


def find_offset(
    text: str,
    needle: str,
    start: int,
    *,
    forward: bool,
    case_sensitive: bool,
    from_edge: bool = False,
) -> int | None:
    """Offset of the next (or previous) ``needle`` in ``text``, or None for no match.

    ``start`` is the caret. Repeated searches begin strictly past it so they advance.
    ``from_edge`` is for a newly-submitted dialog search: it includes the first or last
    visible line, matching the engine cursor's reset to that edge.
    """
    if not needle:
        return None
    haystack = text if case_sensitive else text.lower()
    target = needle if case_sensitive else needle.lower()
    caret = max(0, start)
    if from_edge:
        found = haystack.find(target) if forward else haystack.rfind(target)
    else:
        found = haystack.find(target, caret + 1) if forward else haystack.rfind(target, 0, caret)
    return None if found < 0 else found


@dataclass
class FindState:
    """The last search, so the dialog reopens with it and F3 can repeat it.

    Backwards by default: the output is history, and the interesting thing is nearly
    always behind you.
    """

    term: str = ""
    forward: bool = False
    case_sensitive: bool = False

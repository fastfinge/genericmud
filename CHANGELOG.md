# Changelog

Each release's section here becomes the body of its GitHub release, which is the
text the in-app update dialog reads out. Write it for someone deciding whether to
update, not for someone reading the diff. Tagging a version with no section here
fails the build on purpose.

Entries start at 0.7.1. Earlier releases were tagged before this file existed.

## 0.7.1 — 2026-07-27

**Soundpack channel triggers work again**

* VIPMud soundpacks write a literal square bracket in a pattern as `[[]`, which is
  how they match a channel line like `[General Communication] Someone transmits,
  "Hello all."`. genericMud read those brackets as ordinary text, so the pattern
  looked for three characters where the line only had one, and never matched.
* In the Star Conquest pack that silenced 23 triggers: every communicator channel,
  every ship jump, launch, landing, docking and navigate announcement, and the
  combat shot-fired and destruction calls. Nothing was broken in the sound path,
  which is why the failure was invisible. The lines simply arrived and matched
  nothing.
* Any VIPMud pack using bracketed patterns gains the same triggers back.

**Find text in the output**

* Ctrl+F searches the output for a phrase, with a direction setting (up towards
  older lines, or down towards newer) and a Match case checkbox. F3 repeats the
  search and Shift+F3 repeats it the other way. Both settings stick, so reopening
  the dialog and pressing Enter runs the same search again.
* Find only works once you have tabbed into the output. It searches the full
  scrollback, which is far deeper than the visible output holds, so a match can be
  spoken even when it is too old to move the cursor to.
* Follow mode has moved from Ctrl+F to Ctrl+Shift+F to make room.

**Reading back through the output stays put**

* Arriving text no longer throws the cursor to the newest line while you are
  reading back through the output. Tabbing into the output from the command box is
  now the only thing that takes you to the bottom.

**Command history no longer says "blank"**

* Pressing Up in the command box spoke the recalled command over the top of the
  screen reader's own reading of the field, and the two collided as a spurious
  "blank" before every recall. The client now leaves that announcement to the
  screen reader.

**Bursts of output are no longer cut short**

* A room description, a who list or a help page arrives as a single burst, and the
  speech governor treated any burst over twenty lines as a flood, replacing the
  rest with "N more lines". It now absorbs a couple of screenfuls at a time and
  only genuinely sustained spam is summarised.

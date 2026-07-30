# Changelog

Each release's section here becomes the body of its GitHub release, which is the
text the in-app update dialog reads out. Write it for someone deciding whether to
update, not for someone reading the diff. Tagging a version with no section here
fails the build on purpose.

Entries start at 0.7.1. Earlier releases were tagged before this file existed.

## 0.7.3 — 2026-07-30

**Find now lands the reading cursor on the line it announces**

* On Windows, a successful Find spoke the matched line but parked the cursor
  above it — one character higher for every line of scrollback — so arrowing
  after a search read an unrelated line. The cursor now lands exactly on the
  announced line, at its start, for new searches and F3/Shift+F3 repeats.
* A search result that had just arrived and was not yet painted into the
  output could fail to move the cursor at all; it resolves now.
* A line that merely contained the matched line inside longer text can no
  longer capture the cursor.

## 0.7.2 — 2026-07-30

**Star Conquest communicator sounds actually play**

* The earlier bracket-pattern fix let the communicator trigger fire, but its
  per-channel selector still used VIPMud's `%ifWord` function, which genericMud
  did not understand. Every selector therefore evaluated false before reaching
  its sound.
* `%ifWord`, parenthesized true/false results, `and`, `or`, and `NOT` conditions
  now work. All 11 built-in Star Conquest communicator branches were checked
  against the current 2.8.1.1 pack and resolve their real sound files; the two
  configurable community-channel sounds work as well.

**New worlds and saved worlds have separate dialogs**

* Ctrl+N now opens a focused New World form. Ctrl+O opens an alphabetical
  saved-world list with connection details, Connect, Edit, and New World
  actions. Creating a world saves it by default.
* Host and port errors stay in the form with a useful message instead of
  silently connecting to port 4000. Invalid saved or imported ports are rejected,
  and a damaged worlds file no longer prevents startup.

**Find now finds the first result**

* A new search includes the newest line when searching backward and the oldest
  line when searching forward. This fixes searches in one-line output and terms
  that only occur at a scrollback boundary.
* Reopening Find restarts from the chosen edge. F3 and Shift+F3 remain exclusive
  repeats, so they advance to another match. Find remains scoped to the output:
  Ctrl+F in the command box keeps its normal editing behavior.

**The Windows build opens only the GUI**

* The packaged app now uses the Windows GUI subsystem, so launching
  `genericMud.exe` no longer opens a terminal beside it. The local build script
  now produces the same one-folder, audio-enabled layout as the release build.
* Windowed startup and voice fallback paths no longer assume stdout or stderr
  exists. The alternate web UI chooses free local ports, reports boot failures,
  and closes its engine, socket, and HTTP server cleanly.

**Typing and completion are more reliable**

* Ctrl+Shift+Space can begin completion in reverse in both interfaces. The web
  interface now also learns completion words from output.
* Escape and modified Enter reach the engine in the web interface, while
  copy/paste, browser Find, macOS Command shortcuts, and AltGraph typing remain
  local. Commands entered while its socket is opening are queued after
  authentication instead of disappearing.

**Settings and soundpack updates survive interrupted writes**

* Worlds, preferences, credentials, soundpack indexes, user rules, pack state,
  and updater state now use atomic replacement. Corrupt or malformed rows fall
  back safely instead of crashing startup or turning strings into enabled
  settings.
* Replacing a soundpack is staged and rolls back if copying or index persistence
  fails. The no-code rules editor validates changes before replacing its working
  rules.
* Closing an older tab no longer unregisters a newer tab that happens to use the
  same world name.

**Update prompts carry useful release notes**

* The updater dialog now receives this version's actual changelog section from
  the GitHub release instead of generic installation boilerplate.

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

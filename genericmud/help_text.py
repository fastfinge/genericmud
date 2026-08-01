"""In-app help shown from the Help menu.

Plain text, embedded in code rather than read from README.md: the frozen
Windows build doesn't bundle the markdown files, and the Help menu must never
come up empty. One line per fact, no markdown markup — these strings are read
line by line in a text box by screen-reader users. Keep KEYBOARD_SHORTCUTS in
step with config/keymaps/vipmud.toml, the wx menu accelerators, and README.md.
"""

from __future__ import annotations

GETTING_STARTED = """\
Welcome to genericMud.

Connecting:
Press Ctrl+N, type a name, host, and port, and press Enter. "Save this world"
is checked by default; next time press Ctrl+O and choose it from the saved
world list. A good first MUD is Aardwolf: host aardmud.org, port 4000.

Playing:
Type commands in the command box and press Enter. Try: look, north (or just
n), say hello, and help. Up and Down arrows step through what you've typed.
Tab moves between the output box and the command box; typing while in the
output box drops you back into the command box.

More than one MUD:
Ctrl+N opens another new world and Ctrl+O opens another saved world, each in
its own tab. Ctrl+Tab switches tabs. Only the tab you're on speaks — the
others keep playing quietly, triggers and all.

Making it talk your way:
Ctrl+Shift+F is follow mode: when you move rooms, speech skips straight to the
new room. Ctrl+I makes every line interrupt (fast fights). View menu,
Background silence keeps genericMud quiet while you're in another window.
Esc silences the voice; Shift+F11 stops every sound.

Walking:
The numpad is a compass: 8 north, 2 south, 4 west, 6 east, corners are the
diagonals, 5 or 0 look, period scans, minus up, plus down (turn this off in
the View menu if NVDA needs your numpad). Type .3n2e to speedwalk. Alt+B
drops a breadcrumb and Alt+R walks you back to it.

Triggers and sounds:
Ctrl+B opens the soundpack builder. Ctrl+Shift+B browses soundpacks online.
A trigger watches for text and can play
a sound, speak, send a command, hide the line, or interrupt speech — the
simple match is "the line contains this text", no scripting needed. Soundpacks
menu, Browse soundpacks online fetches ready-made packs.

Sharing:
File menu, Export This World saves your whole setup — connection, triggers,
sounds — as one zip. A friend imports it with File menu, Import a World.

The full shortcut list is under Help, Keyboard Shortcuts.
"""

KEYBOARD_SHORTCUTS = """\
Menus:
Alt+F File.  Alt+R Rules.  Alt+V View.  Alt+H Help.

Connection:
Ctrl+N            Create and connect to a new world
Ctrl+O            Connect to a saved world
Ctrl+D            Disconnect this tab
Ctrl+W            Close this tab
Ctrl+Tab          Next session
Ctrl+Shift+Tab    Previous session
Ctrl+Q            Exit

Typing:
Enter             Send the command line
Up / Down         Command history
Ctrl+Enter        Toggle autoretype (empty Enter resends the last command)
Ctrl+Space        Complete the current word from recent output
Ctrl+Shift+Space  Complete, cycling backwards
Numpad            Compass walking: 8 2 4 6 and corners, 5 or 0 look,
                  period scan, minus up, plus down (View menu toggle)

Speech:
Ctrl+M            Self-voice on or off
Ctrl+Shift+F      Follow mode: speech interrupts when you change rooms
Ctrl+I            Interrupt mode: every line barges in
Esc or F11        Stop speech now
Shift+F11         Stop all sounds (panic)

Reviewing output:
Ctrl+1 to 9       Recall the last nine lines, newest first
Alt+Up / Down     Review line by line
Alt+Left / Right  Review word by word
Alt+Shift+Left / Right   Review character by character
Alt+Home / End    Oldest / newest line
Alt+Shift+Enter   Spell the current line character by character
Alt+T             Repeat the last tell
Alt+C             Repeat the last chat line

Finding text (Tab to the output first; these do nothing in the command box):
Ctrl+F            Find in the output: what to look for, up or down, match case
F3                Find the next match, same settings
Shift+F3          Find the previous match

Chat channels:
Ctrl+Alt+Left / Right    Previous / next channel
Ctrl+Alt+Up / Down       Scroll within the current channel
Ctrl+Alt+Shift+Left / Right   Word by word in the channel line
Ctrl+Alt+1 to 9          Recent messages on the current channel

Walking:
.3n2e             Speedwalk (3 north, 2 east)
..3n2e            Walk it one room at a time, stopping if blocked
Alt+B             Drop a breadcrumb
Alt+R             Retrace back to the breadcrumb
Alt+W             Where am I (GMCP MUDs)
Alt+S             Stop walking

Tools:
Ctrl+P            Manage soundpacks
Ctrl+B            Soundpack builder
Ctrl+Shift+B      Browse soundpacks online
Alt+Shift+L       Log this session to a file
Alt+Shift+D       Speak the diagnostic log location and summary
"""

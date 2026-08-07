# genericMud

An accessible MUD client that talks. It speaks the game through the screen
reader you already run (NVDA, JAWS, VoiceOver — with a system-voice fallback),
plays soundpacks, and gives you keyboard tools for everything: reviewing
output, recalling chat, walking, and building triggers — no scripting needed.
It's free, and it loads many existing VIPMud `.set` and MUSHclient soundpacks
as-is, so a pack you already use very likely just works.

The [genericMud manual](docs/README.md) links to the longer guides, including a
plain-language [automation and Lua scripting guide](docs/scripting.md).

## Getting it running

Download the build for your platform from the
[Releases page](https://github.com/matalvernaz/genericmud/releases). It reads
your screen reader on every platform, and self-voices live output through the
platform's own speech.

**Windows:** unzip `genericMud-windows.zip` anywhere and run `genericMud.exe`.
Everything it saves (worlds, soundpacks, logs) stays in a `genericmud-data`
folder next to the exe, so it's self-contained and portable. Self-voice reads
through NVDA or JAWS if one is running, or the Windows voice otherwise. The app
checks for new releases itself and offers to update in place.

**Mac:** unzip `genericMud-macos.zip` and drag `genericMud.app` to Applications.
Self-voice uses the built-in macOS speech; VoiceOver reads the window as usual.
Worlds and soundpacks live in `~/Library/Application Support/genericMud`.

**Linux:** untar `genericMud-linux.tar.gz` and run `genericMud` from the folder.
Self-voice needs `speech-dispatcher` installed (the same speech engine Orca
uses — `sudo apt install speech-dispatcher`), and Orca reads the window.

**From source** (any platform): `pip install -e '.[gui,voice,audio]'` then run
`genericmud`, or see the "For developers" section below.

## Connecting to a MUD

1. Press **Ctrl+N** (or Alt+F, then New World).
2. Type a name, host, and port — for example Aardwolf: host `aardmud.org`,
   port `4000`. "Save this world" is checked by default.
3. Press Enter.

Next time, press **Ctrl+O** to choose the world from the saved-world list.

Type commands in the command box and press Enter to send them. `look`,
`north` (or just `n`), `say hello`, and `help` are good first commands on
almost any MUD. **Up/Down** step through what you've typed before.

The output box above holds everything the MUD said. **Tab** moves between the
output and command boxes; if you start typing while in the output box you
land back in the command box automatically.

## More than one MUD at once

**Ctrl+N** opens another new world and **Ctrl+O** opens another saved world,
each in its own tab. **Ctrl+Tab** and **Ctrl+Shift+Tab** switch between them.
Only the tab you're on speaks; the others stay quiet but keep playing —
triggers still fire and sounds still play, so you miss nothing.

## Making it talk the way you want

- **Ctrl+Shift+F — follow mode.** When you move to a new room, speech cuts straight
  to the new room instead of finishing the old one. Chat and combat still
  queue up. This is the one to try first if the voice always feels behind.
- **Ctrl+I — interrupt mode.** Every new line barges in. For fast fights.
- **View menu → Background silence.** genericMud stays quiet while you're in
  another window (sounds and triggers keep running), and picks up again when
  you come back.
- **Ctrl+M** turns self-voice off entirely so you can read the output box
  with your screen reader's own commands instead.
- **Esc** or **F11** shuts the voice up right now. **Shift+F11** stops every
  playing sound (the panic button for a stuck looping ambience).

If output floods in faster than speech can keep up, genericMud speaks what it
can and says "12 more lines" instead of falling minutes behind — the full
text is always in the output box.

## Reading back what happened

- **Ctrl+1 through Ctrl+9** speak the last nine lines, newest first.
- **Alt+Up/Down** walk the output line by line; **Alt+Left/Right** by word;
  **Alt+Shift+Left/Right** by character; **Alt+Home/End** jump to the oldest
  or newest line.
- **Alt+Shift+Enter** spells the current line out character by character.
- **Alt+T** repeats the last tell; **Alt+C** the last chat line.

**Chat channels** get their own history. When your triggers route lines to
channels (tells, gossip, auction...), **Ctrl+Alt+Left/Right** cycle between
those channels, **Ctrl+Alt+Up/Down** scroll within the one you're on, and
**Ctrl+Alt+1 through 9** read its recent messages — all without touching the
main output.

## Getting around the game

- The **numpad** is a compass: 8 north, 2 south, 4 west, 6 east, the corner
  keys are the diagonals, 5 or 0 look, `.` scans, `-` goes up, `+` goes down.
  If NVDA's desktop layout needs your numpad, turn this off under View.
- Type `.3n2e` to speed-walk three north and two east. Type `..3n2e` to walk
  it one room at a time, stopping if something blocks the way.
- **Alt+B** drops a breadcrumb. Wander wherever; **Alt+R** walks you straight
  back, skipping any detours you took. **Alt+W** says where you are, on MUDs
  that share your location with the client. **Alt+S** stops a walk in
  progress.
- Typing `sh goblin` when you made an alias `sh *` → `shoot %1`? That's in
  the Automation Manager, next section.

The rest of this section is the detail: how to write a route, how the two kinds
of walk differ, and what the breadcrumb trail can and can't take you back
through. Other clients call some of this fastwalk.

### Writing a route

A route is a run of directions, each with an optional count in front of it.
`3n` is three north; `n` on its own is once. The directions are `n`, `s`, `e`,
`w`, `ne`, `nw`, `se`, `sw`, `u` for up and `d` for down. Case doesn't matter
and there are no spaces or separators, so `.2se4n` is a valid route.

Anything else in the run means it isn't a route at all, and genericMud sends the
line to the MUD as an ordinary command instead. `.3north` and `.n,n,e` go to the
game as text, and so does a zero count like `.3n0e` — a leg you count zero times
is a typo, not one you meant to skip. Routes are capped at 1000 steps, so a
slipped keypress like `.999999999n` is refused rather than flooding the MUD.

A route understands compass directions only. Exits your MUD spells out in words
— `enter portal`, `out`, `climb rope` — aren't part of one. Type those yourself.

### `.` walks it now, `..` walks it carefully

`.3n2e` sends all five moves at once, as fast as the connection carries them.
It's the quick one, and it's the right choice on a route you know is clear.

`..3n2e` sends one move, waits until you've actually arrived, and then sends the
next. On a MUD that tells the client which room you're in (over GMCP or MSDP)
that wait is exact. On a MUD that doesn't, it waits about half a second per step
and carries on, which is slower but still lands you in the right place on a
laggy link.

Either way, if the MUD answers a step with something like "You can't go that
way", "There is no exit" or "The door is closed", the walk gives up there and
says "path blocked, 4 steps abandoned" rather than firing the rest of the route
into a wall. It says "arrived" when it finishes. **Alt+S** stops it early, and
starting another walk cancels one already in progress.

**Alt+S** only has something to stop during a `..` walk. A `.` route and a
retrace are already on their way to the MUD by the time you could press it.

### The breadcrumb trail

genericMud keeps a record of the compass moves you make — pressed on the
numpad, typed short as `n` or `se`, or sent by either kind of walk. That record
is the trail, and **Alt+R** turns it into the way home: the same steps in
reverse, each one flipped to its opposite.

**Alt+B** drops a breadcrumb, which means "start measuring from here". It
forgets the trail so far and begins a new one in your current room, so press it
in the spot you want to be able to come back to.

Retracing leaves your detours out. Go north, then east and straight back west,
and the east and west cancel each other out, so **Alt+R** just sends south.
That folds as deep as it needs to: three rooms up a dead end and back again adds
nothing to the way home.

**Alt+R** sends the whole way back in one burst, the way `.` does, and then
forgets the trail on the assumption you made it. It won't stop partway if a door
has closed behind you, so on a route that might have changed, listen to the
output as it goes and drop a fresh breadcrumb once you're somewhere known.

Two things don't make it into the trail, because genericMud never sees a
direction for them. One is any move that isn't a compass direction: `enter
portal`, a teleport, a mount that carries you off, or an exit your MUD names in
words. The other is a direction typed out in full — `north` sends and works, but
only the short `n` records a step. After either, the way back isn't in the
trail, so drop a new breadcrumb with **Alt+B**.

### Where am I

**Alt+W** speaks the room name, the area, the exits, and how many steps you are
from your breadcrumb. The room details come from the MUD over GMCP or MSDP, so
on a MUD that shares nothing you'll hear "no location info" — the step count
still works, because that's genericMud's own count of your moves.

## Automation: triggers, aliases, hotkeys, channels, and scripts

**Ctrl+B** opens one Automation Manager for the current world. Choose
**Triggers**, **Aliases**, **Hotkeys**, **Channels**, or **Scripts** from the
**Show** box. There is no separate simple or advanced builder.

A trigger reacts to text from the MUD. It can play a sound, speak something
shorter, send commands, hide the matched line, interrupt speech, or route the
line to a chat channel. An alias replaces a shortcut you type: `sh *` can send
`shoot ${1}`. A hotkey runs commands when you press a chosen key. These editors
use ordinary fields; no code is required.

Each trigger, alias, or hotkey can send one command or a sequence. Put one
command on each line. The whole sequence is filled in before its first command
is sent. Command fields understand matched text (`${1}` or the older `%1`), a
value saved by a script (`${script:target}`), and live data sent by the MUD,
such as MSDP `${mud:HEALTH}` or GMCP `${mud:Char.Vitals.hp}`. If a value is not
available, none of that sequence is sent and genericMud speaks the problem once.

Choose **Scripts** in the same manager when the automation needs decisions,
timers, reusable functions, or other Lua code. Scripts are sandboxed, load
alphabetically, and can be saved and reloaded without reconnecting. For example:

```lua
mud.alias("combo *", function(line, captures)
    mud.set_var("target", captures[1])
    mud.command({"stand", "kill ${script:target}", "consider ${1}"})
end)
```

Use **Duplicate** to start from an existing item. **Disable** keeps a trigger,
alias, hotkey, or channel saved without letting it run. Changes work on the
next matching line; scripts have **Reload scripts** and **Open scripts folder**
actions in their category.

Read the [step-by-step automation and scripting guide](docs/scripting.md) for
plain-language instructions, copyable examples, and the full Lua API. The same
shorter guide is available offline under **Automation → Automation help**.

## Soundpacks

Ready-made packs: **Soundpacks → Browse soundpacks online** (or
**Ctrl+Shift+B**) pulls from the
community Soundpack Vault, and **Soundpacks → Set up a soundpack from a folder** installs one
from a folder, a zip, or a download link. VIPMud `.set` packs and MUSHclient
packs load too (MUSHclient ones ask for your trust first, because they
contain code).

## Sharing your setup

**File → Export This World** saves the world you're on — connection details,
all your triggers, aliases, hotkeys, channels, and every sound file
they use, plus its automation scripts — as one zip. Send it to a friend; they
pick **File → Import a World** and the whole thing lands in their Connect
dialog, sounds and scripts included.

## Every keyboard shortcut

Menus: **Alt+F** File, **Alt+P** Soundpacks, **Alt+A** Automation, **Alt+V**
View, **Alt+H** Help.

| Keys | What they do |
| --- | --- |
| Ctrl+N | Create and connect to a new world |
| Ctrl+O | Connect to a saved world |
| Ctrl+D | Disconnect this tab |
| Ctrl+W | Close this tab |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous session |
| Ctrl+Q | Exit |
| Enter | Send the command line |
| Up / Down | Command history |
| Ctrl+Enter | Toggle autoretype (empty Enter resends your last command) |
| Ctrl+Space / Ctrl+Shift+Space | Complete the word you're typing from recent output |
| Numpad | Compass walking (View menu toggle) |
| Ctrl+M | Self-voice on/off |
| Ctrl+Shift+F | Follow mode (speech interrupts on room movement) |
| Ctrl+I | Interrupt mode (every line barges in) |
| Esc / F11 | Stop speech now |
| Shift+F11 | Stop all sounds (panic) |
| Ctrl+1..9 | Recall the last nine lines |
| Alt+Up / Alt+Down | Review line by line |
| Alt+Left / Alt+Right | Review word by word |
| Alt+Shift+Left / Right | Review character by character |
| Alt+Home / Alt+End | Oldest / newest line |
| Alt+Shift+Enter | Spell the current line |
| Alt+T / Alt+C | Last tell / last chat |
| Ctrl+Alt+Left / Right | Previous / next chat channel |
| Ctrl+Alt+Up / Down | Scroll within the current channel |
| Ctrl+Alt+Shift+Left / Right | Word by word in the channel line |
| Ctrl+Alt+1..9 | Recent messages on the current channel |
| Alt+B / Alt+R | Drop a breadcrumb / retrace to it |
| Alt+W / Alt+S | Where am I / stop walking |
| Ctrl+P | Manage soundpacks |
| Ctrl+B | Open the Automation Manager |
| Ctrl+1..5 in Automation Manager | Show triggers / aliases / hotkeys / channels / scripts |
| Ctrl+N in Automation Manager | Create an item in the category being shown |
| Enter / Delete in an automation list | Edit / delete the selected item |
| F2 in the Scripts list | Rename the selected script |
| Ctrl+Shift+B | Browse soundpacks online |
| Alt+Shift+L | Log this session to a file |
| Alt+Shift+D | Speak the diagnostic log location and summary |

## When something goes wrong

- **No speech at all:** genericMud speaks through NVDA or JAWS if one is
  running, and falls back to the Windows voice if not. Check **Ctrl+M**
  wasn't toggled off, and check View → Background silence isn't on while
  you're testing from another window.
- **A soundpack is silent:** press **Alt+Shift+D** — it speaks where the
  diagnostic file is and a one-line summary that usually names the problem
  (pack failed to load, no triggers registered, sound file missing).
- **A looping sound won't stop:** **Shift+F11**.
- **Logs and saved data** live in `genericmud-data` next to the exe (or
  `~/.genericmud` when running from source).
- Found a bug? Open an issue or send your newest `crash-*.log` and
  `diagnostic-*.log` from the logs folder.

## For developers

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
```

Native Python asyncio engine (transport, telnet/MCCP/GMCP/MSDP/MSSP/MSP,
ANSI, triggers/aliases/timers, Lua + VIPMud + MUSHclient dialects, voice
router) with a wxPython native UI, pygame audio, and an alternate web UI
(`--web`) over a localhost WebSocket. The engine is headless-testable; the
whole suite runs without a display, socket, or screen reader. Runtime deps:
`lupa` (Lua) and `regex` (ReDoS-safe matching). Extras: `.[gui]` webview
shell, `.[voice]` native voice backends, `.[audio]` pygame.

The same wxPython UI runs on all three platforms. Self-voice picks a backend
per platform: the screen reader (via accessible_output2) or SAPI on Windows,
`say` on macOS, `speech-dispatcher` on Linux. Build a frozen app for the
current platform with `python tools/build_app.py` — `.exe` onedir on Windows,
`genericMud.app` on macOS, an onedir tarball on Linux. CI builds all three on
tags (`build-windows.yml`, `build-macos.yml`, `build-linux.yml`).

Windows packaging and running from source: `WINDOWS.md`.

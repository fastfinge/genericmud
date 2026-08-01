"""The embedded Help-menu pages stay present and cover the advertised keys."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from genericmud import help_text
from genericmud.scripting import user_scripts

KEYMAP = Path("genericmud/config/keymaps/vipmud.toml")
README = Path("README.md")
SCRIPTING_GUIDE = Path("docs/scripting.md")


def test_pages_are_substantial():
    assert len(help_text.GETTING_STARTED) > 500
    assert len(help_text.KEYBOARD_SHORTCUTS) > 500
    assert len(help_text.SCRIPTING) > 500


def test_shortcuts_page_mentions_every_keymap_namespace_key():
    # Every action family bound in the default keymap has a spoken-name anchor in
    # the shortcuts page, so a rebind/feature landing without help text fails here.
    keys = tomllib.loads(KEYMAP.read_text(encoding="utf-8"))["keys"]
    anchors = {
        "recall:": "Recall the last nine",
        "review:": "Review line by line",
        "chan:": "channel",
        "nav:": "breadcrumb",
        "voice:follow_mode": "Follow mode",
        "voice:interrupt_mode": "Interrupt mode",
        "input:autoretype": "autoretype",
        "log:toggle": "Log this session",
        "diag:where": "diagnostic",
    }
    bound = set(keys.values())
    for prefix, anchor in anchors.items():
        if any(action.startswith(prefix) for action in bound):
            assert anchor in help_text.KEYBOARD_SHORTCUTS, f"help text lost: {anchor}"


def test_menu_access_keys_documented():
    for chunk in ("Alt+F File", "Alt+A Automation", "Alt+H Help"):
        assert chunk in help_text.KEYBOARD_SHORTCUTS


def test_scripting_reference_covers_command_variable_sources():
    for syntax in ("${1}", "${script:attack}", "${mud:HEALTH}", "mud.command"):
        assert syntax in help_text.SCRIPTING


def test_plain_language_scripting_guide_is_linked_and_covers_the_public_surface():
    readme = README.read_text(encoding="utf-8")
    guide = SCRIPTING_GUIDE.read_text(encoding="utf-8")
    assert "docs/scripting.md" in readme
    assert len(guide) > 10_000
    for topic in (
        "## Open the script editor",
        "## Send one command or several commands",
        "## Combine captures, script values, and MUD data",
        "## When a script does not work",
        "## API quick reference",
    ):
        assert topic in guide


def test_every_lua_example_in_the_scripting_guide_is_valid(tmp_path):
    guide = SCRIPTING_GUIDE.read_text(encoding="utf-8")
    examples = re.findall(r"```lua\n(.*?)```", guide, re.DOTALL)
    assert len(examples) >= 20
    for source in examples:
        user_scripts.validate_script(tmp_path, source)


def test_world_commands_and_follow_key_match_the_native_ui():
    for shortcut in ("Ctrl+N", "Ctrl+O", "Ctrl+Shift+F"):
        assert shortcut in help_text.KEYBOARD_SHORTCUTS
    assert "Ctrl+Shift+F is follow mode" in help_text.GETTING_STARTED

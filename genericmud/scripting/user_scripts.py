"""Per-world native Lua scripts: safe storage, validation, and ordered loading."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from genericmud.automation.engine import AutomationEngine
from genericmud.config.atomic import atomic_write_text
from genericmud.scripting.api import ScriptApi
from genericmud.scripting.lua_runtime import LuaPackRuntime

SCRIPTS_DIRNAME = "scripts"
DEFAULT_SCRIPT_NAME = "main.lua"
_SCRIPT_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.lua", re.IGNORECASE)
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

DEFAULT_SCRIPT = """\
-- This world's scripts load alphabetically when the session opens.
--
-- Wildcard capture + multiple commands:
-- mud.alias("combo *", function(line, captures)
--     mud.set_var("target", captures[1])
--     mud.command({"stand", "kill ${target}", "consider ${1}"})
-- end)
--
-- MUD variables come from GMCP, MSDP, or MSSP:
-- mud.trigger("You are hurt", function()
--     mud.command("drink vial at ${mud:HEALTH} health")
-- end)
"""


@dataclass(frozen=True)
class LoadedUserScript:
    name: str
    source: str
    runtime: LuaPackRuntime


def scripts_dir(pack_dir: str | Path) -> Path:
    return Path(pack_dir) / SCRIPTS_DIRNAME


def normalize_script_name(name: str) -> str:
    """Return one portable ``.lua`` filename, or raise for a path/unsafe name."""
    candidate = str(name).strip()
    if not candidate.lower().endswith(".lua"):
        candidate += ".lua"
    if not _SCRIPT_NAME_RE.fullmatch(candidate):
        raise ValueError("script names use only letters, numbers, dot, dash, and underscore")
    if candidate.split(".", 1)[0].casefold() in _WINDOWS_RESERVED:
        raise ValueError(f"{candidate} is a reserved filename")
    return candidate


def script_path(pack_dir: str | Path, name: str) -> Path:
    return scripts_dir(pack_dir) / normalize_script_name(name)


def list_scripts(pack_dir: str | Path) -> list[str]:
    root = scripts_dir(pack_dir)
    try:
        names = []
        for path in root.iterdir():
            if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".lua":
                continue
            try:
                if normalize_script_name(path.name) == path.name:
                    names.append(path.name)
            except ValueError:
                continue
    except OSError:
        return []
    return sorted(names, key=lambda name: (name.casefold(), name))


def read_script(pack_dir: str | Path, name: str) -> str:
    return script_path(pack_dir, name).read_text(encoding="utf-8")


def save_script(pack_dir: str | Path, name: str, source: str) -> Path:
    path = script_path(pack_dir, name)
    atomic_write_text(path, str(source))
    return path


def rename_script(pack_dir: str | Path, old_name: str, new_name: str) -> str:
    old_path = script_path(pack_dir, old_name)
    normalized = normalize_script_name(new_name)
    new_path = script_path(pack_dir, normalized)
    existing = {name.casefold(): name for name in list_scripts(pack_dir)}
    occupied = existing.get(normalized.casefold())
    if occupied is not None and occupied.casefold() != old_path.name.casefold():
        raise ValueError(f"a script named {occupied} already exists")
    if old_path.name == normalized:
        return normalized
    old_path.rename(new_path)
    return normalized


def delete_script(pack_dir: str | Path, name: str) -> None:
    script_path(pack_dir, name).unlink()


def validate_script(pack_dir: str | Path, source: str) -> None:
    """Compile/run one candidate against a sinkless engine before replacing its file."""
    engine = AutomationEngine()
    runtime = LuaPackRuntime(
        ScriptApi(engine, source="user-script-validation", base_dir=str(pack_dir))
    )
    try:
        runtime.run_source(str(source))
    finally:
        engine.cancel_timers()


def load_scripts(
    engine: AutomationEngine, pack_dir: str | Path, *, source_prefix: str
) -> list[LoadedUserScript]:
    """Load every script alphabetically; roll back this source set if any file fails."""
    loaded: list[LoadedUserScript] = []
    attempted_sources: list[str] = []
    try:
        for name in list_scripts(pack_dir):
            source = f"{source_prefix}/{name}"
            attempted_sources.append(source)
            runtime = LuaPackRuntime(
                ScriptApi(engine, source=source, base_dir=str(pack_dir))
            )
            runtime.run_file(str(script_path(pack_dir, name)))
            loaded.append(LoadedUserScript(name, source, runtime))
    except BaseException:
        for source in attempted_sources:
            engine.remove_source(source)
        raise
    return loaded

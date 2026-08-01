"""Pack-scoped require(): a trusted pack loads its own bundled Lua libs, nothing else."""

from __future__ import annotations

import pytest

from genericmud.automation.engine import AutomationEngine
from genericmud.scripting.api import ScriptApi
from genericmud.scripting.lua_runtime import LuaPackRuntime
from tests.helpers import RecordingSink


def _runtime(base_dir):
    sink = RecordingSink()
    engine = AutomationEngine(sink)
    return LuaPackRuntime(ScriptApi(engine, base_dir=str(base_dir))), sink


def test_require_loads_a_bundled_lib(tmp_path):
    (tmp_path / "lua").mkdir()
    (tmp_path / "lua" / "mylib.lua").write_text(
        "local M = {}\nfunction M.greet() return 'hi from lib' end\nreturn M", encoding="utf-8"
    )
    runtime, sink = _runtime(tmp_path)
    runtime.run_source("local m = require('mylib'); mud.echo(m.greet())")
    assert ("hi from lib", "main") in sink.echoed


def test_require_finds_lib_anywhere_under_pack(tmp_path):
    # MUSHclient layout: libs live deep (e.g. MUSHclient/lua/json.lua); found by name.
    deep = tmp_path / "MUSHclient" / "lua"
    deep.mkdir(parents=True)
    (deep / "json.lua").write_text("return {ok = true}", encoding="utf-8")
    runtime, sink = _runtime(tmp_path)
    runtime.run_source("local j = require('json'); mud.echo(tostring(j.ok))")
    assert ("true", "main") in sink.echoed


def test_require_resolves_qualified_module_instead_of_basename_collision(tmp_path):
    wanted = tmp_path / "lua" / "mushz" / "core"
    wanted.mkdir(parents=True)
    (wanted / "config.lua").write_text("return {name = 'mushz'}", encoding="utf-8")
    other = tmp_path / "lua" / "unrelated"
    other.mkdir(parents=True)
    (other / "config.lua").write_text("return {name = 'wrong'}", encoding="utf-8")

    runtime, sink = _runtime(tmp_path)
    runtime.run_source("local m = require('mushz.core.config'); mud.echo(m.name)")

    assert ("mushz", "main") in sink.echoed


def test_require_resolves_explicit_init_module(tmp_path):
    module = tmp_path / "lua" / "app"
    module.mkdir(parents=True)
    (module / "init.lua").write_text("return {name = 'explicit-init'}", encoding="utf-8")

    runtime, sink = _runtime(tmp_path)
    runtime.run_source("local m = require('app.init'); mud.echo(m.name)")

    assert ("explicit-init", "main") in sink.echoed


def test_require_resolves_package_init_module(tmp_path):
    module = tmp_path / "lua" / "app"
    module.mkdir(parents=True)
    (module / "init.lua").write_text("return {name = 'package-init'}", encoding="utf-8")

    runtime, sink = _runtime(tmp_path)
    runtime.run_source("local m = require('app'); mud.echo(m.name)")

    assert ("package-init", "main") in sink.echoed


def test_require_accepts_a_script_shebang(tmp_path):
    (tmp_path / "ini.lua").write_text(
        "#!/usr/bin/lua\nreturn {loaded = true}", encoding="utf-8"
    )
    runtime, sink = _runtime(tmp_path)
    runtime.run_source("local ini = require('ini'); mud.echo(tostring(ini.loaded))")
    assert ("true", "main") in sink.echoed


def test_qualified_no_return_module_exposes_legacy_namespace(tmp_path):
    module = tmp_path / "lua" / "prometheus" / "core"
    module.mkdir(parents=True)
    (module / "bootstrap.lua").write_text("Workspace = 'pack/'", encoding="utf-8")
    runtime, sink = _runtime(tmp_path)
    runtime.run_source(
        "require('prometheus.core.bootstrap'); mud.echo(prometheus.core.bootstrap.Workspace)"
    )
    assert ("pack/", "main") in sink.echoed


def test_require_outside_the_pack_is_blocked(tmp_path):
    runtime, _ = _runtime(tmp_path)
    with pytest.raises(Exception):  # noqa: B017 - lupa surfaces the not-found as a Lua error
        runtime.run_source("require('os')")

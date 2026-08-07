"""The mapper as the app drives it: real GMCP/MSDP wire payloads in, walks out.

test_mapping.py covers the graph itself. These go through on_telnet_event and the
keymap/command surface, because that path — subnegotiation to room report to route — is
where the mapper actually has to work.
"""

from __future__ import annotations

import json

from genericmud.app import EngineApp
from genericmud.config.keymap import load_keymap
from genericmud.protocol.telnet import OPT_GMCP, OPT_MSDP, Subnegotiation
from genericmud.voice.router import VoiceRouter
from tests.helpers import RecordingBackend


def _app(tmp_path=None, name=""):
    backend = RecordingBackend()
    voice = VoiceRouter(backend, clock=lambda: 0.0)
    sent: list[str] = []
    scheduled: list[tuple[float, object]] = []
    app = EngineApp(
        voice,
        send=sent.append,
        post=lambda _message: None,
        schedule=lambda delay, callback: scheduled.append((delay, callback)),
        keymap=load_keymap("vipmud"),
        name=name,
        map_dir=tmp_path,
    )
    return app, backend, sent, scheduled


def _room(app, num, name, exits, zone="midgaard"):
    """Feed one GMCP room.info the way a server sends it."""
    payload = b"room.info " + json.dumps(
        {"num": num, "name": name, "zone": zone, "exits": exits}
    ).encode()
    app.on_telnet_event(Subnegotiation(OPT_GMCP, payload))


def _spoken(backend):
    return " | ".join(backend.spoken)


def test_gmcp_room_reports_build_the_graph():
    app, _backend, _sent, _scheduled = _app()
    _room(app, 3001, "Temple Square", {"n": 3002, "e": 3005})
    _room(app, 3002, "Temple Path", {"s": 3001})
    assert set(app.map.rooms) == {"3001", "3002"}
    assert app.map.here == "3002"
    assert app.map.path_to("3005", start="3001") == ["e"]


def test_msdp_room_reports_build_the_graph_too():
    app, _backend, _sent, _scheduled = _app()
    # MSDP: VAR/VAL pairs, ROOM as a nested table. Bytes per the MSDP spec.
    var, val, table_open, table_close = b"\x01", b"\x02", b"\x03", b"\x04"
    payload = (
        var + b"ROOM" + val + table_open
        + var + b"VNUM" + val + b"7010"
        + var + b"NAME" + val + b"The Dock"
        + var + b"AREA" + val + b"Seaside"
        + var + b"EXITS" + val + table_open
        + var + b"n" + val + b"7011"
        + table_close
        + table_close
    )
    app.on_telnet_event(Subnegotiation(OPT_MSDP, payload))
    assert set(app.map.rooms) == {"7010"}
    room = app.map.rooms["7010"]
    assert (room.name, room.area, room.exits) == ("The Dock", "Seaside", {"n": "7011"})


def test_alt_m_reads_the_room_and_its_exits():
    app, backend, _sent, _scheduled = _app()
    _room(app, 3001, "Temple Square", {"n": 3002, "e": 3005})
    _room(app, 3002, "Temple Path", {"s": 3001})
    _room(app, 3001, "Temple Square", {"n": 3002, "e": 3005})
    app.on_ws_message({"type": "key", "key": "alt+m"})
    spoken = _spoken(backend)
    assert "Temple Square" in spoken
    assert "n to Temple Path" in spoken  # visited, so it's named
    assert "e unexplored" in spoken  # 3005 is only an exit destination so far


def test_goto_walks_the_shortest_route_step_by_step():
    app, backend, sent, scheduled = _app()
    _room(app, 1, "Start", {"n": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 3, "The Bank of Midgaard", {"s": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 1, "Start", {"n": 2})
    sent.clear()
    app.on_ws_message({"type": "input", "text": "/goto bank"})
    assert "walking to The Bank of Midgaard, 2 steps" in _spoken(backend)
    # A safe walk, so only the first step goes out until the room changes.
    assert sent == ["n"]
    assert app._walk is not None and app._walk.active
    assert scheduled  # a per-step timeout is armed for MUDs that don't confirm the move


def test_goto_advances_as_rooms_are_confirmed_and_finishes():
    app, backend, sent, _scheduled = _app()
    _room(app, 1, "Start", {"n": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 3, "Vault", {"s": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 1, "Start", {"n": 2})
    sent.clear()
    app.on_ws_message({"type": "input", "text": "/goto vault"})
    _room(app, 2, "Middle", {"n": 3, "s": 1})  # arrived at the first step
    _room(app, 3, "Vault", {"s": 2})  # arrived at the second
    assert sent == ["n", "n"]
    assert "arrived" in _spoken(backend)
    assert app._walk is not None and not app._walk.active


def test_goto_reports_the_honest_reason_when_it_cannot_walk():
    app, backend, sent, _scheduled = _app()
    app.on_ws_message({"type": "input", "text": "/goto bank"})
    assert "no map yet" in _spoken(backend)

    _room(app, 1, "Start", {"n": 2})
    backend.spoken.clear()
    app.on_ws_message({"type": "input", "text": "/goto nowhere"})
    assert "no mapped room matches nowhere" in _spoken(backend)

    backend.spoken.clear()
    app.on_ws_message({"type": "input", "text": "/goto start"})
    assert "already at Start" in _spoken(backend)

    # A room on the map with no route from here: reachable only the other way round.
    _room(app, 9, "Island", {})
    _room(app, 1, "Start", {"n": 2})
    backend.spoken.clear()
    app.on_ws_message({"type": "input", "text": "/goto island"})
    assert "no known route leads there" in _spoken(backend)
    assert sent == []  # a failed /goto never leaks to the MUD as a command

    backend.spoken.clear()
    app.on_ws_message({"type": "input", "text": "/goto"})
    assert "usage: /goto" in _spoken(backend)


def test_goto_refuses_to_route_from_an_unmappable_room():
    app, backend, _sent, _scheduled = _app()
    _room(app, 1, "Start", {"n": 2})
    _room(app, 2, "Bank", {"s": 1})
    # Aardwolf's off-the-map marker: the player is somewhere the graph can't place.
    _room(app, -1, "Clan Hall", {})
    backend.spoken.clear()
    app.on_ws_message({"type": "input", "text": "/goto bank"})
    assert "this room is not on the map" in _spoken(backend)


def test_label_names_the_room_and_goto_finds_it():
    app, backend, sent, _scheduled = _app()
    _room(app, 1, "A Nondescript Hut", {"n": 2})
    _room(app, 2, "Elsewhere", {"s": 1})
    _room(app, 1, "A Nondescript Hut", {"n": 2})
    app.on_ws_message({"type": "input", "text": "/label home"})
    assert "this room is now home" in _spoken(backend)
    assert app.map.rooms["1"].label == "home"

    _room(app, 2, "Elsewhere", {"s": 1})
    sent.clear()
    backend.spoken.clear()
    app.on_ws_message({"type": "input", "text": "/goto home"})
    assert "walking to home" in _spoken(backend)
    assert sent == ["s"]


def test_map_command_summarizes():
    app, backend, _sent, _scheduled = _app()
    app.on_ws_message({"type": "input", "text": "/map"})
    assert "nothing mapped yet" in _spoken(backend)
    _room(app, 1, "Start", {"n": 2})
    backend.spoken.clear()
    app.on_ws_message({"type": "input", "text": "/map"})
    assert "1 room mapped" in _spoken(backend)


def test_room_wrongdir_halts_a_walk():
    app, backend, sent, _scheduled = _app()
    _room(app, 1, "Start", {"n": 2, "e": 5})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 3, "End", {"s": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 1, "Start", {"n": 2, "e": 5})
    sent.clear()
    app.on_ws_message({"type": "input", "text": "/goto end"})
    assert sent == ["n"]
    # The MUD says that exit isn't there: authoritative, unlike the English line patterns.
    app.on_telnet_event(Subnegotiation(OPT_GMCP, b'room.wrongdir "n"'))
    assert app._walk is not None and not app._walk.active
    assert "no exit n, walk stopped" in _spoken(backend)
    # The exit stays on the map: a closed door and a missing one look the same from here.
    assert app.map.rooms["1"].exits["n"] == "2"


def test_re_reporting_the_same_room_does_not_advance_a_walk():
    app, backend, sent, _scheduled = _app()
    _room(app, 1, "Start", {"n": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 3, "End", {"s": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 1, "Start", {"n": 2})
    sent.clear()
    app.on_ws_message({"type": "input", "text": "/goto end"})
    assert sent == ["n"]
    # The same room reported again with a changed exit list or name is NOT movement.
    # Treating it as movement would send step two before the player had taken step one.
    _room(app, 1, "Start", {"n": 2, "e": 9})
    _room(app, 1, "Start Room", {"n": 2, "e": 9})
    assert sent == ["n"]
    assert app._walk is not None and app._walk.active
    # A genuine move still advances it.
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    assert sent == ["n", "n"]


def test_being_moved_off_a_goto_route_halts_the_walk():
    app, backend, sent, _scheduled = _app()
    _room(app, 1, "Start", {"n": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 3, "End", {"s": 2})
    _room(app, 50, "Far Away Dungeon", {"n": 51})
    _room(app, 1, "Start", {"n": 2})
    sent.clear()
    backend.spoken.clear()
    app.on_ws_message({"type": "input", "text": "/goto end"})
    assert sent == ["n"]
    # A trapdoor, a teleport, being dragged: the player is somewhere the route never ran
    # through, so the remaining directions must not be fired from there.
    _room(app, 50, "Far Away Dungeon", {"n": 51})
    assert sent == ["n"]
    assert app._walk is not None and not app._walk.active
    assert "off the route, 1 steps abandoned" in _spoken(backend)


def test_being_teleported_somewhere_unmappable_also_halts_the_walk():
    app, backend, sent, _scheduled = _app()
    _room(app, 1, "Start", {"n": 2})
    _room(app, 2, "Middle", {"n": 3, "s": 1})
    _room(app, 3, "End", {"s": 2})
    _room(app, 1, "Start", {"n": 2})
    sent.clear()
    app.on_ws_message({"type": "input", "text": "/goto end"})
    _room(app, -1, "Clan Hall", {})  # off the map entirely
    assert sent == ["n"]
    assert app._walk is not None and not app._walk.active
    assert "off the route" in _spoken(backend)


def test_a_plain_speedwalk_still_trusts_any_room_change():
    app, _backend, sent, _scheduled = _app()
    # A typed "..3n" has no route behind it, so there are no waypoints to check against
    # and the old behaviour (advance on any confirmed move) has to be preserved.
    app.on_ws_message({"type": "input", "text": "..2n"})
    assert sent == ["n"]
    _room(app, 77, "Somewhere Unexpected", {"s": 1})
    assert sent == ["n", "n"]


def test_unmapped_muds_stay_silent_and_write_nothing(tmp_path):
    app, backend, _sent, _scheduled = _app(tmp_path, name="godwars")
    app.on_telnet_event(Subnegotiation(OPT_GMCP, b'char.vitals {"hp": 50}'))
    app.on_ws_message({"type": "key", "key": "alt+m"})
    assert "this room is not on the map" in _spoken(backend)
    app.shutdown()
    # No rooms learned means no map file for a MUD that never reports rooms.
    assert list(tmp_path.glob("*.json")) == []


def test_the_map_is_saved_per_world_and_reloaded_on_connect(tmp_path):
    app, _backend, _sent, _scheduled = _app(tmp_path, name="Aardwolf Main")
    _room(app, 3001, "Temple Square", {"n": 3002})
    app.on_ws_message({"type": "input", "text": "/label temple"})
    app.shutdown()

    saved = tmp_path / "Aardwolf_Main.json"
    assert saved.exists()  # world name sanitized into one filename component

    fresh, backend, sent, _scheduled = _app(tmp_path, name="Aardwolf Main")
    fresh.on_connect("Aardwolf Main")
    assert set(fresh.map.rooms) == {"3001"}
    assert fresh.map.rooms["3001"].label == "temple"
    # Position isn't restored, so a route can't be computed from a stale room.
    assert fresh.map.here == ""
    backend.spoken.clear()
    fresh.on_ws_message({"type": "input", "text": "/goto temple"})
    assert "not on the map" in _spoken(backend)
    # One room report places the player again, and the remembered graph is usable.
    _room(fresh, 3002, "Temple Path", {"s": 3001})
    sent.clear()
    backend.spoken.clear()
    fresh.on_ws_message({"type": "input", "text": "/goto temple"})
    assert "walking to temple" in _spoken(backend)
    assert sent == ["s"]


def test_a_long_explore_is_written_before_the_session_ends(tmp_path):
    app, _backend, _sent, _scheduled = _app(tmp_path, name="aardwolf")
    for num in range(1, 27):  # past _MAP_SAVE_INTERVAL
        _room(app, num, f"Room {num}", {"n": num + 1})
    assert (tmp_path / "aardwolf.json").exists()  # not waiting for shutdown


def test_a_session_with_no_name_maps_without_persisting(tmp_path):
    app, _backend, _sent, _scheduled = _app(tmp_path)
    _room(app, 1, "Start", {"n": 2})
    app.shutdown()
    assert app.map.rooms  # mapping still works in the session
    assert list(tmp_path.glob("*.json")) == []

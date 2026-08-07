"""Room identity, edge learning, routing, and persistence for the mapper.

The room payloads here are the ones the GMCP Room specification and the Aardwolf
documentation give verbatim, so the shapes under test are the shapes real servers send.
"""

from __future__ import annotations

from genericmud.mapping import (
    MAX_ROOMS,
    RoomMap,
    load_map,
    normalize_room,
    save_map,
)

# Verbatim from the Aardwolf GMCP documentation.
AARDWOLF_ROOM = {
    "num": 5922,
    "name": "At the entrance of the park",
    "zone": "zoo",
    "terrain": "city",
    "details": "",
    "exits": {"e": 5920, "s": 5916, "w": 12611},
    "coord": {"id": 0, "x": 37, "y": 19, "cont": 0},
}
# Aardwolf's own marker for a room it keeps off the map. Every such room shares num -1.
AARDWOLF_UNMAPPABLE = {
    "num": -1,
    "name": "Emerald Clan Room",
    "zone": "emerald",
    "terrain": "",
    "details": "",
    "exits": {},
    "coord": {"id": -1, "x": -1, "y": -1},
}
# The shape app._msdp_room() builds from MSDP's ROOM table.
MSDP_ROOM = {
    "name": "The Market Square",
    "area": "Midgaard",
    "exits": {"north": "3001", "SOUTH": "3005"},
    "vnum": "3014",
}


def test_normalize_reads_both_protocols():
    gmcp = normalize_room(AARDWOLF_ROOM)
    assert gmcp is not None
    assert (gmcp.id, gmcp.name, gmcp.area) == ("5922", "At the entrance of the park", "zoo")
    assert gmcp.exits == {"e": "5920", "s": "5916", "w": "12611"}

    msdp = normalize_room(MSDP_ROOM)
    assert msdp is not None
    assert (msdp.id, msdp.area) == ("3014", "Midgaard")
    # Long names fold to what the player sends, and direction case doesn't matter.
    assert msdp.exits == {"n": "3001", "s": "3005"}


def test_unmappable_rooms_are_refused():
    # The whole point of the guard: two different clan rooms both report num -1, and
    # accepting them would fuse every unmappable room in the game into one node.
    assert normalize_room(AARDWOLF_UNMAPPABLE) is None
    assert normalize_room({**AARDWOLF_UNMAPPABLE, "name": "Another Clan Room"}) is None
    assert normalize_room({"name": "No id at all", "exits": {}}) is None
    assert normalize_room({"num": 0, "name": "Zero"}) is None
    assert normalize_room({"num": True, "name": "Not room one"}) is None
    assert normalize_room("not a dict") is None
    # A non-numeric identifier is legal per the GMCP Room spec.
    room = normalize_room({"id": "tavern-cellar", "name": "Cellar"})
    assert room is not None and room.id == "tavern-cellar"


def test_maze_exits_keep_the_direction_without_a_destination():
    room = normalize_room({"num": 700, "name": "Maze", "exits": ["n", "e"]})
    assert room is not None
    assert room.exits == {"n": None, "e": None}


def test_entering_an_unmappable_room_leaves_the_player_off_the_map():
    room_map = RoomMap()
    room_map.observe(AARDWOLF_ROOM)
    assert room_map.here == "5922"
    # Walking into a clan room must not leave "here" pointing at the room behind you,
    # or the next route would be computed from a room the player already left.
    assert room_map.observe(AARDWOLF_UNMAPPABLE) is None
    assert room_map.here == ""


def test_observe_merges_and_never_erases_a_learned_destination():
    room_map = RoomMap()
    room_map.observe(AARDWOLF_ROOM)
    # A later report of the same room from inside a maze lists directions with no
    # destinations; that must not throw away the exits already resolved.
    room_map.observe({"num": 5922, "name": "At the entrance of the park", "exits": ["e", "n"]})
    room = room_map.rooms["5922"]
    assert room.exits["e"] == "5920"  # kept
    assert room.exits["n"] is None  # newly seen, still unresolved
    assert room.name == "At the entrance of the park"


def test_routing_takes_the_shortest_known_path():
    room_map = RoomMap()
    # 1 -e-> 2 -e-> 3, and 1 -s-> 4 -e-> 3: both reach 3, the second in the same
    # number of moves, so the answer must be the first found breadth-first.
    room_map.observe({"num": 1, "name": "One", "exits": {"e": 2, "s": 4}})
    room_map.observe({"num": 2, "name": "Two", "exits": {"e": 3, "w": 1}})
    room_map.observe({"num": 4, "name": "Four", "exits": {"e": 3, "n": 1}})
    room_map.observe({"num": 3, "name": "Three", "exits": {"w": 2}})
    assert room_map.path_to("3", start="1") == ["e", "e"]
    assert room_map.path_to("1", start="1") == []
    assert room_map.path_to("999", start="1") is None


def test_routing_reaches_a_room_only_named_by_an_exit_but_not_through_it():
    room_map = RoomMap()
    room_map.observe({"num": 1, "name": "One", "exits": {"n": 2}})
    # Room 2 has never been visited: it exists only as somewhere an exit leads. It's a
    # valid destination, but its own exits are unknown, so nothing routes through it.
    assert room_map.path_to("2", start="1") == ["n"]
    assert "2" not in room_map.rooms
    room_map.observe({"num": 3, "name": "Three", "exits": {}})
    assert room_map.path_to("3", start="1") is None


def test_routing_uses_named_exits_a_compass_cannot_express():
    room_map = RoomMap()
    room_map.observe({"num": 1, "name": "Dock", "exits": {"enter": 2, "out": 3}})
    assert room_map.path_to("2", start="1") == ["enter"]


def test_routing_survives_a_cycle():
    room_map = RoomMap()
    room_map.observe({"num": 1, "name": "One", "exits": {"n": 2}})
    room_map.observe({"num": 2, "name": "Two", "exits": {"s": 1, "n": 3}})
    room_map.observe({"num": 3, "name": "Three", "exits": {"s": 2}})
    assert room_map.path_to("3", start="1") == ["n", "n"]


def test_search_finds_visited_rooms_by_name_or_label():
    room_map = RoomMap()
    room_map.observe({"num": 10, "name": "The Bank of Midgaard", "exits": {"n": 11}})
    room_map.observe({"num": 12, "name": "Bank Street", "exits": {}})
    room_map.set_label("my smithy", "12")
    assert [room.id for room in room_map.search("bank of")] == ["10"]
    # An exact label beats a name substring.
    assert [room.id for room in room_map.search("my smithy")] == ["12"]
    assert [room.id for room in room_map.search("bank")] == ["12", "10"]
    assert room_map.search("nowhere") == []
    assert room_map.search("  ") == []
    # Room 11 is known only as an exit destination, so it has no name to be found by.
    assert room_map.search("11") == []


def test_unexplored_lists_exits_leading_somewhere_unvisited():
    room_map = RoomMap()
    room_map.observe({"num": 1, "name": "One", "exits": {"n": 2, "e": 3, "w": None}})
    room_map.observe({"num": 2, "name": "Two", "exits": {"s": 1}})
    room_map.observe({"num": 1, "name": "One", "exits": {"n": 2, "e": 3}})
    # North leads to a room that has been visited; east and the maze exit west have not.
    assert room_map.unexplored("1") == ["e", "w"]
    assert room_map.unexplored("nosuchroom") == []


def test_describe_speaks_the_room_and_where_the_exits_go():
    room_map = RoomMap()
    room_map.observe({"num": 1, "name": "Temple Square", "zone": "midgaard",
                      "exits": {"d": 2, "n": 3}})
    room_map.observe({"num": 3, "name": "Market Square", "exits": {"s": 1}})
    room_map.observe({"num": 1, "name": "Temple Square", "zone": "midgaard",
                      "exits": {"d": 2, "n": 3}})
    spoken = room_map.describe("1")
    assert spoken == (
        "Temple Square; in midgaard; exits n to Market Square, d unexplored"
    )  # compass order, not alphabetical
    assert room_map.describe("nosuchroom") == "this room is not on the map"
    room_map.observe({"num": 9, "name": "Sealed Vault", "exits": {}})
    assert "no exits listed" in room_map.describe("9")


def test_describe_prefers_the_players_own_label():
    room_map = RoomMap()
    room_map.observe({"num": 1, "name": "A Nondescript Hut", "exits": {}})
    room_map.set_label("home", "1")
    assert room_map.describe("1").startswith("home")
    assert room_map.set_label("nowhere", "404") is False


def test_summary_counts_what_is_mapped():
    room_map = RoomMap()
    assert room_map.summary() == "nothing mapped yet"
    room_map.observe({"num": 1, "name": "One", "zone": "midgaard", "exits": {"n": 2}})
    assert room_map.summary() == "1 room mapped, in 1 area, 1 unexplored exit"
    room_map.observe({"num": 2, "name": "Two", "zone": "aylor", "exits": {"s": 1, "e": 3}})
    # Room 1's north exit is explored now that room 2 is visited; only 2's east is left.
    assert room_map.summary() == "2 rooms mapped, across 2 areas, 1 unexplored exit"


def test_the_graph_stops_growing_at_the_cap(monkeypatch):
    import genericmud.mapping as mapping

    monkeypatch.setattr(mapping, "MAX_ROOMS", 2)
    room_map = RoomMap()
    assert room_map.observe({"num": 1, "name": "One"}) == "1"
    assert room_map.observe({"num": 2, "name": "Two"}) == "2"
    assert room_map.observe({"num": 3, "name": "Three"}) is None
    assert room_map.full is True
    # A room already known still updates once the cap is reached.
    assert room_map.observe({"num": 1, "name": "One", "exits": {"n": 2}}) == "1"
    assert MAX_ROOMS > 2  # the shipped cap is not the test's


def test_map_survives_a_save_and_load(tmp_path):
    room_map = RoomMap()
    room_map.observe(AARDWOLF_ROOM)
    room_map.observe({"num": 5920, "name": "Park Path", "exits": {"w": 5922, "n": None}})
    room_map.set_label("park gate", "5922")
    path = tmp_path / "maps" / "aardwolf.json"
    assert save_map(room_map, path) is True

    restored = load_map(path)
    assert set(restored.rooms) == {"5922", "5920"}
    assert restored.rooms["5922"].label == "park gate"
    assert restored.rooms["5920"].exits == {"w": "5922", "n": None}
    assert restored.rooms["5922"].visited is True
    # Position is deliberately not saved: after a reconnect the player may be anywhere.
    assert restored.here == ""
    assert restored.path_to("5920", start="5922") == ["e"]  # 5922 exits east to 5920


def test_a_corrupt_map_file_costs_the_map_not_the_session(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json at all", encoding="utf-8")
    assert load_map(broken).rooms == {}
    assert load_map(tmp_path / "missing.json").rooms == {}

    wrong_schema = tmp_path / "future.json"
    wrong_schema.write_text('{"version": 99, "rooms": {"1": {}}}', encoding="utf-8")
    assert load_map(wrong_schema).rooms == {}

    junk_rooms = tmp_path / "junk.json"
    junk_rooms.write_text(
        '{"version": 1, "rooms": {"1": {"name": "Fine"}, "-1": {"name": "Bad id"},'
        ' "2": "not a dict"}}',
        encoding="utf-8",
    )
    assert set(load_map(junk_rooms).rooms) == {"1"}

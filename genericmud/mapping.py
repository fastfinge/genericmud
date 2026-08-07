"""Room graph built from the MUD's own room reports — what makes "go to the bank" work.

A MUD that speaks GMCP ``room.info`` or MSDP ``ROOM`` tells the client which room the
player is in *and* where every exit from it leads. So the graph is given, not inferred:
this module never has to guess that the direction just sent is what caused the room just
arrived in, which is the assumption teleports, portals, mounts, following another player
and plain lag all quietly break. That's why mapping is restricted to those MUDs. Identity
is exact, so a wrong edge can't be learned, and a MUD that shares nothing gets no map
rather than a guessed one that walks the player into a wall.

Pure and UI-agnostic: the app feeds room reports in and asks for routes and spoken
summaries. No I/O beyond the explicit load/save helpers.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from genericmud.config.atomic import atomic_write_text

# Long direction names a MUD may use in its exit list, folded to the short form the player
# sends. Anything else — out, enter, portal, a named gate — is kept verbatim: it's still a
# real exit and sending the word walks it, so routes can use exits a compass can't express.
_LONG_DIRECTIONS = {
    "north": "n", "south": "s", "east": "e", "west": "w",
    "northeast": "ne", "northwest": "nw", "southeast": "se", "southwest": "sw",
    "up": "u", "down": "d",
}
# Compass order for spoken exit lists; alphabetical would read "down, east, north".
_SPOKEN_ORDER = ("n", "ne", "e", "se", "s", "sw", "w", "nw", "u", "d")
# Everything the graph holds comes from the server, so every dimension it can grow along
# needs a ceiling — otherwise a broken or hostile MUD can exhaust memory (and the saved
# map, and the work spent describing a room aloud) without ever disconnecting. The limits
# sit far above any real MUD: Aardwolf, the largest commonly mapped, is ~50k rooms, and a
# room with more than a dozen exits is already unusual.
MAX_ROOMS = 100_000
MAX_EXITS_PER_ROOM = 64
_MAX_ID = 64
_MAX_DIRECTION = 32  # "enter portal" is a legitimate exit name; a kilobyte of one is not
_MAX_TEXT = 200  # room and area names, which are only ever spoken or matched against
_SCHEMA_VERSION = 1


def _normalize_direction(name: Any) -> str:
    text = str(name).strip().lower()
    if len(text) > _MAX_DIRECTION:
        return ""  # not a direction anything could sensibly send
    return _LONG_DIRECTIONS.get(text, text)


def spoken_count(number: int, singular: str) -> str:
    """"1 room" / "4 rooms" — spoken counts, so the plural has to agree."""
    return f"{number} {singular}" if number == 1 else f"{number} {singular}s"


def _room_id(value: Any) -> str | None:
    """A room identifier as a string, or None when it isn't a usable one.

    Aardwolf sends ``num: -1`` for rooms it deliberately keeps off the map (clan halls,
    some quest rooms) and every such room shares that id, so treating it as an identity
    would fuse unrelated rooms into one node. Zero and negative ids are refused for the
    same reason. Non-numeric string ids are legitimate — the GMCP Room spec allows them.
    """
    if value is None or isinstance(value, bool):
        return None  # bool is an int subclass, and True is not room 1
    if isinstance(value, (int, float)):
        return str(int(value)) if value > 0 else None
    text = str(value).strip()
    if not text or len(text) > _MAX_ID:
        return None
    if text.lstrip("+-").isdigit():
        return text if int(text) > 0 else None
    return text


def _normalize_exits(value: Any) -> dict[str, str | None]:
    """``{direction: destination-id}``, where None means the MUD didn't name the far end.

    Inside a maze Aardwolf lists the directions without room numbers. The exit is real and
    walkable, just unresolved, and keeping it is what "you haven't been through the west
    exit yet" is built on.
    """
    exits: dict[str, str | None] = {}
    if isinstance(value, dict):
        items: Any = value.items()
    elif isinstance(value, (list, tuple, set)):
        items = ((entry, None) for entry in value)
    else:
        return exits
    for direction, destination in items:
        name = _normalize_direction(direction)
        if not name:
            continue
        if name not in exits and len(exits) >= MAX_EXITS_PER_ROOM:
            continue  # a server inventing exit names can't grow this without limit
        exits[name] = _room_id(destination)
    return exits


@dataclass
class Room:
    """One room in the graph. ``visited`` distinguishes standing in it from hearing of it."""

    id: str
    name: str = ""
    area: str = ""
    exits: dict[str, str | None] = field(default_factory=dict)
    label: str = ""  # the player's own name for this room
    visited: bool = False


def normalize_room(data: dict) -> Room | None:
    """A room report from GMCP or MSDP as a :class:`Room`, or None if it isn't mappable.

    A room needs an id: exits reference rooms by id, so with nothing to attach an edge to
    there is no way to place the room in the graph.
    """
    if not isinstance(data, dict):
        return None
    lowered = {str(key).lower(): value for key, value in data.items()}
    for key in ("num", "vnum", "id", "roomvnum"):
        room_id = _room_id(lowered.get(key))
        if room_id is not None:
            break
    else:
        return None
    return Room(
        id=room_id,
        name=str(lowered.get("name") or "").strip()[:_MAX_TEXT],
        area=str(lowered.get("area") or lowered.get("zone") or "").strip()[:_MAX_TEXT],
        exits=_normalize_exits(lowered.get("exits") or lowered.get("idexits")),
    )


@dataclass
class RoomMap:
    """Rooms keyed by id, plus where the player is standing right now.

    ``here`` is live state, not saved: on reconnect the player may be anywhere, and a
    remembered position would route the first walk from the wrong room.
    """

    rooms: dict[str, Room] = field(default_factory=dict)
    here: str = ""
    full: bool = False  # MAX_ROOMS reached; no longer learning new rooms

    # --- learning ---

    def observe(self, data: dict) -> str | None:
        """Merge one room report and record it as the player's position.

        Returns the room id, or None when the report isn't mappable — in which case the
        player is treated as off the map rather than still in the last known room, so a
        route is never computed from a position they've since left.
        """
        room = normalize_room(data)
        if room is None:
            self.here = ""
            return None
        known = self.rooms.get(room.id)
        if known is None:
            if len(self.rooms) >= MAX_ROOMS:
                # Off the map for the same reason as an unmappable report: the player is
                # somewhere the graph has no node for, so any route from "here" would
                # start from the room they already left.
                self.full = True
                self.here = ""
                return None
            room.visited = True
            self.rooms[room.id] = room
        else:
            known.visited = True
            if room.name:
                known.name = room.name
            if room.area:
                known.area = room.area
            for direction, destination in room.exits.items():
                new_direction = direction not in known.exits
                if new_direction and len(known.exits) >= MAX_EXITS_PER_ROOM:
                    continue  # else successive reports accumulate invented exits forever
                # Merge rather than replace, and never let a later report that omits a
                # destination (a maze listing, a closed door) erase one already learned.
                if destination is not None or new_direction:
                    known.exits[direction] = destination
        self.here = room.id
        return room.id

    def set_label(self, text: str, room_id: str = "") -> bool:
        """Name a room in the player's own words. False if the room isn't on the map."""
        room = self.rooms.get(room_id or self.here)
        if room is None:
            return False
        room.label = text.strip()[:_MAX_TEXT]
        return True

    # --- asking ---

    def route_to(self, goal: str, start: str = "") -> tuple[list[str], list[str]] | None:
        """``(directions, rooms)`` from ``start`` (default: here) to ``goal``, or None.

        ``rooms[i]`` is the room step ``i`` should land in, which is what lets a walk tell
        that it has been moved off its route rather than along it.

        Breadth-first, so the route is the fewest moves the map knows of. A room known
        only as somewhere an exit leads is a valid destination but can't be routed
        *through* — its own exits stay unknown until the player has stood in it.
        """
        start = start or self.here
        if not start or not goal:
            return None
        if start == goal:
            return ([], [])
        queue: deque[tuple[str, list[str], list[str]]] = deque([(start, [], [])])
        seen = {start}
        while queue:
            current, steps, rooms = queue.popleft()
            room = self.rooms.get(current)
            if room is None:
                continue
            for direction, destination in room.exits.items():
                if destination is None or destination in seen:
                    continue
                next_steps, next_rooms = [*steps, direction], [*rooms, destination]
                if destination == goal:
                    return (next_steps, next_rooms)
                seen.add(destination)
                queue.append((destination, next_steps, next_rooms))
        return None

    def path_to(self, goal: str, start: str = "") -> list[str] | None:
        """Only the directions of :meth:`route_to`."""
        route = self.route_to(goal, start)
        return None if route is None else route[0]

    def search(self, query: str) -> list[Room]:
        """Visited rooms whose label or name matches ``query``, closest match first.

        Only visited rooms can match: a room the player has never stood in is in the
        graph as an id an exit points at, with no name to have asked for.
        """
        text = query.strip().lower()
        if not text:
            return []
        ranked: list[tuple[int, str, str, Room]] = []
        for room in self.rooms.values():
            if not room.visited:
                continue
            label, name = room.label.lower(), room.name.lower()
            if text in (label, name):
                rank = 0
            elif label and text in label:
                rank = 1
            elif name and text in name:
                rank = 2
            else:
                continue
            ranked.append((rank, (room.label or room.name).lower(), room.id, room))
        ranked.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
        return [room for *_, room in ranked]

    def unexplored(self, room_id: str = "") -> list[str]:
        """Directions out of a room leading somewhere the player hasn't stood."""
        room = self.rooms.get(room_id or self.here)
        if room is None:
            return []
        return [
            direction
            for direction in self._spoken_directions(room)
            if not self._visited(room.exits[direction])
        ]

    def describe(self, room_id: str = "") -> str:
        """A spoken orientation: this room, and where each exit goes."""
        room = self.rooms.get(room_id or self.here)
        if room is None:
            return "this room is not on the map"
        parts = [room.label or room.name or f"room {room.id}"]
        if room.area:
            parts.append(f"in {room.area}")
        if not room.exits:
            parts.append("no exits listed")
            return "; ".join(parts)
        described = []
        for direction in self._spoken_directions(room):
            destination = room.exits[direction]
            target = self.rooms.get(destination) if destination else None
            if target is not None and target.visited:
                described.append(f"{direction} to {target.label or target.name or 'a room'}")
            else:
                described.append(f"{direction} unexplored")
        parts.append("exits " + ", ".join(described))
        return "; ".join(parts)

    def summary(self) -> str:
        """How much of this world is mapped, for the player to check on."""
        visited = [room for room in self.rooms.values() if room.visited]
        if not visited:
            return "nothing mapped yet"
        openings = sum(len(self.unexplored(room.id)) for room in visited)
        areas = len({room.area for room in visited if room.area})
        parts = [f"{spoken_count(len(visited), 'room')} mapped"]
        if areas:
            parts.append("in 1 area" if areas == 1 else f"across {spoken_count(areas, 'area')}")
        parts.append(spoken_count(openings, "unexplored exit"))
        if self.full:
            parts.append("map is full and no longer growing")
        return ", ".join(parts)

    def _visited(self, room_id: str | None) -> bool:
        if not room_id:
            return False
        room = self.rooms.get(room_id)
        return room is not None and room.visited

    @staticmethod
    def _spoken_directions(room: Room) -> list[str]:
        """This room's exits in compass order, with any named exits after them."""
        compass = [name for name in _SPOKEN_ORDER if name in room.exits]
        named = sorted(name for name in room.exits if name not in _SPOKEN_ORDER)
        return compass + named

    # --- persistence ---

    def to_dict(self) -> dict:
        return {
            "version": _SCHEMA_VERSION,
            "rooms": {
                room.id: {
                    "name": room.name,
                    "area": room.area,
                    "exits": room.exits,
                    "label": room.label,
                    "visited": room.visited,
                }
                for room in self.rooms.values()
            },
        }


def from_dict(data: Any) -> RoomMap:
    """Rebuild a map from :meth:`RoomMap.to_dict`, skipping anything malformed.

    Tolerant by design: a corrupt or hand-edited map file must cost the player their map,
    not their ability to connect.
    """
    room_map = RoomMap()
    if not isinstance(data, dict) or data.get("version") != _SCHEMA_VERSION:
        return room_map
    rooms = data.get("rooms")
    if not isinstance(rooms, dict):
        return room_map
    for room_id, entry in rooms.items():
        if not isinstance(room_id, str) or not isinstance(entry, dict):
            continue
        identity = _room_id(room_id)
        if identity is None:
            continue
        room_map.rooms[identity] = Room(
            id=identity,
            name=str(entry.get("name") or ""),
            area=str(entry.get("area") or ""),
            exits=_normalize_exits(entry.get("exits")),
            label=str(entry.get("label") or ""),
            visited=bool(entry.get("visited")),
        )
    return room_map


def load_map(path: str | Path) -> RoomMap:
    """The saved map at ``path``, or an empty one if it's missing or unreadable."""
    try:
        return from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return RoomMap()


def save_map(room_map: RoomMap, path: str | Path) -> bool:
    """Write the map atomically. False if it couldn't be written."""
    try:
        atomic_write_text(path, json.dumps(room_map.to_dict(), indent=1, sort_keys=True))
    except (OSError, ValueError):
        return False
    return True

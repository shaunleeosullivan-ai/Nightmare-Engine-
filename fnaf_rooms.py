"""
NIGHTMARE ENGINE — FNAF Room Graph
Defines the physical layout of the building: rooms, adjacency, and camera IDs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque


@dataclass
class Room:
    id: str
    display_name: str
    camera_id: str | None       # None = no camera (e.g. Kitchen, Office)
    adjacent: list[str]         # room IDs reachable in one animatronic move
    is_office: bool = False
    is_blind_spot: bool = False # Kitchen — exists but cannot be watched


# ── Room definitions ───────────────────────────────────────────────────────────
# Faithful to FNAF1 layout.  Adjacency is from the animatronic's perspective
# (they always move toward the office).

ROOMS: dict[str, Room] = {
    "show_stage": Room(
        id="show_stage",
        display_name="Show Stage",
        camera_id="cam1A",
        adjacent=["dining_area"],
    ),
    "dining_area": Room(
        id="dining_area",
        display_name="Dining Area",
        camera_id="cam1B",
        adjacent=["backstage", "restrooms", "kitchen"],
    ),
    "backstage": Room(
        id="backstage",
        display_name="Backstage",
        camera_id="cam5",
        adjacent=["supply_closet"],
    ),
    "supply_closet": Room(
        id="supply_closet",
        display_name="Supply Closet",
        camera_id="cam1C",
        adjacent=["west_hall"],
    ),
    "west_hall": Room(
        id="west_hall",
        display_name="West Hall",
        camera_id="cam2A",
        adjacent=["west_hall_corner"],
    ),
    "west_hall_corner": Room(
        id="west_hall_corner",
        display_name="West Hall Corner",
        camera_id="cam2B",
        adjacent=["office"],
    ),
    "pirate_cove": Room(
        id="pirate_cove",
        display_name="Pirate Cove",
        camera_id="cam1C",
        adjacent=["west_hall"],
    ),
    "restrooms": Room(
        id="restrooms",
        display_name="Restrooms",
        camera_id="cam4B",
        adjacent=["kitchen"],
    ),
    "kitchen": Room(
        id="kitchen",
        display_name="Kitchen",
        camera_id=None,           # blind spot — audio only
        is_blind_spot=True,
        adjacent=["east_hall"],
    ),
    "east_hall": Room(
        id="east_hall",
        display_name="East Hall",
        camera_id="cam3",
        adjacent=["east_hall_corner"],
    ),
    "east_hall_corner": Room(
        id="east_hall_corner",
        display_name="East Hall Corner",
        camera_id="cam4A",
        adjacent=["office"],
    ),
    "office": Room(
        id="office",
        display_name="The Office",
        camera_id=None,
        is_office=True,
        adjacent=[],
    ),
}

# Which door blocks which approach room
DOOR_BLOCKS: dict[str, str] = {
    "left":  "west_hall_corner",
    "right": "east_hall_corner",
}

# Reverse: approach room → door side
APPROACH_DOOR: dict[str, str] = {v: k for k, v in DOOR_BLOCKS.items()}

# Camera-id → room (for quick lookup when player switches cams)
CAMERA_TO_ROOM: dict[str, str] = {
    r.camera_id: r.id
    for r in ROOMS.values()
    if r.camera_id is not None
}


def get_path(from_id: str, to_id: str) -> list[str]:
    """BFS shortest path between two rooms. Returns [] if unreachable."""
    if from_id == to_id:
        return [from_id]
    visited: set[str] = {from_id}
    queue: deque[list[str]] = deque([[from_id]])
    while queue:
        path = queue.popleft()
        for neighbour in ROOMS[path[-1]].adjacent:
            if neighbour == to_id:
                return path + [neighbour]
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(path + [neighbour])
    return []


def is_left_approach(room_id: str) -> bool:
    return room_id == "west_hall_corner"


def is_right_approach(room_id: str) -> bool:
    return room_id == "east_hall_corner"


def camera_viewable(room_id: str) -> bool:
    return (
        room_id in ROOMS
        and ROOMS[room_id].camera_id is not None
        and not ROOMS[room_id].is_blind_spot
    )

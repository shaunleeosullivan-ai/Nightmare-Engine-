"""
NIGHTMARE ENGINE — FNAF Game State
Mutable state for a single FNAF night session.
All game logic reads/writes through these dataclasses.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional


# ── Night configuration ────────────────────────────────────────────────────────

NIGHT_DURATION_SECONDS = 540.0   # 9 real minutes = 12 AM → 6 AM

# Base power drain per second at Night N (from documented FNAF1 values)
NIGHT_BASE_DRAIN: dict[int, float] = {
    1: 0.011,
    2: 0.012,
    3: 0.013,
    4: 0.014,
    5: 0.015,
    6: 0.016,
    7: 0.020,   # "20/20/20/20" night
}

# Official FNAF1 AI levels per night [freddy, bonnie, chica, foxy]
NIGHT_AI_LEVELS: dict[int, dict[str, int]] = {
    1: {"freddy": 0, "bonnie": 0, "chica": 0, "foxy": 0},
    2: {"freddy": 0, "bonnie": 3, "chica": 1, "foxy": 2},
    3: {"freddy": 1, "bonnie": 1, "chica": 2, "foxy": 6},
    4: {"freddy": 1, "bonnie": 2, "chica": 4, "foxy": 10},
    5: {"freddy": 3, "bonnie": 5, "chica": 7, "foxy": 16},
    6: {"freddy": 4, "bonnie": 10, "chica": 12, "foxy": 16},
    7: {"freddy": 20, "bonnie": 20, "chica": 20, "foxy": 20},
}


# ── Animatronic state ──────────────────────────────────────────────────────────

@dataclass
class AnimatronicState:
    name: str
    current_room: str
    ai_level: int                  # 0-20
    move_interval: float           # seconds between move attempts
    last_move_attempt: float = field(default_factory=time.time)
    is_at_door: bool = False       # True when in approach room (hallway corner)
    blocked_until: float = 0.0    # time.time() until which they can't move (door blocked)

    # Foxy-specific
    foxy_stage: int = 0            # 0=curtains closed, 1=peeking, 2=out, 3=charging
    cove_peek_count: int = 0       # how many times player checked cam1C this minute
    last_peek_window: float = field(default_factory=time.time)
    is_charging: bool = False      # True when Foxy is sprinting to office


@dataclass
class FnafNightSession:
    exp_id: str
    night_number: int
    start_time: float

    # Phase: "waiting" → "running" → "game_over" | "survived"
    phase: str = "waiting"

    # Power
    power: float = 100.0
    power_drain_base: float = 0.011

    # Player-controlled systems (True = active/closed)
    door_left: bool = False
    door_right: bool = False
    light_left: bool = False
    light_right: bool = False
    camera_monitor_open: bool = False
    active_camera: Optional[str] = None    # camera_id currently viewed

    # Animatronics
    animatronics: dict[str, AnimatronicState] = field(default_factory=dict)

    # Jumpscare info (set on game over)
    jumpscare_animatronic: Optional[str] = None
    jumpscare_cause: Optional[str] = None   # "door_open" | "power_out" | "foxy_charge"


# ── Session store ──────────────────────────────────────────────────────────────

fnaf_sessions: dict[str, FnafNightSession] = {}


# ── Factory ───────────────────────────────────────────────────────────────────

def create_fnaf_session(exp_id: str, night_number: int) -> FnafNightSession:
    """Build a FnafNightSession with correct starting positions and AI levels."""
    night = max(1, min(7, night_number))
    ai = NIGHT_AI_LEVELS[night]

    animatronics = {
        "freddy": AnimatronicState(
            name="freddy",
            current_room="show_stage",
            ai_level=ai["freddy"],
            move_interval=5.0,
        ),
        "bonnie": AnimatronicState(
            name="bonnie",
            current_room="show_stage",
            ai_level=ai["bonnie"],
            move_interval=4.97,
        ),
        "chica": AnimatronicState(
            name="chica",
            current_room="show_stage",
            ai_level=ai["chica"],
            move_interval=4.97,
        ),
        "foxy": AnimatronicState(
            name="foxy",
            current_room="pirate_cove",
            ai_level=ai["foxy"],
            move_interval=5.0,
        ),
    }

    session = FnafNightSession(
        exp_id=exp_id,
        night_number=night,
        start_time=time.time(),
        power_drain_base=NIGHT_BASE_DRAIN.get(night, 0.011),
        animatronics=animatronics,
    )

    fnaf_sessions[exp_id] = session
    return session


def calculate_power_drain(session: FnafNightSession) -> float:
    """
    Power drain per second.
    Faithful to FNAF1 documented values:
      - Base drain varies by night
      - Each closed door: +0.5x base
      - Each active light: +0.25x base
      - Camera monitor open: +0.25x base
    """
    multiplier = 1.0
    if session.door_left:
        multiplier += 0.5
    if session.door_right:
        multiplier += 0.5
    if session.light_left:
        multiplier += 0.25
    if session.light_right:
        multiplier += 0.25
    if session.camera_monitor_open:
        multiplier += 0.25
    return session.power_drain_base * multiplier


def get_hour(session: FnafNightSession) -> int:
    """Return current in-game hour (12, 1, 2, 3, 4, 5, or 6)."""
    elapsed = time.time() - session.start_time
    fraction = min(1.0, elapsed / NIGHT_DURATION_SECONDS)
    # 0% = midnight (12), 100% = 6 AM
    hours_since_midnight = int(fraction * 6)
    hour = (12 + hours_since_midnight) % 12
    return hour if hour != 0 else 12


def build_state_snapshot(session: FnafNightSession) -> dict:
    """Build the full state_tick payload sent to Unity every second."""
    elapsed = time.time() - session.start_time
    return {
        "type": "state_tick",
        "phase": session.phase,
        "power": round(session.power, 2),
        "time_elapsed": round(elapsed, 1),
        "time_remaining": round(max(0.0, NIGHT_DURATION_SECONDS - elapsed), 1),
        "hour": get_hour(session),
        "door_left": session.door_left,
        "door_right": session.door_right,
        "light_left": session.light_left,
        "light_right": session.light_right,
        "camera_monitor_open": session.camera_monitor_open,
        "active_camera": session.active_camera,
        "animatronic_positions": {
            name: a.current_room
            for name, a in session.animatronics.items()
        },
        "at_doors": {
            name: a.is_at_door
            for name, a in session.animatronics.items()
        },
        "foxy_stage": session.animatronics["foxy"].foxy_stage
        if "foxy" in session.animatronics else 0,
    }

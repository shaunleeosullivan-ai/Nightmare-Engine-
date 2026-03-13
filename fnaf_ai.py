"""
NIGHTMARE ENGINE — FNAF Animatronic AI & Game Loop

Implements the per-animatronic movement logic from FNAF1, the master
game loop (power drain, night timer, win/lose conditions), and the
power-out Freddy sequence.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, Awaitable

from fnaf_rooms import (
    ROOMS,
    DOOR_BLOCKS,
    APPROACH_DOOR,
    is_left_approach,
    is_right_approach,
)
from fnaf_state import (
    AnimatronicState,
    FnafNightSession,
    fnaf_sessions,
    calculate_power_drain,
    build_state_snapshot,
    NIGHT_DURATION_SECONDS,
)

BroadcastFn = Callable[[str, dict], Awaitable[None]]


# ── Move probability (core FNAF1 algorithm) ────────────────────────────────────

def _should_move(ai_level: int) -> bool:
    """
    Roll 1d20. Move if roll > (20 - ai_level).
    ai_level=0  → never moves (0/20 chance)
    ai_level=20 → always moves (20/20 chance)
    """
    if ai_level <= 0:
        return False
    if ai_level >= 20:
        return True
    return random.randint(1, 20) > (20 - ai_level)


def _next_room_toward_office(current_room: str, prefer_side: str) -> str | None:
    """
    Pick the best adjacent room moving toward the office.
    prefer_side: "left" (west path) or "right" (east path)
    """
    room = ROOMS.get(current_room)
    if not room or not room.adjacent:
        return None

    office_side_rooms = {
        "left":  {"backstage", "supply_closet", "west_hall", "west_hall_corner"},
        "right": {"restrooms", "kitchen", "east_hall", "east_hall_corner"},
        "any":   {"dining_area"},
    }

    candidates = room.adjacent
    if prefer_side == "left":
        preferred = [r for r in candidates if r in office_side_rooms["left"]]
    else:
        preferred = [r for r in candidates if r in office_side_rooms["right"]]

    if preferred:
        return random.choice(preferred)
    return random.choice(candidates) if candidates else None


# ── Per-animatronic tick functions ─────────────────────────────────────────────

async def _tick_bonnie(
    anim: AnimatronicState,
    session: FnafNightSession,
    broadcast: BroadcastFn,
) -> None:
    """
    Bonnie: left-side path, most aggressive early, probabilistic movement.
    """
    if not _should_move(anim.ai_level):
        return

    old_room = anim.current_room
    if anim.current_room == "west_hall_corner":
        # Bonnie is at the left door
        if not session.door_left:
            # Door open → game over
            await _trigger_jumpscare(session, "bonnie", "door_open", broadcast)
            return
        else:
            # Blocked → retreat
            anim.current_room = "west_hall"
            anim.is_at_door = False
            anim.blocked_until = time.time() + 10.0
    else:
        next_r = _next_room_toward_office(anim.current_room, "left")
        if next_r:
            anim.current_room = next_r
            anim.is_at_door = is_left_approach(next_r)

    if anim.current_room != old_room:
        await broadcast(session.exp_id, {
            "type": "anim_moved",
            "animatronic": "bonnie",
            "from_room": old_room,
            "to_room": anim.current_room,
            "at_door": anim.is_at_door,
        })


async def _tick_chica(
    anim: AnimatronicState,
    session: FnafNightSession,
    broadcast: BroadcastFn,
) -> None:
    """
    Chica: right-side path, slightly less aggressive than Bonnie.
    """
    if not _should_move(anim.ai_level):
        return

    old_room = anim.current_room
    if anim.current_room == "east_hall_corner":
        if not session.door_right:
            await _trigger_jumpscare(session, "chica", "door_open", broadcast)
            return
        else:
            anim.current_room = "east_hall"
            anim.is_at_door = False
            anim.blocked_until = time.time() + 10.0
    else:
        next_r = _next_room_toward_office(anim.current_room, "right")
        if next_r:
            anim.current_room = next_r
            anim.is_at_door = is_right_approach(next_r)

    if anim.current_room != old_room:
        await broadcast(session.exp_id, {
            "type": "anim_moved",
            "animatronic": "chica",
            "from_room": old_room,
            "to_room": anim.current_room,
            "at_door": anim.is_at_door,
        })


async def _tick_freddy(
    anim: AnimatronicState,
    session: FnafNightSession,
    broadcast: BroadcastFn,
) -> None:
    """
    Freddy: follows fixed right-side path, BUT only moves when the camera
    monitor is closed OR when he is in the Kitchen (blind spot, always moves).
    Significantly more dangerous after power out.
    """
    in_blind_spot = ROOMS[anim.current_room].is_blind_spot
    being_watched = (
        session.camera_monitor_open
        and session.active_camera == ROOMS[anim.current_room].camera_id
    )

    # Freddy freezes when watched (unless in blind spot)
    if being_watched and not in_blind_spot:
        return

    if not _should_move(anim.ai_level):
        return

    # Freddy's fixed path
    freddy_path = [
        "show_stage", "dining_area", "restrooms",
        "kitchen", "east_hall", "east_hall_corner", "office"
    ]

    old_room = anim.current_room
    if anim.current_room == "east_hall_corner":
        if not session.door_right:
            await _trigger_jumpscare(session, "freddy", "door_open", broadcast)
            return
        else:
            anim.current_room = "east_hall"
            anim.is_at_door = False
            anim.blocked_until = time.time() + 15.0
    else:
        try:
            idx = freddy_path.index(anim.current_room)
            if idx + 1 < len(freddy_path) - 1:   # don't step into "office" normally
                anim.current_room = freddy_path[idx + 1]
                anim.is_at_door = is_right_approach(anim.current_room)
        except ValueError:
            pass

    if anim.current_room != old_room:
        await broadcast(session.exp_id, {
            "type": "anim_moved",
            "animatronic": "freddy",
            "from_room": old_room,
            "to_room": anim.current_room,
            "at_door": anim.is_at_door,
        })


async def _tick_foxy(
    anim: AnimatronicState,
    session: FnafNightSession,
    broadcast: BroadcastFn,
) -> None:
    """
    Foxy: charges if player neglects Pirate Cove camera.
    Stage progression: 0→1→2→3(charge)
    Watching cam1C resets the stage counter.
    """
    # Advance Foxy's stage based on AI level
    if not _should_move(anim.ai_level):
        return

    if anim.is_charging:
        # Foxy is mid-charge — sprint to office
        old_room = anim.current_room
        if anim.current_room == "pirate_cove":
            anim.current_room = "west_hall"
        elif anim.current_room == "west_hall":
            # Reach the door
            if not session.door_left:
                await _trigger_jumpscare(session, "foxy", "foxy_charge", broadcast)
            else:
                # Blocked — drain power, retreat
                session.power = max(0.0, session.power - 6.0)   # door costs power
                anim.current_room = "pirate_cove"
                anim.foxy_stage = 0
                anim.is_charging = False
                anim.is_at_door = False
                await broadcast(session.exp_id, {
                    "type": "foxy_blocked",
                    "power_remaining": round(session.power, 2),
                })
        if anim.current_room != old_room:
            await broadcast(session.exp_id, {
                "type": "anim_moved",
                "animatronic": "foxy",
                "from_room": old_room,
                "to_room": anim.current_room,
                "at_door": False,
            })
        return

    # Stage advancement
    if anim.foxy_stage < 3:
        anim.foxy_stage += 1
        await broadcast(session.exp_id, {
            "type": "foxy_stage_change",
            "stage": anim.foxy_stage,
        })
        if anim.foxy_stage == 3:
            anim.is_charging = True
            await broadcast(session.exp_id, {"type": "foxy_charging"})


def foxy_camera_check(anim: AnimatronicState) -> None:
    """
    Called when player checks cam1C (Pirate Cove).
    Resets Foxy's stage — watching him keeps him tame.
    """
    now = time.time()
    # Reset peek window every minute
    if now - anim.last_peek_window > 60.0:
        anim.cove_peek_count = 0
        anim.last_peek_window = now

    anim.cove_peek_count += 1

    # Watching resets stage (but each reset gives less benefit at high AI)
    if anim.foxy_stage > 0:
        reset_amount = max(1, 3 - (anim.ai_level // 7))
        anim.foxy_stage = max(0, anim.foxy_stage - reset_amount)
        anim.is_charging = False


# ── Jumpscare ─────────────────────────────────────────────────────────────────

async def _trigger_jumpscare(
    session: FnafNightSession,
    animatronic: str,
    cause: str,
    broadcast: BroadcastFn,
) -> None:
    session.phase = "game_over"
    session.jumpscare_animatronic = animatronic
    session.jumpscare_cause = cause
    await broadcast(session.exp_id, {
        "type": "jumpscare",
        "animatronic": animatronic,
        "cause": cause,
    })


# ── Power-out sequence ────────────────────────────────────────────────────────

async def _power_out_sequence(
    session: FnafNightSession,
    broadcast: BroadcastFn,
) -> None:
    """
    Authentic FNAF1 power-out sequence:
    1. Lights cut
    2. Freddy's music box plays for ~10 seconds
    3. Freddy jumpscares
    """
    session.door_left = False
    session.door_right = False
    await broadcast(session.exp_id, {"type": "power_out"})
    await asyncio.sleep(10.0)   # music box plays
    if session.phase == "running":
        await _trigger_jumpscare(session, "freddy", "power_out", broadcast)


# ── Master game loop ──────────────────────────────────────────────────────────

async def fnaf_game_loop(
    exp_id: str,
    broadcast: BroadcastFn,
    nightmare_sessions: dict,       # reference to main.py's `sessions` dict
) -> None:
    """
    Runs while session.phase == 'running'.
    - Drains power every second
    - Ticks animatronics on their intervals
    - Checks win/lose conditions
    - Broadcasts state snapshot every second
    - Scales AI levels from Nightmare Engine biometric intensity
    """
    if exp_id not in fnaf_sessions:
        return

    session = fnaf_sessions[exp_id]
    session.phase = "running"

    print(f"[FNAF] Night {session.night_number} started for {exp_id}")

    TICK = 1.0  # seconds

    while session.phase == "running":
        now = time.time()
        elapsed = now - session.start_time

        # ── Win condition ──
        if elapsed >= NIGHT_DURATION_SECONDS:
            session.phase = "survived"
            await broadcast(exp_id, {
                "type": "night_complete",
                "night": session.night_number,
                "power_remaining": round(session.power, 2),
            })
            print(f"[FNAF] Night {session.night_number} survived — {exp_id}")
            break

        # ── Power drain ──
        drain = calculate_power_drain(session) * TICK
        session.power = max(0.0, session.power - drain)

        if session.power <= 0.0:
            await _power_out_sequence(session, broadcast)
            break

        # ── Adaptive AI from Nightmare Engine biometrics ──
        nightmare_intensity = nightmare_sessions.get(exp_id, {}).get("current_intensity", 0.3)
        intensity_bonus = int(nightmare_intensity * 4)   # 0-4 extra AI points

        # ── Animatronic ticks ──
        for name, anim in session.animatronics.items():
            if time.time() - anim.last_move_attempt < anim.move_interval:
                continue
            if time.time() < anim.blocked_until:
                continue

            anim.last_move_attempt = time.time()
            # Temporarily boost AI by biometric intensity
            original_ai = anim.ai_level
            anim.ai_level = min(20, anim.ai_level + intensity_bonus)

            if name == "bonnie":
                await _tick_bonnie(anim, session, broadcast)
            elif name == "chica":
                await _tick_chica(anim, session, broadcast)
            elif name == "freddy":
                await _tick_freddy(anim, session, broadcast)
            elif name == "foxy":
                await _tick_foxy(anim, session, broadcast)

            anim.ai_level = original_ai   # restore

            if session.phase != "running":
                break   # jumpscare was triggered inside a tick

        if session.phase != "running":
            break

        # ── Broadcast state snapshot ──
        await broadcast(exp_id, build_state_snapshot(session))

        await asyncio.sleep(TICK)

    print(f"[FNAF] Game loop ended — {exp_id} phase={session.phase}")

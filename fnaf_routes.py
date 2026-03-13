"""
NIGHTMARE ENGINE — FNAF HTTP Routes
Mounted at /api/v1/fnaf via app.include_router(fnaf_router) in main.py
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fnaf_state import (
    fnaf_sessions,
    create_fnaf_session,
    build_state_snapshot,
    NIGHT_AI_LEVELS,
)
from fnaf_rooms import ROOMS, CAMERA_TO_ROOM

fnaf_router = APIRouter(prefix="/api/v1/fnaf", tags=["FNAF"])

# Imported lazily to avoid circular import — set by main.py after startup
_broadcast_fn = None
_nightmare_sessions = None


def register_dependencies(broadcast_fn, nightmare_sessions: dict) -> None:
    """Called from main.py to inject the broadcast helper and sessions dict."""
    global _broadcast_fn, _nightmare_sessions
    _broadcast_fn = broadcast_fn
    _nightmare_sessions = nightmare_sessions


# ── Request models ─────────────────────────────────────────────────────────────

class StartNightRequest(BaseModel):
    exp_id: str
    night_number: int = 1


class AiLevelRequest(BaseModel):
    freddy: Optional[int] = None
    bonnie: Optional[int] = None
    chica: Optional[int] = None
    foxy: Optional[int] = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@fnaf_router.post("/start_night")
async def start_night(req: StartNightRequest):
    """
    Create a FNAF night session tied to an existing Nightmare Engine exp_id.
    Kicks off the game loop as a background asyncio task.
    """
    from fnaf_ai import fnaf_game_loop   # lazy import

    session = create_fnaf_session(req.exp_id, req.night_number)

    if _broadcast_fn is None or _nightmare_sessions is None:
        raise HTTPException(500, "FNAF dependencies not registered")

    asyncio.create_task(
        fnaf_game_loop(req.exp_id, _broadcast_fn, _nightmare_sessions)
    )

    return {
        "status": "started",
        "exp_id": req.exp_id,
        "night": req.night_number,
        "duration_seconds": 540,
        "animatronic_positions": {
            name: a.current_room
            for name, a in session.animatronics.items()
        },
        "ai_levels": {
            name: a.ai_level for name, a in session.animatronics.items()
        },
        "cameras": {
            room_id: room.camera_id
            for room_id, room in ROOMS.items()
            if room.camera_id is not None
        },
    }


@fnaf_router.get("/{exp_id}/status")
async def get_night_status(exp_id: str):
    """Snapshot of current night state — useful for reconnects."""
    if exp_id not in fnaf_sessions:
        raise HTTPException(404, "FNAF session not found")
    return build_state_snapshot(fnaf_sessions[exp_id])


@fnaf_router.post("/{exp_id}/ai_levels")
async def set_ai_levels(exp_id: str, req: AiLevelRequest):
    """Override animatronic AI levels at runtime (difficulty tuning)."""
    if exp_id not in fnaf_sessions:
        raise HTTPException(404, "FNAF session not found")

    session = fnaf_sessions[exp_id]
    updates = {}
    for name, level in [
        ("freddy", req.freddy),
        ("bonnie", req.bonnie),
        ("chica", req.chica),
        ("foxy", req.foxy),
    ]:
        if level is not None and name in session.animatronics:
            session.animatronics[name].ai_level = max(0, min(20, level))
            updates[name] = session.animatronics[name].ai_level

    return {"updated": updates}


@fnaf_router.get("/nights")
async def list_nights():
    """Return the official AI level configs for each night."""
    return {
        str(night): levels
        for night, levels in NIGHT_AI_LEVELS.items()
    }


@fnaf_router.get("/rooms")
async def list_rooms():
    """Return the full room graph (useful for Unity scene setup)."""
    return {
        room_id: {
            "display_name": room.display_name,
            "camera_id": room.camera_id,
            "adjacent": room.adjacent,
            "is_office": room.is_office,
            "is_blind_spot": room.is_blind_spot,
        }
        for room_id, room in ROOMS.items()
    }

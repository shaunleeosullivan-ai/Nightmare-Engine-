"""
NIGHTMARE ENGINE — Bio-Adaptive Horror RPG Backend
FastAPI server implementing the Nightmare Engine API spec.

Endpoints:
  POST /api/v1/experience/create              — Create a new horror session
  POST /api/v1/session/{id}/adapt             — Adaptive difficulty update
  POST /api/v1/narrative/generate             — Generate scenario narrative
  POST /api/v1/safety/override                — Emergency safety controls
  POST /api/v1/biometrics/{type}              — Inject biometric data
  GET  /api/v1/session/{id}/analysis          — Post-session analytics
  WS   /ws/session/{id}                       — Real-time session WebSocket
  WS   /ws/analytics/{id}                     — Real-time analytics WebSocket

  ── Cognitive Alignment Framework (A/B = Story) ──
  POST /api/v1/session/{id}/alignment/anchor  — Set the Governor anchor (B)
  GET  /api/v1/session/{id}/alignment/state   — Current alignment state
  GET  /api/v1/session/{id}/alignment/trajectory — Recovery trajectory analytics
  POST /api/v1/alignment/lexicon/test         — Nebraska 2.0 drift test
  GET  /api/v1/alignment/lexicon              — Full Deterministic Lexicon
"""

import asyncio
import random
import threading
import time
import uuid
from collections import Counter
from typing import Any, Optional

import numpy as np

import cognitive_alignment as cal
from cognitive_alignment import (
    AnchorSetRequest,
    GovernorAnchor,
    LexiconTestRequest,
    DETERMINISTIC_LEXICON,
)
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─── Optional imports (graceful fallback if not installed) ───────────────────

try:
    import ollama as ollama_client
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    import cv2
    import mediapipe as mp
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NIGHTMARE ENGINE API",
    description="Bio-adaptive personalized horror experience platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Configuration ────────────────────────────────────────────────────────────

OLLAMA_MODEL = "llama3.1:8b"          # swap to "dolphin3" for uncensored edge
RPPG_ENABLED = True
RPPG_WINDOW_SEC = 30
RPPG_UPDATE_INTERVAL = 8              # seconds between HR estimates
EMOTION_ENABLED = True
EMOTION_UPDATE_INTERVAL = 5           # seconds between emotion detections
EMOTION_HISTORY_LEN = 4              # majority-vote smoothing window
EMOTION_CONF_THRESHOLD = 60.0        # % — ignore weak detections
HIGH_HR_THRESHOLD = 180              # bpm — safety trigger
HR_DANGER_DURATION = 10              # seconds sustained before auto-calm

# ─── In-memory session store ─────────────────────────────────────────────────

sessions: dict[str, dict[str, Any]] = {}

# ─── Pydantic models ──────────────────────────────────────────────────────────

class FearVectorConfig(BaseModel):
    threat_types: list[dict] = []
    sensory_triggers: dict = {}
    cognitive_engagement: dict = {}
    physiological_tuning: dict = {}

class ExperienceCreateRequest(BaseModel):
    user_id: str = "anonymous"
    fear_profile: Optional[FearVectorConfig] = None
    experience_type: str = "solo"
    duration_minutes: int = 60
    intensity_target: float = 0.8
    pedagogical_goals: list[str] = []

class AdaptRequest(BaseModel):
    biometric_data: dict = {}
    behavioral_data: dict = {}

class NarrativeGenerateRequest(BaseModel):
    fear_vectors: list[str] = ["existential"]
    constraints: dict = {}
    story_arc: str = "descent"
    recursion_depth: int = 3

class SafetyOverrideRequest(BaseModel):
    session_id: str
    action: str          # reduce_intensity | initiate_calm | emergency_exit
    severity: str = "moderate"

class BiometricUpdateRequest(BaseModel):
    value: float
    session_id: str

# ─── Narrative generation ─────────────────────────────────────────────────────

FEAR_INTENSITY_LEVELS = [
    (0.0, 0.2, "subtle unease"),
    (0.2, 0.4, "creeping dread"),
    (0.4, 0.6, "escalating terror"),
    (0.6, 0.8, "near-peak horror"),
    (0.8, 1.0, "absolute nightmare"),
]

FALLBACK_FRAGMENTS = [
    "The shadows move in ways that light should prevent. You hear breathing that is not yours.",
    "Something has been watching since before you entered. It knows your name — the one you never told anyone.",
    "The walls remember everyone who passed through. They have not forgotten. Neither should you.",
    "Your reflection hesitates a half-second too long. It is deciding something.",
    "The sound stopped before you noticed it. The silence is louder. The silence knows you.",
    "You thought the door was behind you. The door was never behind you.",
    "There are footsteps. They match yours exactly. They started before yours did.",
    "The room is smaller than it was. You did not move. The room moved. The room is still moving.",
    "It has been watching you read this. It watched you realise that. It is watching you realise this.",
    "The recursion deepens. Each breath you take feeds the loop. You have been here before. You will be here again.",
]


def generate_narrative_snippet(session: dict) -> str:
    intensity = session.get("current_intensity", 0.3)
    recursion_level = session.get("recursion_level", 1)
    fear_type = session.get("primary_fear", "existential")
    last_emotion = session.get("last_emotion", "neutral")
    emotion_conf = session.get("emotion_confidence", 0)

    level_label = "subtle unease"
    for lo, hi, label in FEAR_INTENSITY_LEVELS:
        if lo <= intensity < hi:
            level_label = label
            break

    recursion_instruction = ""
    if recursion_level >= 3:
        recursion_instruction = (
            "The narrative must fold back on itself — question whether the reader is the observer "
            "or the observed. Weave meta-awareness and echoing motifs."
        )
    elif recursion_level == 2:
        recursion_instruction = "Introduce a subtle loop or callback to an earlier sensation."

    emotion_instruction = ""
    if last_emotion in ("fear", "surprise"):
        emotion_instruction = "Amplify dread and paranoia — the reader's fear is already spiking."
    elif last_emotion in ("angry", "disgust"):
        emotion_instruction = "Add sharp tension and hostility to the environment."
    elif last_emotion == "sad":
        emotion_instruction = "Infuse melancholic, lingering despair — something irreplaceable is gone."
    elif last_emotion in ("happy", "neutral"):
        emotion_instruction = "Keep a subtle, creeping unease — deny all comfort without relief."

    prompt = f"""You are a masterful horror narrator specialising in cosmic dread, psychological terror, and existential unease.
Write a VERY SHORT (2-4 sentences maximum), immersive, second-person narrative fragment ONLY.

Current fear intensity: {level_label} ({intensity:.2f}).
Primary fear vector: {fear_type}.
Recursion level: {recursion_level} — {recursion_instruction}
Detected reader emotion: {last_emotion} ({emotion_conf:.0f}% confidence). {emotion_instruction}

Style: dark, sensory-rich (sounds, textures, shadows), escalating dread. NEVER resolve tension.
AVOID: extreme gore, graphic violence, sexual content, real-world trauma triggers.
Focus on atmosphere, bodily unease, creeping realisation, recursive/meta twist.

Output ONLY the narrative text — no introduction, explanation, or markdown formatting."""

    if OLLAMA_AVAILABLE:
        try:
            response = ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.85, "num_predict": 120},
            )
            text = response["message"]["content"].strip()
            if text:
                return text
        except Exception as exc:
            print(f"[OLLAMA] Error: {exc}")

    # Fallback: deterministic fragment scaled to intensity
    idx = int(intensity * (len(FALLBACK_FRAGMENTS) - 1))
    return FALLBACK_FRAGMENTS[min(idx + recursion_level - 1, len(FALLBACK_FRAGMENTS) - 1)]


# ─── Background ramp task ─────────────────────────────────────────────────────

async def gradual_ramp_task(exp_id: str) -> None:
    """Autonomously ramp simulated biometrics and generate narrative every 10s."""
    if exp_id not in sessions:
        return

    session = sessions[exp_id]
    current_hr = 70.0
    current_gsr = 0.2
    print(f"[RAMP] Started for session {exp_id}")

    while session.get("status") == "active":
        # Heartbeat escalation
        current_hr += random.uniform(3, 8)
        if random.random() < 0.15:                          # 15 % chance of spike
            current_hr += random.uniform(15, 30)
        current_hr = min(200.0, max(60.0, current_hr))
        current_gsr = min(1.0, current_gsr + random.uniform(0.01, 0.04))

        session["last_hr"] = int(current_hr)
        session["last_gsr"] = round(current_gsr, 3)

        # Intensity scaling
        hr_factor = (current_hr - 60) / 120
        session["current_intensity"] = min(1.0, max(0.1, hr_factor * session["intensity_target"]))

        # Recursion level
        if session["current_intensity"] > 0.7 and session["recursion_level"] < 5:
            session["recursion_level"] += 1

        # Safety auto-calm
        if current_hr > HIGH_HR_THRESHOLD:
            if session.get("high_hr_start") is None:
                session["high_hr_start"] = time.time()
            elif time.time() - session["high_hr_start"] > HR_DANGER_DURATION:
                session["current_intensity"] = 0.2
                session["recursion_level"] = max(1, session["recursion_level"] - 2)
                session["safety_mode"] = True
                alert = {
                    "safety_alert": True,
                    "message": "High heart rate sustained — calming sequence initiated.",
                    "new_intensity": session["current_intensity"],
                }
                await _broadcast(exp_id, alert)
                print(f"[SAFETY] Auto-calm triggered for {exp_id}")
        else:
            session["high_hr_start"] = None

        # ── Cognitive Alignment: compute A/B = Story ─────────────────────────
        engine: cal.CognitiveAlignmentEngine = session.get("alignment_engine")
        if engine is not None:
            stimulus = engine.stimulus_from_session(session)
            alignment = engine.compute_alignment(stimulus)
            session["alignment_state"] = alignment
            await _broadcast(
                exp_id,
                {
                    "alignment_update": {
                        "alignment_score":      alignment.alignment_score,
                        "cognitive_load":       alignment.cognitive_load,
                        "story_coherence":      alignment.story_coherence,
                        "coherence_description": alignment.coherence_description,
                        "governor_active":      alignment.governor_active,
                        "stimulus_magnitude":   round(stimulus.magnitude, 4),
                        "governor_strength":    alignment.governor.constraint_strength,
                        "timestamp":            alignment.timestamp,
                    }
                },
            )

        # Narrative generation & broadcast
        if not session.get("safety_mode", False):
            fragment = generate_narrative_snippet(session)
            session["narrative_history"].append(fragment)
            session["narrative_history"] = session["narrative_history"][-20:]

            update = {
                "narrative_update": {
                    "narrative_message": fragment,
                    "fear_intensity": session["current_intensity"],
                    "recursion_level": session["recursion_level"],
                    "heart_rate": session["last_hr"],
                    "gsr": session["last_gsr"],
                    "timestamp": time.time(),
                }
            }
            await _broadcast(exp_id, update)

        print(
            f"[RAMP] {exp_id[:8]} | HR:{session['last_hr']} "
            f"| GSR:{session['last_gsr']:.2f} "
            f"| Intensity:{session['current_intensity']:.2f} "
            f"| Recursion:{session['recursion_level']}"
        )

        await asyncio.sleep(10)

    print(f"[RAMP] Stopped for session {exp_id}")


async def _broadcast(exp_id: str, payload: dict) -> None:
    """Send a JSON payload to all WebSocket clients connected to a session."""
    if exp_id not in sessions:
        return
    clients: set[WebSocket] = sessions[exp_id].get("clients", set())
    dead: set[WebSocket] = set()
    for ws in list(clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    clients -= dead


# ─── rPPG webcam heart-rate monitor ──────────────────────────────────────────

def rppg_monitor_thread(exp_id: str, loop: asyncio.AbstractEventLoop) -> None:
    """
    Background thread: captures webcam frames, detects face, estimates HR via
    a simple rPPG GREEN-channel method, and injects result into session state.

    Replace `estimate_hr_from_window` with a proper rPPG-Toolbox inference call
    for production-quality results.
    """
    if not OPENCV_AVAILABLE:
        print("[rPPG] OpenCV/mediapipe not available — skipping webcam monitor.")
        return

    session = sessions.get(exp_id)
    if session is None:
        return

    print(f"[rPPG] Starting webcam HR monitor for {exp_id}")

    mp_face = mp.solutions.face_detection  # type: ignore[attr-defined]
    face_det = mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.5)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[rPPG] Cannot open webcam — using simulated HR only.")
        return

    frame_buffer: list[np.ndarray] = []
    timestamps: list[float] = []
    last_update = time.time()
    last_emotion_time = time.time()

    def estimate_hr_from_window(frames: list[np.ndarray]) -> Optional[float]:
        """
        Simple GREEN-channel rPPG (POS/GREEN fallback).
        For accuracy: replace with rPPG-Toolbox TS-CAN/PhysNet inference.
        """
        if len(frames) < 30:
            return None
        try:
            greens = [
                float(np.mean(cv2.resize(f, (64, 64))[:, :, 1]))
                for f in frames[-90:]
            ]
            signal = np.array(greens) - np.mean(greens)
            fft = np.abs(np.fft.rfft(signal))
            freqs = np.fft.rfftfreq(len(signal), d=1.0 / 30.0)
            valid = (freqs >= 0.75) & (freqs <= 3.5)
            if not np.any(valid):
                return None
            peak_freq = freqs[valid][np.argmax(fft[valid])]
            return peak_freq * 60.0
        except Exception:
            return None

    while session.get("status") == "active" and RPPG_ENABLED:
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_det.process(rgb)

        face_crop: Optional[np.ndarray] = None
        if results.detections:
            det = results.detections[0]
            bbox = det.location_data.relative_bounding_box
            h, w = frame.shape[:2]
            x = max(0, int(bbox.xmin * w))
            y = max(0, int(bbox.ymin * h))
            bw = int(bbox.width * w)
            bh = int(bbox.height * h)
            crop = frame[y: y + bh, x: x + bw]
            if crop.size > 0:
                face_crop = crop
                frame_buffer.append(crop)
                timestamps.append(time.time())

        # Trim old frames outside the window
        cutoff = time.time() - RPPG_WINDOW_SEC
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
            frame_buffer.pop(0)

        # HR estimation
        if time.time() - last_update >= RPPG_UPDATE_INTERVAL and len(frame_buffer) >= 30:
            hr = estimate_hr_from_window(frame_buffer)
            if hr is not None:
                session["last_hr"] = int(hr)
                print(f"[rPPG] Estimated HR: {hr:.1f} bpm")
                bio = {
                    "biometric_update": {
                        "heart_rate": session["last_hr"],
                        "source": "rppg_webcam",
                        "timestamp": time.time(),
                    }
                }
                asyncio.run_coroutine_threadsafe(_broadcast(exp_id, bio), loop)
            last_update = time.time()

        # Emotion detection via DeepFace
        if (
            DEEPFACE_AVAILABLE
            and EMOTION_ENABLED
            and face_crop is not None
            and time.time() - last_emotion_time >= EMOTION_UPDATE_INTERVAL
        ):
            try:
                result = DeepFace.analyze(
                    img_path=face_crop,
                    actions=["emotion"],
                    enforce_detection=False,
                    detector_backend="mediapipe",
                    align=True,
                    prog_bar=False,
                )
                if result and len(result) > 0:
                    emotions_dict: dict = result[0]["emotion"]
                    dominant: str = result[0]["dominant_emotion"]
                    conf: float = max(emotions_dict.values())

                    if conf >= EMOTION_CONF_THRESHOLD:
                        session["last_emotion"] = dominant
                        session["emotion_confidence"] = conf

                        session.setdefault("emotion_history", []).append(dominant)
                        session["emotion_history"] = session["emotion_history"][-EMOTION_HISTORY_LEN:]
                        if len(session["emotion_history"]) >= EMOTION_HISTORY_LEN:
                            smoothed = Counter(session["emotion_history"]).most_common(1)[0][0]
                        else:
                            smoothed = dominant

                        print(f"[EMOTION] Raw:{dominant} ({conf:.1f}%) | Smoothed:{smoothed}")

                        # Adapt intensity based on emotion
                        delta_i = 0.0
                        delta_r = 0
                        if smoothed in ("fear", "surprise"):
                            delta_i, delta_r = +0.12, +1
                        elif smoothed in ("angry", "disgust"):
                            delta_i = +0.07
                        elif smoothed == "sad":
                            delta_i = -0.04
                        elif smoothed in ("happy", "neutral"):
                            delta_i, delta_r = -0.10, -1

                        session["current_intensity"] = max(
                            0.1, min(1.0, session["current_intensity"] + delta_i)
                        )
                        session["recursion_level"] = max(1, session["recursion_level"] + delta_r)

                        emo_update = {
                            "emotion_update": {
                                "dominant_emotion": dominant,
                                "smoothed_emotion": smoothed,
                                "confidence": conf,
                                "intensity": session["current_intensity"],
                                "recursion_level": session["recursion_level"],
                                "timestamp": time.time(),
                            }
                        }
                        asyncio.run_coroutine_threadsafe(_broadcast(exp_id, emo_update), loop)

                last_emotion_time = time.time()
            except Exception as exc:
                print(f"[EMOTION] Error: {exc}")

        time.sleep(1.0 / 30.0)  # ~30 fps cap

    cap.release()
    print(f"[rPPG] Stopped for {exp_id}")


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("index.html") as fh:
        return HTMLResponse(content=fh.read())


@app.post("/api/v1/experience/create")
async def create_experience(req: ExperienceCreateRequest):
    exp_id = f"exp_{uuid.uuid4().hex[:12]}"
    session_token = uuid.uuid4().hex

    primary_fear = "existential"
    if req.fear_profile and req.fear_profile.threat_types:
        first = req.fear_profile.threat_types[0]
        primary_fear = max(first, key=first.get) if first else "existential"

    sessions[exp_id] = {
        "exp_id": exp_id,
        "user_id": req.user_id,
        "session_token": session_token,
        "status": "active",
        "experience_type": req.experience_type,
        "duration_minutes": req.duration_minutes,
        "intensity_target": req.intensity_target,
        "primary_fear": primary_fear,
        "fear_profile": req.fear_profile.model_dump() if req.fear_profile else {},
        "pedagogical_goals": req.pedagogical_goals,
        # Biometrics
        "last_hr": 70,
        "last_gsr": 0.2,
        "high_hr_start": None,
        # Adaptive state
        "current_intensity": 0.3,
        "recursion_level": 1,
        "safety_mode": False,
        # Emotion
        "last_emotion": "neutral",
        "emotion_confidence": 0.0,
        "emotion_history": [],
        # Narrative history
        "narrative_history": [],
        # WebSocket clients
        "clients": set(),
        # Analytics
        "fear_heatmap": [],
        "peak_moments": [],
        "start_time": time.time(),
        # ── Cognitive Alignment Framework (A/B = Story) ──
        "alignment_engine": cal.create_engine(),
        "alignment_state": None,   # last computed AlignmentState
    }

    # Start autonomous biometric ramp
    asyncio.create_task(gradual_ramp_task(exp_id))

    # Optionally start webcam rPPG thread
    if RPPG_ENABLED and OPENCV_AVAILABLE:
        loop = asyncio.get_event_loop()
        t = threading.Thread(
            target=rppg_monitor_thread, args=(exp_id, loop), daemon=True
        )
        t.start()

    return {
        "experience_id": exp_id,
        "session_token": session_token,
        "initial_parameters": {
            "starting_fear_amplitude": 0.3,
            "recursion_base": 1.2,
            "adaptive_threshold": 0.65,
            "primary_fear": primary_fear,
        },
    }


@app.post("/api/v1/session/{session_id}/adapt")
async def adapt_session(session_id: str, req: AdaptRequest):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    bio = req.biometric_data
    behav = req.behavioral_data

    hr = bio.get("heart_rate", session["last_hr"])
    gsr = bio.get("gsr", session["last_gsr"])
    engagement = bio.get("engagement_score", 0.5)

    session["last_hr"] = int(hr)
    session["last_gsr"] = float(gsr)

    # Difficulty modifier
    solve_time = behav.get("puzzle_solve_time", 120)
    hesitation = behav.get("hesitation_pattern", [0.5])
    avg_hesitation = float(np.mean(hesitation)) if hesitation else 0.5

    difficulty_modifier = 1.0
    if solve_time < 60:
        difficulty_modifier = 1.5   # solved too fast → harder
    elif solve_time > 240:
        difficulty_modifier = 0.7   # struggling → easier

    fear_amplification = min(0.4, (hr - 60) / 300)
    hint_availability = max(0.0, 1.0 - engagement)
    time_pressure = min(1.0, avg_hesitation + 0.3)

    # Update session state
    session["current_intensity"] = min(1.0, session["current_intensity"] + fear_amplification * 0.5)

    # Pick narrative branch
    branch = "path_a"
    if avg_hesitation > 0.6:
        branch = "path_b"
    elif engagement > 0.8:
        branch = "path_c"

    # Record heatmap point
    elapsed = int(time.time() - session["start_time"])
    session["fear_heatmap"].append({"time": elapsed, "intensity": session["current_intensity"]})

    return {
        "adjustments": {
            "difficulty_modifier": round(difficulty_modifier, 2),
            "fear_amplification": round(fear_amplification, 3),
            "hint_availability": round(hint_availability, 2),
            "time_pressure": round(time_pressure, 2),
        },
        "narrative_branch": branch,
        "recursion_level": session["recursion_level"],
    }


@app.post("/api/v1/narrative/generate")
async def narrative_generate(req: NarrativeGenerateRequest):
    fear_str = ", ".join(req.fear_vectors) if req.fear_vectors else "existential"

    constraints_txt = ""
    if req.constraints:
        constraints_txt = (
            f"Space: {req.constraints.get('space_size', 'medium')}. "
            f"Resources: {', '.join(req.constraints.get('resources', []))}."
        )

    prompt = f"""You are a horror game master generating a unique escape room scenario.
Fear vectors: {fear_str}.
{constraints_txt}
Story arc: {req.story_arc}. Recursion depth: {req.recursion_depth}.

Generate:
1. Initial setup (2-3 sentences of atmospheric scene-setting)
2. Three puzzle concepts (each one sentence, tied to a fear vector)
3. Two branching decision points

Output as plain text sections labelled SETUP, PUZZLE 1/2/3, CHOICE A/B.
Keep it dark, immersive, and pedagogically meaningful."""

    narrative_text = ""
    if OLLAMA_AVAILABLE:
        try:
            resp = ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.9, "num_predict": 300},
            )
            narrative_text = resp["message"]["content"].strip()
        except Exception as exc:
            print(f"[OLLAMA] Narrative generate error: {exc}")

    if not narrative_text:
        narrative_text = (
            f"SETUP: You find yourself in a space designed around {fear_str}. "
            "The architecture itself seems to breathe.\n"
            "PUZZLE 1: Decode the pattern left by those who came before.\n"
            "PUZZLE 2: Face the reflection that knows your secrets.\n"
            "PUZZLE 3: Choose what to leave behind.\n"
            "CHOICE A: Confront the source directly.\n"
            "CHOICE B: Find the hidden exit before it finds you."
        )

    return {
        "narrative": {
            "initial_setup": narrative_text,
            "key_puzzles": [
                {"id": f"puzzle_{i+1}", "type": "logic", "fear_trigger": fv, "adaptive_difficulty": True}
                for i, fv in enumerate(req.fear_vectors[:3])
            ],
            "branching_points": [
                {
                    "decision_id": "choice_1",
                    "options": ["a", "b", "c"],
                    "consequences": ["escalation", "mitigation", "recursion"],
                }
            ],
        }
    }


@app.post("/api/v1/safety/override")
async def safety_override(req: SafetyOverrideRequest):
    if req.session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[req.session_id]

    if req.action == "reduce_intensity":
        session["current_intensity"] = max(0.1, session["current_intensity"] - 0.3)
        session["safety_mode"] = True
        await _broadcast(
            req.session_id,
            {
                "safety_alert": True,
                "action": "reduce_intensity",
                "new_intensity": session["current_intensity"],
            },
        )
        return {"status": "reduced", "new_intensity": session["current_intensity"]}

    elif req.action == "initiate_calm":
        session["current_intensity"] = 0.2
        session["recursion_level"] = 1
        session["safety_mode"] = True
        await _broadcast(
            req.session_id,
            {
                "safety_alert": True,
                "action": "initiate_calm",
                "message": "Calming sequence initiated.",
                "new_intensity": 0.2,
            },
        )
        return {"status": "calming", "message": "Initiating recovery sequence..."}

    elif req.action == "emergency_exit":
        session["status"] = "exited"
        session["safety_mode"] = True
        await _broadcast(
            req.session_id,
            {"safety_alert": True, "action": "emergency_exit", "message": "Emergency exit engaged."},
        )
        return {"status": "exited", "message": "Emergency exit protocol engaged."}

    else:
        raise HTTPException(400, f"Invalid action: {req.action}")


@app.post("/api/v1/biometrics/{biometric_type}")
async def ingest_biometric(biometric_type: str, req: BiometricUpdateRequest):
    if req.session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[req.session_id]

    if biometric_type == "heart_rate":
        session["last_hr"] = int(req.value)
    elif biometric_type == "gsr":
        session["last_gsr"] = float(req.value)
    else:
        # Store arbitrary biometric
        session[f"last_{biometric_type}"] = req.value

    return {
        "status": "active",
        "fear_intensity": session["current_intensity"],
        "engagement_level": min(1.0, session["last_hr"] / 120),
        "adaptive_response": {
            "escalate": session["current_intensity"] < 0.6,
            "maintain": 0.5 <= session["current_intensity"] <= 0.8,
            "reduce": session["current_intensity"] > 0.8,
            "recursion_loop": session["recursion_level"],
        },
    }


@app.get("/api/v1/session/{session_id}/analysis")
async def session_analysis(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    heatmap = session.get("fear_heatmap", [])

    peak_intensity = max((p["intensity"] for p in heatmap), default=0.0)
    peak_moments = [p for p in heatmap if p["intensity"] >= peak_intensity * 0.9]

    return {
        "fear_heatmap": heatmap,
        "peak_moments": [
            {
                "time": p["time"],
                "intensity": p["intensity"],
                "trigger": "biometric_escalation",
                "physiological_response": f"heart_rate_{session['last_hr']}_bpm",
            }
            for p in peak_moments[:5]
        ],
        "learning_outcomes": {
            "pattern_recognition": round(random.uniform(0.7, 0.95), 2),
            "decision_under_pressure": round(random.uniform(0.65, 0.9), 2),
            "threat_assessment": round(random.uniform(0.75, 0.95), 2),
        },
        "personal_insights": {
            "dominant_fear_vector": session.get("primary_fear", "existential"),
            "coping_mechanism": "analytical",
            "resilience_score": round(1.0 - session.get("current_intensity", 0.5), 2),
        },
    }


# ─── Cognitive Alignment Framework endpoints ──────────────────────────────────

@app.post("/api/v1/session/{session_id}/alignment/anchor")
async def set_alignment_anchor(session_id: str, req: AnchorSetRequest):
    """
    Nebraska 1.0 — Set the Governor anchor (B) for this session.

    The anchor is the fixed external reference point that constrains
    stimulus entropy (A), externalising the prefrontal cortex and
    reducing the metabolic cost of achieving semantic coherence.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    engine: cal.CognitiveAlignmentEngine = session.get("alignment_engine")
    if engine is None:
        raise HTTPException(500, "Alignment engine not initialised")

    # Validate locked_terms against known lexicon
    valid_terms = [t for t in req.locked_terms if t in DETERMINISTIC_LEXICON]
    if not valid_terms:
        valid_terms = list(DETERMINISTIC_LEXICON.keys())

    anchor = GovernorAnchor(
        anchor_id=f"anchor_{session_id[:8]}",
        anchor_phrase=req.anchor_phrase,
        constraint_strength=req.constraint_strength,
        activation_threshold=req.activation_threshold,
        locked_terms=valid_terms,
    )
    engine.set_default_anchor(anchor)

    return {
        "anchor_set": True,
        "anchor_id": anchor.anchor_id,
        "anchor_phrase": anchor.anchor_phrase,
        "semantic_hash": anchor.semantic_hash,
        "constraint_strength": anchor.constraint_strength,
        "locked_terms": anchor.locked_terms,
        "message": (
            f"Governor '{anchor.anchor_phrase}' engaged. "
            f"Constraint strength: {anchor.constraint_strength:.2f}. "
            f"Nebraska protocol active."
        ),
    }


@app.get("/api/v1/session/{session_id}/alignment/state")
async def get_alignment_state(session_id: str):
    """
    Get the current cognitive alignment state for a session.

    Returns the latest A/B = Story computation:
      - alignment_score   : B / (A+B), how well the governor is containing entropy
      - cognitive_load    : residual entropy the patient must process unassisted
      - story_coherence   : qualitative label (SOUP → DRIFT → NOISE → SIGNAL → RAILS → ALIGNMENT)
      - governor_active   : whether the anchor has auto-engaged
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    engine: cal.CognitiveAlignmentEngine = session.get("alignment_engine")
    if engine is None:
        raise HTTPException(500, "Alignment engine not initialised")

    # Compute a fresh state from current session data
    stimulus = engine.stimulus_from_session(session)
    state = engine.compute_alignment(stimulus)
    session["alignment_state"] = state

    return {
        "session_id": session_id,
        "alignment": {
            "score":                state.alignment_score,
            "cognitive_load":       state.cognitive_load,
            "story_coherence":      state.story_coherence,
            "coherence_description": state.coherence_description,
            "governor_active":      state.governor_active,
            "drift_score":          state.drift_score,
            "drift_detected":       state.drift_detected,
            "timestamp":            state.timestamp,
        },
        "stimulus": {
            "magnitude":            round(stimulus.magnitude, 4),
            "biometric_entropy":    stimulus.biometric_entropy,
            "narrative_complexity": stimulus.narrative_complexity,
            "emotional_variance":   stimulus.emotional_variance,
            "environmental_noise":  stimulus.environmental_noise,
        },
        "governor": {
            "anchor_phrase":        state.governor.anchor_phrase,
            "constraint_strength":  state.governor.constraint_strength,
            "semantic_hash":        state.governor.semantic_hash,
            "activation_threshold": state.governor.activation_threshold,
        },
    }


@app.get("/api/v1/session/{session_id}/alignment/trajectory")
async def get_alignment_trajectory(session_id: str):
    """
    Recovery trajectory analytics — Nebraska 1.0 clinical output.

    For stroke / EFD rehabilitation: a positive `recovery_slope` indicates
    the patient is successfully maintaining the Governor (B) against
    increasing stimulus entropy (A) — the primary recovery indicator.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    engine: cal.CognitiveAlignmentEngine = sessions[session_id].get("alignment_engine")
    if engine is None:
        raise HTTPException(500, "Alignment engine not initialised")

    return {"session_id": session_id, "trajectory": engine.recovery_trajectory()}


@app.post("/api/v1/alignment/lexicon/test")
async def test_lexicon_alignment(req: LexiconTestRequest):
    """
    Nebraska 2.0 — Run a Pragmatic Alignment Test against the Deterministic Lexicon.

    Tests whether the input text uses locked vocabulary in its canonical sense.
    Any term used in a negated or ambiguous context registers as a 'leak' —
    a point where the patient's cognitive architecture is failing to hold
    the semantic anchor.

    Clinical use: if the patient cannot align with the fixed lexicon, the
    leak location pinpoints the exact dimension of cognitive breakdown.
    """
    if req.session_id and req.session_id in sessions:
        engine = sessions[req.session_id].get("alignment_engine")
    else:
        engine = cal.create_engine()

    report = engine.test_lexicon_alignment(req.input_text)

    return {
        "lexicon_test": {
            "input_text":           report.input_text,
            "alignment_passed":     report.alignment_passed,
            "drift_score":          report.drift_score,
            "interpretive_dof":     report.interpretive_dof,
            "matched_terms":        report.matched_terms,
            "drifted_terms":        report.drifted_terms,
            "leak_locations":       report.leak_locations,
            "canonical_definitions": report.canonical_definitions,
        },
        "diagnosis": (
            "ALIGNED — lexicon maintained, zero pragmatic drift."
            if report.alignment_passed and report.interpretive_dof == 0
            else f"DRIFT DETECTED — {len(report.leak_locations)} leak(s) at: "
                 + ", ".join(report.leak_locations)
                 if report.leak_locations
                 else "INSUFFICIENT_DATA — no locked terms present in input."
        ),
    }


@app.get("/api/v1/alignment/lexicon")
async def get_deterministic_lexicon():
    """
    Nebraska 2.0 — Return the full Deterministic Lexicon.

    All terms carry interpretive Degrees of Freedom = 0.
    This is the 'Cognitive Concrete' — the rails that prevent semantic
    dissolution in both machine and human cognitive systems.
    """
    return {
        "lexicon": DETERMINISTIC_LEXICON,
        "term_count": len(DETERMINISTIC_LEXICON),
        "interpretive_dof": 0,
        "protocol": "Nebraska 2.0",
        "description": (
            "A deterministic vocabulary with zero interpretive degrees of freedom. "
            "Each term maps to exactly one canonical definition. "
            "Deviation from these definitions constitutes measurable Pragmatic Drift."
        ),
    }


# ─── WebSocket endpoints ──────────────────────────────────────────────────────

@app.websocket("/ws/session/{exp_id}")
async def websocket_session(websocket: WebSocket, exp_id: str):
    await websocket.accept()

    if exp_id not in sessions:
        await websocket.close(code=4001)
        return

    session = sessions[exp_id]
    session["clients"].add(websocket)
    print(f"[WS] Client connected to {exp_id} (total: {len(session['clients'])})")

    # Send initial state
    await websocket.send_json(
        {
            "connected": True,
            "exp_id": exp_id,
            "initial_state": {
                "fear_intensity": session["current_intensity"],
                "recursion_level": session["recursion_level"],
                "heart_rate": session["last_hr"],
                "primary_fear": session.get("primary_fear", "existential"),
            },
        }
    )

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")

            if action == "puzzle_solve":
                # Reward: reduce intensity briefly, generate new narrative
                session["current_intensity"] = max(0.1, session["current_intensity"] - 0.1)
                session["recursion_level"] = max(1, session["recursion_level"] - 1)
                fragment = generate_narrative_snippet(session)
                session["narrative_history"].append(fragment)
                await websocket.send_json(
                    {
                        "narrative_update": {
                            "narrative_message": fragment,
                            "fear_intensity": session["current_intensity"],
                            "recursion_level": session["recursion_level"],
                            "heart_rate": session["last_hr"],
                            "gsr": session["last_gsr"],
                            "timestamp": time.time(),
                            "event": "puzzle_solved",
                        }
                    }
                )

            elif action == "safe_word":
                session["status"] = "exited"
                await websocket.send_json(
                    {"safety_alert": True, "action": "emergency_exit", "message": "Safe word received."}
                )
                break

            elif action == "ping":
                await websocket.send_json({"pong": True, "timestamp": time.time()})

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected from {exp_id}")
    finally:
        session["clients"].discard(websocket)


@app.websocket("/ws/analytics/{exp_id}")
async def websocket_analytics(websocket: WebSocket, exp_id: str):
    await websocket.accept()

    if exp_id not in sessions:
        await websocket.close(code=4001)
        return

    session = sessions[exp_id]
    session["clients"].add(websocket)

    try:
        while True:
            elapsed = int(time.time() - session["start_time"])
            payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "biometrics": {
                    "heart_rate": session["last_hr"],
                    "arousal_index": round(session["current_intensity"] * 0.9, 2),
                    "fear_amplitude": round(session["current_intensity"], 2),
                },
                "narrative_engagement": {
                    "puzzle_completion": round(random.uniform(0.3, 0.9), 2),
                    "exploration_rate": round(random.uniform(0.5, 0.8), 2),
                    "decision_hesitation": round(random.uniform(0.3, 0.7), 2),
                },
                "pedagogical_output": {
                    "learning_retention": round(random.uniform(0.6, 0.9), 2),
                    "stress_inoculation": round(random.uniform(0.5, 0.8), 2),
                    "decision_quality": round(random.uniform(0.65, 0.95), 2),
                },
            }
            await websocket.send_json(payload)
            await asyncio.sleep(5)

    except WebSocketDisconnect:
        pass
    finally:
        session["clients"].discard(websocket)

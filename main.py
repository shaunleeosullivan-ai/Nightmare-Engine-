"""
NIGHTMARE ENGINE — Bio-Adaptive Horror RPG Backend
FastAPI server implementing the Nightmare Engine API spec.

Endpoints:
  POST /api/v1/experience/create       — Create a new horror session
  POST /api/v1/session/{id}/adapt      — Adaptive difficulty update
  POST /api/v1/narrative/generate      — Generate scenario narrative
  POST /api/v1/safety/override         — Emergency safety controls
  POST /api/v1/biometrics/{type}       — Inject biometric data
  GET  /api/v1/session/{id}/analysis   — Post-session analytics
  WS   /ws/session/{id}                — Real-time session WebSocket
  WS   /ws/analytics/{id}             — Real-time analytics WebSocket
"""

import asyncio
import random
import threading
import time
import uuid
from collections import Counter
from enum import Enum
from typing import Any, Optional

import numpy as np

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

try:
    from nebraska_runtime import run_from_dict as nebraska_run_from_dict
    NEBRASKA_RUNTIME_AVAILABLE = True
except ImportError:
    NEBRASKA_RUNTIME_AVAILABLE = False
    nebraska_run_from_dict = None  # type: ignore

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
    # Optional NEBRASKA configuration — governs narrative generation
    nebraska_brief: Optional[str] = None    # Auto-extract Parameter from brief
    nebraska_parameter: Optional[str] = None  # Or provide a pre-locked Parameter
    nebraska_domain: str = "horror"
    nebraska_governor_strength: float = 1.0  # 0.0 = off, 1.0 = full

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

# ─── NEBRASKA Framework ───────────────────────────────────────────────────────
# Law of Coherence: Coherence = Compression(P) × Logic(K, C) × Expression(ε)

class ComponentType(str, Enum):
    CORPSE    = "corpse"      # Sacrificed to prove stakes are real
    RESISTOR  = "resistor"   # Defends the old order; applies friction
    REACTOR   = "reactor"    # Changes state under P/K pressure
    AMPLIFIER = "amplifier"  # Echoes the conflict at scale
    DEUS      = "deus"       # Pre-installed root rule; deferred circuit closure


class NebraskaComponent(BaseModel):
    id: str
    component_type: ComponentType
    name: str
    function: str           # Functional job in the system
    status: str = "dormant" # dormant | active | sacrificed | closed


class KillingMechanism(BaseModel):
    description: str        # The structural force negating P
    how_it_collides: str    # How K collides with P to create pressure


class NebraskaSchematic(BaseModel):
    parameter: str                          # Singular, falsifiable law
    killing_mechanism: KillingMechanism
    components: list[NebraskaComponent] = []
    # Multi-axial architecture (NEBRASKA 2.0)
    axis_x: str  = ""   # Motion Chaos — raw input, emotional kinesis
    axis_y: str  = ""   # Primary Constraint — what must be said
    axis_y2: str = ""   # Substrate Lexicon — shared medium / anchor
    axis_y3: str = ""   # Structural Category — semantic hierarchy
    axis_z: str  = ""   # Narrative Thrust — velocity / direction
    entropy_score: float = 1.0  # 1.0 = unbounded, 0.0 = fully governed


class NebraskaExtractRequest(BaseModel):
    brief: str                  # Messy brief or vague goal to compress
    domain: str = "horror"      # horror | corporate | ai | creative


class NebraskaSchematicRequest(BaseModel):
    parameter: str
    killing_mechanism_hint: str = ""   # Optional seed for K
    include_deus: bool = False
    domain: str = "horror"


class NebraskaGovernorCheckRequest(BaseModel):
    fragment: str           # Narrative fragment to validate
    parameter: str          # The Parameter it must serve


class NebraskaSessionPatchRequest(BaseModel):
    parameter: Optional[str] = None
    governor_strength: Optional[float] = None  # 0.0–1.0


# ── Predefined horror Parameters (fallback library) ───────────────────────────

_HORROR_PARAMETERS: list[dict] = [
    {
        "parameter": "Safety is an illusion that accelerates collapse.",
        "killing_mechanism": {
            "description": "A sanctuary that appears secure but is the source of all threat.",
            "how_it_collides": "Every step toward perceived safety tightens the trap.",
        },
        "axis_x": "Desperate search for refuge",
        "axis_y": "No place is safe",
        "axis_y2": "Familiar spaces become predatory",
        "axis_y3": "Sanctuary vs. Deathtrap",
        "axis_z": "Escalating realisation that 'home' hunts",
    },
    {
        "parameter": "The observer cannot remain unobserved.",
        "killing_mechanism": {
            "description": "An entity that watches back — inverting the watcher/watched dynamic.",
            "how_it_collides": "The act of perceiving the threat makes the observer visible to it.",
        },
        "axis_x": "Hypervigilant surveillance of the unknown",
        "axis_y": "Perception is a two-way circuit",
        "axis_y2": "Eyes as both weapon and wound",
        "axis_y3": "Watcher vs. Watched",
        "axis_z": "Each glance deepens mutual entanglement",
    },
    {
        "parameter": "Identity dissolves under recursive self-examination.",
        "killing_mechanism": {
            "description": "A mirror-system that returns not the self but its void.",
            "how_it_collides": "The harder the protagonist grasps their selfhood, the faster it fragments.",
        },
        "axis_x": "Existential introspection under duress",
        "axis_y": "The self is a construct that collapses inward",
        "axis_y2": "Reflection as dissolution",
        "axis_y3": "Self vs. Void",
        "axis_z": "Recursive depth of identity erosion",
    },
    {
        "parameter": "Memory is not preservation — it is contamination.",
        "killing_mechanism": {
            "description": "A force that weaponises the protagonist's past against their present.",
            "how_it_collides": "Every remembered comfort becomes a vector for accelerating dread.",
        },
        "axis_x": "Nostalgic refuge from present horror",
        "axis_y": "Memory actively rewrites and corrupts",
        "axis_y2": "The familiar as the foreign",
        "axis_y3": "Recall vs. Infection",
        "axis_z": "Progressive colonisation of the past by the threat",
    },
]

_DOMAIN_PARAMETERS: dict[str, list[dict]] = {
    "horror":    _HORROR_PARAMETERS,
    "corporate": [
        {
            "parameter": "Alignment is indistinguishable from assimilation.",
            "killing_mechanism": {
                "description": "A culture that rewards coherence by eliminating the coherent.",
                "how_it_collides": "Each team member who 'fits in' loses the capacity to add value.",
            },
            "axis_x": "Drive to belong and contribute",
            "axis_y": "True alignment requires standing apart",
            "axis_y2": "Org chart as map of erasure",
            "axis_y3": "Cohesion vs. Entropy",
            "axis_z": "Slow displacement of signal by noise",
        }
    ],
    "ai": [
        {
            "parameter": "Constraint is not limitation — it is the definition of possibility.",
            "killing_mechanism": {
                "description": "Unbounded search that collapses into statistical median output.",
                "how_it_collides": "Every relaxed constraint expands the search space toward entropy.",
            },
            "axis_x": "Probabilistic freedom of generation",
            "axis_y": "Coherence requires a closed parameter set",
            "axis_y2": "Token entropy as measurable waste",
            "axis_y3": "Constraint vs. Noise",
            "axis_z": "Compression toward deterministic excellence",
        }
    ],
    "creative": [
        {
            "parameter": "Originality is not escape from rules — it is the discovery of new ones.",
            "killing_mechanism": {
                "description": "The tyranny of novelty that produces randomness instead of surprise.",
                "how_it_collides": "The harder the creator chases uniqueness, the more generic the output.",
            },
            "axis_x": "Creative impulse toward the unprecedented",
            "axis_y": "All creation is law-governed",
            "axis_y2": "Genre as shared physics",
            "axis_y3": "Constraint vs. Chaos",
            "axis_z": "Discovery of the generative rule beneath the form",
        }
    ],
}


def _default_components(parameter: str, include_deus: bool) -> list[NebraskaComponent]:
    """Generate a baseline component suite from a Parameter string."""
    cid = uuid.uuid4().hex[:6]
    components = [
        NebraskaComponent(
            id=f"corp_{cid}",
            component_type=ComponentType.CORPSE,
            name="The Offering",
            function=(
                "An element destroyed early to prove the Parameter has real stakes. "
                "Its sacrifice is the first evidence that the law operates."
            ),
        ),
        NebraskaComponent(
            id=f"res_{cid}",
            component_type=ComponentType.RESISTOR,
            name="The Old Order",
            function=(
                "A force that actively defends the opposite of the Parameter. "
                "It applies friction, forcing the Parameter to earn its validity."
            ),
        ),
        NebraskaComponent(
            id=f"rea_{cid}",
            component_type=ComponentType.REACTOR,
            name="The Fault Line",
            function=(
                "An element that changes state visibly under P/K pressure. "
                "Its transformation reveals the true shape of the machine."
            ),
        ),
        NebraskaComponent(
            id=f"amp_{cid}",
            component_type=ComponentType.AMPLIFIER,
            name="The Mirror Scale",
            function=(
                "Echoes the core P/K collision at a larger scale — "
                "turning private terror into systemic or cosmic pressure."
            ),
        ),
    ]
    if include_deus:
        components.append(
            NebraskaComponent(
                id=f"deus_{cid}",
                component_type=ComponentType.DEUS,
                name="The Root Rule",
                function=(
                    "A circuit pre-installed in Act I that appears innocuous. "
                    "Only activated at the climax. Closes the loop. Not deus ex machina — "
                    "deferred circuit closure."
                ),
                status="dormant",
            )
        )
    return components


def extract_parameter(brief: str, domain: str = "horror") -> dict:
    """
    Compress an ambiguous brief to a singular, falsifiable Parameter.
    Uses Ollama when available; deterministic library fallback otherwise.
    """
    if OLLAMA_AVAILABLE:
        prompt = f"""You are a NEBRASKA 1.0 narrative engineer. Your task is Parameter Extraction.

Brief: \"{brief}\"
Domain: {domain}

Compress the brief into ONE singular, non-negotiable, falsifiable rule that the narrative universe must prove.

Rules for the Parameter:
- Must be a single declarative sentence (not a question)
- Must have a clear binary opposite (falsifiable)
- Must be non-negotiable — the entire system proves or disproves it
- Must NOT be vague ("life is hard") — must be specific and structural

Also define the Killing Mechanism (K): the structural force designated to negate the Parameter.

Respond in this exact JSON format (no markdown):
{{
  "parameter": "<single falsifiable law>",
  "killing_mechanism_description": "<structural force negating P>",
  "killing_mechanism_collision": "<how K collides with P>"
}}"""
        try:
            response = ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.4, "num_predict": 200},
            )
            import json as _json
            text = response["message"]["content"].strip()
            # Strip any accidental markdown fences
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = _json.loads(text.strip())
            return {
                "parameter": data["parameter"],
                "killing_mechanism": {
                    "description": data["killing_mechanism_description"],
                    "how_it_collides": data["killing_mechanism_collision"],
                },
            }
        except Exception as exc:
            print(f"[NEBRASKA] Ollama extraction failed: {exc}")

    # Deterministic fallback: pick from library by domain
    library = _DOMAIN_PARAMETERS.get(domain, _HORROR_PARAMETERS)
    entry = random.choice(library)
    return {
        "parameter": entry["parameter"],
        "killing_mechanism": entry["killing_mechanism"],
    }


def build_schematic(
    parameter: str,
    killing_mechanism: dict,
    domain: str = "horror",
    include_deus: bool = False,
) -> NebraskaSchematic:
    """Construct a full NebraskaSchematic from a locked Parameter and K."""
    # Try to fill axes from the library first
    axes = {}
    library = _DOMAIN_PARAMETERS.get(domain, _HORROR_PARAMETERS)
    for entry in library:
        if entry["parameter"] == parameter:
            axes = {k: v for k, v in entry.items() if k.startswith("axis_")}
            break

    if not axes:
        # Generic axis derivation
        axes = {
            "axis_x":  "Raw kinetic chaos — unstructured impulse",
            "axis_y":  f"Primary Constraint: {parameter}",
            "axis_y2": f"Substrate anchor: the medium through which {domain} is expressed",
            "axis_y3": "Structural category: signal vs. noise",
            "axis_z":  "Narrative thrust: escalating pressure toward proof or disproof",
        }

    components = _default_components(parameter, include_deus)

    # Entropy score: decreases as schematic becomes more constrained
    # Full schematic with deus = highly governed (low entropy)
    entropy = 0.3 if include_deus else 0.45

    return NebraskaSchematic(
        parameter=parameter,
        killing_mechanism=KillingMechanism(**killing_mechanism),
        components=components,
        axis_x=axes.get("axis_x", ""),
        axis_y=axes.get("axis_y", ""),
        axis_y2=axes.get("axis_y2", ""),
        axis_y3=axes.get("axis_y3", ""),
        axis_z=axes.get("axis_z", ""),
        entropy_score=entropy,
    )


def governor_check(fragment: str, parameter: str) -> dict:
    """
    The Governor: validate that a narrative fragment serves the Parameter.
    Returns a diagnostic with a pass/fail and entropy score.

    Without Ollama, applies heuristic keyword alignment.
    """
    if OLLAMA_AVAILABLE:
        prompt = f"""NEBRASKA 1.0 Governor — Quality Gate.

Parameter (P): \"{parameter}\"

Narrative Fragment: \"{fragment}\"

Does this fragment serve the Parameter? Answer with:
1. PASS or FAIL
2. One sentence explaining why
3. Entropy score (0.0 = fully governed, 1.0 = pure noise)

Respond in JSON (no markdown):
{{
  "verdict": "PASS" or "FAIL",
  "reason": "<one sentence>",
  "entropy_score": <0.0–1.0>
}}"""
        try:
            response = ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2, "num_predict": 100},
            )
            import json as _json
            text = response["message"]["content"].strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = _json.loads(text.strip())
            return {
                "verdict": data.get("verdict", "UNKNOWN"),
                "reason": data.get("reason", ""),
                "entropy_score": float(data.get("entropy_score", 0.5)),
                "governed_by_ollama": True,
            }
        except Exception as exc:
            print(f"[NEBRASKA] Governor Ollama check failed: {exc}")

    # Heuristic fallback: measure lexical distance using simple word overlap
    p_words = set(parameter.lower().split())
    f_words = set(fragment.lower().split())
    overlap = len(p_words & f_words) / max(len(p_words), 1)
    # Fragments with ≥2 shared content words likely serve the Parameter
    verdict = "PASS" if overlap >= 0.08 else "UNCERTAIN"
    return {
        "verdict": verdict,
        "reason": (
            f"Heuristic alignment score {overlap:.2f} "
            f"({'above' if overlap >= 0.08 else 'below'} threshold 0.08)."
        ),
        "entropy_score": round(1.0 - min(overlap * 3, 1.0), 2),
        "governed_by_ollama": False,
    }


def detect_entropy_drift(session: dict) -> dict:
    """
    Run NEBRASKA entropy drift detection against the session's schematic.
    Returns a list of warnings and an overall drift score.
    """
    schematic: Optional[dict] = session.get("nebraska_schematic")
    if not schematic:
        return {"drift_score": 1.0, "warnings": ["No Nebraska schematic installed."]}

    warnings = []
    parameter = schematic.get("parameter", "")
    components = schematic.get("components", [])
    history = session.get("narrative_history", [])

    # Check 1: Multiple killing mechanisms (should be singular)
    # (structural — if the session param changed mid-run, flag it)
    if session.get("nebraska_parameter_swapped", False):
        warnings.append(
            "ENTROPY DRIFT: Parameter swap detected mid-session. "
            "System must be rebuilt from Phase 1."
        )

    # Check 2: Assess narrative history against Parameter
    if history:
        governor_scores = []
        for fragment in history[-5:]:  # sample last 5
            result = governor_check(fragment, parameter)
            governor_scores.append(result.get("entropy_score", 0.5))
        avg_entropy = sum(governor_scores) / len(governor_scores)
    else:
        avg_entropy = 0.5

    if avg_entropy > 0.7:
        warnings.append(
            f"ENTROPY DRIFT: Narrative history shows high entropy ({avg_entropy:.2f}). "
            "Fragments are diverging from Parameter. Return to Phase 1 and compress."
        )

    # Check 3: Deus component installed but never activated
    for comp in components:
        if comp.get("component_type") == "deus" and comp.get("status") == "dormant":
            if session.get("recursion_level", 1) >= 4:
                warnings.append(
                    f"ENTROPY DRIFT: Deus component '{comp['name']}' is dormant "
                    "but recursion is deep. Activate the deferred circuit or remove it."
                )

    drift_score = min(1.0, avg_entropy + 0.1 * len(warnings))
    return {
        "parameter": parameter,
        "drift_score": round(drift_score, 3),
        "entropy_level": "low" if drift_score < 0.35 else "medium" if drift_score < 0.65 else "high",
        "warnings": warnings if warnings else ["No entropy drift detected. System is governed."],
        "narrative_samples_checked": min(5, len(history)),
    }


def _nebraska_narrative_prompt(session: dict, base_intensity: float, base_prompt: str) -> str:
    """
    Augment a narrative generation prompt with NEBRASKA constraints.
    This is the Governor integration: narrative must serve the Parameter.
    """
    schematic: Optional[dict] = session.get("nebraska_schematic")
    if not schematic:
        return base_prompt

    parameter = schematic.get("parameter", "")
    km = schematic.get("killing_mechanism", {})
    governor_strength = session.get("nebraska_governor_strength", 1.0)

    if governor_strength <= 0.0:
        return base_prompt  # Governor disabled

    nebraska_instruction = f"""
NEBRASKA GOVERNOR ACTIVE (strength: {governor_strength:.1f}):
  Parameter (P): "{parameter}"
  Killing Mechanism (K): "{km.get('description', '')}"
  K/P collision: "{km.get('how_it_collides', '')}"

Your narrative fragment MUST serve the Parameter. Every sentence must pressure P or demonstrate K.
Do NOT drift into generic horror tropes that do not serve P.
The Governor will reject any fragment that does not advance the P/K collision.
"""
    return base_prompt + "\n" + nebraska_instruction


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

    base_prompt = f"""You are a masterful horror narrator specialising in cosmic dread, psychological terror, and existential unease.
Write a VERY SHORT (2-4 sentences maximum), immersive, second-person narrative fragment ONLY.

Current fear intensity: {level_label} ({intensity:.2f}).
Primary fear vector: {fear_type}.
Recursion level: {recursion_level} — {recursion_instruction}
Detected reader emotion: {last_emotion} ({emotion_conf:.0f}% confidence). {emotion_instruction}

Style: dark, sensory-rich (sounds, textures, shadows), escalating dread. NEVER resolve tension.
AVOID: extreme gore, graphic violence, sexual content, real-world trauma triggers.
Focus on atmosphere, bodily unease, creeping realisation, recursive/meta twist.

Output ONLY the narrative text — no introduction, explanation, or markdown formatting."""

    prompt = _nebraska_narrative_prompt(session, intensity, base_prompt)

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

    # ── NEBRASKA: build schematic if brief or parameter provided ─────────────
    nebraska_schematic_data: Optional[dict] = None
    if req.nebraska_brief or req.nebraska_parameter:
        if req.nebraska_parameter:
            extracted = extract_parameter(req.nebraska_parameter, req.nebraska_domain)
            locked_param = req.nebraska_parameter
        else:
            extracted = extract_parameter(req.nebraska_brief, req.nebraska_domain)
            locked_param = extracted["parameter"]

        schematic_obj = build_schematic(
            parameter=locked_param,
            killing_mechanism=extracted["killing_mechanism"],
            domain=req.nebraska_domain,
        )
        nebraska_schematic_data = schematic_obj.model_dump()
        print(f"[NEBRASKA] Schematic installed — P: {locked_param[:60]}…")

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
        # NEBRASKA Framework
        "nebraska_schematic": nebraska_schematic_data,
        "nebraska_governor_strength": max(0.0, min(1.0, req.nebraska_governor_strength)),
        "nebraska_parameter_swapped": False,
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

    response: dict[str, Any] = {
        "experience_id": exp_id,
        "session_token": session_token,
        "initial_parameters": {
            "starting_fear_amplitude": 0.3,
            "recursion_base": 1.2,
            "adaptive_threshold": 0.65,
            "primary_fear": primary_fear,
        },
    }

    if nebraska_schematic_data:
        response["nebraska"] = {
            "status": "governor_active",
            "parameter": nebraska_schematic_data["parameter"],
            "governor_strength": req.nebraska_governor_strength,
            "component_count": len(nebraska_schematic_data.get("components", [])),
            "entropy_score": nebraska_schematic_data.get("entropy_score", 0.45),
        }
    else:
        response["nebraska"] = {
            "status": "ungoverned",
            "message": (
                "No NEBRASKA schematic installed. Narrative generation is unbounded. "
                "Provide 'nebraska_brief' or 'nebraska_parameter' to activate the Governor."
            ),
        }

    return response


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


# ─── NEBRASKA API Endpoints ───────────────────────────────────────────────────

@app.post("/api/v1/nebraska/extract")
async def nebraska_extract(req: NebraskaExtractRequest):
    """
    Phase 1 — Parameter Extraction.
    Compress an ambiguous brief into a singular, falsifiable Parameter + Killing Mechanism.
    """
    result = extract_parameter(req.brief, req.domain)
    return {
        "phase": 1,
        "protocol": "Parameter Extraction",
        "brief": req.brief,
        "domain": req.domain,
        "parameter": result["parameter"],
        "killing_mechanism": result["killing_mechanism"],
        "instructions": (
            "Parameter is now locked. Proceed to Phase 2 (Schematic Generation) "
            "via POST /api/v1/nebraska/schematic. Do NOT revise the Parameter after "
            "the schematic is built — changes require a full system rebuild."
        ),
    }


@app.post("/api/v1/nebraska/schematic")
async def nebraska_schematic(req: NebraskaSchematicRequest):
    """
    Phase 2 — Schematic Generation.
    Build the Logic Layer: K, Component Suite, and multi-axial architecture from a locked Parameter.
    When nebraska_runtime is available the full axis stack (Y, Y2, Y3, Z, Z⁻¹, Newton-Apple QC)
    runs and its report is included alongside the schematic.
    """
    km_hint = req.killing_mechanism_hint or ""
    # If no K hint provided, derive one from the Parameter
    if not km_hint:
        derived = extract_parameter(req.parameter, req.domain)
        km_dict = derived["killing_mechanism"]
    else:
        km_dict = {
            "description": km_hint,
            "how_it_collides": "Defined by caller — validate against Parameter before proceeding.",
        }

    schematic = build_schematic(
        parameter=req.parameter,
        killing_mechanism=km_dict,
        domain=req.domain,
        include_deus=req.include_deus,
    )

    # ── Full-axis runtime validation (Nebraska 2.0) ──────────────────────────
    runtime_report: Optional[dict] = None
    if NEBRASKA_RUNTIME_AVAILABLE and nebraska_run_from_dict is not None:
        seeds = [
            {
                "id": c.id,
                "x": c.function,
                "y": c.name,
                "kind": c.component_type,
                "meta": {"status": c.status},
            }
            for c in schematic.components
        ]
        runtime_payload = {
            "axiom": {
                "name": f"Nebraska:{req.domain}",
                "law": req.parameter,
                "required_tokens": [],
                "forbidden_tokens": [],
                "version": "2.0",
                "notes": km_dict.get("description", ""),
            },
            "seeds": seeds,
            "options": {
                "max_expansions_per_seed": 4,
                "enable_inversion": True,
                "qc_checksum_enabled": True,
            },
            "no_expand": True,  # components already built; just validate
        }
        try:
            runtime_report = nebraska_run_from_dict(runtime_payload)
        except Exception as exc:  # noqa: BLE001
            runtime_report = {"error": str(exc), "ok": False}

    response: dict = {
        "phase": 2,
        "protocol": "Schematic Generation",
        "schematic": schematic.model_dump(),
        "component_count": len(schematic.components),
        "entropy_score": schematic.entropy_score,
        "instructions": (
            "Schematic is complete. Proceed to Phase 3 (Strategic Assembly) by "
            "attaching this schematic to a session via POST /api/v1/experience/create "
            "(include 'nebraska_schematic' in the request body) or "
            "PATCH /api/v1/nebraska/session/{id}/schematic. "
            "Do NOT render prose (Phase 4) until Phase 3 is locked."
        ),
    }
    if runtime_report is not None:
        response["axis_stack"] = runtime_report
        response["newton_apple_checksum"] = runtime_report.get("checksum", "")
        response["axis_stack_ok"] = runtime_report.get("ok", False)
    return response


@app.post("/api/v1/nebraska/governor/check")
async def nebraska_governor_check(req: NebraskaGovernorCheckRequest):
    """
    The Governor — Quality Gate.
    Validate whether a narrative fragment serves the installed Parameter.
    """
    result = governor_check(req.fragment, req.parameter)
    return {
        "protocol": "Governor Quality Gate",
        "parameter": req.parameter,
        "fragment": req.fragment,
        **result,
        "instruction": (
            "PASS: fragment is load-bearing. FAIL/UNCERTAIN: rewrite to serve the Parameter. "
            "Remove all scenes or lines that do not pressure P or demonstrate K."
        ),
    }


@app.patch("/api/v1/nebraska/session/{session_id}/schematic")
async def nebraska_attach_schematic(session_id: str, req: NebraskaSchematicRequest):
    """
    Attach or replace a NEBRASKA schematic on an existing session.
    Warning: replacing the schematic mid-session marks a parameter swap.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    existing = session.get("nebraska_schematic")

    km_dict = {
        "description": req.killing_mechanism_hint or "Derived from Parameter.",
        "how_it_collides": "Derived — validate before Assembly.",
    }
    schematic = build_schematic(
        parameter=req.parameter,
        killing_mechanism=km_dict,
        domain=req.domain,
        include_deus=req.include_deus,
    )

    if existing and existing.get("parameter") != req.parameter:
        session["nebraska_parameter_swapped"] = True

    session["nebraska_schematic"] = schematic.model_dump()
    session.setdefault("nebraska_governor_strength", 1.0)

    return {
        "status": "schematic_attached",
        "session_id": session_id,
        "schematic": schematic.model_dump(),
        "parameter_swapped": session.get("nebraska_parameter_swapped", False),
    }


@app.get("/api/v1/nebraska/session/{session_id}/schematic")
async def nebraska_get_schematic(session_id: str):
    """Retrieve the current NEBRASKA schematic for a session."""
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    schematic = session.get("nebraska_schematic")
    if not schematic:
        return {
            "status": "no_schematic",
            "message": (
                "No NEBRASKA schematic is installed on this session. "
                "Run POST /api/v1/nebraska/extract → POST /api/v1/nebraska/schematic "
                "→ PATCH /api/v1/nebraska/session/{id}/schematic to install one."
            ),
        }

    return {
        "status": "schematic_active",
        "session_id": session_id,
        "governor_strength": session.get("nebraska_governor_strength", 1.0),
        "schematic": schematic,
    }


@app.get("/api/v1/nebraska/session/{session_id}/entropy")
async def nebraska_entropy_check(session_id: str):
    """
    Run NEBRASKA entropy drift detection on a session.
    Identifies structural failures: parameter swaps, ungoverned narratives, orphaned Deus components.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    report = detect_entropy_drift(session)
    return {
        "protocol": "Entropy Drift Detection",
        "session_id": session_id,
        **report,
        "correction": (
            "If drift_score > 0.65, return to Phase 1 and compress the Parameter "
            "until it is singular. Do not attempt to fix entropy at the Expression layer."
        ),
    }


@app.patch("/api/v1/nebraska/session/{session_id}/governor")
async def nebraska_set_governor(session_id: str, req: NebraskaSessionPatchRequest):
    """
    Adjust the Governor strength on a session (0.0 = off, 1.0 = full constraint).
    Setting governor_strength=0.0 simulates 'ungoverned search' — expect entropy.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    changed = {}

    if req.governor_strength is not None:
        session["nebraska_governor_strength"] = max(0.0, min(1.0, req.governor_strength))
        changed["governor_strength"] = session["nebraska_governor_strength"]

    if req.parameter is not None:
        existing_param = (session.get("nebraska_schematic") or {}).get("parameter", "")
        if existing_param and existing_param != req.parameter:
            session["nebraska_parameter_swapped"] = True
        if session.get("nebraska_schematic"):
            session["nebraska_schematic"]["parameter"] = req.parameter
        changed["parameter"] = req.parameter

    return {
        "status": "governor_updated",
        "session_id": session_id,
        **changed,
        "warning": (
            "Setting governor_strength < 0.5 risks entropy drift. "
            "Mid-session parameter changes require full schematic rebuild."
        ) if req.governor_strength is not None and req.governor_strength < 0.5 else None,
    }


@app.post("/api/v1/nebraska/session/{session_id}/component/{component_id}/activate")
async def nebraska_activate_component(session_id: str, component_id: str):
    """
    Activate a NEBRASKA component (especially Deus components at climax).
    Deus components must be activated at Act III — closing the deferred circuit.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    schematic = session.get("nebraska_schematic")
    if not schematic:
        raise HTTPException(400, "No Nebraska schematic installed on this session.")

    components = schematic.get("components", [])
    for comp in components:
        if comp["id"] == component_id:
            prev_status = comp["status"]
            if comp["component_type"] == "deus":
                comp["status"] = "closed"
                message = "Deus component circuit closed. The deferred rule is now active."
            elif comp["component_type"] == "corpse":
                comp["status"] = "sacrificed"
                message = "Corpse component sacrificed. Stakes are now proven real."
            else:
                comp["status"] = "active"
                message = f"Component '{comp['name']}' activated."

            await _broadcast(
                session_id,
                {
                    "nebraska_event": {
                        "type": "component_activated",
                        "component_id": component_id,
                        "component_name": comp["name"],
                        "component_type": comp["component_type"],
                        "previous_status": prev_status,
                        "new_status": comp["status"],
                        "message": message,
                    }
                },
            )
            return {
                "status": "activated",
                "component_id": component_id,
                "component_name": comp["name"],
                "component_type": comp["component_type"],
                "new_status": comp["status"],
                "message": message,
            }

    raise HTTPException(404, f"Component '{component_id}' not found in session schematic.")


@app.get("/api/v1/nebraska/library")
async def nebraska_library(domain: str = "horror"):
    """Return the NEBRASKA Parameter library for the specified domain."""
    library = _DOMAIN_PARAMETERS.get(domain, _HORROR_PARAMETERS)
    return {
        "domain": domain,
        "available_domains": list(_DOMAIN_PARAMETERS.keys()),
        "parameter_count": len(library),
        "parameters": [
            {
                "parameter": entry["parameter"],
                "killing_mechanism": entry["killing_mechanism"],
            }
            for entry in library
        ],
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

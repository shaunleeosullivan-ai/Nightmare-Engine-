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

Nebraska 3.0 — Anti-Entropic Assembly Protocol: Extended Operations Layer
  POST /api/v3/nebraska/compile                          — Register & compile schematic
  GET  /api/v3/nebraska/schematics                       — List all registered schematics
  GET  /api/v3/nebraska/schematics/{id}                  — Get schematic record
  DELETE /api/v3/nebraska/schematics/{id}                — Remove from registry
  POST /api/v3/nebraska/schematics/{id}/gaze             — Run Gaze quality gate
  POST /api/v3/nebraska/schematics/{id}/compress         — Re-compress Parameter
  POST /api/v3/nebraska/schematics/{id}/propagate        — Cross-session propagation
  POST /api/v3/nebraska/schematics/{id}/pressure/advance — Advance pressure curve beat
  GET  /api/v3/nebraska/schematics/{id}/pressure         — Current pressure curve position
  POST /api/v3/nebraska/schematics/{id}/components/{type}/activate — Activate Deus/Reactor
  POST /api/v3/nebraska/schematics/{id}/reactor/transition — Record Reactor state change
  POST /api/v3/nebraska/diagnostics/parameter-swap       — Detect Parameter Swap in feedback
  POST /api/v3/nebraska/diagnostics/entropy-drift        — Entropy drift analysis on content
  GET  /api/v3/nebraska/diagnostics/{id}/report          — Full diagnostic report
"""

import asyncio
import math
import random
import threading
import time
import uuid
from collections import Counter
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

# ─── Nebraska 1.0 Framework Data ─────────────────────────────────────────────
# Principia of Narrative Engineering: Anti-Entropic Assembly Protocol
# Coherence = Compression(P) × Logic(K, C) × Expression(ε)

NEBRASKA_PARAMETER_LIBRARY: dict[str, dict] = {
    "existential": {
        "parameter": "Consciousness, once aware of its own void, cannot return to ignorance",
        "negation": "Consciousness can choose to forget what it has seen",
        "killing_mechanism": "The threshold of unknowing — the last moment before dissolution swallows the witness",
        "km_role": "Tests whether awareness is a gift or a wound by forcing the Parameter to the edge of non-existence",
    },
    "claustrophobia": {
        "parameter": "Space is not a physical fact but a permission granted by the mind — withdraw the permission, erase the space",
        "negation": "Space exists independently of the mind that measures it",
        "killing_mechanism": "The shrinking room — a geometry that refuses to honour the permission",
        "km_role": "Tests whether the mind can override what the body insists is real",
    },
    "social": {
        "parameter": "The self only exists inside the gaze of others — remove the gaze, unmake the self",
        "negation": "The self persists independent of any witness",
        "killing_mechanism": "The simultaneous withdrawal — every witness looks away at once",
        "km_role": "Tests whether identity survives total social erasure",
    },
    "cosmic": {
        "parameter": "At sufficient magnitude, meaning inverts to meaninglessness — scale is not neutral",
        "negation": "Meaning is scale-invariant and persists regardless of cosmic context",
        "killing_mechanism": "The perspective that reveals all human significance as a rounding error",
        "km_role": "Tests whether meaning is a property of the universe or a hallucination of scale",
    },
    "predator": {
        "parameter": "The hunted cannot think clearly — survival instinct destroys the cognition required for survival",
        "negation": "Rational thought can coexist with predator pressure",
        "killing_mechanism": "The moment the prey must think to survive but terror makes thought impossible",
        "km_role": "Tests whether intelligence is an asset or a liability when pursued",
    },
    "abandonment": {
        "parameter": "Belonging is not comfort — it is the only proof that the self is real",
        "negation": "The self exists independently of its connections to others",
        "killing_mechanism": "The final departure — the last witness who withdraws and does not return",
        "km_role": "Tests whether identity survives complete relational erasure",
    },
    "body_horror": {
        "parameter": "The body is not a vessel for the self — the self is a passenger in a vehicle it never chose",
        "negation": "The self and body are unified and inseparable",
        "killing_mechanism": "The body's mutation — the moment the vehicle overrides the passenger's controls",
        "km_role": "Tests whether identity persists when the substrate betrays its occupant",
    },
}

NEBRASKA_COMPONENT_TEMPLATES: dict[str, list[dict]] = {
    "existential": [
        {"type": "corpse", "name": "The Certain Past", "function": "Stable identity before awareness struck", "role": "Sacrificed to prove the Parameter has teeth"},
        {"type": "resistor", "name": "The Rationalist", "function": "Defends the belief that ignorance can be reconstructed", "role": "Applies friction — forces the Parameter to earn its proof"},
        {"type": "reactor", "name": "The Witness", "function": "A mind mid-transition between knowing and not-knowing", "role": "Changes state under P/K pressure — reveals the machine's true shape"},
        {"type": "amplifier", "name": "The Archive", "function": "Every previous visitor who did not escape awareness", "role": "Scales the private struggle to cosmic inevitability"},
        {"type": "deus", "name": "The Prior Question", "function": "A question asked before the session began — already answered without the subject knowing", "role": "Pre-installed circuit: planted in Act I, closes only at resolution"},
    ],
    "claustrophobia": [
        {"type": "corpse", "name": "The Open Door", "function": "Proof that exits once existed", "role": "Its destruction confirms the Parameter: permission has been revoked"},
        {"type": "resistor", "name": "The Surveyor's Tape", "function": "Objective measurement that insists dimensions have not changed", "role": "Defends the idea that space is physical, not granted — maximum friction"},
        {"type": "reactor", "name": "The Breath", "function": "The body's involuntary response to shrinking geometry", "role": "Changes state from breathing to gasping — mirrors the Parameter's proof"},
        {"type": "amplifier", "name": "The Other Rooms", "function": "Spaces beyond that are also contracting, unreachable", "role": "Scales the single room's collapse to total environmental withdrawal"},
        {"type": "deus", "name": "The First Measurement", "function": "A dimension recorded before the compression began", "role": "Planted in Act I; activated in Act III to prove the mathematics of withdrawal"},
    ],
    "cosmic": [
        {"type": "corpse", "name": "The Meaningful Object", "function": "An artifact imbued with human significance", "role": "Destroyed by the scale-perspective to prove that meaning does not survive magnitude"},
        {"type": "resistor", "name": "The Humanist", "function": "Insists that scale cannot dissolve significance", "role": "Defends meaning against the Killing Mechanism's perspective"},
        {"type": "reactor", "name": "The Counter", "function": "A mind that attempts to hold human meaning while comprehending cosmic scale", "role": "Changes state: starts with meaning, ends without it — or discovers something beyond both"},
        {"type": "amplifier", "name": "The Other Civilisations", "function": "Every intelligent species that reached the same perspective and went silent", "role": "Scales the single mind's dissolution to universal pattern"},
        {"type": "deus", "name": "The Local Rule", "function": "A constraint that only operates at human scale — invisible from outside it", "role": "Planted in Act I as a comfort; activated in Act III as the only remaining anchor"},
    ],
    "_default": [
        {"type": "corpse", "name": "The Before-State", "function": "Stable order before the Parameter's pressure began", "role": "Sacrificed to prove the stakes are real and irreversible"},
        {"type": "resistor", "name": "The Old Law", "function": "The belief system that denies the Parameter's truth", "role": "Creates structural friction — forces the Parameter to earn its validity"},
        {"type": "reactor", "name": "The Threshold Figure", "function": "An element caught between the old order and the new", "role": "Changes state under P/K collision — reveals the machine's shape"},
        {"type": "amplifier", "name": "The Echo System", "function": "The environment that mirrors the core P/K collision at every scale", "role": "Expands the private conflict to systemic and cosmic pressure"},
        {"type": "deus", "name": "The Planted Rule", "function": "A law installed at the start that only becomes visible at resolution", "role": "Deferred circuit closure — this is not deus ex machina; it is physics"},
    ],
}


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

class NebraskaComponent(BaseModel):
    component_type: str   # corpse | resistor | reactor | amplifier | deus
    name: str
    function: str
    narrative_role: str
    state: str = "initial"
    activated: bool = False

class NebraskaSchematic(BaseModel):
    parameter: str
    parameter_negation: str
    killing_mechanism: str
    killing_mechanism_role: str
    components: list[NebraskaComponent]
    pressure_curve: list[str]
    deus_circuit: Optional[str] = None
    expression_seed: str = ""
    entropy_score: float = 0.0
    fear_vector: str = "existential"

class NebraskaCompileRequest(BaseModel):
    raw_concept: str
    fear_vector: str = "existential"
    session_id: Optional[str] = None

class NebraskaPhaseResult(BaseModel):
    phase: int
    name: str
    output: dict

class NebraskaCompileResponse(BaseModel):
    schematic: NebraskaSchematic
    phases: list[NebraskaPhaseResult]
    governor_active: bool = True
    session_attached: bool = False

class NebraskaAttachRequest(BaseModel):
    schematic: NebraskaSchematic


# ─── Nebraska 3.0 Models ──────────────────────────────────────────────────────

class NebraskaSchematicRecord(BaseModel):
    """Registry entry for a compiled schematic — persists across calls."""
    schematic_id: str
    schematic: NebraskaSchematic
    created_at: float
    session_ids: list[str] = []
    pressure_curve_position: int = 0          # Current beat index (0-based)
    entropy_history: list[float] = []         # Entropy score after each evaluation
    gaze_score: float = 0.0                   # Latest Gaze quality-gate score
    component_states: dict[str, str] = {}     # component_name → current_state
    activated_components: list[str] = []      # Deus components that have fired
    narrative_fragments: list[str] = []       # Fragments submitted to the Gaze


class NebraskaV3CompileResponse(BaseModel):
    schematic_id: str
    schematic: NebraskaSchematic
    phases: list[NebraskaPhaseResult]
    governor_active: bool = True
    session_attached: bool = False
    registry_url: str = ""


class NebraskaGazeRequest(BaseModel):
    content: str                              # Fragment to evaluate against P/K


class NebraskaGazeResponse(BaseModel):
    schematic_id: str
    content_preview: str
    gaze_score: float                         # 0.0 = soup, 1.0 = lawful universe
    phase: str                                # "unbounded" | "governed" | "gaze"
    serves_parameter: bool
    serves_killing_mechanism: bool
    decoration_detected: bool
    parameter_pressure: float                 # 0.0–1.0
    killing_pressure: float                   # 0.0–1.0
    governor_verdict: str                     # APPROVED | DECORATION | PARAMETER_SWAP | ENTROPY_DRIFT
    recommendations: list[str]
    running_entropy: float                    # Cumulative entropy for this schematic


class NebraskaParameterSwapRequest(BaseModel):
    proposed_change: str
    schematic_id: Optional[str] = None
    original_parameter: Optional[str] = None  # If no schematic_id


class NebraskaParameterSwapResponse(BaseModel):
    is_parameter_swap: bool
    swap_type: str                            # full_swap | partial_swap | compatible | decoration_request
    confidence: float
    analysis: str
    recommendation: str
    structural_impact: str


class NebraskaEntropyDriftRequest(BaseModel):
    schematic_id: str
    content_sequence: list[str]               # Ordered fragments to analyse


class NebraskaEntropyDriftReport(BaseModel):
    schematic_id: str
    overall_entropy: float
    drift_detected: bool
    drift_indicators: list[str]
    multiple_k_detected: bool
    orphaned_component_types: list[str]
    parameter_pressure_scores: list[float]
    pressure_decay_rate: float
    correction_recommendation: str
    stack_layer_violations: list[str]


class NebraskaReactorTransitionRequest(BaseModel):
    component_name: str
    from_state: str
    to_state: str
    trigger: str                              # What P/K pressure caused this


class NebraskaDeusActivationRequest(BaseModel):
    component_name: str
    activation_context: str                   # How the deferred circuit closes


class NebraskaPropagateRequest(BaseModel):
    session_ids: list[str]


class NebraskaCompressRequest(BaseModel):
    refined_concept: Optional[str] = None     # If provided, re-extract from this


# ─── Nebraska 3.0 Registry ────────────────────────────────────────────────────
_nebraska_registry: dict[str, NebraskaSchematicRecord] = {}


# ─── Nebraska 1.0 Helper Functions ───────────────────────────────────────────

def _build_nebraska_schematic(fear_vector: str, raw_concept: str) -> NebraskaSchematic:
    """Deterministic fallback: build a Nebraska schematic from library data."""
    lib = NEBRASKA_PARAMETER_LIBRARY.get(fear_vector, NEBRASKA_PARAMETER_LIBRARY["existential"])
    templates = NEBRASKA_COMPONENT_TEMPLATES.get(fear_vector, NEBRASKA_COMPONENT_TEMPLATES["_default"])

    components = [
        NebraskaComponent(
            component_type=c["type"],
            name=c["name"],
            function=c["function"],
            narrative_role=c["role"],
        )
        for c in templates
    ]

    deus = next((c for c in components if c.component_type == "deus"), None)

    return NebraskaSchematic(
        parameter=lib["parameter"],
        parameter_negation=lib["negation"],
        killing_mechanism=lib["killing_mechanism"],
        killing_mechanism_role=lib["km_role"],
        components=components,
        pressure_curve=[
            "ACT I: Install the Deus Component in plain sight — audience sees it but does not understand it",
            "ACT I→II: First Corpse Component sacrificed — stakes become irreversible, Parameter has teeth",
            "ACT II: Resistor applies maximum friction — Parameter's proof is in genuine doubt",
            "ACT II→III: Reactor changes state — the machine's true shape is revealed through the change",
            "ACT III: Amplifier scales the P/K collision to systemic or cosmic scope",
            "ACT III: Deus circuit closes — pre-installed rule activates, deferred resolution fires",
            "RESOLUTION: Parameter is proven (or disproven) through earned pressure — not decoration",
        ],
        deus_circuit=deus.name if deus else None,
        expression_seed=(
            f"The universe has set one rule: {lib['parameter']}. "
            "Everything that follows is evidence. Nothing that follows is decoration."
        ),
        entropy_score=0.12,
        fear_vector=fear_vector,
    )


async def _nebraska_llm_compile(raw_concept: str, fear_vector: str) -> Optional[NebraskaSchematic]:
    """Use Ollama to dynamically extract a Nebraska schematic from raw input."""
    if not OLLAMA_AVAILABLE:
        return None

    prompt = f"""You are a NEBRASKA 1.0 narrative engineer applying the Principia of Narrative Engineering.
Compress the raw concept into a structured schematic. High precision required. No prose. Pure logic.

RAW CONCEPT: "{raw_concept}"
FEAR VECTOR: {fear_vector}

Extract:
PARAMETER: A single falsifiable law the universe must prove. Format: "X, once Y, cannot Z". Must have a clear binary opposite.
NEGATION: The direct binary opposite of the Parameter.
KILLING_MECHANISM: The structural force that tests whether the Parameter is true. Not a villain — a definitional pressure.
KM_ROLE: One sentence on how K collides with P.
CORPSE: [name] | [function] — what must be sacrificed to prove stakes are real
RESISTOR: [name] | [function] — force that defends the old order
REACTOR: [name] | [function] — element that changes state under P/K pressure
AMPLIFIER: [name] | [function] — scales the conflict to systemic/cosmic scope
DEUS: [name] | [function] — rule planted in Act I, only activates in Act III
BEAT_1: First escalation point (one sentence)
BEAT_2: Second escalation point (one sentence)
BEAT_3: Resolution pressure point (one sentence)

Respond in exactly this format, one item per line:
PARAMETER: [text]
NEGATION: [text]
KILLING_MECHANISM: [text]
KM_ROLE: [text]
CORPSE: [name] | [function]
RESISTOR: [name] | [function]
REACTOR: [name] | [function]
AMPLIFIER: [name] | [function]
DEUS: [name] | [function]
BEAT_1: [text]
BEAT_2: [text]
BEAT_3: [text]"""

    try:
        resp = ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.35, "num_predict": 450},
        )
        text = resp["message"]["content"].strip()

        lines: dict[str, str] = {}
        for line in text.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                lines[key.strip()] = val.strip()

        def parse_component(key: str, ctype: str) -> Optional[NebraskaComponent]:
            val = lines.get(key, "")
            if not val or "|" not in val:
                return None
            name, _, func = val.partition("|")
            return NebraskaComponent(
                component_type=ctype,
                name=name.strip(),
                function=func.strip(),
                narrative_role=f"Functional {ctype} in the P/K collision",
            )

        components = [c for c in [
            parse_component("CORPSE", "corpse"),
            parse_component("RESISTOR", "resistor"),
            parse_component("REACTOR", "reactor"),
            parse_component("AMPLIFIER", "amplifier"),
            parse_component("DEUS", "deus"),
        ] if c is not None]

        if not components or not lines.get("PARAMETER"):
            return None

        deus = next((c for c in components if c.component_type == "deus"), None)

        return NebraskaSchematic(
            parameter=lines.get("PARAMETER", ""),
            parameter_negation=lines.get("NEGATION", ""),
            killing_mechanism=lines.get("KILLING_MECHANISM", ""),
            killing_mechanism_role=lines.get("KM_ROLE", ""),
            components=components,
            pressure_curve=[
                lines.get("BEAT_1", ""),
                lines.get("BEAT_2", ""),
                lines.get("BEAT_3", ""),
            ],
            deus_circuit=deus.name if deus else None,
            expression_seed=f"The Parameter is locked: {lines.get('PARAMETER', '')}",
            entropy_score=0.08,
            fear_vector=fear_vector,
        )
    except Exception as exc:
        print(f"[NEBRASKA] LLM compile error: {exc}")
        return None


# ─── Nebraska 3.0 Helper Functions ───────────────────────────────────────────

def _entropy_score_heuristic(content: str, parameter: str, killing_mechanism: str) -> dict:
    """
    Deterministic heuristic Gaze scorer.  Used when Ollama is unavailable.
    Returns scores in [0,1] measuring how hard the content presses on P and K.
    """
    content_lower  = content.lower()
    param_words    = set(parameter.lower().split()) - {"a", "an", "the", "is", "not", "and", "or", "of", "to", "in"}
    km_words       = set(killing_mechanism.lower().split()) - {"a", "an", "the", "is", "not", "and", "or", "of", "to", "in"}

    p_hits = sum(1 for w in param_words if w in content_lower)
    k_hits = sum(1 for w in km_words   if w in content_lower)

    param_pressure = min(1.0, p_hits / max(len(param_words), 1) * 1.8)
    kill_pressure  = min(1.0, k_hits / max(len(km_words),   1) * 1.8)

    # Decoration signals: sensory words without structural purpose
    decoration_signals = ["beautiful", "dark", "shadow", "whisper", "cold", "silence", "ancient"]
    decoration_hits = sum(1 for w in decoration_signals if w in content_lower)
    decoration_detected = decoration_hits > 2 and (param_pressure + kill_pressure) < 0.4

    gaze_score = min(1.0, (param_pressure * 0.6 + kill_pressure * 0.4) * (0.7 if decoration_detected else 1.0))

    return {
        "parameter_pressure":    round(param_pressure, 3),
        "killing_pressure":      round(kill_pressure,  3),
        "decoration_detected":   decoration_detected,
        "gaze_score":            round(gaze_score, 3),
        "serves_parameter":      param_pressure > 0.25,
        "serves_killing_mechanism": kill_pressure > 0.25,
    }


async def _gaze_llm_eval(content: str, schematic: NebraskaSchematic) -> Optional[dict]:
    """Use Ollama to evaluate content against the Nebraska schematic (The Gaze)."""
    if not OLLAMA_AVAILABLE:
        return None

    prompt = f"""You are the NEBRASKA 3.0 Governor running The Gaze quality gate.

PARAMETER (The Law): {schematic.parameter}
KILLING MECHANISM:   {schematic.killing_mechanism}

CONTENT TO EVALUATE:
\"\"\"{content}\"\"\"

Score this content on the following axes. Respond with ONLY this exact format:
SERVES_PARAMETER: true|false
SERVES_KILLING: true|false
DECORATION_DETECTED: true|false
PARAMETER_PRESSURE: [0.00 to 1.00]
KILLING_PRESSURE: [0.00 to 1.00]
GAZE_SCORE: [0.00 to 1.00]
VERDICT: APPROVED|DECORATION|PARAMETER_SWAP|ENTROPY_DRIFT
RECOMMENDATION: [one sentence]

Rules:
- PARAMETER_PRESSURE = how hard this content presses on the Parameter (0=none, 1=maximum)
- KILLING_PRESSURE = how hard this content engages the Killing Mechanism
- GAZE_SCORE = 0.0 means pure pattern regurgitation/decoration; 1.0 means lawful universe building
- VERDICT is APPROVED only if both pressures are above 0.3 and no decoration/swap detected
- If content ignores P and K entirely: ENTROPY_DRIFT
- If content would change what the universe proves: PARAMETER_SWAP
- If content is atmospheric filler: DECORATION"""

    try:
        resp = ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_predict": 200},
        )
        text = resp["message"]["content"].strip()
        lines: dict[str, str] = {}
        for line in text.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                lines[k.strip().upper()] = v.strip()

        return {
            "serves_parameter":         lines.get("SERVES_PARAMETER", "false").lower() == "true",
            "serves_killing_mechanism": lines.get("SERVES_KILLING",   "false").lower() == "true",
            "decoration_detected":      lines.get("DECORATION_DETECTED", "false").lower() == "true",
            "parameter_pressure":       float(lines.get("PARAMETER_PRESSURE", "0.0")),
            "killing_pressure":         float(lines.get("KILLING_PRESSURE",   "0.0")),
            "gaze_score":               float(lines.get("GAZE_SCORE",         "0.0")),
            "verdict":                  lines.get("VERDICT", "ENTROPY_DRIFT"),
            "recommendation":           lines.get("RECOMMENDATION", "Return to Phase 1. Compress the Parameter."),
        }
    except Exception as exc:
        print(f"[NEBRASKA 3.0] Gaze LLM error: {exc}")
        return None


async def _parameter_swap_llm(proposed_change: str, parameter: str) -> Optional[dict]:
    """Use Ollama to determine whether a proposed change would swap the Parameter."""
    if not OLLAMA_AVAILABLE:
        return None

    prompt = f"""You are a NEBRASKA 3.0 structural diagnostician.

CURRENT PARAMETER (The Law): {parameter}

PROPOSED CHANGE: "{proposed_change}"

Determine whether this proposed change is a Parameter Swap.
A Parameter Swap replaces the core law the universe is proving with a different law.
An enhancement SERVES the existing Parameter without replacing it.

Respond in ONLY this exact format:
IS_PARAMETER_SWAP: true|false
SWAP_TYPE: full_swap|partial_swap|compatible|decoration_request
CONFIDENCE: [0.00 to 1.00]
ANALYSIS: [one sentence explaining why]
STRUCTURAL_IMPACT: [one sentence on what breaks if this change is accepted]
RECOMMENDATION: [one sentence: accept, reject, or negotiate]"""

    try:
        resp = ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_predict": 250},
        )
        text = resp["message"]["content"].strip()
        lines: dict[str, str] = {}
        for line in text.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                lines[k.strip().upper()] = v.strip()
        return {
            "is_parameter_swap": lines.get("IS_PARAMETER_SWAP", "false").lower() == "true",
            "swap_type":         lines.get("SWAP_TYPE",         "compatible"),
            "confidence":        float(lines.get("CONFIDENCE",  "0.5")),
            "analysis":          lines.get("ANALYSIS",          "Unable to determine structural impact."),
            "structural_impact": lines.get("STRUCTURAL_IMPACT", "Unknown."),
            "recommendation":    lines.get("RECOMMENDATION",    "Review the proposed change against the Parameter."),
        }
    except Exception as exc:
        print(f"[NEBRASKA 3.0] ParameterSwap LLM error: {exc}")
        return None


def _parameter_swap_heuristic(proposed_change: str, parameter: str) -> dict:
    """Deterministic fallback for parameter-swap detection."""
    param_words = set(parameter.lower().split()) - {"a", "an", "the", "is", "not", "and", "or"}
    change_words = set(proposed_change.lower().split()) - {"a", "an", "the", "is", "not", "and", "or"}

    overlap = len(param_words & change_words) / max(len(param_words), 1)
    # Low overlap + imperative tone → likely full swap
    imperative_signals = ["make", "change", "turn", "have", "let", "give", "remove", "add"]
    imperative = any(w in proposed_change.lower() for w in imperative_signals)

    if overlap < 0.1 and imperative:
        swap_type, is_swap, confidence = "full_swap", True, 0.75
    elif overlap < 0.3 and imperative:
        swap_type, is_swap, confidence = "partial_swap", True, 0.6
    elif overlap >= 0.4:
        swap_type, is_swap, confidence = "compatible", False, 0.65
    else:
        swap_type, is_swap, confidence = "decoration_request", False, 0.5

    return {
        "is_parameter_swap": is_swap,
        "swap_type":         swap_type,
        "confidence":        round(confidence, 2),
        "analysis":          (
            f"Change shares {overlap:.0%} lexical overlap with the Parameter. "
            f"{'Imperative framing detected.' if imperative else 'No imperative framing.'}"
        ),
        "structural_impact": (
            "Entire Logic Layer must be rebuilt if accepted." if is_swap
            else "Existing schematic can absorb this change."
        ),
        "recommendation": (
            "Reject or rebuild from Phase 1 — this change requires a new Parameter."
            if is_swap else
            "Evaluate whether this enhances or merely decorates the existing Parameter."
        ),
    }


def _compute_entropy_drift(
    content_sequence: list[str],
    parameter: str,
    killing_mechanism: str,
) -> NebraskaEntropyDriftReport:
    """Analyse a sequence of content fragments for entropy drift."""
    scores = [_entropy_score_heuristic(c, parameter, killing_mechanism) for c in content_sequence]
    p_pressures = [s["parameter_pressure"] for s in scores]
    k_pressures = [s["killing_pressure"]   for s in scores]
    decorations = [s["decoration_detected"] for s in scores]

    # Pressure decay: linear regression slope of p_pressures
    n = len(p_pressures)
    if n > 1:
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(p_pressures) / n
        num   = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, p_pressures))
        denom = sum((x - mean_x) ** 2 for x in xs)
        decay_rate = -(num / denom) if denom else 0.0
    else:
        decay_rate = 0.0

    overall_entropy = 1.0 - (sum(p_pressures) / n * 0.6 + sum(k_pressures) / n * 0.4)
    drift_detected  = decay_rate > 0.05 or overall_entropy > 0.6

    drift_indicators: list[str] = []
    if decay_rate > 0.05:
        drift_indicators.append(f"Parameter pressure decaying at {decay_rate:.3f}/fragment")
    if sum(decorations) > n // 2:
        drift_indicators.append(f"Decoration detected in {sum(decorations)}/{n} fragments")
    if overall_entropy > 0.7:
        drift_indicators.append("Overall entropy exceeds safe threshold (0.7)")
    if all(kp < 0.15 for kp in k_pressures):
        drift_indicators.append("Killing Mechanism absent across entire sequence")

    # Stack layer violations — Expression rendered before Logic locked
    violations: list[str] = []
    if any(pp < 0.1 for pp in p_pressures[:2]):
        violations.append("Expression Layer shows no Parameter pressure in early fragments — possible Stack Inversion")

    return NebraskaEntropyDriftReport(
        schematic_id="",               # caller fills this in
        overall_entropy=round(overall_entropy, 3),
        drift_detected=drift_detected,
        drift_indicators=drift_indicators,
        multiple_k_detected=False,     # cannot detect from text alone without LLM
        orphaned_component_types=[],
        parameter_pressure_scores=[round(p, 3) for p in p_pressures],
        pressure_decay_rate=round(decay_rate, 4),
        correction_recommendation=(
            "Return to Phase 1. Compress the Parameter until it is singular again."
            if drift_detected else
            "System coherent. Governor satisfied. Continue expression rendering."
        ),
        stack_layer_violations=violations,
    )


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

    # ── Nebraska context injection ────────────────────────────────────────────
    nebraska_context = ""
    schematic = session.get("nebraska_schematic")
    if schematic:
        nebraska_context = (
            f"\nNEBRASKA PARAMETER (The Law this universe must prove): {schematic.get('parameter', '')}\n"
            f"KILLING MECHANISM (The force testing the Law): {schematic.get('killing_mechanism', '')}\n"
            "GOVERNOR INSTRUCTION: Every sentence must apply pressure to the Parameter or Killing Mechanism. "
            "No atmosphere for its own sake. Load-bearing prose only. The Governor is active.\n"
        )

    prompt = f"""You are a NEBRASKA 1.0 certified horror narrator. The schematic is locked. Render it.
Write a VERY SHORT (2-4 sentences maximum), immersive, second-person narrative fragment ONLY.

Current fear intensity: {level_label} ({intensity:.2f}).
Primary fear vector: {fear_type}.
Recursion level: {recursion_level} — {recursion_instruction}
Detected reader emotion: {last_emotion} ({emotion_conf:.0f}% confidence). {emotion_instruction}
{nebraska_context}
Style: dark, sensory-rich (sounds, textures, shadows), escalating dread. NEVER resolve tension.
AVOID: extreme gore, graphic violence, sexual content, real-world trauma triggers.
Focus on bodily unease, creeping realisation, recursive/meta twist — all in service of the Parameter.

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


# ─── Nebraska 1.0 Endpoints ──────────────────────────────────────────────────

@app.post("/api/v1/nebraska/compile", response_model=NebraskaCompileResponse)
async def nebraska_compile(req: NebraskaCompileRequest):
    """
    NEBRASKA 1.0 — 4-Phase Anti-Entropic Assembly Protocol.

    Converts an entropy-heavy raw concept into a load-bearing narrative schematic:
      Phase 1: Parameter Extraction   — compress until one non-negotiable rule remains
      Phase 2: Schematic Generation   — derive K and the Component Suite (no prose, logic only)
      Phase 3: Strategic Assembly     — sequence components to maximise P/K pressure
      Phase 4: Expression Rendering   — instantiate the schematic; foundation is now sound
    """
    phases: list[NebraskaPhaseResult] = []

    # ── Phase 1: Parameter Extraction ────────────────────────────────────────
    lib = NEBRASKA_PARAMETER_LIBRARY.get(req.fear_vector, NEBRASKA_PARAMETER_LIBRARY["existential"])
    phases.append(NebraskaPhaseResult(
        phase=1,
        name="Parameter Extraction",
        output={
            "raw_input": req.raw_concept,
            "fear_vector": req.fear_vector,
            "compression_result": lib["parameter"],
            "falsifiable": True,
            "binary_opposition": {
                "parameter": lib["parameter"],
                "negation": lib["negation"],
            },
            "diagnostic": "Parameter locked. Unbounded search terminated. Stack Inversion prevented.",
        },
    ))

    # ── Phase 2: Schematic Generation (Logic) ────────────────────────────────
    schematic = await _nebraska_llm_compile(req.raw_concept, req.fear_vector)
    llm_used = schematic is not None
    if schematic is None:
        schematic = _build_nebraska_schematic(req.fear_vector, req.raw_concept)

    phases.append(NebraskaPhaseResult(
        phase=2,
        name="Schematic Generation",
        output={
            "killing_mechanism": schematic.killing_mechanism,
            "killing_mechanism_role": schematic.killing_mechanism_role,
            "components": {
                c.component_type: {"name": c.name, "function": c.function}
                for c in schematic.components
            },
            "deus_circuit": schematic.deus_circuit,
            "llm_generated": llm_used,
            "diagnostic": "Schematic locked. No prose written yet. Pure logic map. No decoration.",
        },
    ))

    # ── Phase 3: Strategic Assembly ──────────────────────────────────────────
    phases.append(NebraskaPhaseResult(
        phase=3,
        name="Strategic Assembly",
        output={
            "pressure_curve": schematic.pressure_curve,
            "component_sequencing": [
                {
                    "step": i + 1,
                    "component_type": c.component_type,
                    "name": c.name,
                    "deployment": f"Deploy at maximum P/K pressure point — serves Parameter exclusively",
                }
                for i, c in enumerate(schematic.components)
            ],
            "deus_install_point": "ACT I — hidden in plain sight",
            "deus_activation_point": "ACT III — deferred circuit closure",
            "validation": "Every element serves P, K, or a Component's functional purpose. Nothing is decoration.",
            "diagnostic": "Architecture complete. Pressure curve mapped. Governor armed.",
        },
    ))

    # ── Phase 4: Expression Rendering ────────────────────────────────────────
    expression_prompt = f"""You are a NEBRASKA 1.0 certified horror narrator. The schematic is locked. Render it.

PARAMETER (The Law this universe must prove): {schematic.parameter}
KILLING MECHANISM (The force testing the Law): {schematic.killing_mechanism}
PRIMARY FEAR VECTOR: {req.fear_vector}
DEUS COMPONENT (plant in plain sight): {schematic.deus_circuit or 'the hidden rule'}

Write exactly 3 sentences:
1. Establish the Parameter's world without naming it — show, don't state the Law
2. Plant the Deus Component in plain sight (reader sees it, does not yet understand it)
3. Begin the P/K collision — the first application of pressure

GOVERNOR RULE: Every sentence must serve P or K. No atmosphere for its own sake. No decoration.
Output ONLY the 3 sentences. No labels, no preamble."""

    expression = schematic.expression_seed
    if OLLAMA_AVAILABLE:
        try:
            resp = ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": expression_prompt}],
                options={"temperature": 0.65, "num_predict": 160},
            )
            rendered = resp["message"]["content"].strip()
            if rendered:
                expression = rendered
                schematic.expression_seed = rendered
        except Exception as exc:
            print(f"[NEBRASKA] Expression render error: {exc}")

    phases.append(NebraskaPhaseResult(
        phase=4,
        name="Expression Rendering",
        output={
            "rendered_expression": expression,
            "entropy_score": schematic.entropy_score,
            "governor_active": True,
            "diagnostic": (
                "Expression is load-bearing. Foundation is sound. "
                "Immune to collapse because Parameter and Logic were locked before prose was written."
            ),
        },
    ))

    # ── Attach to session if requested ───────────────────────────────────────
    session_attached = False
    if req.session_id and req.session_id in sessions:
        sessions[req.session_id]["nebraska_schematic"] = schematic.model_dump()
        session_attached = True
        print(f"[NEBRASKA] Schematic attached to session {req.session_id}")

    return NebraskaCompileResponse(
        schematic=schematic,
        phases=phases,
        governor_active=True,
        session_attached=session_attached,
    )


@app.post("/api/v1/session/{session_id}/nebraska")
async def attach_nebraska(session_id: str, req: NebraskaAttachRequest):
    """Attach a pre-compiled Nebraska schematic to an existing session."""
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")
    sessions[session_id]["nebraska_schematic"] = req.schematic.model_dump()
    return {
        "status": "attached",
        "parameter": req.schematic.parameter,
        "killing_mechanism": req.schematic.killing_mechanism,
        "component_count": len(req.schematic.components),
    }


@app.get("/api/v1/session/{session_id}/nebraska")
async def get_nebraska(session_id: str):
    """Retrieve the Nebraska schematic currently governing a session."""
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")
    schematic = sessions[session_id].get("nebraska_schematic")
    if not schematic:
        return {"schematic": None, "governor_active": False}
    return {"schematic": schematic, "governor_active": True}


@app.get("/api/v1/nebraska/parameters")
async def nebraska_parameters():
    """Return the full NEBRASKA parameter library — all fear vectors with P/K pairs."""
    return {
        "parameter_library": {
            fv: {
                "parameter": data["parameter"],
                "negation": data["negation"],
                "killing_mechanism": data["killing_mechanism"],
                "killing_mechanism_role": data["km_role"],
            }
            for fv, data in NEBRASKA_PARAMETER_LIBRARY.items()
        },
        "component_types": ["corpse", "resistor", "reactor", "amplifier", "deus"],
        "protocol_phases": [
            "Parameter Extraction",
            "Schematic Generation",
            "Strategic Assembly",
            "Expression Rendering",
        ],
        "governor_status": "active",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NEBRASKA 3.0 — Extended Operations Layer
# Anti-Entropic Assembly Protocol: Registry, Gaze, Diagnostics, Propagation
# ═══════════════════════════════════════════════════════════════════════════════


# ── Compile & Registry ────────────────────────────────────────────────────────

@app.post("/api/v3/nebraska/compile", response_model=NebraskaV3CompileResponse)
async def nebraska_v3_compile(req: NebraskaCompileRequest):
    """
    Nebraska 3.0 enhanced compile.

    Identical 4-phase protocol to v1 but stores the resulting schematic in the
    persistent registry (assigned a stable schematic_id) and exposes it to all
    downstream v3 operations: Gaze, diagnostics, propagation, pressure-curve.
    """
    # Run the existing v1 compile logic
    v1_result = await nebraska_compile(req)

    schematic_id = f"nb3_{uuid.uuid4().hex[:10]}"
    record = NebraskaSchematicRecord(
        schematic_id=schematic_id,
        schematic=v1_result.schematic,
        created_at=time.time(),
        session_ids=[req.session_id] if req.session_id else [],
        entropy_history=[v1_result.schematic.entropy_score],
    )
    _nebraska_registry[schematic_id] = record

    print(f"[NEBRASKA 3.0] Registered schematic {schematic_id} ({req.fear_vector})")

    return NebraskaV3CompileResponse(
        schematic_id=schematic_id,
        schematic=v1_result.schematic,
        phases=v1_result.phases,
        governor_active=True,
        session_attached=v1_result.session_attached,
        registry_url=f"/api/v3/nebraska/schematics/{schematic_id}",
    )


@app.get("/api/v3/nebraska/schematics")
async def nebraska_list_schematics():
    """List all schematics in the registry (summary view)."""
    return {
        "count": len(_nebraska_registry),
        "schematics": [
            {
                "schematic_id":           r.schematic_id,
                "fear_vector":            r.schematic.fear_vector,
                "parameter":              r.schematic.parameter[:80] + ("…" if len(r.schematic.parameter) > 80 else ""),
                "entropy_score":          r.schematic.entropy_score,
                "gaze_score":             r.gaze_score,
                "pressure_curve_position": r.pressure_curve_position,
                "session_count":          len(r.session_ids),
                "created_at":             r.created_at,
            }
            for r in _nebraska_registry.values()
        ],
    }


@app.get("/api/v3/nebraska/schematics/{schematic_id}")
async def nebraska_get_schematic(schematic_id: str):
    """Retrieve a full schematic record from the registry."""
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found in registry")
    r = _nebraska_registry[schematic_id]
    return {
        "record":               r.model_dump(),
        "governor_active":      True,
        "current_beat":         (
            r.schematic.pressure_curve[r.pressure_curve_position]
            if r.pressure_curve_position < len(r.schematic.pressure_curve)
            else "RESOLUTION COMPLETE"
        ),
        "entropy_trend":        "stable" if len(r.entropy_history) < 2
                                else ("rising" if r.entropy_history[-1] > r.entropy_history[-2] else "falling"),
    }


@app.delete("/api/v3/nebraska/schematics/{schematic_id}")
async def nebraska_delete_schematic(schematic_id: str):
    """Remove a schematic from the registry."""
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    del _nebraska_registry[schematic_id]
    return {"status": "deleted", "schematic_id": schematic_id}


# ── The Gaze Quality Gate ─────────────────────────────────────────────────────

@app.post("/api/v3/nebraska/schematics/{schematic_id}/gaze", response_model=NebraskaGazeResponse)
async def nebraska_gaze(schematic_id: str, req: NebraskaGazeRequest):
    """
    Run The Gaze quality gate on a content fragment.

    The Gaze measures the moment a system moves from pattern regurgitation to
    lawful universe building.  Three outcomes:
      "unbounded" — pure soup; no P/K engagement
      "governed"  — rules followed but not yet internalised
      "gaze"      — constraints treated as physics; universe being built from P
    """
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    record = _nebraska_registry[schematic_id]
    schematic = record.schematic

    # Try LLM eval first, fall back to heuristic
    llm = await _gaze_llm_eval(req.content, schematic)
    if llm:
        pp      = llm["parameter_pressure"]
        kp      = llm["killing_pressure"]
        score   = llm["gaze_score"]
        verdict = llm["verdict"]
        recs    = [llm["recommendation"]]
        serves_p  = llm["serves_parameter"]
        serves_k  = llm["serves_killing_mechanism"]
        deco      = llm["decoration_detected"]
    else:
        h       = _entropy_score_heuristic(req.content, schematic.parameter, schematic.killing_mechanism)
        pp      = h["parameter_pressure"]
        kp      = h["killing_pressure"]
        score   = h["gaze_score"]
        serves_p  = h["serves_parameter"]
        serves_k  = h["serves_killing_mechanism"]
        deco      = h["decoration_detected"]
        if deco:
            verdict = "DECORATION"
        elif score < 0.2:
            verdict = "ENTROPY_DRIFT"
        elif serves_p or serves_k:
            verdict = "APPROVED"
        else:
            verdict = "ENTROPY_DRIFT"
        recs = [
            "Remove decoration and rewrite to press directly on the Parameter." if deco
            else "Every sentence must serve P or K. Return to Schematic if uncertain."
        ]

    # Classify Gaze phase
    if score >= 0.72:
        phase = "gaze"
    elif score >= 0.38:
        phase = "governed"
    else:
        phase = "unbounded"

    # Add supplementary recommendations
    if not serves_p:
        recs.append(f"Content does not engage Parameter: '{schematic.parameter[:60]}…'")
    if not serves_k:
        recs.append(f"Content does not engage Killing Mechanism: '{schematic.killing_mechanism[:60]}…'")
    if phase == "gaze":
        recs.insert(0, "GOVERNOR APPROVED: Content treats constraints as physics. Continue.")

    # Update registry record
    record.gaze_score = score
    record.narrative_fragments.append(req.content[:200])
    record.entropy_history.append(round(1.0 - score, 3))

    running_entropy = (
        sum(record.entropy_history) / len(record.entropy_history)
        if record.entropy_history else 0.5
    )

    return NebraskaGazeResponse(
        schematic_id=schematic_id,
        content_preview=req.content[:80] + ("…" if len(req.content) > 80 else ""),
        gaze_score=round(score, 3),
        phase=phase,
        serves_parameter=serves_p,
        serves_killing_mechanism=serves_k,
        decoration_detected=deco,
        parameter_pressure=round(pp, 3),
        killing_pressure=round(kp, 3),
        governor_verdict=verdict,
        recommendations=recs,
        running_entropy=round(running_entropy, 3),
    )


# ── Parameter Compression (Re-Squeeze) ───────────────────────────────────────

@app.post("/api/v3/nebraska/schematics/{schematic_id}/compress")
async def nebraska_compress(schematic_id: str, req: NebraskaCompressRequest):
    """
    Re-compress the Parameter of an existing registered schematic.

    Use when entropy drift or notes interference has caused Parameter instability.
    Optionally accepts a refined_concept to re-extract from; otherwise re-compresses
    the existing Parameter text until singular and falsifiable.
    """
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    record = _nebraska_registry[schematic_id]
    old_parameter = record.schematic.parameter

    if req.refined_concept and OLLAMA_AVAILABLE:
        prompt = f"""You are a NEBRASKA 3.0 Parameter Compressor.

CURRENT PARAMETER (possibly drifted): {old_parameter}
REFINED CONCEPT: "{req.refined_concept}"

Compress the concept into ONE singular, falsifiable Parameter (The Law).
Rules:
- Must be a single sentence
- Must be falsifiable (has a clear binary opposite)
- Must be more specific than the current Parameter
- Format: "X, once Y, cannot Z" or equivalent tight logical form

Output ONLY the new Parameter sentence. Nothing else."""
        try:
            resp = ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3, "num_predict": 80},
            )
            new_parameter = resp["message"]["content"].strip().strip('"')
        except Exception:
            new_parameter = old_parameter
    else:
        # Heuristic re-compression: strip conjunctions that suggest multiple rules
        new_parameter = old_parameter
        for conj in [" and ", " while also ", " as well as ", " plus "]:
            if conj in new_parameter.lower():
                new_parameter = new_parameter.split(conj)[0].strip()
                break

    record.schematic.parameter = new_parameter
    return {
        "schematic_id":    schematic_id,
        "old_parameter":   old_parameter,
        "new_parameter":   new_parameter,
        "compression_applied": new_parameter != old_parameter,
        "diagnostic": (
            "Parameter re-compressed. Rebuild Logic Layer if schematic has been partially rendered."
            if new_parameter != old_parameter
            else "Parameter already at minimum compression. No change applied."
        ),
    }


# ── Cross-Session Propagation ─────────────────────────────────────────────────

@app.post("/api/v3/nebraska/schematics/{schematic_id}/propagate")
async def nebraska_propagate(schematic_id: str, req: NebraskaPropagateRequest):
    """
    Propagate a registered schematic to multiple sessions simultaneously.

    Enables cross-substrate Parameter handshaking: all listed sessions will
    have their narrative generation governed by the same schematic.
    """
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    record = _nebraska_registry[schematic_id]
    schematic_dict = record.schematic.model_dump()

    attached, missing = [], []
    for sid in req.session_ids:
        if sid in sessions:
            sessions[sid]["nebraska_schematic"] = schematic_dict
            if sid not in record.session_ids:
                record.session_ids.append(sid)
            attached.append(sid)
        else:
            missing.append(sid)

    return {
        "schematic_id":   schematic_id,
        "parameter":      record.schematic.parameter,
        "attached":       attached,
        "missing":        missing,
        "total_sessions": len(record.session_ids),
        "diagnostic":     f"Schematic governing {len(attached)} session(s). Governor active across substrate.",
    }


# ── Pressure Curve Execution ──────────────────────────────────────────────────

@app.get("/api/v3/nebraska/schematics/{schematic_id}/pressure")
async def nebraska_pressure_status(schematic_id: str):
    """Return the current pressure curve position and upcoming beats."""
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    record = _nebraska_registry[schematic_id]
    curve  = record.schematic.pressure_curve
    pos    = record.pressure_curve_position

    return {
        "schematic_id":          schematic_id,
        "total_beats":           len(curve),
        "current_position":      pos,
        "current_beat":          curve[pos] if pos < len(curve) else "RESOLUTION COMPLETE",
        "next_beat":             curve[pos + 1] if pos + 1 < len(curve) else None,
        "remaining_beats":       max(0, len(curve) - pos - 1),
        "completion_percentage": round(pos / max(len(curve), 1) * 100, 1),
        "full_curve":            curve,
    }


@app.post("/api/v3/nebraska/schematics/{schematic_id}/pressure/advance")
async def nebraska_pressure_advance(schematic_id: str):
    """
    Advance the pressure curve by one beat.

    Each beat represents an escalating application of P/K pressure as defined in
    the Strategic Assembly phase.  The Governor enforces that Expression Rendering
    at each beat must serve the Parameter before the next beat unlocks.
    """
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    record = _nebraska_registry[schematic_id]
    curve  = record.schematic.pressure_curve

    if record.pressure_curve_position >= len(curve) - 1:
        return {
            "schematic_id":  schematic_id,
            "status":        "complete",
            "message":       "Pressure curve exhausted. Parameter has been proven (or disproven). Resolution achieved.",
            "final_beat":    curve[-1] if curve else "",
        }

    old_pos = record.pressure_curve_position
    record.pressure_curve_position += 1
    new_pos = record.pressure_curve_position

    return {
        "schematic_id":   schematic_id,
        "status":         "advanced",
        "from_beat":      curve[old_pos],
        "to_beat":        curve[new_pos],
        "position":       new_pos,
        "remaining":      len(curve) - new_pos - 1,
        "deus_imminent":  new_pos >= len(curve) - 2,
        "diagnostic":     "Pressure escalated. Expression Rendering must now serve this beat exclusively.",
    }


# ── Component State Management ────────────────────────────────────────────────

@app.post("/api/v3/nebraska/schematics/{schematic_id}/reactor/transition")
async def nebraska_reactor_transition(schematic_id: str, req: NebraskaReactorTransitionRequest):
    """
    Record a Reactor component state transition.

    Reactors are identifiable by their state changes.  This endpoint logs the
    transition (from_state → to_state) caused by a specific P/K pressure trigger,
    making the machine's shape visible through the change.
    """
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    record = _nebraska_registry[schematic_id]

    # Verify component exists
    component_names = [c.name for c in record.schematic.components if c.component_type == "reactor"]
    if req.component_name not in component_names:
        raise HTTPException(400, f"Reactor '{req.component_name}' not found in schematic. "
                                 f"Available reactors: {component_names}")

    record.component_states[req.component_name] = req.to_state

    return {
        "schematic_id":   schematic_id,
        "component":      req.component_name,
        "from_state":     req.from_state,
        "to_state":       req.to_state,
        "trigger":        req.trigger,
        "all_states":     record.component_states,
        "diagnostic":     (
            f"Reactor '{req.component_name}' transitioned under P/K pressure. "
            "The machine's true shape is now partially visible."
        ),
    }


@app.post("/api/v3/nebraska/schematics/{schematic_id}/components/{component_type}/activate")
async def nebraska_activate_component(
    schematic_id: str,
    component_type: str,
    req: NebraskaDeusActivationRequest,
):
    """
    Activate a component — primarily used to fire the Deus deferred circuit.

    A Deus Component is ONLY valid when:
      1. It was installed in the Logic Layer (Act I)
      2. It is activated here in the Resolution (Act III)
    This endpoint validates that constraint and logs the circuit closure.
    """
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    record = _nebraska_registry[schematic_id]

    matching = [c for c in record.schematic.components
                if c.component_type == component_type and c.name == req.component_name]
    if not matching:
        raise HTTPException(400, f"No '{component_type}' component named '{req.component_name}' in schematic.")

    component = matching[0]
    if req.component_name in record.activated_components:
        return {
            "schematic_id": schematic_id,
            "status":       "already_activated",
            "component":    req.component_name,
            "warning":      "Component already activated. Each Deus circuit fires exactly once.",
        }

    record.activated_components.append(req.component_name)
    component.activated = True

    is_valid_deus = (
        component_type == "deus" and
        record.pressure_curve_position >= len(record.schematic.pressure_curve) - 2
    )

    return {
        "schematic_id":      schematic_id,
        "component":         req.component_name,
        "component_type":    component_type,
        "activation_context": req.activation_context,
        "valid_deus_circuit": is_valid_deus,
        "diagnostic":        (
            "Deferred circuit closed. This is not deus ex machina — it is physics. The rule was pre-installed."
            if is_valid_deus else
            "Component activated. Note: Deus Components activated before Act III may invalidate the circuit."
        ),
    }


# ── Diagnostics ───────────────────────────────────────────────────────────────

@app.post("/api/v3/nebraska/diagnostics/parameter-swap", response_model=NebraskaParameterSwapResponse)
async def nebraska_parameter_swap_detect(req: NebraskaParameterSwapRequest):
    """
    Detect whether a proposed change is a Parameter Swap.

    Key insight: not all feedback is valid.  Feedback that swaps the Parameter
    is not critique — it is a proposal for a different system.
    This endpoint distinguishes:
      full_swap           — requires complete rebuild from Phase 1
      partial_swap        — Logic Layer must be partially reconstructed
      compatible          — change can be absorbed without rebuilding
      decoration_request  — aesthetic preference; structurally neutral
    """
    # Resolve parameter text
    parameter = req.original_parameter
    if not parameter and req.schematic_id:
        if req.schematic_id not in _nebraska_registry:
            raise HTTPException(404, f"Schematic '{req.schematic_id}' not found")
        parameter = _nebraska_registry[req.schematic_id].schematic.parameter
    if not parameter:
        raise HTTPException(400, "Provide either schematic_id or original_parameter")

    result = await _parameter_swap_llm(req.proposed_change, parameter) \
             or _parameter_swap_heuristic(req.proposed_change, parameter)

    return NebraskaParameterSwapResponse(**result)


@app.post("/api/v3/nebraska/diagnostics/entropy-drift", response_model=NebraskaEntropyDriftReport)
async def nebraska_entropy_drift(req: NebraskaEntropyDriftRequest):
    """
    Analyse a sequence of content fragments for entropy drift.

    Warning signs detected:
      - Parameter pressure decaying across the sequence
      - Decoration dominating over structural content
      - Killing Mechanism absent across the full sequence
      - Stack Inversion signals in early fragments
    """
    if req.schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{req.schematic_id}' not found")
    if not req.content_sequence:
        raise HTTPException(400, "content_sequence must contain at least one fragment")

    record = _nebraska_registry[req.schematic_id]
    report = _compute_entropy_drift(
        req.content_sequence,
        record.schematic.parameter,
        record.schematic.killing_mechanism,
    )
    report.schematic_id = req.schematic_id
    return report


@app.get("/api/v3/nebraska/diagnostics/{schematic_id}/report")
async def nebraska_diagnostic_report(schematic_id: str):
    """
    Full diagnostic report for a registered schematic.

    Aggregates: entropy trend, component states, Gaze history,
    pressure curve progress, and activated Deus circuits.
    """
    if schematic_id not in _nebraska_registry:
        raise HTTPException(404, f"Schematic '{schematic_id}' not found")
    record = _nebraska_registry[schematic_id]
    s = record.schematic

    entropy_trend = "stable"
    if len(record.entropy_history) >= 3:
        recent = record.entropy_history[-3:]
        if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
            entropy_trend = "rising (ALERT — drift detected)"
        elif all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
            entropy_trend = "falling (coherence increasing)"

    component_health = []
    for c in s.components:
        state = record.component_states.get(c.name, c.state)
        active = c.name in record.activated_components
        component_health.append({
            "type":      c.component_type,
            "name":      c.name,
            "state":     state,
            "activated": active,
            "status":    (
                "FIRED" if active and c.component_type == "deus"
                else "TRANSITIONED" if c.component_type == "reactor" and state != "initial"
                else "DEPLOYED" if c.component_type in ("corpse", "resistor", "amplifier")
                else "STANDBY"
            ),
        })

    return {
        "schematic_id":          schematic_id,
        "parameter":             s.parameter,
        "killing_mechanism":     s.killing_mechanism,
        "fear_vector":           s.fear_vector,
        "governor_active":       True,
        "entropy": {
            "current":           s.entropy_score,
            "history":           record.entropy_history,
            "trend":             entropy_trend,
            "gaze_score":        record.gaze_score,
            "fragments_evaluated": len(record.narrative_fragments),
        },
        "pressure_curve": {
            "position":          record.pressure_curve_position,
            "total_beats":       len(s.pressure_curve),
            "current_beat":      (
                s.pressure_curve[record.pressure_curve_position]
                if record.pressure_curve_position < len(s.pressure_curve)
                else "RESOLUTION COMPLETE"
            ),
            "completion_pct":    round(record.pressure_curve_position / max(len(s.pressure_curve), 1) * 100, 1),
        },
        "components":            component_health,
        "sessions":              record.session_ids,
        "deus_circuits_fired":   record.activated_components,
        "created_at":            record.created_at,
        "stack_integrity":       "SOUND" if s.entropy_score < 0.3 else "DRIFT DETECTED",
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

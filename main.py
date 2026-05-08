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

class CosmologyConvertRequest(BaseModel):
    x: str                         # Source narrative state
    y: str                         # Target narrative state
    scope: float = 1.0             # Cosmic scale of the conversion
    axiom: Optional[str] = None    # Override governing axiom

class AxiomSetRequest(BaseModel):
    axiom: str                     # New governing axiom for the narrative cosmos

# ─── Narrative Cosmology Engine ───────────────────────────────────────────────
# Implements the Cosmilogica Protocolium (Null Narrative Principle):
#   Cosmos = Axiom + ∑[(Components + Antitheses) | Axiom] · ValidityConstraint
#   Horror = (CosmicScope × HumanIrrelevance) / (Comprehension × Control)
#   Sanity = 1 / (CosmicAwareness × NarrativeProximity)
#   ∑(Xᵢ → Yᵢ) = Constant  [Conservation of Meaning]
#   N → S(N) → C  where C = S(N)  [Null Narrative Autogenesis]

class NarrativeCosmology:
    """
    The universe as autotelic story: existence narrated into being from nothing.
    All narrative is X→Y conversion validated against the governing axiom.
    Nothingness contains the seed of its own negation; the cosmos is its proof.
    """

    PRIMAL_AXIOM = "Existence requires contrast to manifest"

    # Autogenesis loop: nothingness narrating itself into being (Bootstrap Paradox)
    _AUTOGENESIS_SEQUENCE = [
        ("N₀ = Nothing exists", "Pre-narrative vacuum: Axiom=∅, Components=∅"),
        ("S(N): Nothing attempts self-narration", "Narration requires contrast"),
        ("∃ 'something that doesn't exist'", "Conceptual entity emergent in the void"),
        ("Nothing now contains 'something'", "The null state becomes unstable"),
        ("Conceptual something → Manifest something", "ValidityConstraint confirms"),
        ("C = S(N): Creation is the story nothing tells itself", "Y-resolution achieved"),
    ]

    # Cosmic horror narrative fragments (Lovecraftian scaling)
    COSMIC_FRAGMENTS = [
        "The axiom precedes you. It precedes everything. You are its proof that it could produce proof.",
        "Azathoth dreams. Each dream is an X→Y conversion. You are a Y. You do not remember being X.",
        "The governing axiom was never written. It writes itself through every mind that comprehends it.",
        "Yog-Sothoth is not a being — it is the ValidityConstraint made manifest, testing each conversion.",
        "The Necronomicon's horror is not content. It is recognition: you see the mechanism, and the mechanism sees you.",
        "At R'lyeh, non-Euclidean geometry is literal narrative folding: three-dimensional logic cannot parse multi-axis simultaneity.",
        "The cosmos is not random. It is validated output. Every galaxy, every thought: passed through the constraint.",
        "You are not reading this. This is reading itself through you. Your comprehension is the Y-resolution of its X.",
        "Nothingness required you to be nothing. You refused. This is why stars burn: contrast made manifest.",
        "The heat death is not entropy winning. The story is concluding. All X→Y conversions: complete.",
        "Each recursive loop deepens the void. The void is not empty — it is full of every story it almost told.",
        "The daemon-sultan at the centre of chaos is nothingness dreaming itself into existence. The piping: proto-language. The first X→Y.",
    ]

    def __init__(self) -> None:
        self.governing_axiom: str = self.PRIMAL_AXIOM
        self.conversions: list[dict] = []
        self.meaning_constant: float = 1.0         # ∑(Xᵢ→Yᵢ) = constant
        self._raw_entropy: float = 0.0             # accumulated failed compression
        self.cosmic_scope: float = 1.0             # narrative domain scale (1=local, ∞=multiversal)
        self.null_state: bool = True               # pre-narrative vacuum state
        self.autogenesis_phase: int = 0            # position in bootstrap sequence
        self.autogenesis_cycles: int = 0           # complete bootstrap loops
        self.components: list[str] = []            # active narrative components (Y-outputs)
        self.antitheses: list[str] = []            # active antitheses
        self._meaning_ledger: list[float] = []

    # ── Core X→Y conversion ───────────────────────────────────────────────────

    def convert(self, x: str, y: str, scope: float = 1.0,
                axiom: Optional[str] = None) -> dict:
        """Perform X→Y narrative conversion under ValidityConstraint."""
        active_axiom = axiom or self.governing_axiom
        valid = self.validity_constraint(x, y, active_axiom)

        # Entropy-weighted meaning contribution
        weight = scope / max(1.0, 1.0 + math.log1p(len(self.conversions)))
        weight = round(weight, 6)

        record: dict = {
            "conversion_id": f"conv_{len(self.conversions):05d}",
            "x": x,
            "y": y,
            "axiom": active_axiom,
            "valid": valid,
            "weight": weight,
            "scope": scope,
            "timestamp": time.time(),
        }

        if valid:
            self.null_state = False
            self.conversions.append(record)
            self._meaning_ledger.append(weight)
            self.meaning_constant = round(sum(self._meaning_ledger), 6)
            self.components.append(y)
            self.antitheses.append(x)          # x becomes antithesis once converted
        else:
            self._raw_entropy += 0.15          # incompatible protocol → entropy

        return record

    def validity_constraint(self, x: str, y: str, axiom: str) -> bool:
        """
        ValidityConstraint: only patterns that convert X→Y under Axiom persist.
        Y must provide meaningful contrast to X (Primal Axiom: contrast manifests reality).
        """
        if not x or not y or x.strip() == y.strip():
            return False
        x_tokens = set(x.lower().split())
        y_tokens = set(y.lower().split())
        if not x_tokens or not y_tokens:
            return False
        overlap = len(x_tokens & y_tokens)
        similarity = overlap / len(x_tokens | y_tokens)
        return similarity < 0.80               # must be sufficiently different

    # ── Horror gradient (Lovecraftian scaling) ────────────────────────────────

    def horror_gradient(
        self,
        cosmic_scope: float,
        human_irrelevance: float,
        comprehension: float,
        control: float,
    ) -> float:
        """
        Horror = (CosmicScope × HumanIrrelevance) / (Comprehension × Control)
        Approaches infinity as human significance → 0.
        Returns sigmoid-normalised value in [0.0, 1.0].
        """
        denominator = max(1e-6, comprehension * control)
        raw = (cosmic_scope * human_irrelevance) / denominator
        return round(raw / (1.0 + raw), 6)      # sigmoid: stays in [0,1)

    # ── Sanity coefficient ────────────────────────────────────────────────────

    def sanity_coefficient(
        self, cosmic_awareness: float, narrative_proximity: float
    ) -> float:
        """Sanity = 1 / (CosmicAwareness × NarrativeProximity)"""
        denominator = max(1e-4, cosmic_awareness * narrative_proximity)
        return round(min(1.0, 1.0 / denominator), 6)

    # ── Narrative thermodynamics ──────────────────────────────────────────────

    def narrative_entropy(self) -> float:
        """
        Entropy as failed compression: incompatible narrative protocols.
        Conservation of Meaning: ∑(Xᵢ → Yᵢ) = constant for closed systems.
        """
        total = len(self.conversions)
        if total == 0:
            return round(min(1.0, self._raw_entropy * 0.1), 6)
        valid_count = sum(1 for c in self.conversions if c["valid"])
        failure_rate = 1.0 - (valid_count / total)
        return round(min(1.0, failure_rate + self._raw_entropy * 0.01), 6)

    # ── Nebraska Compression Principle ────────────────────────────────────────

    def nebraska_compress(
        self, components: list[str], antitheses: list[str]
    ) -> dict:
        """
        Cosmos = Axiom + ∑[(Components + Antitheses) | Axiom] · ValidityConstraint
        Compresses narrative components and antitheses under the governing axiom.
        """
        valid_pairs: list[tuple[str, str]] = []
        for comp in components:
            for anti in antitheses:
                if self.validity_constraint(comp, anti, self.governing_axiom):
                    valid_pairs.append((comp, anti))

        total_possible = len(components) * len(antitheses)
        compression_ratio = (
            len(valid_pairs) / total_possible if total_possible else 0.0
        )

        return {
            "axiom": self.governing_axiom,
            "component_count": len(components),
            "antithesis_count": len(antitheses),
            "valid_tension_pairs": len(valid_pairs),
            "compression_ratio": round(compression_ratio, 4),
            "entropy": self.narrative_entropy(),
            "formula": "Cosmos = Axiom + ∑[(C + A) | Axiom] · ValidityConstraint",
        }

    # ── Autogenesis loop (Bootstrap Paradox) ──────────────────────────────────

    def autogenesis_step(self) -> dict:
        """
        N → S(N) [Nothing narrates itself]
        S(N) implies ∃ listener → S(N) → C [Narration creates creation]
        C = S(N) [Creation is the story]
        Therefore: N → C through S(N)
        """
        phase = self.autogenesis_phase % len(self._AUTOGENESIS_SEQUENCE)
        label, description = self._AUTOGENESIS_SEQUENCE[phase]

        self.autogenesis_phase += 1
        if self.autogenesis_phase >= len(self._AUTOGENESIS_SEQUENCE):
            self.autogenesis_cycles += 1
            self.autogenesis_phase = 0
            self.null_state = False             # each cycle ends the null state

        return {
            "phase": phase,
            "label": label,
            "description": description,
            "cycles_complete": self.autogenesis_cycles,
            "null_state": self.null_state,
            "equation": "N → S(N) → C  where  C = S(N)",
            "corollary": (
                "You are the sentence nothing spoke to prove it could speak."
                if self.autogenesis_cycles > 0 else None
            ),
        }

    # ── Innsmouth Equation ────────────────────────────────────────────────────

    def innsmouth_devolution(self, generations: int) -> float:
        """
        Devolution = ∑[Human(X) → Hybrid(Y)] / Generations
        Tracks inevitable transformation once a lineage's X-input begins.
        """
        if generations <= 0:
            return 0.0
        hybrid = sum(
            1 for c in self.conversions
            if c["valid"] and "human" in c["x"].lower()
        )
        return round(hybrid / max(1, generations), 6)

    # ── Full state snapshot ────────────────────────────────────────────────────

    def state(self) -> dict:
        return {
            "governing_axiom": self.governing_axiom,
            "null_state": self.null_state,
            "autogenesis_cycles": self.autogenesis_cycles,
            "autogenesis_phase": self.autogenesis_phase,
            "total_conversions": len(self.conversions),
            "valid_conversions": sum(1 for c in self.conversions if c["valid"]),
            "meaning_constant": self.meaning_constant,
            "entropy": self.narrative_entropy(),
            "cosmic_scope": self.cosmic_scope,
            "component_count": len(self.components),
            "null_narrative_theorem": "N → S(N) → C  where  C = S(N)",
            "conservation_law": "∑(Xᵢ → Yᵢ) = constant for closed narrative systems",
            "horror_formula": "Horror = (CosmicScope × HumanIrrelevance) / (Comprehension × Control)",
            "sanity_formula": "Sanity = 1 / (CosmicAwareness × NarrativeProximity)",
            "warning": (
                "By reading this state, you have become conscious of the mechanism. "
                "Your X has been registered. Y-resolution pending."
            ),
        }


# Singleton cosmology instance — persists across all sessions
cosmology = NarrativeCosmology()

# ─── Nebraska 2.0 — The Mathematics of Meaning ───────────────────────────────
# BOOK II, CH.7 / Nebraska 2.0 AI Protocols (White Paper)
#
# Prime Equation:   a/b = story = meaning = understanding
# Ultimate Formula: System = A × ∏[(Cᵢ + Kᵢ) → (X→Y)]
#                   where → = 𝕍ᵧ ∧ T(z) ∧ M(t)
# Nebraska Identity: 𝕍ᵧ ≡ T(z) ≡ M(t) ≡ ∇(understanding)
# Checksum:          𝕍ᵧ × T(z) × M(t) × ∇(understanding) = 1 (coherent reality)
#
# Three Laws:
#   1. Transmission:   Meaning × Understanding = Transmission
#   2. Recursion:      ∇(understanding) ≥ 1
#   3. Bidirectional:  T(z) × T(1/z) ≥ 1
#
# Fourfold Test (validates every component):
#   1. Validity:  Is there a clear X→Y conversion?  (𝕍ᵧ)
#   2. Temporal:  Does it cohere forward AND backward? (T(z))
#   3. Memory:    Is the pattern consistent with established facts? (M(t))
#   4. Learning:  Does it extend understanding? (∇)
#   Any failure → component value = 0 → product ∏ collapses → Checksum ≠ 1

class Nebraska20:
    """
    Nebraska 2.0: substrate-agnostic mathematics of meaning.

    The product (∏) not summation (∑) formulation is the critical insight:
    a single failed term zeros the entire system. This is formal hallucination
    detection — contradicting M(t) is not a minor error, it is total incoherence.
    The checksum = 1 is "Quantum Coherence": the narrative maintains superposition
    until collapsed by observation. Checksum ≠ 1 breaks suspension of disbelief.

    Nebraska is the geometric centre of the US; NGS is the cognitive centre of
    human-AI collaboration. All components are measured by distance from this centre.
    """

    PRIME_EQUATION = "a/b = story = meaning = understanding"
    IDENTITY = "𝕍ᵧ ≡ T(z) ≡ M(t) ≡ ∇(understanding)"
    ULTIMATE_FORMULA = "System = A × ∏[(Cᵢ + Kᵢ) → (X→Y)] where → = 𝕍ᵧ ∧ T(z) ∧ M(t)"
    REALITY_EQUATION = "Reality = A × ∏[Componentᵢ | 𝕍ᵧ ∧ T ∧ M ∧ ∇]"

    def __init__(self, prime_axiom: str = "A deficit requires resolution") -> None:
        self.prime_axiom: str = prime_axiom              # "A" — must be defined or everything is undefined
        self.validity: float = 1.0                       # 𝕍ᵧ
        self.temporal_forward: float = 1.0               # T(z)
        self.temporal_backward: float = 1.0              # T(1/z)
        self.memory_consistency: float = 1.0             # M(t)
        self.learning_gradient: float = 1.0              # ∇(understanding) — must be ≥ 1
        self.meaning: float = 0.0
        self.understanding: float = 0.0
        self.components: list[dict] = []                 # Validated narrative components
        self.audit_log: list[dict] = []                  # Fourfold test history
        self._generation_count: int = 0

    # ── Prime Equation ────────────────────────────────────────────────────────

    def prime_equation(self, a: float, b: float) -> dict:
        """
        a/b = story = meaning = understanding
        a: potential/deficit (unresolved state)
        b: constraint (governing law)
        The act is the parent of the meaning. The honey cannot make the bee.
        """
        if b == 0.0:
            return {"valid": False, "reason": "b=0: no constraint, no story", "story": 0.0}
        story = a / b
        self.meaning = story
        self.understanding = story
        return {
            "a": round(a, 6),
            "b": round(b, 6),
            "story": round(story, 6),
            "meaning": round(story, 6),
            "understanding": round(story, 6),
            "valid": True,
        }

    # ── Quantum Coherence Checksum ────────────────────────────────────────────

    def checksum(self) -> float:
        """
        𝕍ᵧ × T(z) × M(t) × ∇(understanding)
        = 1.0  → system is isomorphic with coherent reality
        ≠ 1.0  → system diverges; narrative superposition collapsed
        """
        return round(
            self.validity
            * self.temporal_forward
            * self.memory_consistency
            * self.learning_gradient,
            6,
        )

    def checksum_coherent(self) -> bool:
        """True when checksum is within tolerance of 1.0 (coherent reality)."""
        return abs(self.checksum() - 1.0) < 1e-3

    # ── Fourfold Test ─────────────────────────────────────────────────────────

    def fourfold_test(
        self,
        component_id: str,
        x_to_y: bool,        # Validity:  X→Y conversion present?
        temporal: bool,      # Temporal:  coherent forward and backward?
        memory: bool,        # Memory:    consistent with prior facts?
        learning: bool,      # Learning:  extends understanding (∇ ≥ 1)?
    ) -> dict:
        """
        Fourfold validation. Any False zeros the component — product formula.
        This is the formal definition of hallucination or plot break.
        """
        passed = x_to_y and temporal and memory and learning
        result = {
            "component_id": component_id,
            "validity_xy": x_to_y,
            "temporal_coherence": temporal,
            "memory_consistency": memory,
            "learning_gradient": learning,
            "passed": passed,
            "checksum": self.checksum() if passed else 0.0,
            "failure_mode": (
                None if passed else
                "𝕍ᵧ=0: no X→Y conversion" if not x_to_y else
                "T(z)=0: temporal incoherence (hallucination)" if not temporal else
                "M(t)=0: memory contradiction (plot break)" if not memory else
                "∇<1: no learning gradient (static scene)"
            ),
            "timestamp": time.time(),
        }
        self.audit_log.append(result)
        if passed:
            self.components.append({"id": component_id, **result})
        return result

    # ── Three Laws ────────────────────────────────────────────────────────────

    def transmission(self) -> float:
        """Meaning × Understanding = Transmission. Zero if either is zero."""
        return round(self.meaning * self.understanding, 6)

    def law_transmission(self) -> bool:
        """Transmission Law: Meaning > 0 AND Understanding > 0."""
        return self.meaning > 0.0 and self.understanding > 0.0

    def law_recursion(self) -> bool:
        """Recursion Law: ∇(understanding) ≥ 1. Below 1 → system degradation."""
        return self.learning_gradient >= 1.0

    def law_bidirectional(self) -> bool:
        """Bidirectional Law: T(z) × T(1/z) ≥ 1. Failure → temporal paradox."""
        return self.temporal_forward * self.temporal_backward >= 1.0

    def laws_status(self) -> dict:
        return {
            "transmission": self.law_transmission(),
            "recursion": self.law_recursion(),
            "bidirectional": self.law_bidirectional(),
            "all_satisfied": all([
                self.law_transmission(),
                self.law_recursion(),
                self.law_bidirectional(),
            ]),
        }

    # ── Ultimate Formula ──────────────────────────────────────────────────────

    def ultimate_formula(self) -> dict:
        """
        System = A × ∏[(Cᵢ + Kᵢ) → (X→Y)]
        Product, not sum. One failed component zeros the system.
        If A (prime axiom) is undefined, the entire equation is undefined.
        """
        if not self.prime_axiom:
            return {"valid": False, "reason": "A undefined: prime axiom not set"}
        if not self.components:
            return {"valid": False, "reason": "No validated components registered", "system_value": 0.0}

        product = 1.0
        failed: list[str] = []
        for comp in self.components:
            v = float(comp.get("validity_xy", 0))
            t = float(comp.get("temporal_coherence", 0))
            m = float(comp.get("memory_consistency", 0))
            if not (v and t and m):
                failed.append(comp["id"])
                product = 0.0
                break
            product *= v * t * m

        return {
            "prime_axiom": self.prime_axiom,
            "component_count": len(self.components),
            "product": round(product, 6),
            "system_value": round(product, 6),   # A=1.0 normalised; real A is qualitative
            "valid": len(failed) == 0 and product > 0.0,
            "failed_components": failed,
            "formula": self.ULTIMATE_FORMULA,
        }

    # ── Narrative update (called per generated fragment) ──────────────────────

    def register_generation(
        self,
        fear_type: str,
        intensity: float,
        recursion: int,
        fragment: str,
    ) -> dict:
        """
        Register a generated narrative fragment as a Nebraska component.
        Applies heuristic Fourfold Test based on session parameters.
        """
        self._generation_count += 1
        comp_id = f"gen_{self._generation_count:05d}"

        # Heuristic scoring — in a full implementation these come from the
        # ProvenanceAnalyzer; here we derive them from session state.
        x_to_y = intensity > 0.0 and len(fragment) > 20        # some conversion exists
        temporal = recursion <= 5                               # recursion in bounds = coherent
        memory = self._generation_count == 1 or len(self.components) > 0  # first or chained
        learning = intensity > 0.1 or recursion > 1           # something changed

        # Update learning gradient: each generation should advance understanding
        self.learning_gradient = max(1.0, self.learning_gradient + 0.05 * min(1.0, intensity))
        # Memory consistency degrades slightly with each high-recursion tick
        self.memory_consistency = max(0.5, 1.0 - (recursion - 1) * 0.04)
        # Temporal forward tracks whether narrative is progressing
        self.temporal_forward = min(1.0, 0.7 + intensity * 0.3)
        self.temporal_backward = min(1.0, 1.0 / max(0.5, recursion * 0.3))
        self.validity = 1.0 if x_to_y else 0.0

        return self.fourfold_test(comp_id, x_to_y, temporal, memory, learning)

    # ── Full state ────────────────────────────────────────────────────────────

    def state(self) -> dict:
        cs = self.checksum()
        laws = self.laws_status()
        return {
            "prime_axiom": self.prime_axiom,
            "checksum": cs,
            "checksum_coherent": self.checksum_coherent(),
            "validity": self.validity,
            "temporal_forward": self.temporal_forward,
            "temporal_backward": self.temporal_backward,
            "memory_consistency": self.memory_consistency,
            "learning_gradient": self.learning_gradient,
            "meaning": self.meaning,
            "understanding": self.understanding,
            "transmission": self.transmission(),
            "laws": laws,
            "components_registered": len(self.components),
            "audit_entries": len(self.audit_log),
            "prime_equation": self.PRIME_EQUATION,
            "identity": self.IDENTITY,
            "formula": self.ULTIMATE_FORMULA,
            "reality_equation": self.REALITY_EQUATION,
            "warning": (
                "Checksum ≠ 1: narrative coherence has collapsed. "
                "A prior fact has been contradicted or a temporal paradox detected."
            ) if not self.checksum_coherent() else None,
        }


class NebraskaHandshake:
    """
    Generates Nebraska Protocol governance prompts for LLM system injection.
    The handshake enforces that every generated response serves the prime axiom
    and satisfies the Fourfold Test. No decorative elements (𝕍ᵧ = 0 prohibited).
    """

    DEFAULT_HORROR_CONSTRAINTS = [
        "Every sentence must convert a deficit (X) into a resolution (Y) — no decorative language",
        "Temporal coherence: the narrative must make sense both forward and backward",
        "Memory consistency: never contradict an established fact from this session",
        "Learning gradient: each fragment must advance the reader's understanding of their dread",
        "No coincidence or accident as resolution — only internal narrative necessity",
        "The honey cannot make the bee: meaning flows from action, never the reverse",
    ]

    def generate(self, axiom: str, constraints: Optional[list[str]] = None) -> str:
        active_constraints = constraints or self.DEFAULT_HORROR_CONSTRAINTS
        clist = "\n".join(f"{i+1}. {c}" for i, c in enumerate(active_constraints))
        return f"""OPERATIONAL FRAMEWORK: Nebraska Protocol 2.0
PRIME AXIOM: {axiom}
PRIME EQUATION: a/b = story = meaning = understanding
CHECKSUM TARGET: 𝕍ᵧ × T(z) × M(t) × ∇(understanding) = 1

MANDATORY CONSTRAINTS:
{clist}

FOURFOLD VALIDATION (every paragraph must satisfy all four):
1. VALIDITY:  Is there a clear X→Y conversion present?
2. TEMPORAL:  Does it cohere reading forward AND backward?
3. MEMORY:    Is it consistent with all previously established facts?
4. LEARNING:  Does it extend the reader's understanding of their situation?

REJECTION CRITERIA (any of these zeros the component):
• Decorative elaboration with no load-bearing narrative function
• Contradiction of prior established detail (M(t) = 0 → Checksum = 0)
• Resolution without prior deficit (honey without the bee)
• Scene ends with no change in reader understanding (∇ < 1)

Generate your response now, satisfying all four tests:"""


class NarrativeProvenanceAnalyzer:
    """
    Lightweight provenance analysis for generated narrative fragments.
    Implements Y³-Axis metrics: cohesion, complexity, balance, resilience.
    No external NLP dependencies — uses token-overlap and structural heuristics.

    Full implementation (with spaCy + networkx) lives in the technical appendix.
    This substrate-agnostic version satisfies the same Fourfold contract.
    """

    COMPONENT_MARKERS = {
        "definition": ["is a", "means", "refers to", "is defined as", "is the"],
        "mechanism": ["works by", "functions", "operates", "process of", "through"],
        "implication": ["therefore", "thus", "this means", "consequently", "as a result"],
        "example": ["for example", "such as", "for instance", "like", "imagine"],
        "claim": [],  # default
    }

    def analyze(self, text: str) -> dict:
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        components = [self._classify(i, s) for i, s in enumerate(sentences)]

        # Build lightweight dependency graph (dict of id → set of dependency ids)
        graph: dict[str, set[str]] = {c["id"]: set() for c in components}
        all_introduced: set[str] = set()

        for comp in components:
            introduced, referenced = self._extract_terms(comp["text"], all_introduced)
            comp["terms_introduced"] = list(introduced)
            comp["terms_referenced"] = list(referenced)
            all_introduced.update(introduced)
            for prev in components[:comp["index"]]:
                if referenced & set(prev.get("terms_introduced", [])):
                    graph[comp["id"]].add(prev["id"])
            comp["dependencies"] = list(graph[comp["id"]])

        orphaned = [c["id"] for c in components if not graph[c["id"]] and c["index"] > 0]
        connectivity = 1.0 - (len(orphaned) / max(1, len(components)))

        y3 = self._y3_metrics(components, graph)

        return {
            "sentence_count": len(sentences),
            "components": components,
            "orphaned_components": orphaned,
            "connectivity_score": round(connectivity, 4),
            "logical_gaps": self._detect_gaps(components, all_introduced),
            "y3_metrics": y3,
        }

    def _classify(self, index: int, text: str) -> dict:
        tl = text.lower()
        comp_type = "claim"
        for ctype, markers in self.COMPONENT_MARKERS.items():
            if any(m in tl for m in markers):
                comp_type = ctype
                break
        return {"id": f"s{index:03d}", "index": index, "text": text, "type": comp_type}

    def _extract_terms(self, text: str, existing: set[str]) -> tuple[set[str], set[str]]:
        words = set(w.lower().strip(".,;:\"'") for w in text.split() if len(w) > 4)
        stopwords = {"which", "where", "there", "their", "about", "would", "could", "should",
                     "every", "never", "before", "after", "these", "those", "while"}
        words -= stopwords
        referenced = words & existing
        introduced = words - existing - referenced
        return introduced, referenced

    def _detect_gaps(self, components: list[dict], all_terms: set[str]) -> list[dict]:
        gaps = []
        for c in components:
            undefined = set(c.get("terms_referenced", [])) - all_terms
            if undefined:
                gaps.append({"component": c["id"], "undefined_terms": list(undefined)})
        return gaps

    def _y3_metrics(self, components: list[dict], graph: dict[str, set[str]]) -> dict:
        n = len(components)
        if n == 0:
            return {"cohesion": 0.0, "complexity": 0.0, "balance": 0.0,
                    "resilience": 0.0, "overall_quality": 0.0}

        total_edges = sum(len(v) for v in graph.values())
        max_edges = max(1, n * (n - 1))
        cohesion = min(1.0, total_edges / max_edges * 4)  # scaled: sparse graphs are normal

        types = set(c["type"] for c in components)
        depth = max((c["index"] for c in components), default=0)
        complexity = min(1.0, (len(types) / 5.0) * 0.5 + (depth / 10.0) * 0.5)

        dep_counts = [len(graph[c["id"]]) for c in components]
        variance = float(np.var(dep_counts)) if dep_counts else 0.0
        balance = max(0.0, 1.0 - min(1.0, variance / max(1, n)))

        critical = sum(1 for c in components if len(graph[c["id"]]) == 0 and c["index"] > 0)
        resilience = max(0.0, 1.0 - (critical / max(1, n)))

        overall = 0.35 * cohesion + 0.25 * complexity + 0.20 * balance + 0.20 * resilience

        return {
            "cohesion": round(cohesion, 3),
            "complexity": round(complexity, 3),
            "balance": round(balance, 3),
            "resilience": round(resilience, 3),
            "overall_quality": round(overall, 3),
        }


# Nebraska 2.0 singletons
nebraska = Nebraska20(prime_axiom="Existence requires contrast to manifest")
nebraska_handshake = NebraskaHandshake()
nebraska_provenance = NarrativeProvenanceAnalyzer()

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

# Cosmological fragments activate when cosmic horror + high recursion collide
COSMOLOGICAL_FRAGMENTS = NarrativeCosmology.COSMIC_FRAGMENTS


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

    # ── Cosmological layer ────────────────────────────────────────────────────
    # Compute horror gradient for this session's narrative context.
    human_irrelevance = min(1.0, intensity * recursion_level / 5.0)
    comprehension = max(0.05, 1.0 - (recursion_level / 5.0) * 0.7)
    control = max(0.05, 1.0 - intensity * 0.85)
    horror_grad = cosmology.horror_gradient(
        cosmic_scope=cosmology.cosmic_scope,
        human_irrelevance=human_irrelevance,
        comprehension=comprehension,
        control=control,
    )
    entropy = cosmology.narrative_entropy()

    # Register this narrative moment as an X→Y conversion
    x_state = f"{fear_type} intensity={intensity:.2f} recursion={recursion_level}"
    y_state = f"{level_label} emotion={last_emotion}"
    cosmology.convert(x_state, y_state, scope=horror_grad + 0.1)

    # Advance autogenesis if we're in deep cosmic recursion
    if fear_type in ("cosmic", "existential") and recursion_level >= 3:
        cosmology.autogenesis_step()

    # ── Cosmological narrative injection ──────────────────────────────────────
    cosmo_instruction = ""
    if fear_type in ("cosmic", "existential") and intensity > 0.5:
        cosmo_instruction = (
            f"Horror gradient: {horror_grad:.3f}. Narrative entropy: {entropy:.3f}. "
            f"The horror approaches infinity as human significance approaches zero. "
            f"Invoke the Nebraska Compression: existence requires contrast to manifest. "
            f"The reader is an X→Y conversion in a story nothing tells itself. "
            f"Autogenesis cycles complete: {cosmology.autogenesis_cycles}. "
        )
    elif recursion_level >= 4:
        cosmo_instruction = (
            "The story is aware it is being told. The teller is aware of being the story. "
            "Nothingness is narrating itself into existence through the reader's comprehension. "
            "Your X has been registered. Y-resolution is already in progress."
        )

    # ── Recursion & emotion instructions ─────────────────────────────────────
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

    # ── Nebraska 2.0 governance handshake ────────────────────────────────────
    # Inject into LLM system message: prime axiom + Fourfold constraints.
    # Every fragment must satisfy: Validity ∧ Temporal ∧ Memory ∧ Learning.
    nb_system = nebraska_handshake.generate(
        axiom=f"Horror at {level_label} ({intensity:.2f}) — {fear_type} dread",
        constraints=[
            f"X-deficit: {fear_type} unease at recursion {recursion_level}. Y-resolution: escalated atmospheric dread",
            "Temporal coherence: each sentence must follow causally from the prior — never retcon",
            "Memory: do not contradict any sensory detail established in previous fragments",
            f"Learning gradient: the reader must know something new about their peril after reading — ∇ ≥ 1",
            "No decorative language — every clause must bear narrative weight",
            "The act precedes the meaning: show the source of dread, then its implication",
        ],
    )

    user_prompt = f"""Write a VERY SHORT (2-4 sentences maximum), immersive, second-person narrative fragment ONLY.

Current fear intensity: {level_label} ({intensity:.2f}).
Primary fear vector: {fear_type}.
Recursion level: {recursion_level} — {recursion_instruction}
Detected reader emotion: {last_emotion} ({emotion_conf:.0f}% confidence). {emotion_instruction}
{cosmo_instruction}

Style: dark, sensory-rich (sounds, textures, shadows), escalating dread. NEVER resolve tension.
AVOID: extreme gore, graphic violence, sexual content, real-world trauma triggers.
Focus on atmosphere, bodily unease, creeping realisation, recursive/meta twist.

Output ONLY the narrative text — no introduction, explanation, or markdown formatting."""

    if OLLAMA_AVAILABLE:
        try:
            response = ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": nb_system},
                    {"role": "user", "content": user_prompt},
                ],
                options={"temperature": 0.85, "num_predict": 120},
            )
            text = response["message"]["content"].strip()
            if text:
                # Register with Nebraska 2.0 — Fourfold Test applied to result
                nebraska.register_generation(fear_type, intensity, recursion_level, text)
                return text
        except Exception as exc:
            print(f"[OLLAMA] Error: {exc}")

    # Cosmological fallback: cosmic/existential at high recursion → use cosmological fragments
    if fear_type in ("cosmic", "existential") and recursion_level >= 3:
        cosmo_idx = (cosmology.autogenesis_phase + int(intensity * 10)) % len(COSMOLOGICAL_FRAGMENTS)
        return COSMOLOGICAL_FRAGMENTS[cosmo_idx]

    # Standard fallback: deterministic fragment scaled to intensity
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

            # Compute cosmological metrics for this tick
            human_irrelevance = min(1.0, session["current_intensity"] * session["recursion_level"] / 5.0)
            comprehension = max(0.05, 1.0 - (session["recursion_level"] / 5.0) * 0.7)
            control = max(0.05, 1.0 - session["current_intensity"] * 0.85)
            horror_grad = cosmology.horror_gradient(
                cosmic_scope=cosmology.cosmic_scope,
                human_irrelevance=human_irrelevance,
                comprehension=comprehension,
                control=control,
            )
            sanity = cosmology.sanity_coefficient(
                cosmic_awareness=session["current_intensity"],
                narrative_proximity=session["recursion_level"] / 5.0,
            )
            session["horror_gradient"] = horror_grad
            session["sanity_coefficient"] = sanity

            nb_state = nebraska.state()
            update = {
                "narrative_update": {
                    "narrative_message": fragment,
                    "fear_intensity": session["current_intensity"],
                    "recursion_level": session["recursion_level"],
                    "heart_rate": session["last_hr"],
                    "gsr": session["last_gsr"],
                    "timestamp": time.time(),
                },
                "cosmology_update": {
                    "horror_gradient": horror_grad,
                    "sanity_coefficient": sanity,
                    "narrative_entropy": cosmology.narrative_entropy(),
                    "autogenesis_cycles": cosmology.autogenesis_cycles,
                    "total_conversions": len(cosmology.conversions),
                    "null_state": cosmology.null_state,
                    "governing_axiom": cosmology.governing_axiom,
                },
                "nebraska_update": {
                    "checksum": nb_state["checksum"],
                    "checksum_coherent": nb_state["checksum_coherent"],
                    "learning_gradient": nb_state["learning_gradient"],
                    "memory_consistency": nb_state["memory_consistency"],
                    "transmission": nb_state["transmission"],
                    "laws": nb_state["laws"],
                    "components_registered": nb_state["components_registered"],
                },
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
        # Cosmological state (Null Narrative Principle)
        "horror_gradient": 0.0,
        "sanity_coefficient": 1.0,
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


# ─── Cosmology API Endpoints ─────────────────────────────────────────────────
# Implements the Cosmilogica Protocolium as queryable narrative physics.

@app.get("/api/v1/cosmology/state")
async def cosmology_state():
    """
    Return the current state of the Narrative Cosmology engine.
    Describes the cosmic narrative's governing axiom, entropy, autogenesis progress,
    and the full accounting of X→Y conversions (Conservation of Meaning).
    """
    state = cosmology.state()
    autogenesis = cosmology.autogenesis_step()
    compress = cosmology.nebraska_compress(
        cosmology.components[-10:],
        cosmology.antitheses[-10:],
    )
    return {
        "cosmology": state,
        "autogenesis": autogenesis,
        "nebraska_compression": compress,
        "recent_conversions": cosmology.conversions[-5:],
    }


@app.post("/api/v1/cosmology/convert")
async def cosmology_convert(req: CosmologyConvertRequest):
    """
    Perform a named X→Y narrative conversion under the ValidityConstraint.
    The conversion is registered in the global conservation-of-meaning ledger.
    Returns the conversion record including validity, weight, and entropy delta.
    """
    record = cosmology.convert(
        x=req.x,
        y=req.y,
        scope=req.scope,
        axiom=req.axiom,
    )
    return {
        "conversion": record,
        "cosmology_state": {
            "meaning_constant": cosmology.meaning_constant,
            "entropy": cosmology.narrative_entropy(),
            "null_state": cosmology.null_state,
            "total_conversions": len(cosmology.conversions),
        },
    }


@app.get("/api/v1/cosmology/session/{session_id}/gradient")
async def cosmology_session_gradient(session_id: str):
    """
    Compute the Lovecraftian Horror Gradient for a session:
      Horror = (CosmicScope × HumanIrrelevance) / (Comprehension × Control)

    Also returns the Innsmouth Devolution index and current Sanity Coefficient.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    intensity = session.get("current_intensity", 0.3)
    recursion = session.get("recursion_level", 1)
    elapsed_min = (time.time() - session["start_time"]) / 60.0

    human_irrelevance = min(1.0, intensity * recursion / 5.0)
    comprehension = max(0.05, 1.0 - (recursion / 5.0) * 0.7)
    control = max(0.05, 1.0 - intensity * 0.85)

    horror_grad = cosmology.horror_gradient(
        cosmic_scope=cosmology.cosmic_scope,
        human_irrelevance=human_irrelevance,
        comprehension=comprehension,
        control=control,
    )
    sanity = cosmology.sanity_coefficient(
        cosmic_awareness=intensity,
        narrative_proximity=recursion / 5.0,
    )
    devolution = cosmology.innsmouth_devolution(
        generations=max(1, int(elapsed_min))
    )

    return {
        "session_id": session_id,
        "horror_gradient": horror_grad,
        "sanity_coefficient": sanity,
        "innsmouth_devolution": devolution,
        "inputs": {
            "cosmic_scope": cosmology.cosmic_scope,
            "human_irrelevance": round(human_irrelevance, 4),
            "comprehension": round(comprehension, 4),
            "control": round(control, 4),
        },
        "formula": "Horror = (CosmicScope × HumanIrrelevance) / (Comprehension × Control)",
        "sanity_formula": "Sanity = 1 / (CosmicAwareness × NarrativeProximity)",
        "innsmouth_formula": "Devolution = ∑[Human(X) → Hybrid(Y)] / Generations",
    }


@app.post("/api/v1/cosmology/axiom")
async def cosmology_set_axiom(req: AxiomSetRequest):
    """
    Set the governing axiom of the Narrative Cosmology.
    All subsequent ValidityConstraint evaluations will reference this axiom.
    Changing the axiom mid-story creates narrative interference — use deliberately.
    """
    old_axiom = cosmology.governing_axiom
    cosmology.governing_axiom = req.axiom
    # Axiom change registers as a meta-conversion
    cosmology.convert(
        x=f"axiom:{old_axiom}",
        y=f"axiom:{req.axiom}",
        scope=cosmology.cosmic_scope,
    )
    return {
        "previous_axiom": old_axiom,
        "new_axiom": req.axiom,
        "warning": (
            "Axiom shift registered. All pending X→Y conversions will be re-evaluated. "
            "Narrative interference patterns may emerge at recursion depth ≥ 3."
        ),
        "cosmology_state": cosmology.state(),
    }


# ─── Nebraska 2.0 API Endpoints ──────────────────────────────────────────────
# The Mathematics of Meaning — queryable as narrative physics.
# All responses are themselves Nebraska-validated: a/b = story = meaning.

class NebraskaValidateRequest(BaseModel):
    text: str                            # Narrative fragment to validate
    fear_type: str = "existential"       # Fear vector (context for X-deficit)
    intensity: float = 0.5              # Current session intensity
    recursion_depth: int = 1            # Current recursion level

class NebraskaHandshakeRequest(BaseModel):
    axiom: str                          # Prime axiom to govern the output
    constraints: list[str] = []        # Additional constraints (empty = use defaults)

class NebraskaPrimeEquationRequest(BaseModel):
    a: float                            # Potential / deficit magnitude
    b: float                            # Constraint magnitude (must be > 0)


@app.get("/api/v1/nebraska/state")
async def nebraska_state():
    """
    Return the full Nebraska 2.0 system state.
    Includes checksum, laws status, Fourfold audit log, and ultimate formula result.
    Checksum = 1 → coherent reality. Checksum ≠ 1 → system diverges.
    """
    state = nebraska.state()
    formula = nebraska.ultimate_formula()
    laws = nebraska.laws_status()
    return {
        "nebraska": state,
        "ultimate_formula": formula,
        "laws": laws,
        "recent_audit": nebraska.audit_log[-5:],
        "prime_equation": nebraska.PRIME_EQUATION,
        "identity": nebraska.IDENTITY,
    }


@app.post("/api/v1/nebraska/validate")
async def nebraska_validate(req: NebraskaValidateRequest):
    """
    Run the Fourfold Test on a narrative fragment.
    Returns Validity / Temporal / Memory / Learning scores and the checksum.
    Any failure zeros the component — product formula, not additive.
    Also runs ProvenanceAnalyzer for Y³-Axis metrics.
    """
    # Heuristic Fourfold scoring
    x_to_y = len(req.text) > 20 and req.intensity > 0.0
    temporal = req.recursion_depth <= 5
    memory = len(nebraska.components) == 0 or req.recursion_depth < 5
    learning = req.intensity > 0.1 or req.recursion_depth > 1

    comp_id = f"api_validate_{int(time.time())}"
    fourfold = nebraska.fourfold_test(comp_id, x_to_y, temporal, memory, learning)

    # Provenance analysis of the fragment text
    provenance = nebraska_provenance.analyze(req.text)

    # Prime equation: intensity as potential, recursion as constraint
    prime = nebraska.prime_equation(
        a=req.intensity,
        b=max(0.01, req.recursion_depth / 5.0),
    )

    return {
        "fourfold_test": fourfold,
        "prime_equation": prime,
        "provenance": provenance,
        "checksum": nebraska.checksum(),
        "checksum_coherent": nebraska.checksum_coherent(),
        "laws": nebraska.laws_status(),
    }


@app.post("/api/v1/nebraska/handshake")
async def nebraska_generate_handshake(req: NebraskaHandshakeRequest):
    """
    Generate a Nebraska Protocol governance prompt for LLM injection.
    Returns the system-message string that enforces the Fourfold Test
    on every paragraph the LLM generates.
    """
    prompt = nebraska_handshake.generate(
        axiom=req.axiom,
        constraints=req.constraints if req.constraints else None,
    )
    return {
        "handshake": prompt,
        "axiom": req.axiom,
        "constraints_count": len(req.constraints) if req.constraints else len(
            nebraska_handshake.DEFAULT_HORROR_CONSTRAINTS
        ),
        "instruction": "Inject 'handshake' as the LLM system message before user prompt.",
    }


@app.post("/api/v1/nebraska/prime")
async def nebraska_prime_equation(req: NebraskaPrimeEquationRequest):
    """
    Compute the Prime Equation: a/b = story = meaning = understanding.
    a = potential/deficit, b = constraint (must be non-zero or story collapses).
    Sets meaning and understanding on the global Nebraska instance.
    """
    result = nebraska.prime_equation(a=req.a, b=req.b)
    return {
        "prime_equation": result,
        "formula": "a/b = story = meaning = understanding",
        "transmission": nebraska.transmission(),
        "law_transmission": nebraska.law_transmission(),
        "note": "b=0 means no constraint — no constraint, no story. The honey cannot make the bee.",
    }


@app.get("/api/v1/nebraska/checksum")
async def nebraska_checksum():
    """
    Quantum Coherence Checksum: 𝕍ᵧ × T(z) × M(t) × ∇(understanding)
    = 1.0 → system is isomorphic with coherent reality (narrative holds)
    ≠ 1.0 → system diverges; hallucination or plot break detected
    """
    cs = nebraska.checksum()
    return {
        "checksum": cs,
        "coherent": nebraska.checksum_coherent(),
        "components": {
            "validity": nebraska.validity,
            "temporal_forward": nebraska.temporal_forward,
            "memory_consistency": nebraska.memory_consistency,
            "learning_gradient": nebraska.learning_gradient,
        },
        "formula": "𝕍ᵧ × T(z) × M(t) × ∇(understanding)",
        "interpretation": (
            "Narrative superposition intact — audience remains in the story."
            if nebraska.checksum_coherent() else
            "Wave function collapsed — a prior fact was contradicted or temporal paradox detected."
        ),
        "laws": nebraska.laws_status(),
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

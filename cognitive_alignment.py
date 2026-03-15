"""
COGNITIVE ALIGNMENT FRAMEWORK — Nebraska 1.0 / 2.0
A/B = Story: Variable Reduction Algorithm and Deterministic Lexicon

Nebraska 1.0 — Variable Reduction Algorithm
    Externalises the prefrontal cortex via a Governor anchor (B) that
    constrains Stimulus entropy (A), reducing the metabolic cost of achieving
    semantic coherence.

Nebraska 2.0 — Deterministic Lexicon
    Locks semantic terms to zero interpretive degrees of freedom (zero DoF),
    preventing Pragmatic Drift in therapist–patient communication and
    pinpointing the exact "leak" when drift occurs.

Information-theoretic foundation
─────────────────────────────────
    A (Stimulus)  : Shannon entropy H(A) of raw biometric / narrative inputs.
                    High A = cognitive "Soup" — unprocessed, un-anchored reality.
    B (Governor)  : Constraint strength of the fixed anchor point.
                    High B = "Rails" — deterministic track preventing dissolution.
    A/B = Story   : The coherent state that emerges when B sufficiently reduces H(A).

    Alignment Score  = B / (A + B)  →  [0, 1], higher = more coherent
    Cognitive Load   = max(0, A − B·strength)  →  residual entropy after constraint

Clinical application
────────────────────
    Executive Function Disorder : B externalises working memory / prefrontal load.
    Aphasia                     : Lexicon prevents pragmatic drift; pinpoints leaks.
    Stroke recovery             : Alignment score tracks B-maintenance across sessions.
"""

import hashlib
import math
import time
from typing import Optional

from pydantic import BaseModel, Field


# ─── Nebraska 2.0: Deterministic Lexicon ──────────────────────────────────────
# All terms carry interpretive DoF = 0.  Any usage that deviates from the
# canonical definition constitutes a measurable "leak."

DETERMINISTIC_LEXICON: dict[str, str] = {
    "anchor":     "A fixed cognitive reference point with zero interpretive variance.",
    "drift":      "Deviation from a canonical semantic anchor; measurable as entropy delta.",
    "governor":   "The B-component constraint that reduces stimulus entropy.",
    "alignment":  "The state achieved when B sufficiently constrains A to produce coherent story.",
    "recursion":  "Self-referential narrative depth; measured in cognitive load units.",
    "intensity":  "Amplitude of the fear stimulus vector; range [0.0, 1.0].",
    "coherence":  "The emergent property when A/B ratio achieves the story state.",
    "leak":       "A point of pragmatic drift where the lexicon fails to constrain interpretation.",
    "stimulus":   "Raw sensory or biometric input to the cognitive processing system.",
    "entropy":    "A measure of disorder or unpredictability in an information source.",
    "nebraska":   "The canonical anchor protocol; a fixed external reference that reduces metabolic cost.",
    "soup":       "The cognitive state of maximum entropy — unprocessed, un-anchored reality.",
    "story":      "The output state of the A/B equation; coherent meaning derived from constrained stimulus.",
    "rails":      "The constraint architecture that prevents semantic dissolution into entropy.",
}


# ─── Coherence level table ─────────────────────────────────────────────────────

COHERENCE_LEVELS = [
    (0.00, 0.20, "SOUP",      "Maximum entropy. No story. Cognitive dissolution."),
    (0.20, 0.40, "DRIFT",     "Narrative fragmenting. Pragmatic drift detectable."),
    (0.40, 0.60, "NOISE",     "Partial structure. Governor marginally engaged."),
    (0.60, 0.75, "SIGNAL",    "Governor active. Coherence emerging."),
    (0.75, 0.90, "RAILS",     "Deterministic track established. Drift minimal."),
    (0.90, 1.01, "ALIGNMENT", "Zero drift. Full Nebraska protocol engaged."),
]


def get_coherence_label(score: float) -> str:
    for lo, hi, label, _ in COHERENCE_LEVELS:
        if lo <= score < hi:
            return label
    return "ALIGNMENT"


def get_coherence_description(score: float) -> str:
    for lo, hi, _, desc in COHERENCE_LEVELS:
        if lo <= score < hi:
            return desc
    return COHERENCE_LEVELS[-1][3]


# ─── Pydantic models ───────────────────────────────────────────────────────────

class StimulusVector(BaseModel):
    """
    A — The raw cognitive/sensory input.
    All components are normalised to [0, 1]; higher = more entropic.
    """
    biometric_entropy: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Shannon entropy of biometric signals (HR variance, GSR fluctuation).",
    )
    narrative_complexity: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Complexity of active narrative threads (recursion depth / max depth).",
    )
    emotional_variance: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Instability of emotion states over the history window.",
    )
    environmental_noise: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Unresolved sensory inputs (current fear intensity).",
    )

    @property
    def magnitude(self) -> float:
        """
        Aggregate stimulus entropy: weighted mean of all A-components.
        Biometric and emotional channels carry higher clinical weight.
        """
        return (
            self.biometric_entropy    * 0.35
            + self.narrative_complexity * 0.20
            + self.emotional_variance   * 0.30
            + self.environmental_noise  * 0.15
        )


class GovernorAnchor(BaseModel):
    """
    B — The fixed cognitive anchor point (Nebraska protocol).
    Externalises the prefrontal cortex by providing a deterministic reference.
    """
    anchor_id: str = Field(..., description="Unique identifier for this anchor.")
    anchor_phrase: str = Field(..., description="The canonical anchor phrase.")
    constraint_strength: float = Field(
        0.7, ge=0.0, le=1.0,
        description="How strongly B constrains A; higher = more load reduction.",
    )
    semantic_hash: str = Field(
        "", description="SHA-256 fingerprint (first 16 chars) of the anchor phrase.",
    )
    activation_threshold: float = Field(
        0.6, ge=0.0, le=1.0,
        description="A-magnitude at which the governor automatically engages.",
    )
    locked_terms: list[str] = Field(
        default_factory=list,
        description="Nebraska 2.0 lexicon terms bound to this anchor.",
    )

    def model_post_init(self, __context) -> None:  # noqa: D401
        if not self.semantic_hash:
            self.semantic_hash = hashlib.sha256(
                self.anchor_phrase.encode()
            ).hexdigest()[:16]


class AlignmentState(BaseModel):
    """A/B = Story — the computed cognitive alignment result."""

    stimulus: StimulusVector
    governor: GovernorAnchor
    alignment_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="B / (A+B): 0 = pure chaos, 1 = perfect alignment.",
    )
    cognitive_load: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Residual entropy after governor constraint.",
    )
    story_coherence: str = Field("", description="Qualitative coherence label.")
    coherence_description: str = Field("", description="Clinical description of coherence state.")
    governor_active: bool = Field(
        False,
        description="Whether A has crossed the governor's activation threshold.",
    )
    drift_score: float = Field(0.0, ge=0.0, le=1.0, description="Pragmatic drift index.")
    drift_detected: bool = Field(False, description="True when drift_score exceeds tolerance.")
    timestamp: float = Field(default_factory=time.time)


class LexiconDriftReport(BaseModel):
    """
    Nebraska 2.0 output: structural report on where patient communication
    breaks from the Deterministic Lexicon.
    """
    input_text: str
    matched_terms: list[str] = Field(
        default_factory=list,
        description="Lexicon terms found in the input.",
    )
    drifted_terms: list[str] = Field(
        default_factory=list,
        description="Terms used in a non-canonical context (potential leaks).",
    )
    drift_score: float = Field(0.0, ge=0.0, le=1.0)
    leak_locations: list[str] = Field(
        default_factory=list,
        description="Specific lexicon keys where pragmatic drift was detected.",
    )
    canonical_definitions: dict[str, str] = Field(
        default_factory=dict,
        description="The locked definitions for all matched terms.",
    )
    alignment_passed: bool = False
    interpretive_dof: int = Field(
        0,
        description="Degrees of Freedom detected in the input (0 = fully locked).",
    )


class AnchorSetRequest(BaseModel):
    anchor_phrase: str
    constraint_strength: float = Field(0.7, ge=0.0, le=1.0)
    activation_threshold: float = Field(0.6, ge=0.0, le=1.0)
    locked_terms: list[str] = Field(default_factory=list)


class LexiconTestRequest(BaseModel):
    input_text: str
    session_id: Optional[str] = None


# ─── Negation / ambiguity markers (Nebraska 2.0 drift heuristic) ──────────────

_NEGATION_MARKERS: frozenset[str] = frozenset({
    "not", "never", "no", "without", "isn't", "aren't", "doesn't",
    "can't", "won't", "unclear", "random", "vague", "maybe", "perhaps",
    "undefined", "unknown", "ambiguous", "flexible", "fluid",
})


# ─── Core Engine ──────────────────────────────────────────────────────────────

class CognitiveAlignmentEngine:
    """
    The A/B = Story computation engine.

    Nebraska 1.0: Computes the alignment score from stimulus entropy and
                  governor constraint strength.
    Nebraska 2.0: Tests communication against the Deterministic Lexicon and
                  identifies pragmatic drift / semantic leaks.
    """

    DRIFT_TOLERANCE: float = 0.35   # above this → drift_detected = True

    def __init__(self) -> None:
        self._history: list[AlignmentState] = []
        self._default_anchor = GovernorAnchor(
            anchor_id="nebraska_default",
            anchor_phrase="Nebraska",
            constraint_strength=0.7,
            activation_threshold=0.6,
            locked_terms=list(DETERMINISTIC_LEXICON.keys()),
        )

    # ── Nebraska 1.0: Variable Reduction ──────────────────────────────────────

    def compute_alignment(
        self,
        stimulus: StimulusVector,
        governor: Optional[GovernorAnchor] = None,
    ) -> AlignmentState:
        """
        Core A/B = Story equation.

            alignment_score = B / (A + B)
            cognitive_load  = max(0, A − B·strength)

        Parameters
        ----------
        stimulus  : StimulusVector — A, the raw entropic input.
        governor  : GovernorAnchor — B, the constraining anchor.

        Returns
        -------
        AlignmentState with all derived metrics.
        """
        if governor is None:
            governor = self._default_anchor

        A = stimulus.magnitude                   # aggregate stimulus entropy [0,1]
        B = governor.constraint_strength         # governor constraint [0,1]

        # A/B = Story: the governor must have sufficient strength to constrain A.
        alignment_score = B / (A + B) if (A + B) > 0.0 else 0.5

        # Residual cognitive load after the governor has applied its constraint.
        cognitive_load = max(0.0, A - B * governor.constraint_strength)
        cognitive_load = min(1.0, cognitive_load)

        governor_active = (A >= governor.activation_threshold)
        coherence = get_coherence_label(alignment_score)
        description = get_coherence_description(alignment_score)

        state = AlignmentState(
            stimulus=stimulus,
            governor=governor,
            alignment_score=round(alignment_score, 4),
            cognitive_load=round(cognitive_load, 4),
            story_coherence=coherence,
            coherence_description=description,
            governor_active=governor_active,
            drift_score=0.0,
            drift_detected=False,
        )

        self._history.append(state)
        self._history = self._history[-100:]   # rolling window — last 100 states
        return state

    def stimulus_from_session(self, session: dict) -> StimulusVector:
        """
        Derive a StimulusVector from a live Nightmare Engine session dict.

        Maps biometric, narrative, and emotional state onto the A-components:
          - HR deviation from resting baseline → biometric_entropy
          - Recursion depth / max depth       → narrative_complexity
          - Emotion transition rate           → emotional_variance
          - Current fear intensity            → environmental_noise
        """
        # Biometric entropy: HR deviation from 70 bpm resting baseline
        hr = session.get("last_hr", 70)
        hr_entropy = min(1.0, abs(hr - 70) / 130.0)   # 200 bpm ceiling

        gsr = session.get("last_gsr", 0.2)
        gsr_entropy = min(1.0, float(gsr))

        biometric_entropy = hr_entropy * 0.7 + gsr_entropy * 0.3

        # Narrative complexity: recursion depth normalised to [0,1]
        recursion = session.get("recursion_level", 1)
        narrative_complexity = min(1.0, recursion / 5.0)

        # Emotional variance: transition rate over emotion history
        emotion_history = session.get("emotion_history", [])
        if len(emotion_history) > 1:
            transitions = sum(
                1 for i in range(1, len(emotion_history))
                if emotion_history[i] != emotion_history[i - 1]
            )
            emotional_variance = min(1.0, transitions / len(emotion_history))
        else:
            conf = session.get("emotion_confidence", 50.0)
            emotional_variance = 1.0 - min(1.0, conf / 100.0)

        # Environmental noise: current fear intensity
        environmental_noise = float(session.get("current_intensity", 0.3))

        return StimulusVector(
            biometric_entropy=round(biometric_entropy, 4),
            narrative_complexity=round(narrative_complexity, 4),
            emotional_variance=round(emotional_variance, 4),
            environmental_noise=round(environmental_noise, 4),
        )

    # ── Nebraska 2.0: Pragmatic Drift Detection ───────────────────────────────

    def test_lexicon_alignment(self, text: str) -> LexiconDriftReport:
        """
        Nebraska 2.0: Test input text against the Deterministic Lexicon.

        Mechanism
        ---------
        1. Identify all locked lexicon terms present in the input.
        2. For each matched term, inspect the surrounding ±30-character window
           for negation markers or ambiguity indicators.
        3. Terms found in an ambiguous context are classified as "leaks".
        4. drift_score = leaked_terms / total_matched_terms.
        5. interpretive_dof = count of ambiguous terms (canonical DoF = 0).
        """
        text_lower = text.lower()
        words = set(text_lower.replace(",", " ").replace(".", " ").split())
        matched = [term for term in DETERMINISTIC_LEXICON if term in words]
        canonical_defs = {t: DETERMINISTIC_LEXICON[t] for t in matched}

        drifted: list[str] = []
        leak_locations: list[str] = []

        for term in matched:
            idx = text_lower.find(term)
            if idx >= 0:
                ctx_start = max(0, idx - 30)
                context = text_lower[ctx_start: idx + len(term) + 30]
                if set(context.split()) & _NEGATION_MARKERS:
                    drifted.append(term)
                    leak_locations.append(term)

        drift_score = len(drifted) / max(len(matched), 1) if matched else 0.0

        return LexiconDriftReport(
            input_text=text,
            matched_terms=matched,
            drifted_terms=drifted,
            drift_score=round(drift_score, 4),
            leak_locations=leak_locations,
            canonical_definitions=canonical_defs,
            alignment_passed=(drift_score < self.DRIFT_TOLERANCE and len(matched) > 0),
            interpretive_dof=len(drifted),
        )

    # ── Recovery Trajectory (clinical analytics) ──────────────────────────────

    def recovery_trajectory(self) -> dict:
        """
        Compute alignment recovery metrics from the rolling history window.

        For clinical use: a positive `recovery_slope` indicates the patient
        is successfully maintaining the B-constraint against increasing A
        (stimulus entropy), which is the key indicator of EFD recovery.
        """
        if len(self._history) < 2:
            return {"insufficient_data": True, "samples": len(self._history)}

        scores = [s.alignment_score for s in self._history]
        loads = [s.cognitive_load for s in self._history]
        n = len(scores)

        # Ordinary least-squares slope over alignment scores
        x_mean = (n - 1) / 2.0
        score_mean = sum(scores) / n
        numerator = sum((i - x_mean) * (scores[i] - score_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator > 1e-9 else 0.0

        return {
            "samples": n,
            "mean_alignment": round(score_mean, 4),
            "peak_alignment": round(max(scores), 4),
            "trough_alignment": round(min(scores), 4),
            "recovery_slope": round(slope, 6),          # positive = improving
            "mean_cognitive_load": round(sum(loads) / n, 4),
            "drift_events": sum(1 for s in self._history if s.drift_detected),
            "governor_activations": sum(1 for s in self._history if s.governor_active),
            "coherence_distribution": _coherence_distribution(self._history),
        }

    def set_default_anchor(self, anchor: GovernorAnchor) -> None:
        """Replace the module-level default Governor anchor (B)."""
        self._default_anchor = anchor

    @property
    def default_anchor(self) -> GovernorAnchor:
        return self._default_anchor


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _coherence_distribution(history: list[AlignmentState]) -> dict[str, int]:
    dist: dict[str, int] = {label: 0 for _, _, label, _ in COHERENCE_LEVELS}
    for state in history:
        dist[state.story_coherence] = dist.get(state.story_coherence, 0) + 1
    return dist


def create_engine() -> CognitiveAlignmentEngine:
    """Factory: create a fresh CognitiveAlignmentEngine per session."""
    return CognitiveAlignmentEngine()

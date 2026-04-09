"""
NEBRASKA GENERATIVE SYSTEM (NGS) — Version 1.0.Y
================================================
Implements the Y-Axis Validity Constraint (𝕍ᵧ) and Z-Axis temporal context
for lawful narrative construction and AI reasoning.

Core Formula:
    System = A + ∑[ (Cᵢ + Kᵢ) | A ] · 𝕍ᵧ

Where:
    A    = Axiom (governing law / central question)
    Cᵢ   = Character Components (agents, entities, personalities)
    Kᵢ   = Kinetic Components (actions, mechanisms, causal functions)
    | A  = Constraint clause — all operations under Axiom's authority
    𝕍ᵧ   = Y-Axis Validity Constraint (binary gate: 1 if X→Y, else 0)

Z-Axis:
    Temporal context that allows bidirectional traversal of a logic chain —
    looking both forward (causal) and backward (retroactive validation) rather
    than only generating probabilistic "guesses".

a/b = story → story = meaning → meaning = understanding (recursive pedagogy).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ─── Enums ────────────────────────────────────────────────────────────────────

class ComponentType(str, Enum):
    CHARACTER = "character"   # Cᵢ — agent / entity / personality
    KINETIC   = "kinetic"     # Kᵢ — action / mechanism / causal function


class AxisDirection(str, Enum):
    FORWARD  = "forward"   # causal: X → Y
    BACKWARD = "backward"  # retroactive: Y ← X  (Z-axis inversion)
    BOTH     = "both"      # full temporal scan (axis intervention)


class ValidationStatus(str, Enum):
    VALID    = "valid"    # 𝕍ᵧ = 1 — retained
    INVALID  = "invalid"  # 𝕍ᵧ = 0 — self-deleted
    PENDING  = "pending"  # not yet tested


# ─── Data models ──────────────────────────────────────────────────────────────

@dataclass
class XState:
    """Deficit state — the open circuit that demands resolution."""
    label: str                  # human-readable name of the deficit
    description: str = ""       # what is missing / unstable / unresolved
    severity: float = 0.5       # 0.0 (trivial) → 1.0 (catastrophic)


@dataclass
class YState:
    """Resolution state — the closed circuit, restored balance."""
    label: str                  # human-readable name of the resolution
    description: str = ""       # what is assigned / stabilised / resolved
    completeness: float = 1.0   # 0.0 (partial) → 1.0 (full resolution)


@dataclass
class ZContext:
    """
    Temporal context — the Z-axis.

    Carries determinism probability vectors for a logic chain so that the
    system can reason in both causal and retroactive directions, not just
    guess from a single probability distribution.
    """
    chain_id: str                        # identifier for this logic chain
    direction: AxisDirection = AxisDirection.BOTH
    history: list[dict[str, Any]] = field(default_factory=list)
    future: list[dict[str, Any]] = field(default_factory=list)
    probability_vector: list[float] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    inverted: bool = False               # True when Z-axis inversion is active
    intervention_active: bool = False    # True when axis intervention is applied

    def invert(self) -> "ZContext":
        """Z-Axis Inversion — analyse backward through the logic chain."""
        return ZContext(
            chain_id=self.chain_id + "_inverted",
            direction=AxisDirection.BACKWARD,
            history=list(reversed(self.future)),
            future=list(reversed(self.history)),
            probability_vector=list(reversed(self.probability_vector)),
            inverted=True,
        )

    def intervene(self, override_vector: list[float]) -> "ZContext":
        """Axis Intervention — manually correct the probability vector."""
        return ZContext(
            chain_id=self.chain_id + "_intervened",
            direction=AxisDirection.BOTH,
            history=self.history,
            future=self.future,
            probability_vector=override_vector,
            inverted=self.inverted,
            intervention_active=True,
        )

    def add_event(self, event: dict[str, Any], is_future: bool = False) -> None:
        event["timestamp"] = time.time()
        if is_future:
            self.future.append(event)
        else:
            self.history.append(event)


@dataclass
class Component:
    """
    A single narrative component (Cᵢ or Kᵢ).

    Must declare its X (deficit) and Y (resolution) states.
    𝕍ᵧ is computed during validation against the governing Axiom.
    """
    name: str
    component_type: ComponentType
    x_state: XState
    y_state: YState
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # Computed fields
    validity: ValidationStatus = ValidationStatus.PENDING
    validity_score: float = 0.0   # 0.0 → 1.0 (confidence of X→Y conversion)
    rejection_reason: str = ""


@dataclass
class Axiom:
    """
    The governing law (A) — the central question the narrative must prove.

    All components are validated against this axiom.  A component that cannot
    contribute to the Axiom's proof (or disproof) is multiplied by zero and
    expelled from the system.
    """
    label: str
    law: str                        # the non-negotiable rule
    question: str = ""              # central question being answered
    domain: str = "narrative"       # narrative | code | research | design
    keywords: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


# ─── 𝕍ᵧ Gate Function ────────────────────────────────────────────────────────

class YAxisValidityConstraint:
    """
    Binary gate function — the heart of the NGS.

        𝕍ᵧ(Component) = {
          1  if (X → Y) under Law A
          0  otherwise
        }

    Illegal components self-delete (are multiplied by zero and excluded from
    the summation).  Only components that perform a lawful X→Y conversion
    under the governing Axiom are retained.
    """

    def __init__(self, axiom: Axiom) -> None:
        self.axiom = axiom

    def gate(self, component: Component, z_context: Optional[ZContext] = None) -> int:
        """
        Apply 𝕍ᵧ.  Returns 1 (retain) or 0 (reject).

        Scoring uses three sub-tests:
          1. X-completeness  — is there a genuine, named deficit?
          2. Y-completeness  — is there a genuine, named resolution?
          3. Axiom alignment — does the conversion serve the governing Law?
        """
        score, reason = self._score(component, z_context)
        component.validity_score = score

        if score > 0.0:
            component.validity = ValidationStatus.VALID
            return 1
        else:
            component.validity = ValidationStatus.INVALID
            component.rejection_reason = reason
            return 0

    def _score(
        self,
        component: Component,
        z_context: Optional[ZContext],
    ) -> tuple[float, str]:
        """Return (score 0.0–1.0, rejection_reason)."""

        # ── Test 1: X completeness ────────────────────────────────────────────
        if not component.x_state.label or not component.x_state.label.strip():
            return 0.0, "No X-state declared: component has no deficit to resolve."

        # ── Test 2: Y completeness ────────────────────────────────────────────
        if not component.y_state.label or not component.y_state.label.strip():
            return 0.0, "No Y-state declared: component produces no resolution."

        # ── Test 3: X ≠ Y (actual conversion, not trivial identity) ───────────
        if component.x_state.label.strip().lower() == component.y_state.label.strip().lower():
            return 0.0, "X-state and Y-state are identical: no conversion occurs."

        # ── Test 4: Axiom alignment ───────────────────────────────────────────
        alignment = self._axiom_alignment(component)
        if alignment == 0.0:
            return (
                0.0,
                f"Component does not serve Axiom '{self.axiom.label}': "
                "no keyword or semantic overlap detected.",
            )

        # ── Test 5: Z-axis temporal coherence (optional) ─────────────────────
        z_bonus = 0.0
        if z_context is not None:
            z_bonus = self._z_coherence(component, z_context)

        # ── Composite score ───────────────────────────────────────────────────
        x_weight  = component.x_state.severity      # heavier deficit → more weight
        y_weight  = component.y_state.completeness   # fuller resolution → more weight
        base      = (x_weight + y_weight) / 2.0
        score     = min(1.0, base * alignment + z_bonus * 0.1)

        return score, ""

    def _axiom_alignment(self, component: Component) -> float:
        """
        Measure how well the component serves the Axiom.

        Returns 0.0 (none) → 1.0 (perfect alignment).
        Checks keyword overlap across axiom law/question and component fields.
        """
        if not self.axiom.keywords:
            # No explicit keywords — accept if axiom law text overlaps
            combined = (
                component.name + " " +
                component.description + " " +
                component.x_state.label + " " +
                component.y_state.label
            ).lower()
            axiom_words = set(
                (self.axiom.law + " " + self.axiom.question).lower().split()
            )
            comp_words  = set(combined.split())
            overlap     = axiom_words & comp_words
            if not overlap:
                return 0.0
            return min(1.0, len(overlap) / max(1, len(axiom_words) * 0.3))

        # Explicit keyword matching
        combined = (
            component.name + " " +
            component.description + " " +
            component.x_state.label + " " +
            component.y_state.label
        ).lower()
        hits = sum(1 for kw in self.axiom.keywords if kw.lower() in combined)
        return min(1.0, hits / max(1, len(self.axiom.keywords) * 0.5))

    def _z_coherence(self, component: Component, z_context: ZContext) -> float:
        """
        Z-axis temporal coherence bonus.

        Analyses the logic chain in both directions (forward: causal, backward:
        retroactive validation) to confirm the component's X→Y conversion is
        consistent with the chain's trajectory.
        """
        if not z_context.probability_vector:
            return 0.0

        vec = z_context.probability_vector

        if z_context.direction == AxisDirection.FORWARD:
            # Trend: probability should rise toward resolution
            trend = (vec[-1] - vec[0]) if len(vec) > 1 else 0.0
            return max(0.0, trend)

        if z_context.direction == AxisDirection.BACKWARD:
            # Inverted: validate backward — probability should have risen
            trend = (vec[0] - vec[-1]) if len(vec) > 1 else 0.0
            return max(0.0, trend)

        # BOTH — average forward and backward signals
        if len(vec) >= 2:
            fwd = max(0.0, vec[-1] - vec[0])
            bwd = max(0.0, vec[0] - vec[-1])
            return (fwd + bwd) / 2.0

        return 0.0


# ─── Nebraska System ──────────────────────────────────────────────────────────

class NebraskaSystem:
    """
    The complete Nebraska Generative System.

        System = A + ∑[ (Cᵢ + Kᵢ) | A ] · 𝕍ᵧ

    Usage:
        axiom = Axiom(label="Haunted House", law="Every space must prove danger",
                      keywords=["danger", "threat", "safety", "fear"])
        ngs = NebraskaSystem(axiom)

        component = Component(
            name="Jack-in-the-Box",
            component_type=ComponentType.CHARACTER,
            x_state=XState(label="Portable evil", severity=0.9),
            y_state=YState(label="Architect in residence", completeness=1.0),
        )
        gate_result = ngs.validate(component)  # returns 0 or 1
        system_output = ngs.build()            # returns the validated system
    """

    def __init__(self, axiom: Axiom) -> None:
        self.axiom        = axiom
        self.gate         = YAxisValidityConstraint(axiom)
        self.components:  list[Component]   = []
        self.z_contexts:  list[ZContext]    = []
        self.valid_sum:   list[Component]   = []
        self.invalid_sum: list[Component]   = []
        self.built:       bool              = False

    # ── Public API ────────────────────────────────────────────────────────────

    def add_component(self, component: Component) -> None:
        """Register a component for validation.  Does not validate yet."""
        component.validity = ValidationStatus.PENDING
        self.components.append(component)
        self.built = False

    def add_z_context(self, z_context: ZContext) -> None:
        """Attach a Z-axis temporal context to the system."""
        self.z_contexts.append(z_context)

    def validate(
        self,
        component: Component,
        z_context: Optional[ZContext] = None,
    ) -> int:
        """
        Apply 𝕍ᵧ to a single component.  Returns 1 (valid) or 0 (invalid).
        Does NOT add the component to the system — call add_component first.
        """
        ctx = z_context or (self.z_contexts[0] if self.z_contexts else None)
        return self.gate.gate(component, ctx)

    def build(self) -> dict[str, Any]:
        """
        Execute the full NGS formula.

        Validates all registered components, partitions into valid/invalid
        sets, and returns the completed narrative machine.
        """
        ctx = self.z_contexts[0] if self.z_contexts else None

        self.valid_sum   = []
        self.invalid_sum = []

        for component in self.components:
            gate_val = self.gate.gate(component, ctx)
            if gate_val == 1:
                self.valid_sum.append(component)
            else:
                self.invalid_sum.append(component)

        self.built = True

        return {
            "axiom": {
                "label":    self.axiom.label,
                "law":      self.axiom.law,
                "question": self.axiom.question,
                "domain":   self.axiom.domain,
            },
            "formula": "System = A + ∑[ (Cᵢ + Kᵢ) | A ] · 𝕍ᵧ",
            "components": {
                "total":   len(self.components),
                "valid":   len(self.valid_sum),
                "invalid": len(self.invalid_sum),
            },
            "valid_components": [
                _serialize_component(c) for c in self.valid_sum
            ],
            "invalid_components": [
                _serialize_component(c) for c in self.invalid_sum
            ],
            "z_contexts": [
                _serialize_z(z) for z in self.z_contexts
            ],
            "system_coherence": self._coherence_score(),
            "meaning_transmitted": len(self.valid_sum) > 0,
        }

    def story(self) -> str:
        """
        a/b = story — derive the narrative from the validated system.

        Returns a plain-text story skeleton built from valid components.
        The story is the ratio of resolution (Y) to deficit (X) across the
        system, under the Axiom's law.
        """
        if not self.built:
            self.build()

        if not self.valid_sum:
            return (
                f"[NGS] No valid components under Axiom '{self.axiom.label}'. "
                "System produces no story."
            )

        lines = [
            f"AXIOM: {self.axiom.law}",
            "",
            "STORY (a/b):",
        ]
        for i, comp in enumerate(self.valid_sum, 1):
            lines.append(
                f"  [{i}] {comp.name} ({comp.component_type.value}): "
                f"{comp.x_state.label} → {comp.y_state.label} "
                f"[𝕍ᵧ={comp.validity_score:.2f}]"
            )

        lines += [
            "",
            f"MEANING: {self.axiom.question or self.axiom.law}",
            f"UNDERSTANDING: {self._understanding()}",
        ]
        return "\n".join(lines)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _coherence_score(self) -> float:
        """System coherence = mean validity scores of valid components."""
        if not self.valid_sum:
            return 0.0
        return round(
            sum(c.validity_score for c in self.valid_sum) / len(self.valid_sum),
            4,
        )

    def _understanding(self) -> str:
        """Recursive pedagogy — understanding derived from meaning."""
        if not self.valid_sum:
            return "No understanding: system is empty."
        score = self._coherence_score()
        if score >= 0.85:
            return "High coherence — meaning transmitted with structural certainty."
        if score >= 0.60:
            return "Moderate coherence — meaning partially transmitted; some drift."
        return "Low coherence — meaning unstable; re-examine Axiom alignment."


# ─── Serialisation helpers ────────────────────────────────────────────────────

def _serialize_component(c: Component) -> dict[str, Any]:
    return {
        "name":             c.name,
        "type":             c.component_type.value,
        "x_state":          {"label": c.x_state.label, "severity": c.x_state.severity},
        "y_state":          {"label": c.y_state.label, "completeness": c.y_state.completeness},
        "description":      c.description,
        "validity":         c.validity.value,
        "validity_score":   round(c.validity_score, 4),
        "rejection_reason": c.rejection_reason,
        "metadata":         c.metadata,
    }


def _serialize_z(z: ZContext) -> dict[str, Any]:
    return {
        "chain_id":             z.chain_id,
        "direction":            z.direction.value,
        "probability_vector":   z.probability_vector,
        "history_len":          len(z.history),
        "future_len":           len(z.future),
        "inverted":             z.inverted,
        "intervention_active":  z.intervention_active,
        "timestamp":            z.timestamp,
    }


# ─── Convenience factory ──────────────────────────────────────────────────────

def quick_validate(
    axiom_label: str,
    axiom_law: str,
    components_raw: list[dict[str, Any]],
    keywords: Optional[list[str]] = None,
    z_vector: Optional[list[float]] = None,
) -> dict[str, Any]:
    """
    One-shot helper — build an NGS system and return validation results.

    components_raw: list of dicts with keys:
        name, type ("character"|"kinetic"), x_label, x_severity,
        y_label, y_completeness, description (optional)
    """
    axiom = Axiom(
        label=axiom_label,
        law=axiom_law,
        keywords=keywords or [],
    )
    ngs = NebraskaSystem(axiom)

    if z_vector:
        ngs.add_z_context(ZContext(
            chain_id=f"{axiom_label}_z",
            probability_vector=z_vector,
        ))

    for raw in components_raw:
        comp = Component(
            name=raw["name"],
            component_type=ComponentType(raw.get("type", "character")),
            x_state=XState(
                label=raw.get("x_label", ""),
                description=raw.get("x_description", ""),
                severity=float(raw.get("x_severity", 0.5)),
            ),
            y_state=YState(
                label=raw.get("y_label", ""),
                description=raw.get("y_description", ""),
                completeness=float(raw.get("y_completeness", 1.0)),
            ),
            description=raw.get("description", ""),
            metadata=raw.get("metadata", {}),
        )
        ngs.add_component(comp)

    result = ngs.build()
    result["story"] = ngs.story()
    return result

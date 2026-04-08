"""
Nebraska Protocols v2.0 — Runtime Contract for Structured Narrative Generation

FORMULA:
    a / b = story → meaning → understanding

    a  =  potential  (deficit, unresolved state, open wound)
    b  =  constraint (governing Axiom — makes resolution inevitable)
    /  =  the lawful conversion (story is the measurable difference)

    story   → encountered by a reader/system   → meaning
    meaning → internalized and re-applied       → understanding
    understanding is RECURSIVE PEDAGOGY: it feeds back as new potential.
    Meaning cannot transmit without BOTH a (potential) and b (constraint).
    If b = 0, the division is undefined. There is no story. There is only noise.

PRIME EQUATION (Nebraska Identity):
    𝕍ᵧ ≡ T(z) ≡ M(t) ≡ ∇(understanding)

CONTRACT (enforced at every gate):
    "State the X. Name the Y. Prove the conversion serves the Law. Otherwise, reject."

─────────────────────────────────────────────────────────────────────────────
UNIVERSAL NARRATIVE QUADRIVIUM — The Fourfold Test (Ch. 7.3 / 2.0 §2)

  Every narrative component must pass all four invariants.  Failure at any
  one returns ZERO — because coherence is MULTIPLICATIVE, not additive.
  A great scene attached to a memory contradiction does not produce a slightly-
  flawed story.  It produces a story that does not hold.

  𝕍ᵧ  — Validity             X→Y under Axiom, or component self-deletes
  T(z) — Temporal Coherence  T(z) × T(1/z) ≥ 1  (forward AND backward)
  M(t) — Memory Consistency  Σ[Patternᵢ × Contextᵢ] / Timeᵢ
  ∇    — Learning Gradient   ∇(understanding) ≥ 1 (never regress)

NOTE ON THE Z-AXIS (2.0 spec):
  The Z-axis IS the temporal axis.  It allows the system to look in BOTH
  directions of a logic chain — not just guessing forward.
  T(z)   = forward pass  (standard inference: does this flow from what precedes?)
  T(1/z) = backward pass (retroactive: does this remain valid read from the end?)
  Together they produce DETERMINISTIC STRUCTURE rather than probabilistic drift.

QUANTUM COHERENCE STANDARD:
  QCS = 𝕍ᵧ × T(z) × M(t) × ∇ × S
  S = Substrate Independence Score [0,1]
  QCS = 1  → perfect coherence
  QCS ≥ 0.9 → production-ready (Nebraska Bronze)
  QCS < 0.7 → quarantine required

AXIS STACK (generation → validation order):
  X-Axis   → Expansion / generation (diverge freely)
  Y-Axis   → Primary Gate (𝕍ᵧ: X→Y under Axiom)
  Y²-Axis  → Thematic Rail (dominant theme permeates every atom)
  Y³-Axis  → Context Flag (semantic consistency with established context)
  Z-Axis   → Meta / Premise validity (First Thing carries built-in deficit)
  Z-Invert → Adversarial Flip (remove component — does logic snap?)
  Z-Proof  → Inverted Proof (remove axiom — does police report remain?)
  Intervene→ Governor / Structure Veto ("no is where structure lives")
  Newton QC→ Final Invariant Checksum via QCS
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ─── Formula constants ────────────────────────────────────────────────────────

FORMULA = "a/b = story → meaning → understanding"
PRIME_EQUATION = "𝕍ᵧ ≡ T(z) ≡ M(t) ≡ ∇(understanding)"
CONTRACT = "State the X. Name the Y. Prove the conversion serves the Law. Otherwise, reject."
RECURSIVE_LAW = (
    "Understanding is recursive pedagogy. "
    "Meaning cannot transmit without both a (potential) and b (constraint)."
)

# ─── Certification thresholds (Nebraska 2.0 §5.2) ────────────────────────────

QCS_THRESHOLDS = {
    "platinum": 0.99,
    "gold":     0.90,
    "silver":   0.80,
    "bronze":   0.70,
}


def qcs_certification(qcs: float) -> str:
    for level, threshold in QCS_THRESHOLDS.items():
        if qcs >= threshold:
            return f"Nebraska {level.capitalize()}"
    return "Quarantine required (QCS < 0.70)"


# ─── Fear Axioms ─────────────────────────────────────────────────────────────

FEAR_AXIOMS: dict[str, str] = {
    "existential":    "Every existence harbors a void that demands confrontation",
    "claustrophobia": "Space contracts until escape becomes its own prison",
    "social":         "Connection conceals the sharpest edge of isolation",
    "cosmic":         "The universe's indifference is its most deliberate cruelty",
    "predator":       "Hunter and hunted are reflections in the same dark mirror",
    "abandonment":    "Absence reshapes us more profoundly than presence ever could",
    "body_horror":    "The body is the first and most intimate betrayer",
}

DEFAULT_AXIOM = "Every story is a deficit demanding resolution under its own law"

# ─── Pattern libraries ────────────────────────────────────────────────────────

# X-indicators: signal a deficit / instability is present
_X_PATTERNS = [
    r"\b(something|nothing|no one|nowhere)\b",
    r"\b(watch(?:es|ing)|follow(?:s|ing)|wait(?:s|ing)|hunt(?:s|ing)|com(?:es|ing))\b",
    r"\b(missing|gone|lost|empty|absent|without|cannot|never|no longer)\b",
    r"\b(darkness|shadow|void|silence|unknown|uncertain|unresolved)\b",
    r"\b(wrong|broken|impossible|strange|distorted)\b",
    r"\b(danger|threat|fear|dread|terror|horror)\b",
]

# Y-indicators: signal transformation / escalation / revelation
_Y_PATTERNS = [
    r"\b(realise?s?|know(?:s|n)|understand(?:s)?|discover(?:s)?|see(?:s|n)|feel(?:s)?)\b",
    r"\b(become?s?|is now|has become|turned|changed|transformed)\b",
    r"\b(deeper|closer|louder|more|growing|spreading|escalat(?:es|ing))\b",
    r"\b(reveal(?:s|ed)?|show(?:s|n)|expose(?:s|d)?|uncover(?:s|ed)?)\b",
    r"\b(you have been|you will|you are|you were)\b",
    r"\b(begins?|starts?|awakens?|stirs?)\b",
]

# Thematic Y² markers: pervasive dread-frequency words
_THEMATIC_PATTERNS = [
    r"\b(you|your)\b",           # second-person immersion
    r"\b(always|never|every|each|still)\b",  # permanence markers
    r"\bthe\b",                  # definite article (specificity)
]

# Convenience word-tokenizer (no dependencies)
_WORD_RE = re.compile(r"[a-z]+")


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


# ─── Data structures ─────────────────────────────────────────────────────────

@dataclass
class NarrativeComponent:
    """
    A single story element carrying its full Quadrivium validation state.

    Formula role: one (Cᵢ + Kᵢ) term in System = A + ∑[(Cᵢ+Kᵢ)|A] · 𝕍ᵧ
    """
    name: str
    content: str

    # Y-axis
    x: str = ""
    y: str = ""
    vy: int = -1              # 𝕍ᵧ: -1=unvalidated, 0=invalid, 1=valid

    # Y²-axis (Thematic Rail)
    y2_pass: bool = False

    # Fourfold Test scores [0, 1]
    t_score: float = -1.0    # T(z) temporal coherence
    m_score: float = -1.0    # M(t) memory consistency
    grad_score: float = -1.0 # ∇ learning gradient

    # Quantum Coherence Standard (multiplicative product)
    qcs: float = -1.0

    # Rejection audit
    rejection_reason: str = ""

    def is_valid(self) -> bool:
        """Component passes when 𝕍ᵧ=1, Y² passes, and QCS is meaningful."""
        return self.vy == 1 and self.y2_pass

    def summary(self) -> dict:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "vy": self.vy,
            "y2_pass": self.y2_pass,
            "t_score": round(self.t_score, 3) if self.t_score >= 0 else None,
            "m_score": round(self.m_score, 3) if self.m_score >= 0 else None,
            "grad_score": round(self.grad_score, 3) if self.grad_score >= 0 else None,
            "qcs": round(self.qcs, 4) if self.qcs >= 0 else None,
            "certification": qcs_certification(self.qcs) if self.qcs >= 0 else None,
            "valid": self.is_valid(),
            "rejection_reason": self.rejection_reason,
            "content_preview": self.content[:100],
        }


@dataclass
class NebraskaAudit:
    """Complete audit trail produced by running the full axis stack."""
    axiom: str
    formula: str = FORMULA
    prime_equation: str = PRIME_EQUATION

    components_generated: int = 0
    components_y_valid: int = 0
    components_y2_valid: int = 0
    y3_coherent: bool = False
    z_premise_valid: bool = False
    z_inversion_survivors: int = 0
    z_inverted_proof: Optional[bool] = None   # True = axiom was load-bearing
    newton_qc_pass: bool = False
    mean_qcs: float = 0.0
    certification: str = "Uncertified"
    intervention_count: int = 0
    governor_vetoes: int = 0

    rejected: list = field(default_factory=list)
    validated: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "axiom": self.axiom,
            "formula": self.formula,
            "prime_equation": self.prime_equation,
            "components_generated": self.components_generated,
            "components_y_valid": self.components_y_valid,
            "components_y2_valid": self.components_y2_valid,
            "y3_coherent": self.y3_coherent,
            "z_premise_valid": self.z_premise_valid,
            "z_inversion_survivors": self.z_inversion_survivors,
            "z_inverted_proof": self.z_inverted_proof,
            "newton_qc_pass": self.newton_qc_pass,
            "mean_qcs": round(self.mean_qcs, 4),
            "certification": self.certification,
            "intervention_count": self.intervention_count,
            "governor_vetoes": self.governor_vetoes,
            "rejected": self.rejected,
            "validated": self.validated,
        }


# ─── Core Protocol Class ─────────────────────────────────────────────────────

class NebraskaProtocol:
    """
    Nebraska Generative System (NGS) v2.0 — Universal Narrative Quadrivium.

    Every axis is a phase transition — the story state that enters is not
    the same as the state that exits.  Validation IS generation.

    Quick start:
        proto = NebraskaProtocol.from_fear_type("existential")
        survivors, qc = proto.run_full_pipeline(
            candidates=["fragment1", ...],
            narrative_history=session["narrative_history"],
            premise="haunted house",
        )
    """

    def __init__(self, axiom: str):
        self.axiom = axiom
        self.audit = NebraskaAudit(axiom=axiom)

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def from_fear_type(cls, fear_type: str, experience_type: str = "solo") -> "NebraskaProtocol":
        axiom = FEAR_AXIOMS.get(fear_type, DEFAULT_AXIOM)
        if experience_type == "multiplayer":
            axiom += " — shared witnesses compound the law"
        return cls(axiom)

    # ── X-Axis: Generation / Expansion Layer ─────────────────────────────────

    def x_axis_generate(
        self,
        candidates: list[str],
        names: Optional[list[str]] = None,
    ) -> list[NarrativeComponent]:
        """
        X-Axis: divergent, generative phase.  Accept all without filtering.
        'Ask what could exist in this story given the Axiom.'  Nothing is
        rejected here — brainstorm every possibility freely.  vy=-1 for all.
        """
        components = [
            NarrativeComponent(
                name=names[i] if (names and i < len(names)) else f"component_{i + 1}",
                content=text,
            )
            for i, text in enumerate(candidates)
        ]
        self.audit.components_generated = len(components)
        return components

    # ── Y-Axis: Validity — Primary Gate (𝕍ᵧ) ────────────────────────────────

    def y_axis_validate(self, components: list[NarrativeComponent]) -> list[NarrativeComponent]:
        """
        Y-Axis: primary filter.  Extract X and Y; ask 'Does X→Y under Axiom?'

        𝕍ᵧ = 1 → retained     (component performs lawful conversion)
        𝕍ᵧ = 0 → rejected     (decorative element — self-deletes from system)
        """
        for comp in components:
            x, y = self._extract_xy(comp.content)
            comp.x = x
            comp.y = y

            if not x:
                comp.vy = 0
                comp.rejection_reason = "Y-gate: X undefined — no deficit identified"
            elif not y:
                comp.vy = 0
                comp.rejection_reason = "Y-gate: Y undefined — no transformation found"
            elif not self._conversion_serves_axiom(x, y):
                comp.vy = 0
                comp.rejection_reason = (
                    f"Y-gate: conversion ({x[:30]}→{y[:30]}) does not serve Axiom"
                )
            else:
                comp.vy = 1

        valid = [c for c in components if c.vy == 1]
        rejected = [c for c in components if c.vy == 0]
        self.audit.components_y_valid = len(valid)
        self.audit.rejected.extend(
            {"name": c.name, "reason": c.rejection_reason} for c in rejected
        )
        return components

    # ── Y²-Axis: Thematic Rail ────────────────────────────────────────────────

    def y2_axis_check(self, components: list[NarrativeComponent]) -> list[NarrativeComponent]:
        """
        Y²-Axis: the Thematic Rail and clean-conversion check.

        From Ch. 7.5: 'The governing theme is not a lesson delivered at the end.
        It is a texture present in every atom of the work.'

        Failure modes:
          • X is vague / undefined
          • Y does not logically follow from X (non-sequitur)
          • Thematic frequency of Axiom domain is absent from content
        """
        for comp in components:
            if comp.vy != 1:
                continue

            issues: list[str] = []

            if len(comp.x.split()) < 2:
                issues.append("X too vague (fewer than 2 words)")
            if len(comp.y.split()) < 2:
                issues.append("Y too vague (fewer than 2 words)")
            if not self._y_follows_from_x(comp.x, comp.y):
                issues.append("Y does not logically follow from X")
            if not self._thematic_rail_passes(comp.content):
                issues.append("Y²-Thematic Rail: dominant thematic frequency absent")

            if issues:
                comp.y2_pass = False
                comp.vy = 0
                comp.rejection_reason = "Y²-gate: " + "; ".join(issues)
                self.audit.rejected.append({"name": comp.name, "reason": comp.rejection_reason})
            else:
                comp.y2_pass = True

        self.audit.components_y2_valid = sum(1 for c in components if c.y2_pass)
        return components

    # ── Y³-Axis: Context Flag / Integration Coherence ────────────────────────

    def y3_axis_integrate(
        self,
        components: list[NarrativeComponent],
        narrative_history: Optional[list[str]] = None,
    ) -> bool:
        """
        Y³-Axis: Context Flag and system-level coherence.

        From Ch. 7.5: 'When a character speaks in a way semantically inconsistent
        with the established emotional or factual context, the flag triggers.'

        Checks:
          1. Every valid component has stated X and Y (can link to chain)
          2. Component domains don't contradict established context (history)
        """
        valid = [c for c in components if c.is_valid()]

        if not valid:
            self.audit.y3_coherent = False
            return False

        # All components must have explicit X and Y
        chain_ok = all(c.x and c.y for c in valid)

        # Context flag: no component's Y-domain should contradict the Axiom
        context_ok = True
        if narrative_history:
            for comp in valid:
                if self._context_flag_triggered(comp, narrative_history):
                    context_ok = False
                    comp.rejection_reason = (
                        "Y³-Context Flag: component semantically inconsistent "
                        "with established narrative context"
                    )
                    comp.vy = 0
                    self.audit.rejected.append(
                        {"name": comp.name, "reason": comp.rejection_reason}
                    )

        self.audit.y3_coherent = chain_ok and context_ok
        return self.audit.y3_coherent

    # ── Fourfold Test: Universal Narrative Quadrivium ─────────────────────────

    def fourfold_test(
        self,
        component: NarrativeComponent,
        narrative_history: Optional[list[str]] = None,
    ) -> float:
        """
        The four-part minimum viable check (Ch. 7.3 / Nebraska 2.0 §2).

        Coherence is MULTIPLICATIVE — any zero zeros the entire score:
          QCS = 𝕍ᵧ × T(z) × M(t) × ∇ × S

        Returns QCS [0, 1].  Sets component.t_score, .m_score, .grad_score, .qcs.
        """
        # 1. Validity (𝕍ᵧ)
        vy = 1.0 if (component.vy == 1 and component.y2_pass) else 0.0

        # 2. Temporal Coherence T(z) — bidirectional Z-axis
        t = self._temporal_coherence(component, narrative_history)
        component.t_score = t

        # 3. Memory Consistency M(t)
        m = self._memory_consistency(component, narrative_history)
        component.m_score = m

        # 4. Learning Gradient ∇
        grad = self._learning_gradient(component, narrative_history)
        component.grad_score = grad

        # S = Substrate Independence (fixed at 1.0 — single substrate)
        s = 1.0

        qcs = vy * t * m * grad * s
        component.qcs = round(qcs, 4)
        return component.qcs

    # ── Z-Axis: Meta-Evaluation / Premise Validity ────────────────────────────

    def z_axis_meta(self, premise: str) -> bool:
        """
        Z-Axis: does the premise (First Thing) carry a built-in deficit?

        'If your initial story concept doesn't imply a deficit that needs
        resolution, it's not a First Thing — it's a prop.'

        A premise without X has no narrative engine — no tension to resolve.
        The Z-axis ensures the very premise is structural, not decorative.
        """
        has_deficit = self._premise_implies_deficit(premise)
        self.audit.z_premise_valid = has_deficit
        return has_deficit

    # ── Z-Axis Inversion: Adversarial Flip Test ───────────────────────────────

    def z_axis_invert(self, components: list[NarrativeComponent]) -> list[NarrativeComponent]:
        """
        Z-Inversion: remove each component — does the story snap?

        'Swap them, and the logic chain snaps.' — only if it truly snaps
        does the component earn its place.

        Components whose removal leaves the story intact are not load-bearing.
        Applied only when ≥3 valid components exist.
        """
        valid = [c for c in components if c.is_valid()]

        if len(valid) < 3:
            self.audit.z_inversion_survivors = len(valid)
            return valid

        indispensable: list[NarrativeComponent] = []

        for i, comp in enumerate(valid):
            others = valid[:i] + valid[i + 1:]
            if not self._story_works_without(comp, others):
                indispensable.append(comp)
            else:
                comp.rejection_reason = (
                    "Z-inversion: not load-bearing — story survives component removal"
                )
                comp.vy = 0
                self.audit.rejected.append({"name": comp.name, "reason": comp.rejection_reason})

        self.audit.z_inversion_survivors = len(indispensable)
        return indispensable

    # ── Z-Inverted Proof: Remove-Axiom Test ──────────────────────────────────

    def z_inverted_proof(self, components: list[NarrativeComponent]) -> bool:
        """
        Z-Inverted Proof (Ch. 7.6): strip the Axiom and examine what remains.

        'If what remains is a police report — facts with no weight, no necessity
        — the system was working.  The axiom was the thing that made the sequence
        into literature.'

        If the story STILL works without the Axiom, the Axiom was decorative.
        Returns True if the Axiom was genuinely load-bearing (system was real).
        """
        valid = [c for c in components if c.is_valid()]
        if not valid:
            self.audit.z_inverted_proof = False
            return False

        # Without the axiom, do conversions still hold via the axiom's vocabulary?
        axiom_words = _words(self.axiom) - {"every", "under", "their", "there", "where", "that"}

        # Count how many valid components rely on axiom-domain vocabulary for their conversion
        axiom_dependent = sum(
            1 for c in valid
            if axiom_words & (_words(c.x) | _words(c.y))
        )

        # If ≥ half the valid components depend on axiom vocabulary, the axiom was real
        axiom_was_real = axiom_dependent >= max(1, len(valid) // 2)
        self.audit.z_inverted_proof = axiom_was_real
        return axiom_was_real

    # ── Governor: Executive Governance Mechanism ─────────────────────────────

    def governor(self, component: NarrativeComponent) -> bool:
        """
        The Governor — the 'stop-the-machine' function (Ch. 7.4).

        'The Governor is the part of the system that stands at the table and
        refuses to let the narrative introduce coincidence, accident, or
        convenience as resolution.'

        It enforces b (constraint).  Without it, b becomes negotiable and
        the equation collapses.

        Returns True (VETO — route back) if the component:
          • Cannot derive its Y from prior established conditions (arbitrary)
          • Has Y that appears convenient rather than structurally necessary
          • Fails basic structural integrity
        """
        # Arbitrary resolution: Y appeared without a causal X
        arbitrary = not component.x or not component.y

        # Convenience test: Y is a positive resolution in a horror/dread context
        # (convenience would be safety/relief where the axiom demands escalation)
        convenience_words = {"safe", "saved", "escape", "free", "happy", "relief", "calm", "peace"}
        y_words = _words(component.y)
        convenience_veto = bool(y_words & convenience_words) and "prison" not in y_words

        # Structural minimum
        structural_fail = len(component.content.strip()) < 15

        if arbitrary or structural_fail:
            self.audit.governor_vetoes += 1
            return True  # VETO

        if convenience_veto and self.axiom:
            # Only veto convenience if the Axiom demands continued tension
            tension_axioms = {
                "void", "prison", "mirror", "cruelty", "betrayer", "isolation"
            }
            if _words(self.axiom) & tension_axioms:
                self.audit.governor_vetoes += 1
                return True  # VETO — convenience resolution violates tension Axiom

        return False  # passes Governor

    # ── Axis of Intervention: Structure Veto ─────────────────────────────────

    def axis_intervention(self, component: NarrativeComponent) -> bool:
        """
        Axis of Intervention: immediate veto for off-structure elements.

        'No is where structure lives.'

        Triggers on: decorative, no transformation, already-failed components.
        Caller should reject and re-run or replace.
        """
        triggers = [
            len(component.content.strip()) < 15,
            not any(ch.isalpha() for ch in component.content),
            component.vy == 0,
        ]
        if any(triggers):
            self.audit.intervention_count += 1
            return True
        return False

    # ── Newton's Apple QC Checksum ────────────────────────────────────────────

    def newton_qc(
        self,
        components: list[NarrativeComponent],
        narrative_history: Optional[list[str]] = None,
    ) -> dict:
        """
        Final Invariant Check — 'Newton's Apple' test.

        The story's logic must fall predictably into place every time, like
        gravity.  Given the same Axiom and components, the outcome is inevitable.

        This check runs the Fourfold Test on every valid component and computes
        the mean QCS.  Any invariant failure collapses the score to zero for
        that component (multiplicative, not additive).

        Invariants (non-negotiable):
          1. Axiom fixed — the law of physics for this story
          2. Every component states X and Y
          3. Each Y clearly follows from X
          4. Each conversion serves the Axiom
          5. QCS ≥ 0.70 for at least one component (Bronze certification)
        """
        valid = [c for c in components if c.is_valid()]
        failures: list[str] = []
        qcs_scores: list[float] = []

        for comp in valid:
            if not comp.x:
                failures.append(f"{comp.name}: X undefined")
            if not comp.y:
                failures.append(f"{comp.name}: Y undefined")
            if comp.x and comp.y and not self._y_follows_from_x(comp.x, comp.y):
                failures.append(f"{comp.name}: Y does not follow from X")
            if comp.x and comp.y and not self._conversion_serves_axiom(comp.x, comp.y):
                failures.append(f"{comp.name}: conversion does not serve Axiom")

            # Run Fourfold Test for QCS score
            qcs = self.fourfold_test(comp, narrative_history)
            qcs_scores.append(qcs)

        mean_qcs = (sum(qcs_scores) / len(qcs_scores)) if qcs_scores else 0.0
        passed = len(failures) == 0 and len(valid) > 0 and mean_qcs >= QCS_THRESHOLDS["bronze"]

        self.audit.newton_qc_pass = passed
        self.audit.mean_qcs = mean_qcs
        self.audit.certification = qcs_certification(mean_qcs)
        self.audit.validated = [c.summary() for c in valid]

        return {
            "pass": passed,
            "axiom": self.axiom,
            "formula": FORMULA,
            "valid_components": len(valid),
            "mean_qcs": round(mean_qcs, 4),
            "certification": self.audit.certification,
            "failures": failures,
            "audit": self.audit.to_dict(),
        }

    # ── Full Pipeline ─────────────────────────────────────────────────────────

    def run_full_pipeline(
        self,
        candidates: list[str],
        names: Optional[list[str]] = None,
        premise: str = "",
        narrative_history: Optional[list[str]] = None,
        apply_z_inversion: bool = False,
        apply_z_proof: bool = False,
    ) -> tuple[list[NarrativeComponent], dict]:
        """
        Execute the full axis stack in order and return (valid_components, qc_report).

        Order:
          Z-meta → X-gen → Y-validate → Y²-check → Y³-context
          → [Z-invert] → [Z-proof] → Newton QC (Fourfold)
        """
        if premise:
            self.z_axis_meta(premise)

        components = self.x_axis_generate(candidates, names)
        self.y_axis_validate(components)
        self.y2_axis_check(components)
        self.y3_axis_integrate(components, narrative_history)

        if apply_z_inversion:
            self.z_axis_invert(components)

        if apply_z_proof:
            self.z_inverted_proof(components)

        qc = self.newton_qc(components, narrative_history)
        survivors = [c for c in components if c.is_valid()]
        return survivors, qc

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _extract_xy(self, content: str) -> tuple[str, str]:
        """Heuristic extraction of X (deficit) and Y (resolution) from text."""
        cl = content.lower()

        def _find_context(patterns: list[str], text: str, window: int = 30) -> str:
            for pattern in patterns:
                m = re.search(pattern, text)
                if m:
                    start = max(0, m.start() - window)
                    end = min(len(text), m.end() + window)
                    return text[start:end].strip()[:60]
            return ""

        return _find_context(_X_PATTERNS, cl), _find_context(_Y_PATTERNS, cl)

    def _conversion_serves_axiom(self, x: str, y: str) -> bool:
        """Does the X→Y conversion serve the governing Axiom?"""
        axiom_words = {
            w for w in _words(self.axiom)
            if len(w) > 4 and w not in {"every", "under", "their", "there", "where"}
        }
        combined = _words(x) | _words(y)
        escalation = {
            "deeper", "closer", "louder", "growing", "spreading",
            "reveals", "becomes", "realise", "realize", "discover",
            "understand", "know", "begin", "awaken",
        }
        return bool(axiom_words & combined) or bool(escalation & combined)

    def _y_follows_from_x(self, x: str, y: str) -> bool:
        """Y must be distinct from X (transformation occurred, not stasis)."""
        if not x or not y:
            return False
        return x.strip().lower() != y.strip().lower()

    def _thematic_rail_passes(self, content: str) -> bool:
        """Y²: Is the dominant thematic frequency present in the content?"""
        cl = content.lower()
        hits = sum(
            1 for p in _THEMATIC_PATTERNS if re.search(p, cl)
        )
        return hits >= 1

    def _context_flag_triggered(
        self,
        comp: NarrativeComponent,
        narrative_history: list[str],
    ) -> bool:
        """
        Y³ Context Flag: does this component contradict established context?

        Checks for semantic conflict between the component's content and the
        dominant vocabulary of the narrative history.
        """
        if not narrative_history:
            return False

        # Build established vocabulary from last 5 history entries
        recent = " ".join(narrative_history[-5:]).lower()
        established = _words(recent)

        # Anti-pattern: component uses resolution/safety vocabulary while
        # established context is firmly in dread territory
        dread_domain = {
            "shadow", "watching", "follow", "cannot", "never", "void",
            "darkness", "silence", "wrong", "broken", "impossible",
        }
        safety_domain = {"safe", "bright", "happy", "free", "warm", "peaceful"}

        established_in_dread = bool(established & dread_domain)
        comp_in_safety = bool(_words(comp.content) & safety_domain)

        # Flag only when established context is clearly dread AND component breaks it
        return established_in_dread and comp_in_safety

    def _temporal_coherence(
        self,
        component: NarrativeComponent,
        narrative_history: Optional[list[str]],
    ) -> float:
        """
        T(z): Temporal Coherence — bidirectional Z-axis validation.

        T(z)   = forward pass:  does this component flow from what precedes it?
        T(1/z) = backward pass: does this component remain valid read from the end?
        Together: T(z) × T(1/z) — the Z-axis looks in BOTH directions.

        Returns score in [0, 1].
        """
        if not narrative_history:
            # No history → first component → full forward coherence (baseline 0.85)
            return 0.85

        # Forward pass T(z): does this fragment continue from established vocabulary?
        recent_words = _words(" ".join(narrative_history[-3:]))
        comp_words = _words(component.content)

        # Word overlap with recent history (continuity signal)
        overlap = len(recent_words & comp_words)
        # Normalise: 3+ overlapping content words = strong continuity
        content_words_recent = recent_words - {"the", "a", "an", "of", "in", "to", "and", "it"}
        t_forward = min(1.0, overlap / max(1, len(content_words_recent) * 0.15))
        t_forward = max(0.4, t_forward)  # floor: novel fragments are valid too

        # Backward pass T(1/z): does this fragment not contradict the axiom
        # when read as if it were the END of the story?
        axiom_words = _words(self.axiom)
        # A fragment whose X/Y domain overlaps with the axiom is valid backwards
        xy_domain = _words(component.x + " " + component.y)
        t_backward = 0.8 if (axiom_words & xy_domain) else 0.6

        # Combined bidirectional score
        return round(min(1.0, (t_forward + t_backward) / 2), 4)

    def _memory_consistency(
        self,
        component: NarrativeComponent,
        narrative_history: Optional[list[str]],
    ) -> float:
        """
        M(t): Memory Consistency — current patterns align with remembered patterns.

        'A character cannot be afraid of fire in scene three if the story
        has already shown them unafraid of it in scene one, unless the story
        has also shown why that changed.'

        Returns score in [0, 1].
        """
        if not narrative_history:
            return 0.9  # no memory to conflict with

        # Check if the component's fear-domain vocabulary is consistent
        # with the fear type embedded in the Axiom
        axiom_words = _words(self.axiom)
        comp_words = _words(component.content)

        # Positive signal: component shares vocabulary with axiom domain
        domain_match = len(axiom_words & comp_words) / max(1, len(axiom_words))

        # Negative signal: component introduces vocabulary that contradicts
        # the established narrative memory (safety in dread context, etc.)
        history_words = _words(" ".join(narrative_history))
        contradiction_words = {"safe", "calm", "bright", "joy", "peace", "free"}
        dread_established = bool(history_words & {
            "shadow", "watching", "void", "darkness", "unknown", "cannot"
        })

        contradiction_penalty = 0.0
        if dread_established and (comp_words & contradiction_words):
            contradiction_penalty = 0.3

        score = max(0.0, min(1.0, 0.6 + domain_match * 0.4 - contradiction_penalty))
        return round(score, 4)

    def _learning_gradient(
        self,
        component: NarrativeComponent,
        narrative_history: Optional[list[str]],
    ) -> float:
        """
        ∇: Learning Gradient — understanding must increase or be conserved.

        'A scene that ends with the audience knowing exactly what they knew
        when it began has failed this test.'

        High novelty (low overlap with history) → high ∇.
        Near-repetition → ∇ approaches 0.

        Returns score in [0, 1].
        """
        if not narrative_history:
            return 1.0  # first component — maximum novelty

        comp_words = _words(component.content)
        # Compare against recent history
        recent_text = " ".join(narrative_history[-5:])
        history_words = _words(recent_text)

        content_words = comp_words - {"the", "a", "an", "of", "in", "to", "and", "it", "is", "was"}
        if not content_words:
            return 0.5

        # Overlap ratio: high overlap = repetition = low gradient
        overlap_ratio = len(content_words & history_words) / len(content_words)
        # Invert: novel content scores high
        grad = max(0.2, 1.0 - overlap_ratio * 0.7)
        return round(grad, 4)

    def _check_chain_coherence(self, components: list[NarrativeComponent]) -> bool:
        """Y³: do valid components form a coherent causal chain?"""
        if not components:
            return False
        return all(c.x and c.y for c in components)

    def _premise_implies_deficit(self, premise: str) -> bool:
        """Z-axis: does the premise contain an implied deficit?"""
        cl = premise.lower()
        deficit_words = [
            "haunt", "fear", "horror", "terror", "dark", "unknown", "lost",
            "danger", "threat", "monster", "ghost", "curse", "doom", "dread",
            "nightmare", "shadow", "void", "abyss", "escape", "trap", "hunt",
            "existential", "claustro", "cosmic", "predator", "abandon", "body",
            "strange", "wrong", "missing", "silence", "watch", "follow",
        ]
        return any(word in cl for word in deficit_words)

    def _story_works_without(
        self,
        comp: NarrativeComponent,
        others: list[NarrativeComponent],
    ) -> bool:
        """Z-inversion: does the remaining story function without this component?"""
        if not others:
            return False
        comp_x_words = _words(comp.x)
        for other in others:
            if comp_x_words & _words(other.y):
                return True  # another component already covers this deficit
        return False

"""
Nebraska Protocols — Runtime Contract for Structured Narrative Generation

Implements the Nebraska Generative System (NGS) axis stack:

  X-Axis   : Generation / Expansion Layer  (diverge — brainstorm without judgment)
  Y-Axis   : Validation / Primary Gate     (𝕍ᵧ — X→Y under Axiom, or reject)
  Y²-Axis  : Second-Order Validity         (clean conversions — no weasel logic)
  Y³-Axis  : Integration Validity          (system coherence — chain composes)
  Z-Axis   : Meta-Evaluation              (premise carries built-in deficit)
  Z-Invert : Adversarial Flip Test         (remove each element — does story snap?)
  Intervene: Structure Governor            ("no is where structure lives")
  Newton QC: Final Invariant Check         (a/b = story; story = meaning)

Formula:
  story = a / b    where  a = resolution state (Y)
                          b = deficit state    (X)
  Meaning is produced when the system proves it moved from X → Y under Axiom
  without cheating on logic.

Contract (enforced at every gate):
  "State the X. Name the Y. Prove the conversion serves the Law. Otherwise, reject."
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ─── Fear Axioms ─────────────────────────────────────────────────────────────
# The governing law extracted from the fear profile.  Every narrative operation
# must occur "under the Axiom's authority" — either upholding or testing it.

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

# X-indicator patterns: words that signal a deficit / instability is present
_X_PATTERNS = [
    r"\b(something|nothing|no one|nowhere)\b",
    r"\b(watch(?:es|ing)|follow(?:s|ing)|wait(?:s|ing)|hunt(?:s|ing)|com(?:es|ing))\b",
    r"\b(missing|gone|lost|empty|absent|without|cannot|never|no longer)\b",
    r"\b(darkness|shadow|void|silence|unknown|uncertain|unresolved)\b",
    r"\b(wrong|broken|impossible|strange|wrong|distorted)\b",
    r"\b(danger|threat|fear|dread|terror|horror)\b",
]

# Y-indicator patterns: words that signal transformation / escalation / revelation
_Y_PATTERNS = [
    r"\b(realise?s?|know(?:s|n)|understand(?:s)?|discover(?:s)?|see(?:s|n)|feel(?:s)?)\b",
    r"\b(become?s?|is now|has become|turned|changed|transformed)\b",
    r"\b(deeper|closer|louder|more|growing|spreading|escalat(?:es|ing))\b",
    r"\b(reveal(?:s|ed)?|show(?:s|n)|expose(?:s|d)?|uncover(?:s|ed)?)\b",
    r"\b(you have been|you will|you are|you were)\b",
    r"\b(begins?|starts?|awakens?|stirs?)\b",
]


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class NarrativeComponent:
    """A single story element with its X (deficit) → Y (resolution) conversion."""
    name: str
    content: str
    x: str = ""                # deficit state — what is wrong / missing
    y: str = ""                # resolution state — what the component delivers
    vy: int = -1               # 𝕍ᵧ score: -1=unvalidated, 0=invalid, 1=valid
    y2_pass: bool = False      # second-order validity passed
    rejection_reason: str = "" # why this component was rejected (if any)

    def is_valid(self) -> bool:
        return self.vy == 1 and self.y2_pass

    def summary(self) -> dict:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "vy": self.vy,
            "y2_pass": self.y2_pass,
            "valid": self.is_valid(),
            "rejection_reason": self.rejection_reason,
            "content_preview": self.content[:100],
        }


@dataclass
class NebraskaAudit:
    """Complete audit trail produced by running the full axis stack."""
    axiom: str
    components_generated: int = 0
    components_y_valid: int = 0
    components_y2_valid: int = 0
    y3_coherent: bool = False
    z_premise_valid: bool = False
    z_inversion_survivors: int = 0
    newton_qc_pass: bool = False
    intervention_count: int = 0
    rejected: list = field(default_factory=list)
    validated: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "axiom": self.axiom,
            "components_generated": self.components_generated,
            "components_y_valid": self.components_y_valid,
            "components_y2_valid": self.components_y2_valid,
            "y3_coherent": self.y3_coherent,
            "z_premise_valid": self.z_premise_valid,
            "z_inversion_survivors": self.z_inversion_survivors,
            "newton_qc_pass": self.newton_qc_pass,
            "intervention_count": self.intervention_count,
            "rejected": self.rejected,
            "validated": self.validated,
        }


# ─── Core Protocol Class ─────────────────────────────────────────────────────

class NebraskaProtocol:
    """
    Nebraska Generative System (NGS) — full axis stack.

    Usage:
        proto = NebraskaProtocol.from_fear_type("existential")

        # X-axis: generate candidates freely
        candidates = proto.x_axis_generate(["fragment1", "fragment2", ...])

        # Y-axis: primary gate
        proto.y_axis_validate(candidates)

        # Y²-axis: clean conversions
        proto.y2_axis_check(candidates)

        # Y³-axis: integration coherence
        coherent = proto.y3_axis_integrate(candidates)

        # Z-axis: meta check on premise
        valid_premise = proto.z_axis_meta(premise_string)

        # Z-inversion: adversarial flip test
        survivors = proto.z_axis_invert(candidates)

        # Newton QC: final invariant checksum
        result = proto.newton_qc(candidates)
    """

    def __init__(self, axiom: str):
        self.axiom = axiom
        self.audit = NebraskaAudit(axiom=axiom)

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def from_fear_type(cls, fear_type: str, experience_type: str = "solo") -> "NebraskaProtocol":
        """Extract Axiom from fear profile and instantiate protocol."""
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
        X-Axis: divergent, generative phase.  Accept all candidates without
        filtering — brainstorm every possibility under the Axiom.

        Nothing is rejected here.  vy=-1 (unvalidated) for all outputs.
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

    # ── Y-Axis: Validation / Primary Gate (𝕍ᵧ) ─────────────────────────────

    def y_axis_validate(self, components: list[NarrativeComponent]) -> list[NarrativeComponent]:
        """
        Y-Axis: primary filter.  For each component, extract X (deficit) and
        Y (resolution), then ask: "Does X → Y under the Axiom?"

        𝕍ᵧ = 1  →  retained
        𝕍ᵧ = 0  →  rejected (reason recorded in audit)

        Decorative elements with no structural X→Y are eliminated here.
        """
        for comp in components:
            x, y = self._extract_xy(comp.content)
            comp.x = x
            comp.y = y

            if not x:
                comp.vy = 0
                comp.rejection_reason = "Y-gate: X undefined — no deficit identified in content"
            elif not y:
                comp.vy = 0
                comp.rejection_reason = "Y-gate: Y undefined — no transformation or resolution found"
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

    # ── Y²-Axis: Second-Order Validity ───────────────────────────────────────

    def y2_axis_check(self, components: list[NarrativeComponent]) -> list[NarrativeComponent]:
        """
        Y²-Axis: catches weasel conversions and fuzzy logic that slipped through
        the primary gate.

        Failure modes (per Nebraska spec):
          • X is vague or undefined
          • Y does not logically follow from X
          • Conversion does not serve the core law
        """
        for comp in components:
            if comp.vy != 1:
                continue  # already failed — don't double-count

            issues: list[str] = []

            if len(comp.x.split()) < 2:
                issues.append("X is too vague (fewer than 2 meaningful words)")
            if len(comp.y.split()) < 2:
                issues.append("Y is too vague (fewer than 2 meaningful words)")
            if not self._y_follows_from_x(comp.x, comp.y):
                issues.append("Y does not logically follow from X (non-sequitur conversion)")

            if issues:
                comp.y2_pass = False
                comp.vy = 0
                comp.rejection_reason = "Y²-gate: " + "; ".join(issues)
                self.audit.rejected.append({"name": comp.name, "reason": comp.rejection_reason})
            else:
                comp.y2_pass = True

        self.audit.components_y2_valid = sum(1 for c in components if c.y2_pass)
        return components

    # ── Y³-Axis: Integration Validity ────────────────────────────────────────

    def y3_axis_integrate(self, components: list[NarrativeComponent]) -> bool:
        """
        Y³-Axis: do the individually-valid components compose into a single
        narrative machine without breaking the causal chain?

        Returns True if systemic coherence is confirmed.
        """
        valid = [c for c in components if c.is_valid()]

        if not valid:
            self.audit.y3_coherent = False
            return False

        coherent = self._check_chain_coherence(valid)
        self.audit.y3_coherent = coherent
        return coherent

    # ── Z-Axis: Meta-Evaluation ───────────────────────────────────────────────

    def z_axis_meta(self, premise: str) -> bool:
        """
        Z-Axis: does the premise (First Thing) inherently carry a deficit?

        "If your initial story concept doesn't imply a deficit that needs
        resolution, it's not a First Thing — it's a prop."

        A premise without a built-in X has no narrative engine.
        """
        has_deficit = self._premise_implies_deficit(premise)
        self.audit.z_premise_valid = has_deficit
        return has_deficit

    # ── Z-Axis Inversion: Adversarial Flip Test ───────────────────────────────

    def z_axis_invert(self, components: list[NarrativeComponent]) -> list[NarrativeComponent]:
        """
        Z-Inversion: remove each component and test whether the story survives.
        Components that are not load-bearing are flagged and excluded.

        "Swap them, and the logic chain snaps." — only if it truly snaps does
        the component earn its place.

        Applied only when ≥3 valid components exist (fewer = each is trivially
        indispensable).
        """
        valid = [c for c in components if c.is_valid()]

        if len(valid) < 3:
            # Too few to run inversion — all survivors are indispensable by default
            self.audit.z_inversion_survivors = len(valid)
            return valid

        indispensable: list[NarrativeComponent] = []

        for i, comp in enumerate(valid):
            others = valid[:i] + valid[i + 1:]
            if not self._story_works_without(comp, others):
                indispensable.append(comp)
            else:
                comp.rejection_reason = (
                    "Z-inversion: component not load-bearing — story survives its removal"
                )
                comp.vy = 0
                self.audit.rejected.append({"name": comp.name, "reason": comp.rejection_reason})

        self.audit.z_inversion_survivors = len(indispensable)
        return indispensable

    # ── Axis of Intervention: Structure Governor ──────────────────────────────

    def axis_intervention(self, component: NarrativeComponent) -> bool:
        """
        Axis of Intervention: the 'stop-the-machine' lever.

        "No is where structure lives."

        Returns True (intervene / veto) when the component clearly violates
        structural integrity.  The caller should reject and re-run the gate.
        """
        triggers = [
            len(component.content.strip()) < 15,               # too short to carry meaning
            not any(ch.isalpha() for ch in component.content),  # no linguistic content
            component.vy == 0,                                  # already failed a gate
        ]

        if any(triggers):
            self.audit.intervention_count += 1
            return True   # VETO — structure governor fires
        return False

    # ── Newton's Apple QC Checksum ────────────────────────────────────────────

    def newton_qc(self, components: list[NarrativeComponent]) -> dict:
        """
        Final Invariant Check — "Newton's Apple" test.

        The story's logic must fall predictably into place every time, like
        gravity.  If any invariant is violated, the structure is corrupted.

        Invariants (non-negotiable):
          1. Axiom stays fixed as the law of this story
          2. Every component can state its X and Y
          3. Each Y clearly follows from its X
          4. Each conversion serves the Axiom's purpose

        Returns a full QC report with pass/fail and audit trail.
        """
        valid = [c for c in components if c.is_valid()]
        failures: list[str] = []

        for comp in valid:
            if not comp.x:
                failures.append(f"{comp.name}: X undefined")
            if not comp.y:
                failures.append(f"{comp.name}: Y undefined")
            if comp.x and comp.y and not self._y_follows_from_x(comp.x, comp.y):
                failures.append(f"{comp.name}: Y does not follow from X")
            if comp.x and comp.y and not self._conversion_serves_axiom(comp.x, comp.y):
                failures.append(f"{comp.name}: conversion does not serve Axiom")

        passed = (len(failures) == 0) and (len(valid) > 0)
        self.audit.newton_qc_pass = passed
        self.audit.validated = [c.summary() for c in valid]

        return {
            "pass": passed,
            "axiom": self.axiom,
            "valid_components": len(valid),
            "failures": failures,
            "audit": self.audit.to_dict(),
        }

    # ── Convenience: run full pipeline on a list of text candidates ───────────

    def run_full_pipeline(
        self,
        candidates: list[str],
        names: Optional[list[str]] = None,
        premise: str = "",
        apply_z_inversion: bool = False,
    ) -> tuple[list[NarrativeComponent], dict]:
        """
        Execute all axes in order and return (valid_components, qc_report).

        Axis order:
          Z-meta (premise)  →  X-gen  →  Y-validate  →  Y²-check
          →  Y³-integrate  →  [Z-invert]  →  Newton QC
        """
        if premise:
            self.z_axis_meta(premise)

        components = self.x_axis_generate(candidates, names)
        self.y_axis_validate(components)
        self.y2_axis_check(components)
        self.y3_axis_integrate(components)

        if apply_z_inversion:
            survivors = self.z_axis_invert(components)
        else:
            survivors = [c for c in components if c.is_valid()]

        qc = self.newton_qc(components)
        return survivors, qc

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _extract_xy(self, content: str) -> tuple[str, str]:
        """
        Heuristic extraction of X (deficit) and Y (resolution) from narrative text.

        For horror narratives:
          X = the instability / threat / absence (what is wrong)
          Y = the escalation / revelation / transformation (what changes)
        """
        cl = content.lower()

        def _find_context(patterns: list[str], text: str, window: int = 30) -> str:
            for pattern in patterns:
                m = re.search(pattern, text)
                if m:
                    start = max(0, m.start() - window)
                    end = min(len(text), m.end() + window)
                    return text[start:end].strip()[:60]
            return ""

        x_label = _find_context(_X_PATTERNS, cl)
        y_label = _find_context(_Y_PATTERNS, cl)
        return x_label, y_label

    def _conversion_serves_axiom(self, x: str, y: str) -> bool:
        """
        Does the X→Y conversion serve the governing Axiom?

        A conversion serves the Axiom when:
          • The conversion domain overlaps with Axiom keywords, OR
          • The conversion represents a clear escalation / revelation (horror-valid Y)
        """
        axiom_words = {
            w for w in self.axiom.lower().split()
            if len(w) > 4 and w not in {"every", "under", "their", "there", "where"}
        }
        combined = (x + " " + y).lower()

        escalation_markers = {
            "deeper", "closer", "louder", "growing", "spreading",
            "reveals", "becomes", "realise", "realize", "discover",
            "understand", "know", "now", "begin", "start", "awaken",
        }

        axiom_overlap = any(word in combined for word in axiom_words)
        has_transformation = any(word in combined for word in escalation_markers)

        return axiom_overlap or has_transformation

    def _y_follows_from_x(self, x: str, y: str) -> bool:
        """
        Does Y logically follow from X?

        Minimum requirement: X and Y are distinct non-empty strings
        (some transformation occurred rather than stasis).
        For horror: any non-identical X/Y pair with real content is a valid
        transformation — dread escalating is a lawful Y for a threat-X.
        """
        if not x or not y:
            return False
        return x.strip().lower() != y.strip().lower()

    def _check_chain_coherence(self, components: list[NarrativeComponent]) -> bool:
        """
        Y³: do the valid components form a coherent causal chain?

        Coherence criterion: every component has a stated X and Y, indicating
        it carries a defined conversion that can link to adjacent components.
        """
        if not components:
            return False
        return all(c.x and c.y for c in components)

    def _premise_implies_deficit(self, premise: str) -> bool:
        """
        Z-axis: does the premise contain an implied deficit (X)?

        Horror premises almost always carry a built-in instability.
        We check for deficit-indicator vocabulary.
        """
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
        """
        Z-inversion helper: does the remaining story still work without `comp`?

        A component is redundant (story works without it) when another component
        already covers the same X→Y conversion territory.
        """
        if not others:
            return False

        comp_x_words = set(comp.x.lower().split())
        for other in others:
            other_y_words = set(other.y.lower().split())
            # If another component's Y overlaps with this component's X,
            # this component's deficit is already being addressed
            if comp_x_words & other_y_words:
                return True  # redundant — story survives removal

        return False  # unique conversion — story needs this component

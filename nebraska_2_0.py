"""
Nebraska 2.0 — Substrate-Agnostic Logic Layer

Implements the universal narrative engine described in the Nebraska 2.0
Substrate Agnosticism white paper (§3–6).

ARCHITECTURE:
  NebraskaEngine            — core processing loop (a/b = story → meaning → understanding)
  SubstrateAdapter (ABC)    — abstract interface for any generation substrate
  TransformerAdapter        — LLM substrate (Ollama / any chat model)
  TemplateAdapter           — deterministic fallback substrate
  TemporalGuardian          — enforces T(z) × T(1/z) ≥ 1 (bidirectional Z-axis)
  HandshakeGenerator        — validates component-to-component chain linkage (A.Y → B.X)
  ProvenanceRecord          — single record in the chain-of-custody audit
  ProvenanceAnalyzer        — full chain-of-custody validator
  QuadriviumAuditor         — independent validation of all four invariants
  NebraskaInterfaceProtocol — cross-substrate transmission protocol

PROCESSING LOOP (§3.1):
  while System.active:
      potential  = sense(Environment)          # a in a/b
      constraint = retrieve(Invariants)        # b in a/b
      narrative  = potential / constraint      # story generation
      coherence  = validate(𝕍ᵧ, T, M, ∇)     # Quadrivium check
      if coherence:
          commit(narrative); transmit(narrative)
      else:
          quarantine(narrative); adjust(constraints)

PRIME DIRECTIVES (§8.1):
  1. No Narrative Without Understanding   — ∇ ≥ 1 always
  2. No Transmission Without Validation   — QCS ≥ 0.70 always
  3. No Modification Without Consent      — substrate autonomy preserved
  4. No Isolation Without Reconciliation  — quarantine includes resolution path
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nebraska_protocols import (
    NarrativeComponent,
    NebraskaProtocol,
    NebraskaAudit,
    FEAR_AXIOMS,
    DEFAULT_AXIOM,
    FORMULA,
    CONTRACT,
    RECURSIVE_LAW,
    QCS_THRESHOLDS,
    qcs_certification,
    _words,
)

# ─── Optional Ollama ─────────────────────────────────────────────────────────

try:
    import ollama as _ollama
    _OLLAMA_AVAILABLE = True
except ImportError:
    _OLLAMA_AVAILABLE = False

DEFAULT_MODEL = "llama3.1:8b"

# ─── Enums ────────────────────────────────────────────────────────────────────

class SubstrateType(str, Enum):
    TRANSFORMER = "transformer"   # LLM / neural (production)
    TEMPLATE    = "template"      # deterministic fallback
    HUMAN       = "human"         # human-authored input
    HYBRID      = "hybrid"        # human + AI co-generation


class ProcessingStatus(str, Enum):
    COMMITTED   = "committed"     # passed Quadrivium → committed to chain
    QUARANTINED = "quarantined"   # failed Quadrivium → needs reconciliation
    IMPROVING   = "improving"     # auto-improvement loop running
    PENDING     = "pending"       # awaiting validation


# ─── Provenance ───────────────────────────────────────────────────────────────

@dataclass
class ProvenanceRecord:
    """Chain-of-custody record for a single narrative component."""
    component_name: str
    substrate: SubstrateType
    origin_text: str
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    qcs_history: list[float] = field(default_factory=list)
    improvement_iterations: int = 0
    final_status: str = "pending"
    rejection_reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "component": self.component_name,
            "substrate": self.substrate.value,
            "gates_passed": self.gates_passed,
            "gates_failed": self.gates_failed,
            "qcs_history": [round(q, 4) for q in self.qcs_history],
            "improvement_iterations": self.improvement_iterations,
            "final_status": self.final_status,
            "rejection_reason": self.rejection_reason,
            "timestamp": self.timestamp,
        }


# ─── Handshake ────────────────────────────────────────────────────────────────

@dataclass
class Handshake:
    """
    Validated chain link between two narrative components.

    A valid handshake means A.Y creates the conditions for B.X —
    the output of A is the structural input of B.
    'Swap them, and the logic chain snaps.'
    """
    from_component: str
    to_component: str
    a_y: str           # resolution of A
    b_x: str           # deficit of B
    link_words: list[str]
    valid: bool
    proof: str
    causal_strength: float = 0.0   # [0,1] overlap-based strength score

    def to_dict(self) -> dict:
        return {
            "from": self.from_component,
            "to": self.to_component,
            "a_y": self.a_y,
            "b_x": self.b_x,
            "link_words": self.link_words,
            "valid": self.valid,
            "proof": self.proof,
            "causal_strength": round(self.causal_strength, 4),
        }


# ─── Substrate Adapters ───────────────────────────────────────────────────────

class SubstrateAdapter(ABC):
    """
    Abstract base for any generation substrate (§3.2 NIP).

    A substrate provides: generate(), validate(), and transmit().
    Nebraska validation (𝕍ᵧ, T, M, ∇) is always applied on top of
    whatever the substrate produces.
    """
    substrate_type: SubstrateType = SubstrateType.TEMPLATE

    @abstractmethod
    def generate(
        self,
        potential: str,
        axiom: str,
        count: int = 3,
        context: Optional[dict] = None,
    ) -> list[str]:
        """Generate `count` candidate texts from potential under axiom."""
        ...

    def substrate_info(self) -> dict:
        return {"substrate_type": self.substrate_type.value}


class TransformerAdapter(SubstrateAdapter):
    """
    LLM substrate — wraps Ollama (§4.2 TransformerNebraska).

    Attention head alignment maps to 𝕍ᵧ.
    Causal masking maps to T(z).
    Embedding continuity maps to M(t).
    Gradient descent maps to ∇.
    """
    substrate_type = SubstrateType.TRANSFORMER

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.available = _OLLAMA_AVAILABLE

    def generate(
        self,
        potential: str,
        axiom: str,
        count: int = 3,
        context: Optional[dict] = None,
    ) -> list[str]:
        if not self.available:
            return []

        domain = (context or {}).get("domain", "story")
        history = (context or {}).get("narrative_history", [])
        history_note = ""
        if history:
            last = history[-1][:120]
            history_note = f"\nPrevious: {last!r}"

        prompt = _build_generation_prompt(potential, axiom, domain, count, history_note)

        results: list[str] = []
        try:
            for i in range(min(count, 3)):
                resp = _ollama.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    options={"temperature": 0.85 + i * 0.05, "num_predict": 150},
                )
                text = resp["message"]["content"].strip()
                if text and text not in results:
                    results.append(text)
        except Exception as exc:
            print(f"[NE2.0/Transformer] Generation error: {exc}")

        return results

    def substrate_info(self) -> dict:
        return {
            "substrate_type": self.substrate_type.value,
            "model": self.model,
            "available": self.available,
        }


class TemplateAdapter(SubstrateAdapter):
    """
    Deterministic template substrate — always available, domain-aware fallback.

    Ensures the Nebraska Prime Directive 'No Narrative Without Understanding'
    is never violated by a missing dependency.
    """
    substrate_type = SubstrateType.TEMPLATE

    def generate(
        self,
        potential: str,
        axiom: str,
        count: int = 3,
        context: Optional[dict] = None,
    ) -> list[str]:
        domain = (context or {}).get("domain", "story")
        templates = DOMAIN_TEMPLATES.get(domain, DOMAIN_TEMPLATES["story"])
        # Return `count` templates, cycling if necessary
        selected: list[str] = []
        for i in range(count):
            selected.append(templates[i % len(templates)])
        return selected


# ─── Temporal Guardian ────────────────────────────────────────────────────────

class TemporalGuardian:
    """
    Enforces T(z) × T(1/z) ≥ 1 — the dedicated temporal Z-axis validator.

    The Z-axis IS the temporal axis.  It allows the system to look in BOTH
    directions of a logic chain — not just forward-guessing.

      T(z):   forward pass  — does this component flow from what precedes?
      T(1/z): backward pass — does this component remain valid read from the end?

    The context_window is the engine's short-term memory (≡ AI operating system).
    The temporal_index is the long-term record (≡ AI core data, access + retrieval).
    """

    def __init__(self, window_size: int = 10):
        self.context_window: list[str] = []       # short-term memory (STM)
        self.temporal_index: list[dict] = []       # long-term memory (LTM)
        self.window_size = window_size

    def push(self, content: str, qcs: float = 1.0) -> None:
        """Commit a validated component into temporal memory."""
        self.context_window.append(content)
        self.context_window = self.context_window[-self.window_size:]
        self.temporal_index.append({
            "content": content[:120],
            "content_words": list(_words(content))[:20],
            "qcs": round(qcs, 4),
            "t": time.time(),
        })

    def forward_score(self, content: str) -> float:
        """T(z): how well does this content follow from current context?"""
        if not self.context_window:
            return 0.85
        recent = " ".join(self.context_window[-3:])
        recent_words = _words(recent) - {"the", "a", "an", "of", "in", "to", "and", "it"}
        comp_words = _words(content)
        overlap = len(recent_words & comp_words)
        score = min(1.0, overlap / max(1, len(recent_words) * 0.15))
        return max(0.4, score)

    def backward_score(self, content: str, axiom: str) -> float:
        """T(1/z): does this content remain valid when read from the end backward?"""
        axiom_words = _words(axiom)
        comp_words = _words(content)
        xy_overlap = bool(axiom_words & comp_words)
        return 0.85 if xy_overlap else 0.6

    def bidirectional(self, content: str, axiom: str) -> float:
        """T(z) × T(1/z) combined temporal coherence score."""
        t_fwd = self.forward_score(content)
        t_bwd = self.backward_score(content, axiom)
        return round((t_fwd + t_bwd) / 2, 4)

    def adjacency_determinant_nonzero(self) -> bool:
        """
        §2.2 validation: temporal adjacency matrix determinant ≠ 0.
        Simplified: the context window has at least one non-empty entry.
        """
        return any(e.get("qcs", 0) > 0 for e in self.temporal_index)

    def status(self) -> dict:
        return {
            "context_window_size": len(self.context_window),
            "temporal_index_entries": len(self.temporal_index),
            "stm_last": self.context_window[-1][:60] if self.context_window else None,
            "adjacency_valid": self.adjacency_determinant_nonzero(),
        }


# ─── Handshake Generator ─────────────────────────────────────────────────────

class HandshakeGenerator:
    """
    Validates component-to-component chain linkage.

    A handshake proves: A.Y → B.X  (A's resolution creates B's deficit condition).
    Without a valid handshake, the logic chain snaps.

    Used to verify that individually-valid components actually chain into a
    coherent narrative machine (Y³ system coherence at the micro level).
    """

    def generate(
        self,
        comp_a: NarrativeComponent,
        comp_b: NarrativeComponent,
        axiom: str,
    ) -> Handshake:
        """
        Generate and validate the chain link A.Y → B.X.

        Causal strength = Jaccard similarity of A.Y vocabulary and B.X vocabulary.
        """
        a_y_words = _words(comp_a.y)
        b_x_words = _words(comp_b.x)

        # Jaccard similarity for causal strength
        if a_y_words or b_x_words:
            intersection = a_y_words & b_x_words
            union = a_y_words | b_x_words
            causal_strength = len(intersection) / max(1, len(union))
        else:
            intersection = set()
            causal_strength = 0.0

        # Semantic bridge: does A's Y-domain relate to axiom words that B's X addresses?
        axiom_words = _words(axiom)
        semantic_bridge = bool(
            (a_y_words & axiom_words) and (b_x_words & axiom_words)
        )

        valid = bool(intersection) or semantic_bridge
        link_words = sorted(intersection)

        if valid:
            proof = (
                f"A.Y {comp_a.y[:35]!r} → B.X {comp_b.x[:35]!r} "
                f"[link: {', '.join(link_words) if link_words else 'semantic bridge via axiom'}]"
            )
        else:
            proof = (
                f"No causal link: A.Y {comp_a.y[:30]!r} "
                f"does not create conditions for B.X {comp_b.x[:30]!r}"
            )

        return Handshake(
            from_component=comp_a.name,
            to_component=comp_b.name,
            a_y=comp_a.y,
            b_x=comp_b.x,
            link_words=link_words,
            valid=valid,
            proof=proof,
            causal_strength=round(causal_strength, 4),
        )

    def validate_chain(
        self,
        components: list[NarrativeComponent],
        axiom: str,
    ) -> dict:
        """
        Validate the full chain: A→B→C→…  Every adjacent pair must handshake.
        Returns chain validity + list of broken links.
        """
        if len(components) < 2:
            return {
                "valid": True,
                "handshakes": [],
                "broken_links": [],
                "chain_strength": 1.0,
            }

        handshakes: list[dict] = []
        broken: list[str] = []

        for i in range(len(components) - 1):
            hs = self.generate(components[i], components[i + 1], axiom)
            handshakes.append(hs.to_dict())
            if not hs.valid:
                broken.append(
                    f"{components[i].name} → {components[i + 1].name}: {hs.proof}"
                )

        chain_strength = (
            sum(h["causal_strength"] for h in handshakes) / len(handshakes)
            if handshakes else 0.0
        )

        return {
            "valid": len(broken) == 0,
            "handshakes": handshakes,
            "broken_links": broken,
            "chain_strength": round(chain_strength, 4),
        }


# ─── Provenance Analyzer ─────────────────────────────────────────────────────

class ProvenanceAnalyzer:
    """
    Full chain-of-custody audit for narrative components.

    Tracks: origin substrate, gate passage history, QCS evolution,
    improvement iterations, and final status.

    Enables full traceability from raw candidate → committed component.
    """

    def build_record(
        self,
        comp: NarrativeComponent,
        substrate: SubstrateType = SubstrateType.TEMPLATE,
    ) -> ProvenanceRecord:
        """Build a provenance record from a fully-processed NarrativeComponent."""
        record = ProvenanceRecord(
            component_name=comp.name,
            substrate=substrate,
            origin_text=comp.content[:200],
            final_status="valid" if comp.is_valid() else "rejected",
            rejection_reason=comp.rejection_reason,
        )

        # Gate history
        if comp.vy == 1:
            record.gates_passed.append("Y-axis (𝕍ᵧ)")
        elif comp.vy == 0:
            record.gates_failed.append(f"Y-axis: {comp.rejection_reason[:60]}")

        if comp.y2_pass:
            record.gates_passed.append("Y²-axis (Thematic Rail)")
        elif comp.vy == 1:  # passed Y but not Y²
            record.gates_failed.append("Y²-axis")

        if comp.qcs >= 0:
            record.qcs_history.append(comp.qcs)

        return record

    def analyze_chain(
        self,
        components: list[NarrativeComponent],
        substrate: SubstrateType = SubstrateType.TEMPLATE,
    ) -> dict:
        """Full provenance analysis for a list of components."""
        records = [self.build_record(c, substrate) for c in components]
        valid_records = [r for r in records if r.final_status == "valid"]
        rejected_records = [r for r in records if r.final_status == "rejected"]

        # Find weak links: valid components with low QCS
        weak_links = [
            r.component_name
            for r in valid_records
            if r.qcs_history and r.qcs_history[-1] < QCS_THRESHOLDS["bronze"]
        ]

        return {
            "total_components": len(records),
            "valid": len(valid_records),
            "rejected": len(rejected_records),
            "weak_links": weak_links,
            "records": [r.to_dict() for r in records],
        }


# ─── Quadrivium Auditor ───────────────────────────────────────────────────────

class QuadriviumAuditor:
    """
    Independent validation of all four invariants (§8.2).

    'Quadrivium Auditors: Independent validation of 𝕍ᵧ, T, M, ∇'

    The auditor operates independently of the generating NebraskaProtocol
    instance — it validates from the outside, ensuring no conflict of interest
    between generation and validation.
    """

    def __init__(self, temporal_guardian: Optional[TemporalGuardian] = None):
        self.temporal_guardian = temporal_guardian or TemporalGuardian()

    def audit(
        self,
        components: list[NarrativeComponent],
        axiom: str,
        narrative_history: Optional[list[str]] = None,
    ) -> dict:
        """Full independent audit: runs Fourfold Test on each component."""
        proto = NebraskaProtocol(axiom)
        results: list[dict] = []

        for comp in components:
            qcs = proto.fourfold_test(comp, narrative_history)
            results.append({
                "name": comp.name,
                "valid": comp.is_valid(),
                "vy": comp.vy,
                "t_score": round(comp.t_score, 3) if comp.t_score >= 0 else None,
                "m_score": round(comp.m_score, 3) if comp.m_score >= 0 else None,
                "grad_score": round(comp.grad_score, 3) if comp.grad_score >= 0 else None,
                "qcs": round(qcs, 4),
                "certification": qcs_certification(qcs),
                "prime_directive_1": comp.grad_score >= 0.5 if comp.grad_score >= 0 else None,
                "prime_directive_2": qcs >= QCS_THRESHOLDS["bronze"],
            })

        valid_qcs = [r["qcs"] for r in results if r["valid"] and r["qcs"] >= 0]
        mean_qcs = sum(valid_qcs) / max(1, len(valid_qcs)) if valid_qcs else 0.0

        prime_directive_violations = [
            r["name"] for r in results
            if not r["prime_directive_2"] and r["valid"]
        ]

        return {
            "audit_type": "QuadriviumAuditor",
            "axiom": axiom,
            "components_audited": len(results),
            "mean_qcs": round(mean_qcs, 4),
            "certification": qcs_certification(mean_qcs),
            "prime_directive_violations": prime_directive_violations,
            "results": results,
        }


# ─── Nebraska Interface Protocol (NIP) ───────────────────────────────────────

class NebraskaInterfaceProtocol:
    """
    Cross-substrate transmission protocol (§3.3).

    Encodes a narrative in substrate-agnostic format with QCS hashes,
    then validates on receipt at the target substrate.

    encode → transmit → decode → validate → integrate (or reconcile)
    """

    @staticmethod
    def encode(
        components: list[NarrativeComponent],
        axiom: str,
        qc_report: dict,
    ) -> dict:
        """Encode a validated narrative for cross-substrate transmission."""
        return {
            "nip_version": "2.0",
            "axiom": axiom,
            "formula": FORMULA,
            "validity_hash": hash(axiom + "".join(c.content for c in components)),
            "temporal_index": [
                {"name": c.name, "qcs": c.qcs, "t": time.time()}
                for c in components
            ],
            "memory_references": [c.x for c in components if c.x],
            "learning_gradient": qc_report.get("audit", {}).get("components_y2_valid", 0),
            "payload": [c.summary() for c in components],
            "qc_report": qc_report,
        }

    @staticmethod
    def validate_transmission(encoded: dict, axiom: str) -> bool:
        """Validate a received transmission against local Axiom."""
        if encoded.get("axiom") != axiom:
            return False
        if encoded.get("nip_version") != "2.0":
            return False
        # QCS check: at least one component must meet Bronze
        payloads = encoded.get("payload", [])
        passing = any(
            p.get("qcs", 0) >= QCS_THRESHOLDS["bronze"]
            for p in payloads
        )
        return passing


# ─── Nebraska Engine (Core Processing Loop) ──────────────────────────────────

class NebraskaEngine:
    """
    Nebraska 2.0 Core Processing Loop (§3.1).

    This is the substrate-agnostic narrative machine.  It wraps
    NebraskaProtocol (the domain logic) with:
      • Substrate adapters (generation)
      • Temporal Guardian (T(z) memory)
      • Handshake validation (chain linking)
      • Provenance tracking (chain of custody)
      • Quadrivium auditing (independent QCS)
      • NIP encoding/transmission

    PROCESSING LOOP:
        potential / constraint = narrative
        validate(𝕍ᵧ, T, M, ∇) → commit or quarantine
        recursive improvement until QCS ≥ Bronze or max_iter reached

    PRIME DIRECTIVES:
        1. ∇ ≥ 1 always  (no narrative without understanding)
        2. QCS ≥ 0.70 always  (no transmission without validation)
        3. Substrate autonomy preserved
        4. Quarantine always has a resolution path
    """

    def __init__(
        self,
        primary_adapter: Optional[SubstrateAdapter] = None,
        model: str = DEFAULT_MODEL,
        max_improvement_iterations: int = 3,
    ):
        self.primary_adapter = primary_adapter or TransformerAdapter(model)
        self.fallback_adapter = TemplateAdapter()
        self.temporal_guardian = TemporalGuardian()
        self.handshake_gen = HandshakeGenerator()
        self.provenance = ProvenanceAnalyzer()
        self.auditor = QuadriviumAuditor(self.temporal_guardian)
        self.nip = NebraskaInterfaceProtocol()
        self.max_improvement_iterations = max_improvement_iterations

        self.committed: list[dict] = []
        self.quarantined: list[dict] = []
        self._run_id = uuid.uuid4().hex[:8]

    # ── Main entry point ──────────────────────────────────────────────────────

    def process(
        self,
        potential: str,
        axiom: str,
        count: int = 3,
        names: Optional[list[str]] = None,
        context: Optional[dict] = None,
    ) -> dict:
        """
        a / b = story → meaning → understanding

        potential  = a  (what exists to be converted)
        axiom      = b  (constraint — makes conversion lawful and inevitable)
        narrative  = potential / axiom  (the lawful division)

        Runs the full processing loop.  Returns committed result or
        quarantine report with reconciliation path.
        """
        history = self.temporal_guardian.context_window[:]
        proto = NebraskaProtocol(axiom)

        # Z-axis: premise must have a deficit
        z_valid = proto.z_axis_meta(potential)

        # Generate candidates (primary → fallback if needed)
        candidates = self.primary_adapter.generate(potential, axiom, count, context)
        substrate = self.primary_adapter.substrate_type
        if len(candidates) < count:
            extra = self.fallback_adapter.generate(
                potential, axiom, count - len(candidates), context
            )
            candidates.extend(extra)
            substrate = SubstrateType.HYBRID if candidates else SubstrateType.TEMPLATE

        # Full pipeline
        survivors, qc = proto.run_full_pipeline(
            candidates=candidates,
            names=names,
            premise=potential,
            narrative_history=history,
            apply_z_proof=True,
        )

        # Recursive improvement loop (Nebraska 3.0 §)
        iteration = 0
        while (
            not qc["pass"]
            and iteration < self.max_improvement_iterations
            and candidates
        ):
            iteration += 1
            print(
                f"[NE2.0/Engine] QC fail — improvement iteration {iteration}/{self.max_improvement_iterations}"
            )
            extra_candidates = self.fallback_adapter.generate(
                potential, axiom, count, context
            )
            improved_proto = NebraskaProtocol(axiom)
            survivors, qc = improved_proto.run_full_pipeline(
                candidates=candidates + extra_candidates,
                premise=potential,
                narrative_history=history,
            )
            if qc["pass"]:
                proto = improved_proto
                break

        # Commit or quarantine
        if survivors and qc["pass"]:
            for comp in survivors:
                self.temporal_guardian.push(comp.content, comp.qcs)
            status = ProcessingStatus.COMMITTED
            self.committed.append({
                "potential": potential[:80],
                "axiom": axiom,
                "qcs": qc.get("mean_qcs", 0.0),
                "certification": qc.get("certification"),
            })
            print(
                f"[NE2.0/Engine] COMMITTED | {len(survivors)} components | "
                f"QCS={qc.get('mean_qcs', 0):.3f} | {qc.get('certification')}"
            )
        else:
            status = ProcessingStatus.QUARANTINED
            self.quarantined.append({
                "potential": potential[:80],
                "axiom": axiom,
                "reason": qc.get("failures", ["unknown"]),
                "improvement_iterations": iteration,
                "reconciliation_path": _reconciliation_path(qc),
            })
            print(
                f"[NE2.0/Engine] QUARANTINED | "
                f"failures={qc.get('failures')} | "
                f"reconciliation: {self.quarantined[-1]['reconciliation_path'][:60]}"
            )

        # Provenance + independent audit
        all_components = proto.x_axis_generate(candidates, names)
        prov = self.provenance.analyze_chain(all_components, substrate)
        audit = self.auditor.audit(survivors, axiom, history)

        # Handshake chain validation
        chain_result = (
            self.handshake_gen.validate_chain(survivors, axiom)
            if len(survivors) >= 2 else None
        )

        # NIP encoding for transmission
        encoded = self.nip.encode(survivors, axiom, qc) if survivors else None

        return {
            "run_id": self._run_id,
            "status": status.value,
            "axiom": axiom,
            "formula": FORMULA,
            "z_premise_valid": z_valid,
            "survivors": [c.summary() for c in survivors],
            "survivors_count": len(survivors),
            "qc": qc,
            "improvement_iterations": iteration,
            "provenance": prov,
            "audit": audit,
            "chain": chain_result,
            "encoded": encoded,
            "temporal": self.temporal_guardian.status(),
        }

    # ── Convenience wrappers ──────────────────────────────────────────────────

    def validate_single(
        self,
        content: str,
        axiom: str,
        name: str = "input",
        narrative_history: Optional[list[str]] = None,
    ) -> dict:
        """Validate a single component through the full Fourfold Test."""
        comp = NarrativeComponent(name=name, content=content)
        proto = NebraskaProtocol(axiom)

        proto.y_axis_validate([comp])
        proto.y2_axis_check([comp])
        history = narrative_history or self.temporal_guardian.context_window[:]
        qcs = proto.fourfold_test(comp, history)

        return {
            "component": comp.summary(),
            "axiom": axiom,
            "qcs": round(qcs, 4),
            "certification": qcs_certification(qcs),
            "governor_veto": proto.governor(comp),
        }

    def handshake(
        self,
        comp_a: NarrativeComponent,
        comp_b: NarrativeComponent,
        axiom: str,
    ) -> dict:
        """Public handshake validation for two components."""
        hs = self.handshake_gen.generate(comp_a, comp_b, axiom)
        return hs.to_dict()

    def status(self) -> dict:
        """Engine status report."""
        return {
            "run_id": self._run_id,
            "formula": FORMULA,
            "prime_equation": "𝕍ᵧ ≡ T(z) ≡ M(t) ≡ ∇(understanding)",
            "contract": CONTRACT,
            "recursive_law": RECURSIVE_LAW,
            "primary_substrate": self.primary_adapter.substrate_info(),
            "committed_count": len(self.committed),
            "quarantined_count": len(self.quarantined),
            "temporal": self.temporal_guardian.status(),
            "qcs_thresholds": QCS_THRESHOLDS,
            "certifications": {
                "platinum": "QCS ≥ 0.99 — universal coherence",
                "gold":     "QCS ≥ 0.90 — production ready",
                "silver":   "QCS ≥ 0.80 — requires reconciliation",
                "bronze":   "QCS ≥ 0.70 — single-substrate coherence",
                "quarantine":"QCS < 0.70 — substrate quarantine required",
            },
            "prime_directives": [
                "No Narrative Without Understanding (∇ ≥ 1)",
                "No Transmission Without Validation (QCS ≥ 0.70)",
                "No Modification Without Consent (substrate autonomy)",
                "No Isolation Without Reconciliation (quarantine has path)",
            ],
        }


# ─── Domain Templates (TemplateAdapter fallback content) ─────────────────────

DOMAIN_TEMPLATES: dict[str, list[str]] = {
    # Every template must contain ≥1 X-pattern word and ≥1 Y-pattern word
    # so each reliably passes the Y-axis gate.
    "story": [
        "Something watches from the void — you realize too late it has always known your name.",
        "Nothing remains unknown for long here — you discover the pattern before the pattern discovers you.",
        "The silence grows deeper now; something is waiting for you to realize it has never left.",
        "You cannot see what follows, but it grows louder as you begin to understand what it wants.",
        "The shadow reveals itself only when you realize you cannot leave the way you came.",
    ],
    "strategy": [
        "The market's unresolved gap grows larger — early movers discover what incumbents cannot see.",
        "Nothing in the competitive landscape is truly unknown; we realize the hidden structure before anyone else does.",
        "The absent capability grows more visible to customers — we discover the conversion before the market names it.",
        "Something is missing in every existing solution; we realize that missing element becomes the product.",
        "The unknown customer behavior grows clearer through usage data — we discover the law before we write it.",
    ],
    "research": [
        "The unknown mechanism grows clearer as we discover the confounding variable the field has never named.",
        "Nothing in the existing literature resolves the gap — we realize the assumption that has never been tested.",
        "Something is wrong with the prevailing model; we discover the edge case that reveals the underlying law.",
        "The missing longitudinal data reveals what was never measured — the absence becomes the primary signal.",
        "The uncertainty grows deeper until we realize the prior studies were measuring the wrong variable.",
    ],
    "design": [
        "The user cannot find what they need — we reveal the hidden path through spatial and semantic clarity.",
        "Nothing in the current flow is broken, yet something is missing; we realize the cognitive gap the interface ignores.",
        "Something is wrong with onboarding — we realize the moment users never return is the design's most honest data.",
        "The unknown user behavior reveals what the error message cannot explain — we discover the true mental model.",
        "The friction grows visible as we discover users avoiding the core feature — the workaround becomes the design.",
    ],
    "code": [
        "The unknown failure mode grows clearer — we discover the missing invariant the type system never enforced.",
        "Nothing in the current architecture resolves the coupling; we realize the abstraction layer that was never built.",
        "Something is wrong with shared mutable state — we realize the single source of truth that never existed.",
        "The edge case reveals what the interface cannot guarantee; we discover the broken contract before production does.",
        "The dependency grows unmanageable — we discover the bounded domain that cannot be violated from outside.",
    ],
}

# ─── Domain Axioms ────────────────────────────────────────────────────────────

DOMAIN_AXIOMS: dict[str, str] = {
    "story":    "Every story is a deficit demanding resolution under its own law",
    "strategy": "Every market position converts a structural deficit to competitive advantage under constraint",
    "research": "Every thesis converts a knowledge gap to validated insight under evidential law",
    "design":   "Every design decision converts user confusion to intuitive clarity under cognitive law",
    "code":     "Every architectural decision converts system complexity to bounded capability under constraint",
}

# ─── Domain Generation Prompts ────────────────────────────────────────────────

DOMAIN_PROMPTS: dict[str, str] = {
    "story": (
        "You are a masterful horror narrator. Write a VERY SHORT (2-4 sentences), "
        "second-person narrative fragment. Dark, sensory-rich, escalating dread. "
        "Every sentence must identify a deficit (X) and provide a transformation (Y). "
        "Output ONLY the narrative text."
    ),
    "strategy": (
        "You are a strategy consultant. Write ONE strategic initiative (2-3 sentences). "
        "It must identify a market/organizational deficit (X) and describe how the "
        "initiative converts it to structural advantage (Y) under the governing law. "
        "Output ONLY the initiative description."
    ),
    "research": (
        "You are a research scientist. Write ONE research contribution (2-3 sentences). "
        "It must identify a knowledge gap or methodological deficit (X) and describe "
        "how this work converts it to validated insight (Y). "
        "Output ONLY the contribution description."
    ),
    "design": (
        "You are a UX designer. Write ONE design decision (2-3 sentences). "
        "It must identify a user confusion or friction point (X) and describe how "
        "the design converts it to clarity or ease (Y). "
        "Output ONLY the design decision description."
    ),
    "code": (
        "You are a software architect. Write ONE architectural decision (2-3 sentences). "
        "It must identify a system complexity or constraint (X) and describe how "
        "the design converts it to bounded capability (Y). "
        "Output ONLY the decision description."
    ),
}


# ─── Private helpers ─────────────────────────────────────────────────────────

def _build_generation_prompt(
    potential: str,
    axiom: str,
    domain: str,
    count: int,
    history_note: str,
) -> str:
    base = DOMAIN_PROMPTS.get(domain, DOMAIN_PROMPTS["story"])
    return (
        f"{base}\n\n"
        f"Governing Axiom: {axiom}\n"
        f"Current potential/premise: {potential[:200]}"
        f"{history_note}\n\n"
        f"Generate ONE fragment only."
    )


def _reconciliation_path(qc: dict) -> str:
    """Suggest a reconciliation path for a quarantined narrative."""
    failures = qc.get("failures", [])
    audit = qc.get("audit", {})

    if not audit.get("z_premise_valid"):
        return "Refine premise: it must carry a built-in deficit (X)"
    if audit.get("components_y_valid", 0) == 0:
        return "All components failed Y-gate: strengthen X→Y conversions or revise Axiom"
    if audit.get("components_y2_valid", 0) == 0:
        return "Y²-gate failures: make X and Y more specific; remove vague language"
    if failures:
        return f"Fix: {failures[0]}"
    return "Run Z-axis inversion to identify non-load-bearing components"

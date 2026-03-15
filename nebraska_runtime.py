#!/usr/bin/env python3
# nebraska_runtime.py
#
# Nebraska Generative System — Full Axis Stack Runtime
# Implements: NEBRASKA 1.0 / 2.0 Protocol (Shaun O'Sullivan)
#
# Architecture:
#   X  axis  — Expansion (candidate generation / generative entropy)
#   Y  axis  — Validity gate (𝕍ᵧ: must declare X, Y, prove conversion serves Axiom)
#   Y2 axis  — Anti-weasel filter (clean, specific language; no vague X/Y)
#   Y3 axis  — Integration check (components compose without breaking the chain)
#   Z  axis  — Meta-evaluation (axiom must reject something; premise implies deficit)
#   Z⁻¹      — Adversarial inversion (detect non-load-bearing components)
#   Axis Intervention — Hard stop / prune / reset when coherence breaks
#   Newton-Apple QC  — Invariant checksum of the validated system
#
# Formula:
#   System = A + ∑[(Cᵢ + Kᵢ) | A] · 𝕍ᵧ · M(t) · T(z)
#
# Usage:
#   python nebraska_runtime.py run --in input.json --out report.json
#   python nebraska_runtime.py run --in input.json --pretty
#   cat input.json | python nebraska_runtime.py run --stdin

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─── Core Types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Axiom:
    """
    Governing Law (A).

    law:              The invariant statement — what all conversions must serve.
    required_tokens:  Z-axis positive anchors (ski slopes, pine needles).
    forbidden_tokens: Z-inversion negative anchors (beaches in ski brochures).
    """
    name: str
    law: str = ""
    required_tokens: Tuple[str, ...] = ()
    forbidden_tokens: Tuple[str, ...] = ()
    version: str = "1.0"
    notes: str = ""


@dataclass(frozen=True)
class Seed:
    """
    First canonical input: the initial X and desired Y.
    The Seed is your First Thing — the object/concept you're extracting the Axiom from.
    """
    id: str
    x: str              # Deficit state / raw input state
    y: str              # Resolution state / desired output state
    kind: str = "seed"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Component:
    """
    Narrative component claiming X → Y under the Axiom.

    transform:     Explicit, declared conversion rule (not vibes).
    justification: Plain explanation tying X→Y to the Axiom (used by Y-axis + QC).
    parent_id:     Seed or component that spawned this (audit trail).
    """
    id: str
    kind: str
    x: str
    y: str
    transform: str
    justification: str
    parent_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    ok: bool
    axis: str
    details: str
    score: float = 1.0


@dataclass(frozen=True)
class Rejection:
    id: str
    axis: str
    reason: str
    kind: str = ""
    parent_id: Optional[str] = None


@dataclass(frozen=True)
class RuntimeOptions:
    max_expansions_per_seed: int = 6
    enable_inversion: bool = True
    stop_on_first_system_failure: bool = False
    qc_checksum_enabled: bool = True
    verbose: bool = False


@dataclass
class SystemReport:
    ok: bool
    axiom: Axiom
    summary: Dict[str, Any]
    kept: List[Component]
    rejected: List[Rejection]
    system_verdicts: Dict[str, Verdict]
    checksum: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

_WS = re.compile(r"\s+")
_VAGUE = re.compile(
    r"\b(something|somehow|stuff|things|etc|whatever|kind\s+of|sort\s+of|maybe|various)\b",
    re.I,
)


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip())


def _nonempty(s: str) -> bool:
    return bool(_norm(s))


def _looks_vague(s: str) -> bool:
    s = _norm(s)
    if not s:
        return True
    if len(s) < 12:
        return True
    return len(_VAGUE.findall(s)) >= 2


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _to_plain(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {k: _to_plain(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in obj]
    return obj


def _text_has_any(haystack: str, needles: Tuple[str, ...]) -> bool:
    h = _norm(haystack).lower()
    return any(_norm(n).lower() in h for n in needles if _nonempty(n))


# ─── X Axis: Expansion ────────────────────────────────────────────────────────

def axis_x_expand(seed: Seed, n: int) -> List[Component]:
    """
    X axis: generative expansion.
    Creates n candidate components from a seed using explicit, auditable templates.
    The Y / Y2 axes will kill the weak ones — this layer generates, not validates.
    """
    sx = _norm(seed.x)
    sy = _norm(seed.y)

    templates = [
        ("beat",      "add_pressure",       f"{sx} + pressure applied",      sy, "Adds pressure that forces motion toward Y."),
        ("beat",      "reveal_constraint",   f"{sx} + constraint revealed",   sy, "Narrows the field of possible paths toward Y."),
        ("beat",      "tradeoff",            f"{sx} + cost incurred",         sy, "Makes the conversion to Y earned through sacrifice."),
        ("scene",     "cause_effect",        f"{sx} → consequence",           sy, "Links an immediate consequence to push toward Y."),
        ("character", "agent_of_conversion", f"{sx} + agent introduced",      sy, "Introduces an agent whose function is to convert X toward Y."),
        ("prop",      "instrument",          f"{sx} + instrument appears",    sy, "Adds an instrument enabling the conversion."),
    ]

    out: List[Component] = []
    for i, (kind, transform, x, y, just) in enumerate(templates[: max(1, n)]):
        out.append(
            Component(
                id=f"{seed.id}::cand::{i + 1}",
                kind=kind,
                x=x,
                y=y,
                transform=transform,
                justification=just,
                parent_id=seed.id,
                meta={"generated": True, "template": transform},
            )
        )
    return out


# ─── Y Axis: Validity Gate (𝕍ᵧ) ──────────────────────────────────────────────

def axis_y_gate(axiom: Axiom, c: Component) -> Verdict:
    """
    Y axis gate.
    Must state X, state Y, prove conversion serves the Law.
    Justification must reference tokens from the Axiom law string.
    """
    if not _nonempty(c.x):
        return Verdict(False, "Y", "X undefined/empty.", 0.0)
    if not _nonempty(c.y):
        return Verdict(False, "Y", "Y undefined/empty.", 0.0)
    if not _nonempty(c.transform):
        return Verdict(False, "Y", "No explicit transform declared (conversion rule missing).", 0.2)
    if not _nonempty(c.justification):
        return Verdict(False, "Y", "No justification declared (cannot audit X→Y under Law).", 0.2)

    law = _norm(axiom.law)
    if _nonempty(law):
        law_tokens = tuple(t for t in re.split(r"[^a-zA-Z0-9]+", law) if len(t) >= 4)
        if law_tokens and not _text_has_any(c.justification, law_tokens):
            return Verdict(
                False, "Y",
                f"Justification does not connect to axiom law: '{axiom.law}'.",
                0.4,
            )

    return Verdict(True, "Y", "Pass: X and Y declared; law-tied justification present.", 1.0)


# ─── Y2 Axis: Anti-Weasel Filter ─────────────────────────────────────────────

def axis_y2_clean(c: Component) -> Verdict:
    """
    Y2 axis: no vague language.
    If you can't state X or Y in specific, concrete terms you don't have a component.
    """
    if _looks_vague(c.x):
        return Verdict(False, "Y2", "X is vague/underspecified.", 0.2)
    if _looks_vague(c.y):
        return Verdict(False, "Y2", "Y is vague/underspecified.", 0.2)
    if _looks_vague(c.justification):
        return Verdict(False, "Y2", "Justification is vague/hand-wavy.", 0.3)
    return Verdict(True, "Y2", "Pass: clean, specific conversion language.", 1.0)


# ─── Y3 Axis: Integration Check ───────────────────────────────────────────────

def axis_y3_integration(kept: List[Component]) -> Verdict:
    """
    Y3 axis: components must compose into one machine.
    Checks seed-root provenance and keyword continuity between components.
    """
    if not kept:
        return Verdict(False, "Y3", "No components kept; nothing to integrate.", 0.0)

    # Rule 1: Provenance chain must root back to seeds.
    seed_roots = {c.parent_id for c in kept if c.parent_id and "::" not in c.parent_id}
    if not seed_roots:
        return Verdict(False, "Y3", "No seed root detected (broken provenance chain).", 0.2)

    # Rule 2: Sequential keyword overlap (cheap continuity test).
    vocab: set = set()
    breaks = 0
    for idx, c in enumerate(kept):
        tokens = set(t.lower() for t in re.findall(r"[a-zA-Z0-9]{4,}", f"{c.x} {c.y} {c.transform}"))
        if idx == 0:
            vocab |= tokens
            continue
        if not tokens & vocab:
            breaks += 1
        vocab |= tokens

    if breaks:
        return Verdict(
            False, "Y3",
            f"Integration breaks detected (no continuity overlap), count={breaks}.",
            0.5,
        )

    return Verdict(True, "Y3", "Pass: components compose with continuity.", 1.0)


# ─── Z Axis: Meta-Evaluation ──────────────────────────────────────────────────

def axis_z_meta(
    axiom: Axiom, kept: List[Component], rejected: List[Rejection]
) -> Verdict:
    """
    Z axis: is the axiom doing real work?
    An axiom that rejects nothing is a decoration, not a law.
    Also enforces required/forbidden token anchors (your ski-resort sanity check).
    """
    if not _nonempty(axiom.name):
        return Verdict(False, "Z", "Axiom name empty.", 0.0)
    if not kept:
        return Verdict(False, "Z", "No kept components; system produces no lawful output.", 0.0)
    if len(rejected) == 0:
        return Verdict(False, "Z", "Axiom rejected nothing; likely not doing real work.", 0.5)

    # Deficit implication: at least one X must differ from its Y.
    if not any(_norm(c.x).lower() != _norm(c.y).lower() for c in kept):
        return Verdict(False, "Z", "No deficit implied anywhere (X==Y everywhere).", 0.4)

    # Z-axis required tokens (must appear somewhere in the kept set).
    if axiom.required_tokens:
        blob = " ".join(f"{c.x} {c.y} {c.justification}" for c in kept)
        if not _text_has_any(blob, axiom.required_tokens):
            return Verdict(False, "Z", "Required Z-anchors are missing from kept set.", 0.6)

    # Z-inversion forbidden tokens (must NOT appear).
    if axiom.forbidden_tokens:
        blob = " ".join(f"{c.x} {c.y} {c.justification}" for c in kept)
        if _text_has_any(blob, axiom.forbidden_tokens):
            return Verdict(False, "Z", "Forbidden tokens found; Z-inversion guard failed.", 0.3)

    return Verdict(True, "Z", "Pass: axiom constrains output; premise implies deficit.", 1.0)


# ─── Z Inversion: Adversarial Flip Test ───────────────────────────────────────

def axis_z_inversion(axiom: Axiom, kept: List[Component]) -> Verdict:
    """
    Z⁻¹: flip the first component's X/Y and retest Y3 + Z.
    If the system still passes, that component is non-load-bearing — decorative.
    Load-bearing components break coherence when inverted.
    """
    if not kept:
        return Verdict(False, "ZINV", "No kept components to invert.", 0.0)
    if len(kept) == 1:
        return Verdict(False, "ZINV", "Single-component systems are trivially non-load-bearing.", 0.2)

    target = kept[0]
    flipped = dataclasses.replace(
        target,
        id=target.id + "::INV",
        x=target.y,
        y=target.x,
        transform=target.transform + "::inverted",
        justification=target.justification + " (inverted test)",
        meta={**target.meta, "inverted": True},
    )
    trial = [flipped] + kept[1:]

    v_y3 = axis_y3_integration(trial)
    v_z = axis_z_meta(axiom, trial, rejected=[Rejection("_dummy", "Y", "dummy")])

    if v_y3.ok and v_z.ok:
        return Verdict(
            False, "ZINV",
            f"Inversion did not break system; '{target.id}' appears non-load-bearing.",
            0.4,
        )

    return Verdict(True, "ZINV", "Pass: inversion breaks coherence; components appear load-bearing.", 1.0)


# ─── Axis Intervention: The Governor ─────────────────────────────────────────

def axis_intervention_prune(
    axiom: Axiom, candidates: List[Component]
) -> Tuple[List[Component], List[Rejection]]:
    """
    The Governor — applies Y then Y2 to every candidate.
    Anything failing is rejected immediately.
    This is not polite. It is allowed to be rude.
    """
    kept: List[Component] = []
    rejected: List[Rejection] = []

    for c in candidates:
        v_y = axis_y_gate(axiom, c)
        if not v_y.ok:
            rejected.append(Rejection(c.id, v_y.axis, v_y.details, kind=c.kind, parent_id=c.parent_id))
            continue

        v_y2 = axis_y2_clean(c)
        if not v_y2.ok:
            rejected.append(Rejection(c.id, v_y2.axis, v_y2.details, kind=c.kind, parent_id=c.parent_id))
            continue

        kept.append(c)

    return kept, rejected


# ─── Newton-Apple QC Checksum ─────────────────────────────────────────────────

def newton_apple_checksum(
    axiom: Axiom,
    kept: List[Component],
    rejected: List[Rejection],
    system_verdicts: Dict[str, Verdict],
) -> str:
    """
    Invariant hash of the validated system.
    Same inputs → same audit trail.
    If the story changes, the hash breaks.

    Checksum = 𝕍ᵧ × T(z) × M(t) × ∇(understanding)
    Here encoded as a SHA-256 of the serialised system state.
    """
    payload = {
        "axiom": _to_plain(axiom),
        "kept": [_to_plain(c) for c in kept],
        "rejected": [_to_plain(r) for r in rejected],
        "verdicts": {k: _to_plain(v) for k, v in system_verdicts.items()},
    }
    return _hash_payload(payload)


# ─── End-to-end Runtime ───────────────────────────────────────────────────────

def run_system(
    axiom: Axiom,
    seeds: List[Seed],
    options: Optional[RuntimeOptions] = None,
    expand: bool = True,
    provided_components: Optional[List[Component]] = None,
) -> SystemReport:
    """
    Full Nebraska axis stack.

    Phase 0 — initialise
    Phase 1 — X axis expansion (or use provided_components)
    Phase 2 — Axis Intervention (Y + Y2 pruning)
    Phase 3 — Y3, Z, Z⁻¹ system-level verdicts
    Phase 4 — Newton-Apple QC checksum
    """
    options = options or RuntimeOptions()

    all_candidates: List[Component] = []
    if provided_components:
        all_candidates.extend(provided_components)

    if expand:
        for s in seeds:
            all_candidates.extend(axis_x_expand(s, options.max_expansions_per_seed))
    else:
        # No expansion: convert seeds directly into components.
        for s in seeds:
            all_candidates.append(
                Component(
                    id=s.id,
                    kind=s.kind,
                    x=s.x,
                    y=s.y,
                    transform="seed",
                    justification=f"Seed conversion attempt under axiom: {axiom.law}",
                    parent_id=None,
                    meta=s.meta,
                )
            )

    kept, rejected = axis_intervention_prune(axiom, all_candidates)

    system_verdicts: Dict[str, Verdict] = {}
    system_verdicts["Y3"] = axis_y3_integration(kept)
    system_verdicts["Z"] = axis_z_meta(axiom, kept, rejected)

    if options.enable_inversion:
        system_verdicts["ZINV"] = axis_z_inversion(axiom, kept)
    else:
        system_verdicts["ZINV"] = Verdict(True, "ZINV", "Skipped by option.", 1.0)

    ok = all(v.ok for v in system_verdicts.values())

    checksum = ""
    if options.qc_checksum_enabled:
        checksum = newton_apple_checksum(axiom, kept, rejected, system_verdicts)

    summary = {
        "seed_count": len(seeds),
        "candidate_count": len(all_candidates),
        "kept_count": len(kept),
        "rejected_count": len(rejected),
        "system_ok": ok,
        "axiom": axiom.name,
        "axiom_version": axiom.version,
        # Nebraska 2.0 memory architecture summary
        "memory": {
            "short_term": f"{min(len(kept), 7)} active components (STM ceiling: 7±2)",
            "long_term": f"{len(kept)} patterns validated for LTM storage",
            "temporal_axis": "Z bidirectional" if options.enable_inversion else "Z forward-only",
        },
    }

    return SystemReport(
        ok=ok,
        axiom=axiom,
        summary=summary,
        kept=kept,
        rejected=rejected,
        system_verdicts=system_verdicts,
        checksum=checksum,
    )


# ─── Python API (importable by main.py) ──────────────────────────────────────

def run_from_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience wrapper for the Nightmare Engine FastAPI layer.
    Accepts a plain dict, returns a plain dict report.
    """
    ax = payload.get("axiom", {})
    axiom = Axiom(
        name=str(ax.get("name", "Unnamed")),
        law=str(ax.get("law", "")),
        required_tokens=tuple(ax.get("required_tokens") or []),
        forbidden_tokens=tuple(ax.get("forbidden_tokens") or []),
        version=str(ax.get("version", "1.0")),
        notes=str(ax.get("notes", "")),
    )

    seeds = [
        Seed(
            id=str(s["id"]),
            x=str(s.get("x", "")),
            y=str(s.get("y", "")),
            kind=str(s.get("kind", "seed")),
            meta=dict(s.get("meta") or {}),
        )
        for s in (payload.get("seeds") or [])
    ]

    comps_raw = payload.get("components")
    provided = None
    if comps_raw:
        provided = [
            Component(
                id=str(c["id"]),
                kind=str(c.get("kind", "component")),
                x=str(c.get("x", "")),
                y=str(c.get("y", "")),
                transform=str(c.get("transform", "")),
                justification=str(c.get("justification", "")),
                parent_id=c.get("parent_id"),
                meta=dict(c.get("meta") or {}),
            )
            for c in comps_raw
        ]

    opt = payload.get("options") or {}
    options = RuntimeOptions(
        max_expansions_per_seed=int(opt.get("max_expansions_per_seed", 6)),
        enable_inversion=bool(opt.get("enable_inversion", True)),
        stop_on_first_system_failure=bool(opt.get("stop_on_first_system_failure", False)),
        qc_checksum_enabled=bool(opt.get("qc_checksum_enabled", True)),
        verbose=bool(opt.get("verbose", False)),
    )

    report = run_system(
        axiom=axiom,
        seeds=seeds,
        options=options,
        expand=not bool(payload.get("no_expand", False)),
        provided_components=provided,
    )
    return _to_plain(report)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _load_json(path: Optional[str], use_stdin: bool) -> Dict[str, Any]:
    if use_stdin:
        raw = sys.stdin.read()
        if not raw.strip():
            raise SystemExit("stdin empty; pass --in FILE or pipe JSON into --stdin")
        return json.loads(raw)
    if not path:
        raise SystemExit("Missing --in FILE (or use --stdin)")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Optional[str], obj: Any) -> None:
    out = json.dumps(_to_plain(obj), ensure_ascii=False, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(out + "\n")
    else:
        sys.stdout.write(out + "\n")


def _pretty_summary(report: SystemReport) -> None:
    """Compact human-readable output to stderr."""
    ok = report.ok
    s = report.summary
    print(f"\n── Nebraska Report ─────────────────────────────", file=sys.stderr)
    print(f"  Axiom     : {report.axiom.name} (v{report.axiom.version})", file=sys.stderr)
    print(f"  Seeds     : {s['seed_count']}", file=sys.stderr)
    print(f"  Candidates: {s['candidate_count']}", file=sys.stderr)
    print(f"  Kept      : {s['kept_count']}", file=sys.stderr)
    print(f"  Rejected  : {s['rejected_count']}", file=sys.stderr)
    print(f"  System OK : {ok}", file=sys.stderr)
    if report.checksum:
        print(f"  Checksum  : {report.checksum[:16]}…", file=sys.stderr)

    print(f"\n  Axis verdicts:", file=sys.stderr)
    for axis, v in report.system_verdicts.items():
        tag = "✓" if v.ok else "✗"
        print(f"    [{tag}] {axis}: {v.details}", file=sys.stderr)

    if report.rejected:
        print(f"\n  First rejections (up to 5):", file=sys.stderr)
        for r in report.rejected[:5]:
            print(f"    [{r.axis}] {r.id}: {r.reason}", file=sys.stderr)
    print(file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="nebraska_runtime",
        description=(
            "Nebraska Generative System — Full axis stack runtime.\n"
            "Implements: X expansion → Y validity gate → Y2 anti-weasel → "
            "Y3 integration → Z meta → Z⁻¹ inversion → Newton-Apple QC checksum."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("cmd", choices=["run"], help="run the axis stack on a JSON payload")
    p.add_argument("--in", dest="in_path", help="input JSON file path")
    p.add_argument("--out", dest="out_path", help="output JSON file path (default: stdout)")
    p.add_argument("--stdin", action="store_true", help="read input from stdin")
    p.add_argument("--no-expand", action="store_true", help="skip X expansion; validate seeds/components directly")
    p.add_argument("--no-inversion", action="store_true", help="disable Z-inversion adversarial test")
    p.add_argument("--no-checksum", action="store_true", help="disable Newton-Apple QC checksum")
    p.add_argument("--pretty", action="store_true", help="print human-readable summary to stderr")
    args = p.parse_args(argv)

    inp = _load_json(args.in_path, args.stdin)

    ax = inp.get("axiom", {})
    axiom = Axiom(
        name=str(ax.get("name", "")),
        law=str(ax.get("law", "")),
        required_tokens=tuple(ax.get("required_tokens") or []),
        forbidden_tokens=tuple(ax.get("forbidden_tokens") or []),
        version=str(ax.get("version", "1.0")),
        notes=str(ax.get("notes", "")),
    )

    seeds = [
        Seed(
            id=str(s["id"]),
            x=str(s.get("x", "")),
            y=str(s.get("y", "")),
            kind=str(s.get("kind", "seed")),
            meta=dict(s.get("meta") or {}),
        )
        for s in (inp.get("seeds") or [])
    ]

    comps_raw = inp.get("components")
    provided_components = None
    if comps_raw:
        provided_components = [
            Component(
                id=str(c["id"]),
                kind=str(c.get("kind", "component")),
                x=str(c.get("x", "")),
                y=str(c.get("y", "")),
                transform=str(c.get("transform", "")),
                justification=str(c.get("justification", "")),
                parent_id=c.get("parent_id"),
                meta=dict(c.get("meta") or {}),
            )
            for c in comps_raw
        ]

    opt = inp.get("options") or {}
    options = RuntimeOptions(
        max_expansions_per_seed=int(opt.get("max_expansions_per_seed", 6)),
        enable_inversion=not args.no_inversion and bool(opt.get("enable_inversion", True)),
        stop_on_first_system_failure=bool(opt.get("stop_on_first_system_failure", False)),
        qc_checksum_enabled=not args.no_checksum and bool(opt.get("qc_checksum_enabled", True)),
        verbose=bool(opt.get("verbose", False)),
    )

    report = run_system(
        axiom=axiom,
        seeds=seeds,
        options=options,
        expand=not args.no_expand,
        provided_components=provided_components,
    )

    if args.pretty:
        _pretty_summary(report)

    _write_json(args.out_path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

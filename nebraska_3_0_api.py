"""
Nebraska 3.0 — Creative Suite API

A substrate-agnostic, multi-domain creative generation and validation platform
implementing the Nebraska Generative System as a collaborative human-AI workspace.

Nebraska 3.0 features (roadmap §9.2):
  • Recursive self-improvement within Quadrivium constraints
  • Emergent narrative discovery (system can surface Axiom variations)
  • Universal creativity protocol — works across all domains
  • Human-AI collaborative workspace (propose, validate, chain, export)

Supported domains:
  story     — Narrative / fiction / horror
  strategy  — Business strategy / competitive positioning
  research  — Academic argument / hypothesis / contribution
  design    — UX / product / systems design decisions
  code      — Software architecture / engineering decisions

Endpoints:
  POST /v3/workspace/create              — Create collaborative workspace
  GET  /v3/workspace/{id}                — Get workspace state
  DELETE /v3/workspace/{id}              — Close workspace
  POST /v3/workspace/{id}/generate       — AI-generate & validate components
  POST /v3/workspace/{id}/propose        — Human-propose a component for validation
  POST /v3/workspace/{id}/improve        — Auto-improve lowest-QCS component
  POST /v3/workspace/{id}/pipeline       — Run full axis stack on pending components
  POST /v3/workspace/{id}/handshake      — Validate A→B chain link
  GET  /v3/workspace/{id}/chain          — Get validated chain
  GET  /v3/workspace/{id}/audit          — Full Nebraska audit trail
  GET  /v3/workspace/{id}/provenance     — Component provenance chain
  GET  /v3/workspace/{id}/export         — Export validated narrative
  POST /v3/axiom/extract                 — Extract Axiom from any premise
  POST /v3/axiom/emerge                  — Surface emergent Axiom variations from components
  POST /v3/component/validate            — Standalone component validation
  POST /v3/handshake                     — Standalone handshake validation
  GET  /v3/engine/status                 — Engine status, QCS thresholds, Prime Directives
  POST /v3/engine/process                — Direct engine processing (low-level)
  WS   /v3/stream/{workspace_id}         — Real-time collaborative event stream

Run standalone:
  uvicorn nebraska_3_0_api:app --host 0.0.0.0 --port 8001 --reload
"""

import asyncio
import time
import uuid
from enum import Enum
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from nebraska_protocols import (
    NarrativeComponent,
    NebraskaProtocol,
    FORMULA,
    CONTRACT,
    RECURSIVE_LAW,
    QCS_THRESHOLDS,
    qcs_certification,
    DEFAULT_AXIOM,
)
from nebraska_2_0 import (
    NebraskaEngine,
    TransformerAdapter,
    TemplateAdapter,
    HandshakeGenerator,
    ProvenanceAnalyzer,
    QuadriviumAuditor,
    NebraskaInterfaceProtocol,
    SubstrateType,
    ProcessingStatus,
    DOMAIN_AXIOMS,
    DOMAIN_TEMPLATES,
)

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Nebraska 3.0 Creative Suite",
    description=(
        "Substrate-agnostic collaborative narrative generation and validation platform.\n\n"
        f"**Formula:** {FORMULA}\n\n"
        f"**Contract:** {CONTRACT}"
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Domain enum ─────────────────────────────────────────────────────────────

class Domain(str, Enum):
    STORY    = "story"
    STRATEGY = "strategy"
    RESEARCH = "research"
    DESIGN   = "design"
    CODE     = "code"

# ─── In-memory workspace store ────────────────────────────────────────────────

workspaces: dict[str, dict[str, Any]] = {}

# ─── Shared engine ────────────────────────────────────────────────────────────

_engine = NebraskaEngine()
_handshake_gen = HandshakeGenerator()
_provenance = ProvenanceAnalyzer()
_auditor = QuadriviumAuditor()
_nip = NebraskaInterfaceProtocol()

# ─── Pydantic models ─────────────────────────────────────────────────────────

class WorkspaceCreateRequest(BaseModel):
    domain: Domain = Domain.STORY
    premise: str
    axiom: Optional[str] = None          # override auto-extracted axiom
    collaborator_id: str = "anonymous"

class GenerateRequest(BaseModel):
    count: int = 3
    context: Optional[dict] = None       # extra domain context

class ProposeRequest(BaseModel):
    content: str
    name: Optional[str] = None
    author: str = "human"                # "human" | "ai"

class ImproveRequest(BaseModel):
    target_component: Optional[str] = None  # name of component to improve; None = lowest QCS

class PipelineRequest(BaseModel):
    candidates: list[str]
    names: Optional[list[str]] = None
    apply_z_inversion: bool = False
    apply_z_proof: bool = True

class WorkspaceHandshakeRequest(BaseModel):
    from_component: str                  # component name
    to_component: str                    # component name

class AxiomExtractRequest(BaseModel):
    premise: str
    domain: Domain = Domain.STORY
    fear_type: Optional[str] = None      # for story domain

class AxiomEmergeRequest(BaseModel):
    workspace_id: str

class ComponentValidateRequest(BaseModel):
    content: str
    axiom: str
    name: str = "input"
    narrative_history: Optional[list[str]] = None

class StandaloneHandshakeRequest(BaseModel):
    content_a: str
    name_a: str = "component_a"
    x_a: str = ""
    y_a: str = ""
    content_b: str
    name_b: str = "component_b"
    x_b: str = ""
    y_b: str = ""
    axiom: str

class EngineProcessRequest(BaseModel):
    potential: str
    axiom: str
    count: int = 3
    domain: Domain = Domain.STORY
    names: Optional[list[str]] = None

# ─── Workspace helpers ────────────────────────────────────────────────────────

def _new_workspace(
    domain: Domain,
    premise: str,
    axiom: str,
    collaborator_id: str,
) -> dict:
    ws_id = f"ws_{uuid.uuid4().hex[:12]}"
    proto = NebraskaProtocol(axiom)
    z_valid = proto.z_axis_meta(premise)

    return {
        "workspace_id": ws_id,
        "domain": domain.value,
        "premise": premise,
        "axiom": axiom,
        "z_premise_valid": z_valid,
        "components": [],           # all NarrativeComponent summaries
        "chain": [],                # ordered validated chain
        "narrative_history": [],    # content of validated components
        "pending": [],              # proposed but not yet validated
        "audit_trail": [],          # log of all operations
        "collaborators": set(),     # WebSocket clients
        "qcs_scores": [],           # running QCS history
        "certification": "Uncertified",
        "created_at": time.time(),
        "collaborator_id": collaborator_id,
        "emergent_axioms": [],      # system-surfaced axiom variations
    }


def _get_workspace(workspace_id: str) -> dict:
    if workspace_id not in workspaces:
        raise HTTPException(404, f"Workspace '{workspace_id}' not found")
    return workspaces[workspace_id]


def _log(ws: dict, event: str, detail: dict) -> None:
    ws["audit_trail"].append({
        "t": time.time(),
        "event": event,
        **detail,
    })


async def _broadcast(workspace_id: str, payload: dict) -> None:
    if workspace_id not in workspaces:
        return
    clients: set[WebSocket] = workspaces[workspace_id].get("collaborators", set())
    dead: set[WebSocket] = set()
    for ws in list(clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    clients -= dead


def _extract_axiom(premise: str, domain: Domain, fear_type: Optional[str] = None) -> tuple[str, bool]:
    """Extract Axiom from premise. Returns (axiom, z_valid)."""
    from nebraska_protocols import FEAR_AXIOMS

    if domain == Domain.STORY and fear_type:
        axiom = FEAR_AXIOMS.get(fear_type, DOMAIN_AXIOMS["story"])
    else:
        axiom = DOMAIN_AXIOMS.get(domain.value, DEFAULT_AXIOM)

    proto = NebraskaProtocol(axiom)
    z_valid = proto.z_axis_meta(premise)
    return axiom, z_valid


# ─── Workspace endpoints ──────────────────────────────────────────────────────

@app.post("/v3/workspace/create", summary="Create collaborative workspace")
async def workspace_create(req: WorkspaceCreateRequest):
    """
    Create a Nebraska 3.0 collaborative workspace.

    The workspace is the creative container — it holds:
      • The governing Axiom (extracted or provided)
      • All proposed and validated components
      • The growing validated chain
      • A full Nebraska audit trail
    """
    axiom, z_valid = _extract_axiom(req.premise, req.domain)
    if req.axiom:
        axiom = req.axiom   # honour explicit override
        proto = NebraskaProtocol(axiom)
        z_valid = proto.z_axis_meta(req.premise)

    ws = _new_workspace(req.domain, req.premise, axiom, req.collaborator_id)
    workspaces[ws["workspace_id"]] = ws
    _log(ws, "workspace_created", {
        "domain": req.domain.value,
        "axiom": axiom,
        "z_premise_valid": z_valid,
    })

    return {
        "workspace_id": ws["workspace_id"],
        "domain": req.domain.value,
        "axiom": axiom,
        "formula": FORMULA,
        "z_premise_valid": z_valid,
        "message": (
            "Workspace created. Axiom is the governing law. "
            "Every component must convert X→Y under this law, or be rejected."
        ),
        "next_steps": [
            "POST /v3/workspace/{id}/generate — AI-generate validated components",
            "POST /v3/workspace/{id}/propose  — Propose your own component",
            "GET  /v3/workspace/{id}/audit    — Inspect audit trail",
            "GET  /v3/workspace/{id}/export   — Export validated narrative",
        ],
    }


@app.get("/v3/workspace/{workspace_id}", summary="Get workspace state")
async def workspace_get(workspace_id: str):
    ws = _get_workspace(workspace_id)
    valid_count = sum(1 for c in ws["components"] if c.get("valid"))
    mean_qcs = (
        sum(ws["qcs_scores"]) / len(ws["qcs_scores"])
        if ws["qcs_scores"] else 0.0
    )
    return {
        "workspace_id": workspace_id,
        "domain": ws["domain"],
        "axiom": ws["axiom"],
        "formula": FORMULA,
        "z_premise_valid": ws["z_premise_valid"],
        "components_total": len(ws["components"]),
        "components_valid": valid_count,
        "chain_length": len(ws["chain"]),
        "pending_count": len(ws["pending"]),
        "mean_qcs": round(mean_qcs, 4) if mean_qcs else None,
        "certification": qcs_certification(mean_qcs) if mean_qcs else "Uncertified",
        "emergent_axioms": ws["emergent_axioms"],
        "created_at": ws["created_at"],
    }


@app.delete("/v3/workspace/{workspace_id}", summary="Close workspace")
async def workspace_delete(workspace_id: str):
    ws = _get_workspace(workspace_id)
    del workspaces[workspace_id]
    return {"status": "closed", "workspace_id": workspace_id}


# ─── Generation & validation ─────────────────────────────────────────────────

@app.post("/v3/workspace/{workspace_id}/generate", summary="AI-generate validated components")
async def workspace_generate(workspace_id: str, req: GenerateRequest):
    """
    Generate `count` candidates using the AI substrate, validate them through
    the full Nebraska axis stack, and add survivors to the workspace.

    Includes recursive self-improvement: if QC fails, the engine automatically
    generates alternatives until QCS ≥ Bronze or max iterations reached.
    """
    ws = _get_workspace(workspace_id)
    axiom = ws["axiom"]
    history = ws["narrative_history"]

    ctx = {"domain": ws["domain"], "narrative_history": history}
    if req.context:
        ctx.update(req.context)

    result = _engine.process(
        potential=ws["premise"],
        axiom=axiom,
        count=req.count,
        context=ctx,
    )

    survivors = result["survivors"]
    for comp_summary in survivors:
        ws["components"].append(comp_summary)
        ws["chain"].append(comp_summary)
        ws["narrative_history"].append(comp_summary.get("content_preview", ""))
        if comp_summary.get("qcs") is not None:
            ws["qcs_scores"].append(comp_summary["qcs"])

    mean_qcs = sum(ws["qcs_scores"]) / max(1, len(ws["qcs_scores"]))

    _log(ws, "generate", {
        "generated": req.count,
        "survivors": len(survivors),
        "mean_qcs": round(mean_qcs, 4),
        "improvement_iterations": result.get("improvement_iterations", 0),
    })

    await _broadcast(workspace_id, {
        "event": "components_generated",
        "survivors": len(survivors),
        "mean_qcs": round(mean_qcs, 4),
        "certification": qcs_certification(mean_qcs),
    })

    return {
        "survivors": survivors,
        "survivors_count": len(survivors),
        "z_premise_valid": result["z_premise_valid"],
        "qc": result["qc"],
        "improvement_iterations": result.get("improvement_iterations", 0),
        "chain_length": len(ws["chain"]),
        "mean_qcs": round(mean_qcs, 4),
        "certification": qcs_certification(mean_qcs),
    }


@app.post("/v3/workspace/{workspace_id}/propose", summary="Propose a component for validation")
async def workspace_propose(workspace_id: str, req: ProposeRequest):
    """
    Human (or any author) proposes a component.  Nebraska validates it
    through the full Fourfold Test under the workspace Axiom.

    Nothing gets in without a valid X→Y conversion.  Human and AI components
    are subject to exactly the same gates — no free passes.
    """
    ws = _get_workspace(workspace_id)
    axiom = ws["axiom"]
    name = req.name or f"proposal_{len(ws['components']) + 1}"

    result = _engine.validate_single(
        content=req.content,
        axiom=axiom,
        name=name,
        narrative_history=ws["narrative_history"],
    )

    comp_summary = result["component"]

    if comp_summary.get("valid"):
        ws["components"].append(comp_summary)
        ws["chain"].append(comp_summary)
        ws["narrative_history"].append(req.content[:200])
        if comp_summary.get("qcs") is not None:
            ws["qcs_scores"].append(comp_summary["qcs"])
        status = "accepted"
    else:
        ws["pending"].append(comp_summary)
        status = "rejected"

    _log(ws, "propose", {
        "author": req.author,
        "name": name,
        "status": status,
        "qcs": result.get("qcs"),
        "rejection_reason": comp_summary.get("rejection_reason", ""),
    })

    await _broadcast(workspace_id, {
        "event": "component_proposed",
        "name": name,
        "author": req.author,
        "status": status,
        "qcs": result.get("qcs"),
    })

    return {
        "status": status,
        "component": comp_summary,
        "qcs": result.get("qcs"),
        "certification": result.get("certification"),
        "governor_veto": result.get("governor_veto"),
        "chain_length": len(ws["chain"]),
    }


@app.post("/v3/workspace/{workspace_id}/improve", summary="Auto-improve lowest-QCS component")
async def workspace_improve(workspace_id: str, req: ImproveRequest):
    """
    Nebraska 3.0 recursive self-improvement.

    Identifies the lowest-QCS component in the chain, removes it, and
    regenerates a replacement that better serves the Axiom.

    This is the 'Recursive self-improvement within Quadrivium constraints' feature.
    """
    ws = _get_workspace(workspace_id)
    axiom = ws["axiom"]

    if not ws["chain"]:
        raise HTTPException(400, "No components in chain to improve")

    # Find target: lowest QCS, or named component
    target = None
    if req.target_component:
        target = next(
            (c for c in ws["chain"] if c.get("name") == req.target_component),
            None,
        )
        if not target:
            raise HTTPException(404, f"Component '{req.target_component}' not in chain")
    else:
        valid_comps = [c for c in ws["chain"] if c.get("qcs") is not None]
        if valid_comps:
            target = min(valid_comps, key=lambda c: c.get("qcs", 0))

    if not target:
        raise HTTPException(400, "No valid component found for improvement")

    old_qcs = target.get("qcs", 0)
    old_name = target.get("name", "unknown")

    # Remove target from chain
    ws["chain"] = [c for c in ws["chain"] if c.get("name") != old_name]
    ws["components"] = [c for c in ws["components"] if c.get("name") != old_name]

    # Regenerate
    ctx = {"domain": ws["domain"], "narrative_history": ws["narrative_history"]}
    result = _engine.process(
        potential=ws["premise"],
        axiom=axiom,
        count=3,
        context=ctx,
    )

    survivors = result["survivors"]
    if survivors:
        replacement = survivors[0]
        ws["components"].append(replacement)
        ws["chain"].append(replacement)
        ws["narrative_history"].append(replacement.get("content_preview", ""))
        if replacement.get("qcs") is not None:
            ws["qcs_scores"].append(replacement["qcs"])
        improved = replacement.get("qcs", 0) > old_qcs
    else:
        replacement = None
        improved = False

    _log(ws, "improve", {
        "target": old_name,
        "old_qcs": old_qcs,
        "new_qcs": replacement.get("qcs") if replacement else None,
        "improved": improved,
    })

    return {
        "target_removed": old_name,
        "old_qcs": old_qcs,
        "replacement": replacement,
        "improved": improved,
        "improvement_iterations": result.get("improvement_iterations", 0),
        "chain_length": len(ws["chain"]),
    }


@app.post("/v3/workspace/{workspace_id}/pipeline", summary="Run full axis stack on candidates")
async def workspace_pipeline(workspace_id: str, req: PipelineRequest):
    """
    Run the full Nebraska axis stack on a provided list of candidate texts.

    Useful for batch validation of externally-sourced content.
    """
    ws = _get_workspace(workspace_id)
    axiom = ws["axiom"]
    proto = NebraskaProtocol(axiom)

    survivors, qc = proto.run_full_pipeline(
        candidates=req.candidates,
        names=req.names,
        premise=ws["premise"],
        narrative_history=ws["narrative_history"],
        apply_z_inversion=req.apply_z_inversion,
        apply_z_proof=req.apply_z_proof,
    )

    for comp in survivors:
        ws["components"].append(comp.summary())
        ws["chain"].append(comp.summary())
        ws["narrative_history"].append(comp.content[:200])
        if comp.qcs >= 0:
            ws["qcs_scores"].append(comp.qcs)

    _log(ws, "pipeline", {
        "candidates": len(req.candidates),
        "survivors": len(survivors),
        "qc_pass": qc["pass"],
    })

    return {
        "survivors": [c.summary() for c in survivors],
        "survivors_count": len(survivors),
        "qc": qc,
        "chain_length": len(ws["chain"]),
    }


# ─── Chain building ───────────────────────────────────────────────────────────

@app.post("/v3/workspace/{workspace_id}/handshake", summary="Validate A→B chain link")
async def workspace_handshake(workspace_id: str, req: WorkspaceHandshakeRequest):
    """
    Validate the chain link between two components in the workspace.

    A valid handshake proves A.Y creates the conditions for B.X.
    'Swap them, and the logic chain snaps.'
    """
    ws = _get_workspace(workspace_id)
    axiom = ws["axiom"]

    comp_a_data = next(
        (c for c in ws["components"] if c.get("name") == req.from_component), None
    )
    comp_b_data = next(
        (c for c in ws["components"] if c.get("name") == req.to_component), None
    )

    if not comp_a_data:
        raise HTTPException(404, f"Component '{req.from_component}' not in workspace")
    if not comp_b_data:
        raise HTTPException(404, f"Component '{req.to_component}' not in workspace")

    comp_a = NarrativeComponent(
        name=comp_a_data["name"],
        content=comp_a_data.get("content_preview", ""),
        x=comp_a_data.get("x", ""),
        y=comp_a_data.get("y", ""),
    )
    comp_b = NarrativeComponent(
        name=comp_b_data["name"],
        content=comp_b_data.get("content_preview", ""),
        x=comp_b_data.get("x", ""),
        y=comp_b_data.get("y", ""),
    )

    hs = _handshake_gen.generate(comp_a, comp_b, axiom)
    _log(ws, "handshake", {
        "from": req.from_component,
        "to": req.to_component,
        "valid": hs.valid,
        "causal_strength": hs.causal_strength,
    })

    return hs.to_dict()


@app.get("/v3/workspace/{workspace_id}/chain", summary="Get validated chain")
async def workspace_chain(workspace_id: str):
    """
    Return the current validated component chain with full handshake analysis.
    """
    ws = _get_workspace(workspace_id)
    axiom = ws["axiom"]

    comps = [
        NarrativeComponent(
            name=c.get("name", f"c_{i}"),
            content=c.get("content_preview", ""),
            x=c.get("x", ""),
            y=c.get("y", ""),
            vy=1 if c.get("valid") else 0,
            y2_pass=c.get("y2_pass", False),
            qcs=c.get("qcs", -1.0),
        )
        for i, c in enumerate(ws["chain"])
    ]

    chain_result = (
        _handshake_gen.validate_chain(comps, axiom)
        if len(comps) >= 2 else {"valid": True, "handshakes": [], "broken_links": []}
    )

    return {
        "axiom": axiom,
        "chain_length": len(ws["chain"]),
        "components": ws["chain"],
        "chain_validation": chain_result,
    }


# ─── Audit & export ──────────────────────────────────────────────────────────

@app.get("/v3/workspace/{workspace_id}/audit", summary="Full Nebraska audit trail")
async def workspace_audit(workspace_id: str):
    ws = _get_workspace(workspace_id)
    axiom = ws["axiom"]
    history = ws["narrative_history"]

    comps = [
        NarrativeComponent(
            name=c.get("name", f"c_{i}"),
            content=c.get("content_preview", ""),
            x=c.get("x", ""),
            y=c.get("y", ""),
            vy=1 if c.get("valid") else 0,
            y2_pass=c.get("y2_pass", False),
        )
        for i, c in enumerate(ws["chain"])
    ]

    audit_result = _auditor.audit(comps, axiom, history)
    mean_qcs = audit_result.get("mean_qcs", 0.0)

    return {
        "workspace_id": workspace_id,
        "axiom": axiom,
        "formula": FORMULA,
        "prime_equation": "𝕍ᵧ ≡ T(z) ≡ M(t) ≡ ∇(understanding)",
        "contract": CONTRACT,
        "recursive_law": RECURSIVE_LAW,
        "z_premise_valid": ws["z_premise_valid"],
        "chain_length": len(ws["chain"]),
        "audit": audit_result,
        "mean_qcs": round(mean_qcs, 4),
        "certification": qcs_certification(mean_qcs),
        "operations_log": ws["audit_trail"][-20:],   # last 20 operations
        "emergent_axioms": ws["emergent_axioms"],
    }


@app.get("/v3/workspace/{workspace_id}/provenance", summary="Component provenance chain")
async def workspace_provenance(workspace_id: str):
    ws = _get_workspace(workspace_id)

    comps = [
        NarrativeComponent(
            name=c.get("name", f"c_{i}"),
            content=c.get("content_preview", ""),
            vy=1 if c.get("valid") else 0,
            y2_pass=c.get("y2_pass", False),
            qcs=c.get("qcs", -1.0),
            rejection_reason=c.get("rejection_reason", ""),
        )
        for i, c in enumerate(ws["components"])
    ]

    prov = _provenance.analyze_chain(comps, SubstrateType.HYBRID)

    return {
        "workspace_id": workspace_id,
        "axiom": ws["axiom"],
        "provenance": prov,
    }


@app.get("/v3/workspace/{workspace_id}/export", summary="Export validated narrative")
async def workspace_export(workspace_id: str):
    """
    Export the workspace's validated narrative as a structured document.

    The export contains:
      • Axiom (governing law)
      • Validated component chain with X→Y mappings
      • QCS scores and certification
      • Full Nebraska audit
      • NIP-encoded transmission packet
    """
    ws = _get_workspace(workspace_id)
    axiom = ws["axiom"]

    comps = [
        NarrativeComponent(
            name=c.get("name", f"c_{i}"),
            content=c.get("content_preview", ""),
            x=c.get("x", ""),
            y=c.get("y", ""),
            vy=1 if c.get("valid") else 0,
            y2_pass=c.get("y2_pass", False),
            qcs=c.get("qcs", -1.0),
        )
        for i, c in enumerate(ws["chain"])
    ]

    proto = NebraskaProtocol(axiom)
    qc = proto.newton_qc(comps, ws["narrative_history"])
    encoded = _nip.encode(comps, axiom, qc)

    return {
        "export_version": "nebraska_3.0",
        "domain": ws["domain"],
        "axiom": axiom,
        "formula": FORMULA,
        "contract": CONTRACT,
        "premise": ws["premise"],
        "z_premise_valid": ws["z_premise_valid"],
        "chain": [
            {
                "order": i + 1,
                "name": c.get("name"),
                "x": c.get("x", ""),
                "y": c.get("y", ""),
                "content": c.get("content_preview", ""),
                "qcs": c.get("qcs"),
                "certification": qcs_certification(c.get("qcs", 0)) if c.get("qcs") else None,
            }
            for i, c in enumerate(ws["chain"])
        ],
        "mean_qcs": qc.get("mean_qcs"),
        "certification": qc.get("certification"),
        "qc_pass": qc["pass"],
        "nip_encoded": encoded,
        "exported_at": time.time(),
    }


# ─── Axiom endpoints ─────────────────────────────────────────────────────────

@app.post("/v3/axiom/extract", summary="Extract Axiom from any premise")
async def axiom_extract(req: AxiomExtractRequest):
    """
    Extract the governing Axiom from a premise in any domain.

    The Axiom is the first principle the narrative will test or prove.
    Everything that follows must occur under its authority.
    """
    axiom, z_valid = _extract_axiom(req.premise, req.domain, req.fear_type)
    proto = NebraskaProtocol(axiom)

    return {
        "axiom": axiom,
        "domain": req.domain.value,
        "z_premise_valid": z_valid,
        "domain_template": DOMAIN_AXIOMS.get(req.domain.value),
        "formula": FORMULA,
        "note": (
            "The Axiom is the law.  Every component must convert X→Y under this law, "
            "or be excluded from the system."
            if z_valid
            else
            "WARNING: Premise may not carry a built-in deficit.  "
            "Refine it so there is a problem that demands resolution."
        ),
    }


@app.post("/v3/axiom/emerge", summary="Surface emergent Axiom variations")
async def axiom_emerge(req: AxiomEmergeRequest):
    """
    Nebraska 3.0 emergent narrative discovery.

    Analyzes the components already in the workspace and surfaces alternative
    Axiom formulations that might better capture the narrative's actual law.

    'Emergent narrative discovery (beyond human design).'
    """
    ws = _get_workspace(req.workspace_id)
    current_axiom = ws["axiom"]

    if not ws["chain"]:
        return {
            "current_axiom": current_axiom,
            "emergent_axioms": [],
            "recommendation": "Generate components first; emergence requires material to analyze.",
        }

    # Collect X and Y vocabulary from validated chain
    x_words: set[str] = set()
    y_words: set[str] = set()
    for comp in ws["chain"]:
        x_words.update(comp.get("x", "").lower().split())
        y_words.update(comp.get("y", "").lower().split())

    # Filter to content words
    stop = {"the", "a", "an", "of", "in", "to", "and", "it", "is", "was", "for"}
    x_words -= stop
    y_words -= stop

    # Surface emergent axiom: "Every [dominant X] converts to [dominant Y] under [domain law]"
    top_x = sorted(x_words, key=lambda w: len(w), reverse=True)[:3]
    top_y = sorted(y_words, key=lambda w: len(w), reverse=True)[:3]

    emergent: list[str] = []
    domain = ws["domain"]

    if top_x and top_y:
        emergent.append(
            f"Every {top_x[0]} carries the potential to convert into {top_y[0]} "
            f"under the law this {domain} establishes"
        )
    if len(top_x) >= 2 and len(top_y) >= 2:
        emergent.append(
            f"The {top_x[1]} and {top_x[0]} are not separate problems — "
            f"they are a single deficit demanding {top_y[0]}"
        )
    if domain in DOMAIN_AXIOMS:
        emergent.append(DOMAIN_AXIOMS[domain] + f" — specifically through {top_x[0] if top_x else 'the unnamed deficit'}")

    ws["emergent_axioms"] = emergent[:3]
    _log(ws, "emerge", {"emergent_count": len(emergent)})

    return {
        "current_axiom": current_axiom,
        "emergent_axioms": emergent,
        "dominant_x_vocabulary": top_x,
        "dominant_y_vocabulary": top_y,
        "recommendation": (
            f"Consider updating workspace Axiom to: '{emergent[0]}'"
            if emergent else "No clear emergent pattern yet — generate more components."
        ),
    }


# ─── Standalone endpoints ─────────────────────────────────────────────────────

@app.post("/v3/component/validate", summary="Standalone component validation")
async def component_validate(req: ComponentValidateRequest):
    """
    Validate a single component outside a workspace.
    Runs the full Fourfold Test: 𝕍ᵧ, T(z), M(t), ∇.
    """
    result = _engine.validate_single(
        content=req.content,
        axiom=req.axiom,
        name=req.name,
        narrative_history=req.narrative_history,
    )
    return result


@app.post("/v3/handshake", summary="Standalone handshake validation")
async def standalone_handshake(req: StandaloneHandshakeRequest):
    """
    Validate a chain link A.Y → B.X outside a workspace.
    """
    comp_a = NarrativeComponent(
        name=req.name_a, content=req.content_a,
        x=req.x_a, y=req.y_a,
    )
    comp_b = NarrativeComponent(
        name=req.name_b, content=req.content_b,
        x=req.x_b, y=req.y_b,
    )

    # If X/Y not provided, extract via protocol
    if not req.x_a or not req.y_a:
        proto = NebraskaProtocol(req.axiom)
        proto.y_axis_validate([comp_a])
    if not req.x_b or not req.y_b:
        proto = NebraskaProtocol(req.axiom)
        proto.y_axis_validate([comp_b])

    hs = _handshake_gen.generate(comp_a, comp_b, req.axiom)
    return hs.to_dict()


@app.get("/v3/engine/status", summary="Engine status and Prime Directives")
async def engine_status():
    """
    Nebraska 2.0 engine status: substrate info, QCS thresholds,
    certification levels, and Prime Directives.
    """
    return _engine.status()


@app.post("/v3/engine/process", summary="Direct engine processing (low-level)")
async def engine_process(req: EngineProcessRequest):
    """
    Direct access to the NebraskaEngine processing loop.

    a / b = story → meaning → understanding
    potential / axiom = narrative → validated → committed or quarantined
    """
    ctx = {"domain": req.domain.value}
    result = _engine.process(
        potential=req.potential,
        axiom=req.axiom,
        count=req.count,
        names=req.names,
        context=ctx,
    )
    return result


# ─── WebSocket streaming ──────────────────────────────────────────────────────

@app.websocket("/v3/stream/{workspace_id}")
async def workspace_stream(websocket: WebSocket, workspace_id: str):
    """
    Real-time collaborative event stream for a workspace.

    Events emitted:
      connected              — initial workspace state
      components_generated   — new components added from AI generation
      component_proposed     — human or AI proposal + validation result
      axiom_updated          — Axiom changed
      emergent_axioms        — new emergent axiom variations surfaced
      chain_updated          — chain modified
      audit_snapshot         — periodic QCS snapshot
    """
    await websocket.accept()

    if workspace_id not in workspaces:
        await websocket.close(code=4001)
        return

    ws = workspaces[workspace_id]
    ws["collaborators"].add(websocket)

    # Send initial state
    await websocket.send_json({
        "event": "connected",
        "workspace_id": workspace_id,
        "axiom": ws["axiom"],
        "formula": FORMULA,
        "chain_length": len(ws["chain"]),
        "z_premise_valid": ws["z_premise_valid"],
    })

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")

            if action == "ping":
                await websocket.send_json({"event": "pong", "t": time.time()})

            elif action == "audit_snapshot":
                mean_qcs = (
                    sum(ws["qcs_scores"]) / len(ws["qcs_scores"])
                    if ws["qcs_scores"] else 0.0
                )
                await websocket.send_json({
                    "event": "audit_snapshot",
                    "chain_length": len(ws["chain"]),
                    "mean_qcs": round(mean_qcs, 4),
                    "certification": qcs_certification(mean_qcs),
                })

            elif action == "get_chain":
                await websocket.send_json({
                    "event": "chain_state",
                    "chain": ws["chain"][-10:],  # last 10 components
                    "chain_length": len(ws["chain"]),
                })

    except WebSocketDisconnect:
        pass
    finally:
        ws["collaborators"].discard(websocket)


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", summary="Nebraska 3.0 Creative Suite")
async def root():
    return {
        "name": "Nebraska 3.0 Creative Suite",
        "version": "3.0.0",
        "formula": FORMULA,
        "prime_equation": "𝕍ᵧ ≡ T(z) ≡ M(t) ≡ ∇(understanding)",
        "contract": CONTRACT,
        "recursive_law": RECURSIVE_LAW,
        "domains": [d.value for d in Domain],
        "quick_start": [
            "POST /v3/workspace/create   — start with a premise and domain",
            "POST /v3/workspace/{id}/generate — AI-generate validated components",
            "POST /v3/workspace/{id}/propose  — add your own components",
            "GET  /v3/workspace/{id}/audit    — inspect the audit trail",
            "GET  /v3/workspace/{id}/export   — export the validated narrative",
        ],
        "engine_status": "/v3/engine/status",
    }

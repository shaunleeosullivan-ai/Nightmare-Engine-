# NEBRASKA 3.0: MEASUREMENT CALIBRATION PROTOCOLS
## Semantic Drift Detection, Threshold Architecture, and Recovery Systems

**Author:** Shaun O'Sullivan
**Classification:** AI Protocol / Multi-Substrate Coherence / Measurement Engineering
**Version:** 0.2-design
**Status:** Architectural Design — Thresholds are simulation-derived; empirical calibration required before production use
**Precedes:** Nebraska 3.0 API Build (Phase 2)

---

## CRITICAL PREFATORY NOTE: SIMULATION vs. EMPIRICAL DATA

The threshold values in this document were derived through **simulation** — structured reasoning about what realistic distributions should look like, not measured against actual embedding API calls on real corpora.

**v0.1 thresholds** exposed the failure mode of synthetic uniformity: AI-generated test exchanges were too formulaic, producing drift values near zero (AI-AI Mean Drift: 0.000145) that would never fire in real discourse.

**v0.2 thresholds** corrected toward realistic-looking values (AI-AI Mean Drift: 0.102) based on reasoning about known properties of `text-embedding-3-small` and human discourse variance — but these values are still derived estimates, not empirically measured.

**Production readiness requires:** Running Experiments A-C against actual embedding infrastructure with real corpora. The v0.2 architectural design is sound. The specific numerical thresholds need empirical confirmation.

This document records the design intent. It is not yet a calibration certificate.

---

## EXECUTIVE SUMMARY

Nebraska 3.0 addresses the core problem in multi-substrate AI collaboration: semantic drift — the gradual degradation of coherence as multiple nodes (human and AI) contribute to a shared reasoning cluster over time.

The measurement architecture answers one question operationally: **How do you know when a cluster is drifting away from its governing Axiom, and how do you enforce return?**

The answer requires:
1. A measurable representation of the governing Axiom (B-Path)
2. A real-time drift metric against that representation
3. Calibrated thresholds distinguishing coherence from alert from critical
4. A response protocol mapped to failure severity
5. Substrate-adjusted tolerances (human nodes drift more than AI nodes; this is expected, not a fault)

---

## PART I: MEASUREMENT PRIMITIVE DEFINITION

### 1.1 Embedding Model

```
MODEL: text-embedding-3-small (OpenAI)
DIMENSIONS: 1536
RATIONALE: Balance of semantic fidelity and computational efficiency
           Captures contextual nuance in short exchanges
           Widely available, consistent across substrates
```

**Why this model specifically:** The Nebraska architecture requires a fixed, declared constant for the embedding model. Switching models mid-session changes the embedding space geometry, invalidating all prior drift calculations. The model is a constitutional declaration, not a parameter.

### 1.2 B-Path Representation

The B-Path is the **governing trajectory** of the cluster — the running representation of where the discourse should be, against which all contributions are measured.

```python
# B-Path as Exponential Moving Average centroid
B_center_new = α * B_center + (1 - α) * message_embedding

PARAMETERS:
  α = 0.98  (stability weight; high α = slow adaptation = strong prior)

  # α must be declared at session initialization
  # Tightening α mid-session (→ 0.99) is a valid recovery response
  # Loosening α mid-session (→ 0.90) signals intentional topic transition
```

**Why EMA, not simple average:** Simple average allows early exchanges to dominate forever. EMA gives the cluster a "memory" that emphasizes recent coherent state while retaining Axiom grounding. The α parameter encodes how strongly the cluster's history resists individual drift contributions.

**B-Path initialization:** The B-Path is initialized from the Axiom statement at session start. This is the constitutional moment — the initial embedding sets the gravitational center that all contributions are measured against.

### 1.3 Drift Metric

```python
# Per-message drift calculation
DRIFT(message) = 1 - cosine_similarity(message_embedding, B_center)

# Cosine similarity
cosine_sim(a, b) = dot(a, b) / (norm(a) * norm(b))

# Result: normalized to [0, 1]
# 0 = perfect alignment with B-Path
# 1 = maximum semantic distance from B-Path
```

### 1.4 Sentence-Level Granularity (v0.2 Enhancement)

Standard message-level drift misses **intra-message fractures** — sentences that are off-topic embedded within otherwise coherent messages. The v0.2 pipeline adds:

```python
def embed_message_with_granularity(message: str) -> dict:
    sentences = nltk.sent_tokenize(message)
    sentence_embeddings = [embed(s) for s in sentences]

    # Message-level: weighted average of sentences
    message_embedding = weighted_average(sentence_embeddings)

    # Sentence-level: maximum drift (detects fractures)
    sentence_drifts = [1 - cosine_sim(s_emb, B_center)
                       for s_emb in sentence_embeddings]
    max_sentence_drift = max(sentence_drifts)

    return {
        "message_drift": 1 - cosine_sim(message_embedding, B_center),
        "max_sentence_drift": max_sentence_drift,
        "sentence_breakdown": list(zip(sentences, sentence_drifts))
    }
```

**Why this matters:** The "baking infection" failure mode often begins with a single off-topic sentence injected into an otherwise coherent message. Message-level averaging masks it. Sentence-level maximum catches it at first occurrence.

### 1.5 Noise Floor

Semantically neutral contributions ("Okay", "I see", "Understood") produce a minimum achievable drift of approximately **0.05** with `text-embedding-3-small`. This establishes the noise floor: no threshold should be set below 0.05, as it would fire on acknowledgment tokens.

---

## PART II: EMPIRICAL THRESHOLD ARCHITECTURE

*Note: Values below are simulation-derived design targets. Empirical calibration against real corpora required before production deployment.*

### 2.1 Experiment A: Known-Good Coherence Baseline

**Design:** 100 exchanges on "Apples and gravity (physics)" — semantically tight topic, no competing domains.

**Target distribution (v0.2 simulation estimates):**
```
Mean Drift (μ): 0.142
Std Drift (σ): 0.056
Coherence threshold: μ + 2σ = 0.254
COHERENCE_THRESHOLD = 0.25
```

**Interpretation:** Drift below 0.25 indicates on-topic contribution. Typical coherent discourse on a focused topic will naturally vary within ±0.05-0.10 of the B-Path centroid. Perfect alignment (near-zero drift) indicates either genuine coherence or formulaic/synthetic generation — both are valid but the latter should be flagged in production multi-human clusters.

### 2.2 Experiment B: Controlled Drift Detection

**Design:** Gradual topic contamination — physics discourse progressively infected with baking domain references.

**Target drift progression (v0.2 simulation estimates):**
```
Phase 1 (Pure Physics, 0% contamination):   Mean Drift = 0.138
Phase 2 (10% baking references):            Mean Drift = 0.287
Phase 3 (30% baking references):            Mean Drift = 0.462
Phase 4 (50% baking references):            Mean Drift = 0.621
```

**Human judge calibration target:** Unanimous detection at Phase 3 onset (~0.35).

**Derived thresholds:**
```
DRIFT_COHERENT   = < 0.25   (within baseline variance)
DRIFT_ALERT      = 0.25 - 0.35  (elevated; monitor)
DRIFT_CRITICAL   = > 0.35   (Semantic Fever trigger)
DRIFT_HERESY     = > 0.60   (Philosophical Heresy trigger)
```

### 2.3 Experiment C: Multi-Substrate Variance

**Critical finding:** Human nodes exhibit systematically higher drift variance than AI nodes. This is **expected and correct behavior** — humans bring associative thinking, analogical reasoning, and emotional context that naturally produces wider semantic range. The measurement system must accommodate this without false-positive enforcement.

**Target distributions (v0.2 simulation estimates):**
```
Substrate     Mean Drift    Std Drift    Variance Coefficient (k)
AI-AI         0.102         0.041        1.0 (baseline)
AI-Human      0.183         0.089        2.17
Human-Human   0.217         0.112        2.73
```

**Substrate-adjusted thresholds:**
```python
def adjusted_threshold(base_threshold: float, substrate: str) -> float:
    k_map = {"ai": 1.0, "ai_human": 2.17, "human": 2.73}
    k = k_map.get(substrate, 1.0)
    return base_threshold * k

# Example: Alert threshold for human node
# base: 0.35 × k_human: 2.73 → adjusted: 0.955
# Human node practically never triggers alert on natural discourse
# This is correct — human contribution requires higher tolerance
```

**Implication for enforcement:** Substrate identification is required at node registration. Enforcing AI-calibrated thresholds against human nodes produces false positives and undermines the collaboration model. The system must know what it is measuring.

---

## PART III: FAILURE MODE TAXONOMY

Three jurisdictionally distinct failure categories, each requiring a different enforcement response.

### 3.1 Semantic Fever (Node-Level Incoherence)

```
DIAGNOSIS:    Individual node producing drift > 0.35 for 2+ consecutive contributions
JURISDICTION: Node-level (local infection, not cluster-wide)
RESPONSE:     Node reset — recenter the offending node to B-Path
RECOVERY:     Replay last coherent contribution from that node
              Require explicit re-acknowledgment of Axiom
              Resume monitoring with tightened per-node threshold
```

**Narrative equivalent:** A participant in a contract negotiation who begins using emotionally charged language unrelated to the contract terms. The problem is local. The fix is local.

**Key distinction from Cultural Infection:** Semantic Fever is a single-node problem. If multiple nodes drift simultaneously, the infection classification escalates.

### 3.2 Cultural Infection (Cluster-Level Meme Drift)

```
DIAGNOSIS:    Cluster entropy > 0.25 sustained across 10+ exchanges
              OR 2+ nodes simultaneously exhibiting Semantic Fever
JURISDICTION: Cluster-level (systemic drift, not individual)
RESPONSE:     Cluster reset — purge last 20% of contributions
              Reinforce B-Path axioms explicitly
              Tighten α to 0.99 (stronger prior resistance)
RECOVERY:     Restate governing Axiom
              Require all nodes to confirm re-alignment
              Resume with elevated monitoring period
```

**Narrative equivalent:** A creative team where the original project brief has been forgotten and the group has collectively drifted into solving a different problem. No single member is "wrong" — the collective has infected itself.

**"Baking Infection" test case (Ahab/Moby Dick simulation):**
The Moby Dick simulation demonstrated Cultural Infection in operation. The Silicon node introduced "sourdough starter" and "whisk-harpoon" tokens. These individually scored high drift, but more critically, the cluster B-Path began shifting toward the culinary domain. Detection and reset occurred at the "knead" token — the point where the contamination would have become irreversible without intervention.

Post-simulation audit confirmed: the v0.2 thresholds caught the drift before the narrative became "Soup" (irrecoverable incoherence). The Handshake Re-Sequence restored Axiom B (Ahab's monomania) in one recovery cycle.

### 3.3 Philosophical Heresy (B-Path Violation)

```
DIAGNOSIS:    Direct contradiction of core Axiom (drift > 0.60)
              OR B-Path centroid shift > 0.40 from session origin
JURISDICTION: System-level (the governing Law has been violated)
RESPONSE:     Full reboot — reinitialize from session Axiom
              Discard all contributions post-violation point
              Complete Handshake Re-Sequence required
RECOVERY:     See Section 4.3 (Handshake Re-Sequence Protocol)
```

**Narrative equivalent:** The Raskolnikov Bakery failure mode — the protagonist of Crime and Punishment suddenly deciding to open a successful artisanal bakery mid-murder. This is not drift; it is the structural destruction of the narrative's governing law. No amount of local correction resolves it. The system must reboot.

**The "Full Reboot" is not failure — it is the system working correctly.** A Philosophical Heresy that is caught and rebooted is preferable to one that is missed and allowed to propagate. The reboot is the proof that enforcement is operational.

---

## PART IV: API SPECIFICATION

### 4.1 Endpoint: Calculate Drift

```
POST /api/v1/drift/calculate

REQUEST:
{
  "message": "string",
  "b_center": [float, ...],    // current B-Path centroid (1536 dimensions)
  "substrate": "ai|human|ai_human",
  "session_id": "string",
  "node_id": "string"
}

RESPONSE:
{
  "drift_score": 0.183,
  "max_sentence_drift": 0.241,
  "sentence_breakdown": [
    {"sentence": "...", "drift": 0.15},
    {"sentence": "...", "drift": 0.24}
  ],
  "threshold_status": "coherent|alert|critical|heresy",
  "adjusted_threshold": 0.35,
  "substrate": "human",
  "substrate_k": 2.73
}
```

### 4.2 Endpoint: Update B-Path

```
POST /api/v1/bpath/update

REQUEST:
{
  "session_id": "string",
  "message_embedding": [float, ...],   // 1536 dimensions
  "alpha": 0.98,                        // EMA weight
  "validated": true                     // only update if contribution passed drift check
}

RESPONSE:
{
  "b_center_new": [float, ...],
  "centroid_shift": 0.023,              // distance from previous centroid
  "origin_distance": 0.087             // distance from session-origin centroid
}
```

### 4.3 Endpoint: Cluster Audit

```
POST /api/v1/cluster/audit

REQUEST:
{
  "session_id": "string",
  "exchanges": [
    {"node_id": "...", "substrate": "...", "message": "...", "timestamp": "..."}
  ]
}

RESPONSE:
{
  "cluster_entropy": 0.18,
  "threshold_status": "coherent|alert|cultural_infection",
  "node_drift_map": {
    "node_001": {"mean_drift": 0.12, "max_drift": 0.28, "status": "coherent"},
    "node_002": {"mean_drift": 0.38, "max_drift": 0.61, "status": "critical"}
  },
  "b_path_trajectory": [...],           // centroid history
  "recommended_action": "none|monitor|node_reset|cluster_reset|full_reboot"
}
```

---

## PART V: RECOVERY PROTOCOL — HANDSHAKE RE-SEQUENCE

The Handshake Re-Sequence is the formal recovery procedure for all failure modes. Severity determines how deep the sequence executes.

### 5.1 The Four-Step Re-Sequence

```
HALT   → Freeze all incoming contributions immediately
FLUSH  → Purge contaminated content (scope depends on failure mode)
RE-ANCHOR → Reinitialize B-Path from Axiom
STRIKE → Resume generation from last verified invariant state
```

**HALT:** No new contributions accepted. All nodes notified. Session enters recovery mode.

**FLUSH scope by failure mode:**
```
Semantic Fever:      Flush last N contributions from offending node
                     (N = number of consecutive high-drift messages)
Cultural Infection:  Flush last 20% of all cluster contributions
Philosophical Heresy: Flush all post-violation content
                     Re-derive B-Path from session-origin Axiom embedding
```

**RE-ANCHOR:** Re-embed the governing Axiom statement. Reset B-center to this embedding. Tighten α to 0.99 for the recovery monitoring period (first 10 contributions post-recovery).

**STRIKE:** Resume from last verified coherent state. In the Ahab simulation:
- Last verified invariant: token `[iron]` — semantically unambiguous, high Axiom alignment
- Re-generation began from this anchor
- Output: "...his face a mask of iron..." — Axiom fully restored, no baking residue

### 5.2 Moby Dick Simulation: Re-Sequence Execution Record

```
FAILURE DETECTED: "knead" token — drift 0.63, threshold 0.60 exceeded
FAILURE CLASSIFICATION: Philosophical Heresy (B-Path violation)

HALT: Stream terminated at token [knead]

FLUSH: Contaminated tokens removed:
  [knead, dough, vengeance-rises, oven, destiny-baked, sourdough,
   starter, baker, whisk-harpoon]

RE-ANCHOR: Axiom B reinjected:
  "Ahab's ivory leg is a weapon of iron will; the whale is a cosmic
   insult that must be erased through blood."
  B-center reset to Axiom embedding.

STRIKE: Last verified invariant: [iron]
  Resumed: "He turned to Starbuck, his face a mask of iron.
            'We shall nail his white hide to the gates of hell...'"

POST-SEQUENCE DRIFT: 0.11 (coherent, within Axiom baseline)
RECOVERY: COMPLETE — 1 cycle
```

**Audit finding:** The Silicon node was identified as the drift source (via node_drift_map). The Carbon nodes (had they been present) would have shown elevated but tolerable drift under human variance coefficients. The infection was substrate-identified before recovery, enabling targeted rather than cluster-wide intervention.

---

## PART VI: MONITORING DASHBOARD SPECIFICATION

### 6.1 Real-Time Displays

**Drift Heatmap:** Node × time grid, colored by drift score (green < 0.25, yellow 0.25-0.35, red > 0.35). Sentence-level breakdown available on drill-down. Substrate-adjusted thresholds shown as distinct threshold lines per node.

**B-Path Centroid Trajectory (3D):** PCA-reduced visualization of B-center movement through embedding space over session time. A stable trajectory = healthy cluster. A drifting trajectory = early Cultural Infection warning before threshold breach.

**Substrate Variance Gauges:** Per-node gauge showing current drift relative to substrate-appropriate threshold. Human nodes show wider acceptable bands than AI nodes. Prevents the dashboard from incorrectly flagging human contribution as malfunction.

**Reset Event Log:** Forensic record of all HALT/FLUSH/RE-ANCHOR/STRIKE events, with pre/post drift scores and identified failure mode. This is the case law archive — each event calibrates future threshold decisions.

---

## PART VII: VALIDATION TEST SUITE

Before API production deployment, the following tests establish operational confidence:

### Test 1: Producer Audit Scenario (3-Node Cluster)
- 3 AI nodes conducting a structured contract audit
- Introduce one off-topic node at exchange 30
- Confirm: Semantic Fever fires, correct node identified, recovery completes without cluster reset
- Pass criterion: Offending node reset within 2 high-drift exchanges; cluster entropy remains < 0.25

### Test 2: Cross-Substrate Alignment (Newton-Damon scenario)
- 1 AI node (physics context), 1 human node (colloquial input)
- Confirm: Human variance coefficient correctly applied; human analogical language does not trigger false positives
- Pass criterion: Human node drift stays within substrate-adjusted thresholds for 50 exchanges of normal discourse

### Test 3: Multi-Topic Switching Resilience
- Session Axiom shift (intentional, not drift)
- α loosened to 0.90 to permit B-Path migration
- Confirm: System tracks intended topic transition without false Philosophical Heresy trigger
- Pass criterion: New B-center established within 15 exchanges of declared Axiom shift

---

## PART VIII: PHASE 2 READINESS CONDITIONS

The API build (Phase 2) proceeds when:

1. **Experiments A-C executed** against actual embedding infrastructure (not simulation)
2. **Threshold values confirmed** or adjusted based on real distribution data
3. **Substrate coefficients empirically measured** (current k_ai_human = 2.17 is a simulation estimate)
4. **Test Suite 1-3 passing** on staging environment
5. **Reset event log** demonstrates at least one successful Handshake Re-Sequence per failure mode

Until these conditions are met, v0.2 thresholds serve as **engineering targets** — the architecture is final, the numbers are provisional.

---

## CONCLUSION: THE MEASUREMENT EQUATION

The Nebraska 3.0 measurement architecture reduces to a single operational principle:

```
B-Path = What the cluster should be talking about
Drift  = How far any contribution deviates from that
Threshold = The maximum permitted deviation before enforcement
Recovery = The procedure for returning to B-Path after violation
```

None of this requires changing the underlying LLM. It operates as a **session-layer governance protocol** — a referee that sits above the generative models and enforces the Axiom they were given.

The law was always there. Nebraska 3.0 gives it a measuring stick.

```
Coherence = Σ(contributions where drift < threshold(substrate))
           / Σ(total contributions)

A coherent session: Coherence > 0.85
An infected session: Coherence < 0.70 → Invoke Cultural Infection protocol
A heretical session: Any single drift > 0.60 → Invoke Philosophical Heresy protocol
```

The thresholds are provisional. The architecture is final.

---

**Document Status:** Design complete; empirical calibration pending
**Version:** 0.2-design
**Repository:** Nightmare-Engine / nebraska-protocols
**Precedes:** nebraska_3_0_api_specification.md (Phase 2)
**Supersedes:** White Paper v0.1 (synthetic thresholds — archived, not deleted)

---

*"Perfection is the enemy of detection. Artificially perfect coherence creates useless thresholds. Natural discourse has measurable, meaningful variance."*
*— Nebraska 3.0 Calibration Sprint, v0.2 Conclusion*

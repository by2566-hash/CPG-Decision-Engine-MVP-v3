# ADR-0009: Introduce Evidence Graph Snapshot

## Status
Accepted
Date: 2026-04-10

## Context
V3's LLM Renderer (`layer2_decision/pillar3_llm/llm_renderer.py`) currently
receives scored candidates plus scattered fields (`verification_trace`,
`violations`, `evidence_refs`) from multiple objects. This creates two concrete
problems:

1. **LLM hallucination risk**: The model has access to outcome data but not the
   causal chain that produced it. Without a structured trace, the renderer must
   interpret disparate fields to construct a narrative — creating opportunities
   to add facts that were not in the decision logic.

2. **Complex prompt construction**: `_build_template_context()` manually assembles
   context from a dozen loosely-typed dict fields. The 5-Gate Bouncer's evidence
   grounding check (Gate 5) must reverse-engineer evidence claims from these same
   disparate fields.

Sunny (team member) proposed aggregating the full decision trace — from L1 state
through L3 verification — into a single typed object, so the LLM's role becomes
pure "logic-to-language translation" rather than "outcome interpretation."

## Decision
Introduce two new Pydantic models in `contracts.py`:

```python
EvidenceTraceEntry:
  step: Literal["L1_State", "L2_KG", "L3_Constraint", "L3_Scoring", "L3_Verification"]
  finding: str       # human-readable structured fact
  source_data: dict  # raw data backing the finding (for grounding checks)

EvidenceGraphSnapshot:
  candidate_id: str
  winner_action: str
  evidence_trace: list[EvidenceTraceEntry]
  computed_at: datetime
```

Both models are `frozen=True`.

The pipeline aggregates trace entries during:
- Step 2 (MSM state) → `L1_State` entry
- Step 5 (candidate generation + constraints) → `L3_Constraint` entry
- Step 6 (scoring) → `L3_Scoring` entry
- Step 6 (verification) → `L3_Verification` entry
- Step 5 (KG/playbook) → `L2_KG` entry

For top-K eligible candidates (K=3), the pipeline builds an
`EvidenceGraphSnapshot` and attaches it to the candidate dict under key
`"evidence_snapshot"`.

The `LLMRenderer` gains a new method `render_from_snapshot(snapshot)` that uses
the trace as its sole substantive input. The existing `render()` method is
unchanged. In Phase 1 deterministic mode, `render_from_snapshot()` formats the
trace into a readable paragraph without an LLM API call.

Snapshots are computed only for top-K candidates (not all candidates) to control
per-request overhead.

## Alternatives Considered

**Keep current scattered approach**: Rejected. LLM hallucination risk and complex
prompt construction are real problems at Phase 2+ when a real LLM call is made.
The current template-mode Phase 1 behavior masks the problem.

**Build a graph database for evidence**: Rejected as over-engineering. An ordered
list of trace entries is sufficient for Phase 1-2. If cross-references between
entries are needed (entity X supports entity Y), upgrade to a graph structure then
(update this ADR or write a new one).

**Compute trace only at LLM call time (lazy)**: Rejected. The trace must be
persisted to L5 WSM for offline analysis — "why did the bandit learn this policy?"
requires causal features, not just outcomes. Eager computation at decision time is
required.

## Consequences

### Positive
- LLM becomes pure translator: "Translate this logic chain. Do not add facts not
  present in the trace." Zero hallucination by design.
- 5-Gate Bouncer's evidence grounding check has structured, machine-readable input
- L5 Learning Fabric receives causal feature data with each decision record
- Aligns with "Explainability IS the product" core principle
- `render_from_snapshot()` is testable: output must reference only facts in
  `source_data` dicts — this is an automated invariant test

### Negative
- Pipeline must explicitly construct trace entries at each stage (small per-step
  overhead, O(K) not O(N) where K=3 top candidates)
- Adds two new contract types to maintain

### Neutral
- Snapshot is computed for top-K candidates, not all candidates (cost control)
- Phase 1 deterministic mode: `render_from_snapshot()` just formats the trace
  into readable text. Phase 2: LLM API call replaces the formatter.

## When to Revisit
If trace entries need cross-references (entity X supports entity Y — e.g., KG
fact A is the causal basis for scoring decision B), upgrade to an actual graph
structure. At that point, `evidence_trace: list[EvidenceTraceEntry]` becomes
`evidence_graph: Graph[EvidenceTraceEntry]` and this ADR is superseded.

## References
- `V3/CLAUDE.md` — L4 Experience & Delivery Plane section
- `V3/src/decision_engine/layer2_decision/pillar3_llm/llm_renderer.py`
- `V3/src/decision_engine/layer4_serving/pipeline.py` — Steps 2, 5, 6
- ADR-0001 (PolicyDecision provides constraint trace data as violations list)
- ADR-0005 (Feature Plane — DecisionFeatureVector is the numeric context; EvidenceGraphSnapshot is the causal trace)

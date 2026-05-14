# ADR-0013: MSM-State-Driven Playbook Routing Contract

## Status
Accepted
Date: 2026-04-14

## Context

Codex audit (2026-04-14) surfaced a potential ambiguity: meta-pattern YAMLs
contain `triggers.condition` expressions (e.g. `cvr_drop_vs_baseline >
${thresholds.cvr_collapse_threshold}`) and `${thresholds.*}` placeholders.
A reader could reasonably assume these conditions are evaluated at routing time
to select the matching playbook.

They are not. Current routing is **MSM-state-driven**.

Runtime evidence (read-only):

- `playbook_registry.match_playbook()` accepts `module` + `pattern["msm_state"]`
  + optional `merchant_id`. The trigger loop reads `trigger.get("msm_state", "")`
  and matches on that string alone. `trigger.condition` is not parsed or evaluated.
- `pipeline._generate_candidates()` calls `match_playbook(module,
  {"msm_state": state.value}, merchant_id=merchant_id)`. The `state.value` is
  an enum string (`HEALTHY` / `WATCH` / `DEGRADING` / `CRITICAL`) computed
  upstream by the L1 MSM layer.
- `${thresholds.*}` placeholders are rendered by
  `PlaybookRegistry._render_with_thresholds()` for display / explanation
  purposes, not evaluated as routing predicates.

The MSM layer (L1) is the upstream signal-conclusion layer. By the time routing
runs, MSM has already ingested raw metrics, applied threshold logic, and
produced a discrete state value. Routing consumes the *conclusion*, not the
raw metrics again.

## Decision

**Playbook routing is MSM-state-driven.** The canonical function signature
(ADR-0012) is:

```python
match_playbook(self, module: str, pattern: dict, merchant_id: str = "") -> dict | None
```

The `pattern` dict currently carries one field that drives routing:
`pattern["msm_state"]`. No other field in `pattern` is read by the routing
logic today. The dict wrapper exists for future extensibility (ADR-0012
is the canonical signature contract; do not flatten it).

`triggers.condition` expressions and `${thresholds.*}` values in meta-pattern
YAMLs serve three purposes:

1. **Authoring / human interpretation** — record the business logic that
   describes *when* this pattern is relevant, for domain expert review.
2. **Explanation / DecisionCard narrative** — rendered into evidence strings
   and LLM renderer context so the merchant can understand the diagnosis.
3. **Future Phase 3 signal** — condition strings are a structured record for
   a potential future condition-evaluation layer; they are not wasted authoring.

They are **not** routing-evaluation inputs in the current architecture.

This is intentional. MSM is already the upstream signal-conclusion layer; re-
evaluating raw conditions at routing time would duplicate L1 logic, introduce
a second threshold-evaluation path, and require the routing layer to have
access to live metric values it currently does not hold.

Selection priority within the MSM-state-driven router (ADR-0012):
1. Brand-bound meta-pattern matching `msm_state`, alphabetical by id
2. Any meta-pattern matching `msm_state` (load order)
3. Any flat playbook matching `msm_state`
4. Any meta-pattern (no state match — last resort)
5. First registered playbook for module

## Non-goals

- This ADR does **not** prohibit adding a condition-evaluation layer in the
  future. It records the current contract so future engineers know what they
  are changing.
- This ADR does **not** change the structure of `triggers.condition` fields
  in meta-pattern YAMLs. They remain authored and remain valuable as
  explanation artifacts.
- This ADR does **not** change threshold rendering behavior.
  `_render_with_thresholds()` is unaffected.

## Consequences

### Positive
- Routing logic remains simple, fast, and fully testable with discrete enum
  inputs. No live metric access required at routing time.
- `triggers.condition` strings remain useful for explanation without imposing
  a runtime evaluation dependency.
- Audit trail is unambiguous: routing decision is always traceable to a single
  `msm_state` value produced by L1.

### Negative
- A reader unfamiliar with this ADR may assume `triggers.condition` is
  evaluated. All meta-pattern authors and reviewers must be aware of this
  distinction (enforced by SOP authoring guidance).
- Two patterns that share the same `msm_state` for the same module cannot be
  differentiated by routing alone; they depend on brand-binding mutual
  exclusivity (ADR-0012 premise).

### Neutral
- `triggers.condition` authored fields are not dead code — they carry semantic
  meaning for explanation and for future Phase 3 condition evaluation.

## Escalation Conditions

This contract must be revisited in a new ADR under any of the following:

1. **A merchant requires two patterns active simultaneously within the same
   module + MSM state.** If mutual exclusivity (ADR-0012 premise) cannot be
   maintained across brand-bound patterns for the same module and state,
   condition-level routing becomes necessary to differentiate them.

2. **A use case requires a pattern to activate only when a specific metric
   threshold is crossed, and MSM state is insufficient to express that
   granularity.** For example: two patterns both fire at acquisition/DEGRADING,
   but one should activate only when CPM exceeds a brand-specific threshold
   while the other activates when CAC spikes without CPM movement. MSM state
   cannot encode this distinction today.

3. **The L1 MSM layer is extended to produce sub-states or confidence scores
   rather than discrete four-value enums.** If MSM output is no longer a
   discrete `{HEALTHY, WATCH, DEGRADING, CRITICAL}` value, the routing
   contract must be re-specified to consume the new output shape.

4. **A condition-evaluation layer is introduced for Phase 3 (or earlier) as a
   first-class architectural component.** At that point, `triggers.condition`
   strings become executable predicates and this ADR is superseded.

### Escalation Process

**Do not modify `match_playbook()` routing logic without a superseding ADR.
Any code change to routing behavior without a prior ADR is a violation of
this contract.**

When an escalation condition is met:

1. **Stop. Write the superseding ADR first.** Document what condition was
   triggered, what new routing input(s) are required, and how `pattern` dict
   will be extended. Reference this ADR and ADR-0012. The ADR must be merged
   before any code change is committed.

2. **Check ADR-0012 for interaction.** If the escalation also violates
   ADR-0012's mutual-exclusivity premise (e.g. Condition 1 above), follow
   ADR-0012's escalation checklist in parallel — the two escalations compose.

3. **Update routing code and call site together.** Changes required:
   - `src/decision_engine/layer2_decision/pillar1_kg/playbook_registry.py`
     — `match_playbook()` routing logic
   - `src/decision_engine/layer4_serving/pipeline.py`
     — `_generate_candidates()` call site (passes `{"msm_state": state.value}`)

4. **Update the architecture invariant test.** Test 10 in
   `tests/architecture/test_architecture_invariants.py`
   (`test_match_playbook_return_type_is_dict_or_none`) locks the current
   contract machine-checkably. Update or supersede it to reflect the new
   contract before the PR is merged.

## How To Verify This ADR Is Still Accurate

ADR-0013 makes specific claims about runtime behavior that can drift silently.
Run these commands to confirm the described contract still matches the code:

**1. Confirm `trigger.condition` is not read inside the routing loop.**
The routing loop in `match_playbook()` must only read `trigger.get("msm_state")`.
If this grep returns a hit inside the trigger loop, the contract has drifted:

```bash
grep -n "trigger.*condition\|condition.*trigger" \
  src/decision_engine/layer2_decision/pillar1_kg/playbook_registry.py
# Expected: no matches (or only comment/schema-doc lines, not routing logic)
```

**2. Confirm `_generate_candidates()` still passes only `msm_state` to the router.**
The call site must pass `{"msm_state": state.value}` — no additional fields:

```bash
grep -n 'match_playbook' src/decision_engine/layer4_serving/pipeline.py
# Expected: exactly one call, passing {"msm_state": state.value}
```

**3. Confirm threshold rendering is string substitution, not predicate evaluation.**
`_render_with_thresholds()` must use regex replacement, not `eval` or `compile`:

```bash
grep -n "eval\|compile" \
  src/decision_engine/layer2_decision/pillar1_kg/playbook_registry.py
# Expected: no matches (or only unrelated occurrences outside _render_with_thresholds)
```

**4. Confirm the `dict | None` return type invariant still passes.**
Test 10 in the architecture invariant suite machine-checks this contract:

```bash
python -m pytest tests/architecture/test_architecture_invariants.py \
  -k "test_match_playbook_return_type_is_dict_or_none" -v
# Expected: PASSED
```

If any of commands 1–3 return unexpected results, or command 4 fails,
this ADR has drifted from the code. Either update the ADR (if the change
was intentional and the new ADR was written) or revert the code change.

## References
- ADR-0011: Three-layer KG playbook structure (action authority, meta-pattern contract)
- ADR-0012: `match_playbook()` single-return contract and mutual-exclusivity premise
- `src/decision_engine/layer2_decision/pillar1_kg/playbook_registry.py` — `match_playbook()`
- `src/decision_engine/layer4_serving/pipeline.py` — `_generate_candidates()`

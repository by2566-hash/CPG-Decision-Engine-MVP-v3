# Legacy Use Cases — Wandering Bear

## What is in this directory

This directory contains Wandering Bear use cases that were translated **before
ADR-0011 (three-layer KG playbook structure) was formalized**. They are
preserved as evidence records but are **not part of the active three-layer KG
system**.

Current contents:

| File | Use Case | Phase 1 Stub Ref |
|------|----------|-----------------|
| `wb_003_evergreen_naming_test.yaml` | Evergreen flavor naming A/B test (CVR mix shift) | `conversion_merchandising_v1` |
| `wb_006_inventory_spend_pullback.yaml` | Inventory-driven spend pullback improved CAC | `acquisition_efficiency_v1` |

## Why these files are legacy

Both files reference `meta_pattern_ref` values that point to **Phase 1 flat
stub playbooks** (`conversion_merchandising_v1`, `acquisition_efficiency_v1`),
not real Layer-1 meta-patterns defined under the three-layer structure.

Under ADR-0011, a valid active use case must:
1. Reference a real meta-pattern in `playbooks/meta/` (Layer 1)
2. Have a corresponding brand binding in `playbooks/brands/wandering_bear/` (Layer 2)
3. Serve as the SSoT evidence record for that brand × pattern combination (Layer 3)

These use cases satisfy condition 3 (they contain good evidence data) but fail
conditions 1 and 2 — the meta-patterns they reference are flat stubs, not
three-layer meta-patterns.

## Promotion path

To promote a file from `_legacy/` back into active three-layer status:

1. **Create the meta-pattern** — write a real Layer-1 meta-pattern YAML in
   `playbooks/meta/<pattern_id>.yaml` following ADR-0011 structure (triggers,
   actions[], analysis_path, evidence_refs_template).
2. **Create the brand binding** — write a Layer-2 brand binding YAML in
   `playbooks/brands/wandering_bear/<pattern_id>.yaml` with thresholds and
   action_utility_priors.
3. **Update `meta_pattern_ref`** in this use case file to point to the new
   meta-pattern id (not the stub).
4. **Move the file** back to `use_cases/wandering_bear/`.
5. **Add a fixture test** in `tests/layer2/` verifying the pattern fires
   correctly for the Wandering Bear brand.
6. **Run** `python -m pytest -q` and `python scripts/kg_dryrun.py` to confirm
   no regressions.

See ADR-0011 for the full three-layer structure specification.

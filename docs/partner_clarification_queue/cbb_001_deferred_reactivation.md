# Partner Clarification: cbb_001 — LTV Quality Trap (P2 Deferred)

**Case**: Consumer Brand B — Offer-Heavy Creative / LTV Quality Trap
**Dormant YAML**: `playbooks/meta/_deferred/acquisition_ltv_quality_trap.yaml`
**Status**: Captured as dormant meta-pattern. Active translation blocked by
Phase 2 dependencies.

## Why Deferred

cbb_001's trigger condition requires `second_order_rate_delta` — a
creative-level cohort attribution metric measuring repeat purchase behavior
by creative type (offer-led vs value-led) within a retargeting audience.

This field does not exist in Phase 1 infrastructure:
- `DecisionFeatureVector` has `repeat_rate_7d` (population-level only)
- Population-level repeat rate CANNOT distinguish offer-led efficiency gains
  from genuine efficiency gains
- L0 Meta Ads connector does not capture creative-level attribution
- L5 Outcome Log does not accumulate 60-75 day cohort data in Phase 1

## Reactivation Requires (all three)

1. **creative_level_cohort_attribution** — Phase 2 Track A (Shopline API access).
   Meta Ads API must deliver creative-level attribution so second order rate can
   be segmented by creative type within a retargeting audience.

2. **post_purchase_cohort_tracking_60_75d** — Phase 2 Track A.
   L5 Outcome Log must accumulate 60-75 day post-purchase cohort data per
   creative type. Cannot be backfilled without creative-level tagging at
   acquisition time.

3. **second_order_rate_delta field in DecisionFeatureVector** — Phase 2 Track B.
   Add `second_order_rate_delta: Optional[float]` to `contracts.py`.
   Requires all three above before it can be populated.

## Open Questions for Partner (collect at Phase 2 entry)

1. At what offer-creative share of retargeting spend does LTV risk become material?
   *(Calibrates `thresholds.offer_creative_share_threshold` in brand binding)*

2. What is the minimum acceptable second order rate for a healthy retargeting cohort?
   *(Calibrates the trigger gate for `PAUSE_OFFER_CREATIVE` action)*

3. Does the 60-75d validation window change for different product replenishment
   cycles? *(Some CPG categories replenish at 30d, others at 90d)*

4. Was the value-led creative that replaced the offer creative a specific format
   (video, static, UGC)? *(Affects cross-pattern relationship with cba_001)*

## What Is Preserved

- Full trigger schema and analysis_path (schema design frozen for Phase 2)
- `cross_module: true` and `requires_retention_validation: true` fields
- Soft-guard configuration for LLM renderer (Option B injection text)
- All partner-observed data points in the case narrative
- `blocked_by` dependency registry with owner and ADR references

## ADR References

- ADR-0006 (Phase 2 dual-track): Track A entry conditions (Shopline API access)
- ADR-0012 (match_playbook contract): _deferred/ loader exclusion documented

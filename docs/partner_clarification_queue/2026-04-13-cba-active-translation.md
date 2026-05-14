# Partner Clarification Queue — CBA Active Translation (2026-04-13)

**Scope**: cba_001 (acquisition_ugc_creative) and cba_002 (conversion_compliance_friction)
**Status**: Both patterns active, fixture tests green, dryrun exit 0.
**Purpose**: Resolve estimated values and confirm calibration data before confidence upgrades.

---

## Priority: High — Blocks Calibration Confidence

These items affect `gmv_lift_prior` accuracy and currently block confidence from being raised
above the partner_prior calibration status.

### H1 — cba_001: Monthly GMV during observation period
- **Source**: `use_cases/consumer_brand_a/cba_001_ugc_creative.yaml`
- **Current value**: $1M estimated (from $320K monthly ad spend × ~3× ROAS)
- **Why it matters**: `gmv_lift_prior` for SCALE_TOP_CREATIVE (0.08) is derived using this estimate.
  If actual GMV differs materially, the prior must be recalculated.
- **Ask**: "What was monthly GMV during the observation period when the UGC program launched?"

### H2 — cba_001: Average order value (AOV) during observation period
- **Source**: `use_cases/consumer_brand_a/cba_001_ugc_creative.yaml`
- **Current value**: $50 estimated — not provided by partner
- **Why it matters**: Used directly in `monthly_new_customers_est × aov_est` in the derivation.
- **Ask**: "What was the average order value during the UGC program observation period?"

### H3 — cba_002: Monthly sessions to the quiz flow
- **Source**: `use_cases/consumer_brand_a/cba_002_compliance_ux.yaml`
- **Current value**: Not provided — affects the absolute GMV impact calculation
- **Why it matters**: Without session volume, we can't convert the CVR delta (1.8pp) to absolute
  revenue impact. The `gmv_lift_prior` of 0.12 is upward-adjusted from the 0.029 CVR-basis
  estimate; partner session data would allow a direct calculation.
- **Ask**: "How many monthly sessions reached the quiz entry step during the observation period?"

### H4 — cba_002: Paid vs organic traffic split to the quiz flow
- **Source**: `use_cases/consumer_brand_a/cba_002_compliance_ux.yaml`
- **Current value**: Cross-source multiplier of 2.0 (paid + organic both affected) — assumed equal weight
- **Why it matters**: If paid traffic dominated the quiz flow, the cross-source multiplier is correct.
  If organic dominated, the multiplier should be reweighted.
- **Ask**: "What was the paid vs organic traffic split to the quiz/health data flow during the observation period?"

---

## Priority: Medium — Affects Prior Accuracy

These items do not block current calibration but would improve the quality of `gmv_lift_prior` values.

### M1 — cba_001: Exact timeframe of the UGC program launch and baseline period
- **Source**: `use_cases/consumer_brand_a/cba_001_ugc_creative.yaml`
- **Current value**: "Phase 1 intake — timeframe to be confirmed by partner"
- **Why it matters**: Allows seasonality-adjustment of the baseline and confirmation of the
  observation window for the CAC and CPM data.
- **Ask**: "When did the UGC creator program launch? What was the baseline measurement period?"

### M2 — cba_001: Total monthly ad spend across all channels
- **Source**: `use_cases/consumer_brand_a/cba_001_ugc_creative.yaml`
- **Current value**: Not provided — $320K/month Meta assumed from $58K/week UGC spend × 4 + overhead
- **Ask**: "What was total monthly ad spend across all channels during the observation period?"

### M3 — cba_002: Exact date of the compliance popup deploy
- **Source**: `use_cases/consumer_brand_a/cba_002_compliance_ux.yaml`
- **Current value**: "Phase 1 intake — timeframe to be confirmed by partner"
- **Why it matters**: Timeline correlation is the mandatory first analysis step (SOP Section 10).
  The exact deploy date confirms that the CVR collapse onset coincided with the popup deploy.
- **Ask**: "On what date was the health data consent popup deployed? On what date did CVR drop?"

### M4 — cba_002: Was the 3× CVR recovery measured against the collapsed CVR or original baseline?
- **Source**: `use_cases/consumer_brand_a/cba_002_compliance_ux.yaml`
- **Current value**: Interpreted as 3× the collapsed CVR (0.9% → 2.7%)
- **Why it matters**: If 3× was measured against the original baseline (2.5%), the recovered CVR
  would be 7.5% — a very different calibration input.
- **Ask**: "The '3× recovery' — was that 3× the <1% collapsed CVR, or 3× the original 2.5% baseline CVR?"

### M5 — cba_002: Monthly GMV during the observation period
- **Source**: `use_cases/consumer_brand_a/cba_002_compliance_ux.yaml`
- **Current value**: Not provided — affects absolute impact calculation
- **Ask**: "What was monthly GMV during the compliance popup observation period?"

---

## Priority: Low — Future Improvement

These items refine threshold calibration and pattern disambiguation but do not block current use.

### L1 — cba_001: At what CPM-vs-baseline ratio does creative composition become the primary suspect?
- **Source**: `playbooks/meta/acquisition_ugc_creative.yaml` `partner_clarifications_needed`
- **Current value**: `cpm_spike_ratio: 1.20` (20% above 30d baseline) — calibrated from WB baseline
- **Ask**: "Is a 20% CPM spike the right trigger threshold for this brand, or should it be higher/lower?"

### L2 — cba_001: Is the UGC share floor category-specific or brand-specific?
- **Source**: `playbooks/meta/acquisition_ugc_creative.yaml` `partner_clarifications_needed`
- **Current value**: `creative_ugc_share_floor: 0.20` (below 20% → WATCH)
- **Ask**: "Is a 20% UGC floor right for this brand, or does it differ by product category?"

### L3 — cba_001: Minimum test period for UGC creative before drawing performance conclusions
- **Source**: `playbooks/meta/acquisition_ugc_creative.yaml` `partner_clarifications_needed`
- **Ask**: "How many days of data do you need before UGC creative performance is considered reliable?"

### L4 — cba_001: Does this pattern apply equally to TikTok Spark Ads, or is it Meta-specific?
- **Source**: `playbooks/meta/acquisition_ugc_creative.yaml` `partner_clarifications_needed`
- **Ask**: "Did you observe similar UGC vs brand-produced CAC/CPM dynamics on TikTok?"

### L5 — cba_002: Minimum CVR drop threshold that confirms compliance friction vs normal variation
- **Source**: `playbooks/meta/conversion_compliance_friction.yaml` `partner_clarifications_needed`
- **Current value**: `cvr_collapse_threshold: 0.50` (>50% drop) — set conservatively (actual was >60%)
- **Ask**: "At what % CVR drop do you consider it a compliance friction event vs normal variation?"

### L6 — cba_002: Legal constraints on redesigning the compliance flow without re-approval
- **Source**: `playbooks/meta/conversion_compliance_friction.yaml` `partner_clarifications_needed`
- **Ask**: "Which parts of the health data consent flow can be redesigned (copy/placement/UX) without
  requiring legal re-review vs. which require legal sign-off before any change?"

---

## Summary Table

| ID | Pattern | Priority | Blocks | Status |
|----|---------|----------|--------|--------|
| H1 | cba_001 | High | SCALE_TOP_CREATIVE gmv_lift accuracy | Open |
| H2 | cba_001 | High | SCALE_TOP_CREATIVE gmv_lift accuracy | Open |
| H3 | cba_002 | High | REMOVE_COMPLIANCE_FRICTION gmv_lift accuracy | Open |
| H4 | cba_002 | High | Cross-source multiplier calibration | Open |
| M1 | cba_001 | Medium | Seasonality-adjusted baseline | Open |
| M2 | cba_001 | Medium | GMV estimate accuracy | Open |
| M3 | cba_002 | Medium | Timeline correlation confirmation | Open |
| M4 | cba_002 | Medium | CVR recovery magnitude | Open |
| M5 | cba_002 | Medium | GMV impact calculation | Open |
| L1–L6 | both | Low | Threshold refinement | Open |

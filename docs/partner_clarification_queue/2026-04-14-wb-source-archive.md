# Partner Clarification: Wandering Bear Source Archive Retrieval

**Date:** 2026-04-14
**Brand:** Wandering Bear
**Type:** Source archive retrieval (traceability)
**Priority:** Medium — needed before outcome calibration (not blocking demo)

## Background

Wandering Bear use cases (wb_001–wb_005) were translated during Phase 1 intake
from partner conversations and data exports. The original source materials were
not formally archived at translation time. ADR-0011 requires a `_source/`
archive per brand. This request formally tracks retrieval of those materials.

## Items requested from partner

### 1. wb_001 — Subscription mix / SKU dilution
- Recharge subscription rate export showing sub rates by SKU
- Order data showing PM SKU share of total orders (~52.6%)
- Period: Q1 2023 or the equivalent observation window

### 2. wb_002 — ShopCash denominator fix
- Channel order export confirming ShopCash order volume as share of total orders
- The corrected sub rate calculation after ShopCash exclusion

### 3. wb_004 — Brand vs DR CPA split
- Meta Ads Manager export: brand campaign CPA and DR campaign CPA split
- Period covering the DR CPA improvement ($43.09 → $38.00)
- Budget share confirmation: DR ~59% of total ad spend

### 4. wb_005 — Meta destination routing fix
- Meta Ads Manager destination-level report: IG Shop / FB Shop vs Shopify PDP
- March 2023 (before): sitewide CAC $54.79
- April 2023 (after): sitewide CAC $45.25

## Archive location

Received files should be placed in:
`use_cases/wandering_bear/_source/`

See `use_cases/wandering_bear/_source/_RETRIEVAL_NEEDED.md` for retrieval
checklist. Mark items retrieved as they are received.

## Resolution

This item can be closed when all four source files are archived and
`_RETRIEVAL_NEEDED.md` shows all items checked.

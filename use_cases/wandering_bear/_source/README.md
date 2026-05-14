# Source Archive — Wandering Bear

## Why this directory exists

ADR-0011 requires each brand's use case directory to contain a `_source/`
archive holding the **original partner-provided source materials** that the
use case translations were derived from (Slack exports, spreadsheets, partner
briefs, data pulls, etc.).

For Wandering Bear, this archive is being added **retroactively**. The use
cases (wb_001–wb_005) were translated during Phase 1 intake from partner
conversations and data exports, but the original source materials were not
formally archived at translation time.

## Status

Source materials for all active Wandering Bear use cases are **pending
retrieval**. See `_RETRIEVAL_NEEDED.md` for the retrieval checklist and
`docs/partner_clarification_queue/2026-04-14-wb-source-archive.md` for the
formal partner clarification request.

## Active use cases requiring source retrieval

| Use Case | Pattern | Source Type Needed |
|----------|---------|--------------------|
| `wb_001_subscription_mix_dilution.yaml` | conversion_subscription_mix | Recharge sub-rate export, SKU-level order data |
| `wb_002_shopcash_denominator.yaml` | conversion_subscription_mix | ShopCash order channel export, denominator calculation |
| `wb_004_brand_vs_dr_cpa.yaml` | acquisition_cac_channel_mix | Meta Ads Manager CPA export (brand vs DR split) |
| `wb_005_meta_destination_mix.yaml` | acquisition_cac_channel_mix | Meta Ads Manager destination-level CAC export |

## Excluded from retrieval

`wb_003` and `wb_006` are in `_legacy/` — they are pre-three-layer artifacts
and are not part of the active KG system. Source retrieval for those cases
will be handled if/when they are promoted to three-layer status.

## Promotion path for source materials

When source files are retrieved from the partner:
1. Place the original file(s) in this directory with a descriptive name
   (e.g. `wb_001_recharge_sub_rate_export_2023q1.csv`).
2. Add a pointer in the relevant use case YAML under `data_observed.source_file`.
3. Update `_RETRIEVAL_NEEDED.md` to mark the item as retrieved.
4. Remove the corresponding entry from `docs/partner_clarification_queue/`.

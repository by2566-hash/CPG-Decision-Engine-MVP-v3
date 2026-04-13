"""BrightSkin demo script for funding presentation.

Run from V3/:
    python scripts/demo_brightskin.py

Prints readable summary of top candidates for BrightSkin scenario.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.decision_engine.layer4_serving import pipeline
from src.decision_engine.layer2_decision.scoring import ScoringEngine
from fixtures.brightskin.scenario import (
    build_brightskin_state,
    build_brightskin_signals,
    build_brightskin_policy,
)

_STEP_LABELS = {
    "L1_State":        "L1 Merchant State",
    "L2_KG":           "L2 KG / Playbook",
    "L3_Constraint":   "L3 Constraints",
    "L3_Scoring":      "L3 Scoring",
    "L3_Verification": "L3 Verification",
}


def main():
    print("=" * 70)
    print("CPG Decision Engine V3 — BrightSkin Demo")
    print("=" * 70)

    msm = build_brightskin_state()
    signals = build_brightskin_signals()
    policy = build_brightskin_policy()

    print(f"\nMerchant:    {msm.merchant_id}")
    print(f"Retention:   {msm.retention_state}  (urgency: {msm.retention_urgency:.2f})")
    print(f"Acquisition: {msm.acquisition_state}  (urgency: {msm.acquisition_urgency:.2f})")
    print(f"Conversion:  {msm.conversion_state}")
    print(f"Promotion:   {msm.promotion_state}")

    candidates = pipeline._generate_candidates(msm, signals, policy)
    print(f"\n{len(candidates)} candidates generated.\n")


    # Show Feature Plane snapshot (same for all candidates — built once per run)
    if candidates:
        fv = candidates[0].get("feature_vector")
        if fv:
            print("Feature Plane snapshot:")
            print(f"  inventory_days:      {fv.inventory_days:.1f}")
            print(f"  margin_pct:          {fv.margin_pct:.1%}")
            print(f"  repeat_rate_7d:      {fv.repeat_rate_7d:.1%}")
            print(f"  churn_score:         {fv.churn_score:.2f}")
            print(f"  stock_pressure_score:{fv.stock_pressure_score:.2f}")

    scoring = ScoringEngine()
    ranked = scoring.rank_actions(msm_state=msm, candidates=candidates, policy=policy)

    eligible = [c for c in ranked if c.get("eligible", True) and c.get("final_score", float("-inf")) > float("-inf")]
    blocked  = [c for c in ranked if not c.get("eligible", True)]

    print(f"\nTop recommendations ({len(eligible)} eligible, {len(blocked)} blocked by constraints):")
    print("-" * 70)
    for i, c in enumerate(eligible[:3], 1):
        print(f"\n#{i}. {c.get('action_id')}  [module: {c.get('module')}]")
        print(f"    Final score: {c.get('final_score', 0):.4f}")
        print(f"    U_base: {c.get('u_base', 0):.4f}  |  "
              f"U_ucb: {c.get('u_ucb', 0):.4f}  |  "
              f"Risk penalty: {c.get('risk_penalty', 0):.4f}")
        # constraints_result is not in ranked output; use direct fields
        violations = c.get("violations", [])
        if violations:
            print(f"    Violations: {', '.join(violations)}")

    if blocked:
        print(f"\nBlocked candidates ({len(blocked)}):")
        for c in blocked[:3]:
            violations = c.get("violations", [])
            print(f"  - {c.get('action_id')} — {', '.join(violations) or 'verification failed'}")

    # ── Evidence Graph Snapshot for top recommendation ────────────────
    top_eligible = [c for c in ranked if c.get("eligible", True)]
    if top_eligible:
        top = top_eligible[0]
        snapshot = pipeline._build_evidence_snapshot(top, msm)

        print(f"\n{'=' * 70}")
        print(f"Evidence Chain — #{1} Recommendation: {snapshot.winner_action}")
        print(f"{'=' * 70}")
        for entry in snapshot.evidence_trace:
            label = _STEP_LABELS.get(entry.step, entry.step)
            print(f"\n  [{label}]")
            print(f"  {entry.finding}")
        print()

    print("=" * 70)
    print("Demo complete.")


if __name__ == "__main__":
    main()

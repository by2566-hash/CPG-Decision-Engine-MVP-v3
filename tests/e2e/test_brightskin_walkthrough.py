"""BrightSkin end-to-end walkthrough test.

This test is the Phase 1 contract: the full pipeline must produce
sensible results for BrightSkin's scenario. If this fails, something
in the decision path is broken.

BrightSkin state: retention DEGRADING, acquisition WATCH,
conversion HEALTHY, promotion HEALTHY.

Enforces: V3/docs/PHASE_ROADMAP.md Phase 1 / BrightSkin end-to-end fixture
"""

import pytest

from src.decision_engine.layer4_serving import pipeline
from src.decision_engine.layer2_decision.scoring import ScoringEngine
from src.decision_engine.contracts import (
    DecisionFeatureVector, PolicyDecision, EvidenceGraphSnapshot,
)
from fixtures.brightskin.scenario import (
    build_brightskin_state,
    build_brightskin_signals,
    build_brightskin_policy,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def brightskin_candidates():
    """Generate candidates once for all tests in this module."""
    return pipeline._generate_candidates(
        build_brightskin_state(),
        build_brightskin_signals(),
        build_brightskin_policy(),
    )


@pytest.fixture(scope="module")
def brightskin_ranked():
    """Generate and rank candidates, emit evidence snapshots for top-K."""
    msm = build_brightskin_state()
    signals = build_brightskin_signals()
    policy = build_brightskin_policy()
    candidates = pipeline._generate_candidates(msm, signals, policy)
    scoring = ScoringEngine()
    ranked = scoring.rank_actions(msm_state=msm, candidates=candidates, policy=policy)
    # Emit evidence snapshots for top-3 eligible (mirrors run_once Step 8b)
    eligible = [a for a in ranked if a.get("eligible", True)]
    for action in eligible[:3]:
        action["evidence_snapshot"] = pipeline._build_evidence_snapshot(action, msm)
    return ranked


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_brightskin_pipeline_produces_retention_focused_candidates(brightskin_candidates):
    """DEGRADING retention state must surface retention candidates.

    BrightSkin has retention DEGRADING — the pipeline must propose at least
    one retention module action. If retention candidates are absent, either
    the MSM state is wrong or the candidate generation skips DEGRADING.
    """
    assert len(brightskin_candidates) > 0, "No candidates generated at all."
    retention_candidates = [
        c for c in brightskin_candidates if c.get("module") == "retention"
    ]
    assert len(retention_candidates) > 0, (
        "No retention candidates for DEGRADING retention state. "
        "Check _generate_candidates() DEGRADING threshold logic."
    )


def test_brightskin_acquisition_watch_also_generates_candidates(brightskin_candidates):
    """WATCH acquisition state must also surface acquisition candidates.

    BrightSkin has acquisition WATCH (severity >= 1). The pipeline should
    generate acquisition module candidates alongside retention ones.
    """
    acquisition_candidates = [
        c for c in brightskin_candidates if c.get("module") == "acquisition"
    ]
    assert len(acquisition_candidates) > 0, (
        "No acquisition candidates for WATCH acquisition state."
    )


def test_brightskin_candidates_have_policy_decisions(brightskin_candidates):
    """Every candidate must have a PolicyDecision attached (ADR-0001).

    ConstraintEngine.check_all() runs for every candidate in
    _generate_candidates(). A missing PolicyDecision means the constraint
    engine was not called for that candidate.
    """
    for c in brightskin_candidates:
        pd = c.get("constraints_result")
        assert pd is not None, (
            f"Candidate {c.get('action_id')!r} missing 'constraints_result'."
        )
        assert isinstance(pd, PolicyDecision), (
            f"Candidate {c.get('action_id')!r}: expected PolicyDecision, "
            f"got {type(pd).__name__!r}."
        )


def test_brightskin_candidates_have_feature_vectors(brightskin_candidates):
    """Every candidate must have a DecisionFeatureVector (ADR-0005, Stage 5).

    FeatureBuilder.build() is called once per _generate_candidates() run
    and attached to every candidate under 'feature_vector'.
    """
    for c in brightskin_candidates:
        fv = c.get("feature_vector")
        assert fv is not None, (
            f"Candidate {c.get('action_id')!r} missing 'feature_vector'."
        )
        assert isinstance(fv, DecisionFeatureVector), (
            f"Candidate {c.get('action_id')!r}: expected DecisionFeatureVector, "
            f"got {type(fv).__name__!r}."
        )
        # Margin must be reflected from BrightSkin signals
        assert fv.margin_pct == pytest.approx(0.33), (
            f"feature_vector.margin_pct should be 0.33 (BrightSkin margin), "
            f"got {fv.margin_pct}."
        )


def test_brightskin_returning_customer_allows_discounts(brightskin_candidates):
    """customer_orders_count=5 must not trigger cold_prospect_gate.

    BrightSkin's customers have placed 5+ orders — they are returning
    customers. The cold_prospect_gate should not fire.
    """
    discount_candidates = [
        c for c in brightskin_candidates
        if "DISCOUNT" in c.get("action_id", "").upper()
    ]
    if discount_candidates:
        for c in discount_candidates:
            pd = c["constraints_result"]
            violations_str = " ".join(pd.violations)
            assert "cold_prospect_gate" not in violations_str, (
                f"cold_prospect_gate fired for {c['action_id']!r} "
                "despite customer_orders_count=5. "
                "Check cold_prospect_gate threshold in constraints.py."
            )


def test_brightskin_margin_floor_respected(brightskin_candidates):
    """margin_pct=0.33 must allow a 10% discount (post-margin 0.23 >= 0.15 floor).

    BrightSkin's 33% margin can absorb a 10% discount and still clear the
    15% margin floor. margin_floor constraint must not fire for DISCOUNT_10PCT.
    """
    for c in brightskin_candidates:
        if "DISCOUNT_10PCT" in c.get("action_id", ""):
            pd = c["constraints_result"]
            violations_str = " ".join(pd.violations)
            assert "margin_floor" not in violations_str, (
                f"margin_floor fired for DISCOUNT_10PCT despite margin_pct=0.33. "
                f"Post-discount margin: 0.33 × 0.90 = 0.297 >= 0.15 floor. "
                f"Violations: {pd.violations}"
            )


def test_brightskin_feature_vector_stock_pressure_is_zero(brightskin_candidates):
    """inventory_days=38 must produce stock_pressure_score=0.0 (healthy stock).

    BrightSkin has 38 days of inventory — well above the 7-day pressure
    threshold. stock_pressure_score should be 0.0.
    """
    assert brightskin_candidates
    fv = brightskin_candidates[0]["feature_vector"]
    assert fv.stock_pressure_score == pytest.approx(0.0), (
        f"Expected stock_pressure_score=0.0 for inventory_days=38, "
        f"got {fv.stock_pressure_score}."
    )


def test_brightskin_churn_score_reflects_signals(brightskin_candidates):
    """churn_score must reflect the elevated overdue_ratio=0.61 from signals."""
    assert brightskin_candidates
    fv = brightskin_candidates[0]["feature_vector"]
    assert fv.churn_score == pytest.approx(0.61), (
        f"Expected churn_score=0.61 (from overdue_ratio), got {fv.churn_score}."
    )


# ── Evidence Graph Snapshot tests (ADR-0009) ──────────────────────────────────

def test_brightskin_winner_has_evidence_snapshot(brightskin_ranked):
    """Top eligible candidate must have an evidence_snapshot key.

    Enforces: ADR-0009 — pipeline emits EvidenceGraphSnapshot for top-K
    eligible candidates after scoring.
    """
    eligible = [c for c in brightskin_ranked if c.get("eligible", True)]
    assert eligible, "No eligible candidates for BrightSkin."
    top = eligible[0]
    assert "evidence_snapshot" in top, (
        f"Top candidate {top.get('action_id')!r} missing 'evidence_snapshot'. "
        "Check pipeline Step 8b in run_once()."
    )
    assert isinstance(top["evidence_snapshot"], EvidenceGraphSnapshot), (
        f"evidence_snapshot must be EvidenceGraphSnapshot, "
        f"got {type(top['evidence_snapshot']).__name__!r}."
    )


def test_brightskin_evidence_snapshot_winner_action_matches_candidate(brightskin_ranked):
    """evidence_snapshot.winner_action must equal the candidate's action_id."""
    eligible = [c for c in brightskin_ranked if c.get("eligible", True)]
    for c in eligible[:3]:
        snap = c.get("evidence_snapshot")
        if snap is None:
            continue
        assert snap.winner_action == c.get("action_id"), (
            f"Snapshot winner_action {snap.winner_action!r} does not match "
            f"candidate action_id {c.get('action_id')!r}."
        )


def test_brightskin_evidence_trace_contains_l1_and_l3_steps(brightskin_ranked):
    """Evidence trace for top candidate must contain at least L1_State and L3_Scoring.

    Enforces: ADR-0009 — the causal chain starts at L1 and passes through L3.
    An empty or L3-only trace means the pipeline helper is not aggregating all
    required steps.
    """
    eligible = [c for c in brightskin_ranked if c.get("eligible", True)]
    assert eligible
    snap = eligible[0].get("evidence_snapshot")
    assert snap is not None
    steps = {entry.step for entry in snap.evidence_trace}
    assert "L1_State" in steps, (
        f"L1_State entry missing from evidence trace. Got steps: {steps}. "
        "Check _build_evidence_snapshot() L1 section."
    )
    assert "L3_Scoring" in steps, (
        f"L3_Scoring entry missing from evidence trace. Got steps: {steps}. "
        "Check _build_evidence_snapshot() scoring section."
    )


def test_brightskin_renderer_consumes_snapshot(brightskin_ranked):
    """render_from_snapshot must produce output referencing snapshot facts.

    Enforces: ADR-0009 — renderer translates facts from the trace, it does not
    fabricate new ones.
    """
    from src.decision_engine.layer2_decision.pillar3_llm.llm_renderer import LLMRenderer
    eligible = [c for c in brightskin_ranked if c.get("eligible", True)]
    assert eligible
    snap = eligible[0].get("evidence_snapshot")
    assert snap is not None

    renderer = LLMRenderer()
    result = renderer.render_from_snapshot(snap)

    assert isinstance(result, dict)
    # Winner action must appear somewhere in the output
    result_str = str(result)
    assert snap.winner_action in result_str, (
        f"renderer output does not mention winner_action {snap.winner_action!r}. "
        "The renderer may not be using the snapshot as input. "
        "See ADR-0009."
    )

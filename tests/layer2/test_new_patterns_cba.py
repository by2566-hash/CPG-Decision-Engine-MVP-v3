# ── Fixture Tests: Consumer Brand A — cba_001 and cba_002 ─────────────────────
# TDD: tests were written BEFORE the YAML translations (Step 3.B red phase).
# Target green state: all 9 tests pass after Step 3.C translation.
#
# cba_001: acquisition_ugc_creative (acquisition / DEGRADING / NOVEL)
# cba_002: conversion_compliance_friction (conversion / CRITICAL / NOVEL)
#
# Reference: Step 3 Execution Prompt 2026-04-13
# ──────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import PlaybookRegistry

# ── Path helpers ──────────────────────────────────────────────────────────────

_V3_ROOT = Path(__file__).resolve().parents[2]
_META_DIR = _V3_ROOT / "playbooks" / "meta"
_BRANDS_DIR = _V3_ROOT / "playbooks" / "brands"
_CBA_BRAND = "consumer_brand_a"

_CBA_001_META = _META_DIR / "acquisition_ugc_creative.yaml"
_CBA_002_META = _META_DIR / "conversion_compliance_friction.yaml"
_CBA_001_BINDING = _BRANDS_DIR / _CBA_BRAND / "acquisition_ugc_creative.yaml"
_CBA_002_BINDING = _BRANDS_DIR / _CBA_BRAND / "conversion_compliance_friction.yaml"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def registry():
    """Default PlaybookRegistry with all active playbooks loaded."""
    reg = PlaybookRegistry()
    reg._ensure_loaded()
    return reg


@pytest.fixture(scope="module")
def cba_001_meta() -> dict:
    """Load cba_001 meta-pattern YAML directly (structural tests)."""
    if not _CBA_001_META.exists():
        pytest.skip(f"cba_001 meta-pattern not yet written: {_CBA_001_META}")
    with open(_CBA_001_META) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def cba_002_meta() -> dict:
    """Load cba_002 meta-pattern YAML directly (structural tests)."""
    if not _CBA_002_META.exists():
        pytest.skip(f"cba_002 meta-pattern not yet written: {_CBA_002_META}")
    with open(_CBA_002_META) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def cba_001_binding() -> dict:
    """Load consumer_brand_a brand binding for cba_001."""
    if not _CBA_001_BINDING.exists():
        pytest.skip(f"cba_001 brand binding not yet written: {_CBA_001_BINDING}")
    with open(_CBA_001_BINDING) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def cba_002_binding() -> dict:
    """Load consumer_brand_a brand binding for cba_002."""
    if not _CBA_002_BINDING.exists():
        pytest.skip(f"cba_002 brand binding not yet written: {_CBA_002_BINDING}")
    with open(_CBA_002_BINDING) as f:
        return yaml.safe_load(f)


# ─────────────────────────────────────────────────────────────────────────────
# cba_001: acquisition_ugc_creative
# ─────────────────────────────────────────────────────────────────────────────

class TestCba001UgcCreative:

    def test_cba_001_fires_on_cpm_rise_with_stable_spend_and_audience(self, registry):
        """cba_001 must match acquisition / DEGRADING for consumer_brand_a.

        Positive fire: CAC and CPM rising with no change in spend / audience /
        campaign structure — creative composition is the primary suspect.
        The pattern must be returned by match_playbook() for the brand.

        Fails red phase because acquisition_ugc_creative.yaml does not exist yet.
        """
        playbook = registry.match_playbook(
            "acquisition",
            {"msm_state": "DEGRADING"},
            merchant_id=_CBA_BRAND,
        )
        assert playbook is not None, (
            "No playbook returned for acquisition/DEGRADING with merchant_id=consumer_brand_a. "
            "Expected acquisition_ugc_creative to be loaded and bound."
        )
        assert playbook.get("id") == "acquisition_ugc_creative", (
            f"Expected 'acquisition_ugc_creative', got '{playbook.get('id')}'. "
            "Brand binding for consumer_brand_a must reference acquisition_ugc_creative."
        )

    def test_cba_001_does_not_fire_on_cac_rise_without_cpm_rise(self, registry, cba_001_meta):
        """cba_001 trigger requires BOTH CAC rise AND CPM rise (no structure change).

        This disambiguates from acquisition_cac_channel_mix (destination routing).
        cac_channel_mix fires when CAC rises but on-platform content views spike.
        ugc_creative fires when CAC AND CPM rise with stable campaign structure,
        making creative composition the isolated variable.

        Test: the meta-pattern must declare a trigger condition that references
        cpm_spike_ratio (or equivalent CPM metric), not just CAC.
        """
        triggers = cba_001_meta.get("triggers", [])
        assert triggers, "cba_001 meta-pattern has no triggers"

        # At least one trigger condition must reference CPM (to disambiguate from
        # acquisition_cac_channel_mix which only checks CAC/ROAS)
        trigger_conditions = " ".join(
            str(t.get("condition", "")) for t in triggers
        )
        has_cpm_signal = (
            "cpm" in trigger_conditions.lower()
            or "creative" in trigger_conditions.lower()
        )
        assert has_cpm_signal, (
            "cba_001 trigger condition must reference CPM or creative signal to "
            "disambiguate from acquisition_cac_channel_mix (which fires on CAC/ROAS alone). "
            f"Current trigger conditions: {trigger_conditions}"
        )

    def test_cba_001_does_not_fire_for_merchant_without_brand_binding(self, registry):
        """A merchant without a brand binding for acquisition_ugc_creative must
        not have that pattern selected as their brand-bound match.

        Post ADR-0012: match_playbook() with merchant_id uses Priority 1
        (brand-bound meta). A merchant with no binding gets Priority 2 (first
        meta by load order). If acquisition_cac_channel_mix loads before
        acquisition_ugc_creative alphabetically, a no-binding merchant will
        get acquisition_cac_channel_mix, NOT acquisition_ugc_creative.

        This test confirms the pattern does not misfire on a non-CBA merchant.
        """
        # Use a merchant that has no brand binding for acquisition module
        playbook = registry.match_playbook(
            "acquisition",
            {"msm_state": "DEGRADING"},
            merchant_id="unknown_merchant_xyz",
        )
        # The result must NOT be acquisition_ugc_creative bound to consumer_brand_a
        # (it may be another pattern — that's fine, we just confirm no mis-binding)
        if playbook is not None:
            # If a playbook was returned, it must be because of load-order fallback
            # (no brand binding), not because of a consumer_brand_a binding leak
            binding = registry.get_brand_binding(
                "unknown_merchant_xyz", playbook.get("id", "")
            )
            assert binding is None, (
                f"Merchant 'unknown_merchant_xyz' has an unexpected brand binding for "
                f"'{playbook.get('id')}'. Brand bindings must be brand-specific. "
                "Check playbooks/brands/ directory for stray binding files."
            )

    def test_cba_001_evidence_refs_populated_in_brand_binding(self, cba_001_binding):
        """Brand binding for cba_001 must have evidence_refs_template.

        evidence_refs_template is required for DecisionCard.evidence to be
        populated with brand-specific observed metric values. Without it,
        the DecisionCard has no evidence grounding — Gate 3 of the 5-Gate
        Bouncer (evidence grounding) may fail.
        """
        assert "evidence_refs_template" in cba_001_binding, (
            "consumer_brand_a brand binding for acquisition_ugc_creative is missing "
            "evidence_refs_template. Add at least one evidence reference. "
            "See SOP Section 3 and ADR-0009 (evidence grounding requirement)."
        )
        refs = cba_001_binding["evidence_refs_template"]
        assert isinstance(refs, list) and len(refs) >= 1, (
            "evidence_refs_template must be a non-empty list. "
            f"Got: {refs!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# cba_002: conversion_compliance_friction
# ─────────────────────────────────────────────────────────────────────────────

class TestCba002ComplianceFriction:

    def test_cba_002_fires_on_cvr_collapse_with_recent_site_change(self, registry):
        """cba_002 must match conversion / CRITICAL for consumer_brand_a.

        Positive fire: CVR dropped suddenly (overnight, >60% relative) across
        paid AND organic, coinciding with a recent compliance/legal site change.
        MSM conversion dimension resolves to CRITICAL (mobile_below_degrading
        AND cvr_trending_down — both true for a sitewide compliance block).

        Fails red phase because conversion_compliance_friction.yaml does not exist.
        """
        playbook = registry.match_playbook(
            "conversion",
            {"msm_state": "CRITICAL"},
            merchant_id=_CBA_BRAND,
        )
        assert playbook is not None, (
            "No playbook returned for conversion/CRITICAL with merchant_id=consumer_brand_a. "
            "Expected conversion_compliance_friction to be loaded and bound."
        )
        assert playbook.get("id") == "conversion_compliance_friction", (
            f"Expected 'conversion_compliance_friction', got '{playbook.get('id')}'. "
            "Brand binding for consumer_brand_a must reference conversion_compliance_friction."
        )

    def test_cba_002_does_not_fire_on_gradual_cvr_decline(self, cba_002_meta):
        """cba_002 must NOT fire on a gradual CVR decline.

        Gradual decline (WATCH or DEGRADING) has different root causes —
        funnel optimization, offer fatigue, seasonal. The compliance shock
        pattern requires CRITICAL state (sudden, cross-source, large magnitude).
        Test: the meta-pattern must declare a CRITICAL trigger, not WATCH or DEGRADING.
        """
        triggers = cba_002_meta.get("triggers", [])
        msm_states = [t.get("msm_state", "") for t in triggers]

        assert "CRITICAL" in msm_states, (
            "cba_002 must have at least one trigger with msm_state=CRITICAL. "
            "Compliance CVR collapse is a CRITICAL event, not WATCH/DEGRADING. "
            f"Found msm_states: {msm_states}"
        )
        # Must not also fire on WATCH (no accidental WATCH trigger for this pattern)
        assert "WATCH" not in msm_states, (
            "cba_002 must NOT have a WATCH trigger. Gradual CVR decline is a "
            "different pattern. cba_002 is only for sudden cross-source collapses. "
            f"Found msm_states: {msm_states}"
        )

    def test_cba_002_does_not_fire_without_recent_site_change_signal(self, cba_002_meta):
        """cba_002 trigger condition must reference recent_change detection.

        The pattern requires the conjunction: CVR collapse AND recent site/flow/
        legal change. Without the site change signal, CVR collapse alone could be
        traffic quality or media issue (different remediation entirely).

        Test: at least one trigger condition references recent_change_window_days
        or a recent_change equivalent signal.
        """
        triggers = cba_002_meta.get("triggers", [])
        trigger_conditions = " ".join(
            str(t.get("condition", "")) for t in triggers
        )
        has_change_signal = (
            "recent_change" in trigger_conditions.lower()
            or "site_change" in trigger_conditions.lower()
            or "change_window" in trigger_conditions.lower()
        )
        assert has_change_signal, (
            "cba_002 trigger condition must reference a recent site/flow/legal change "
            "signal (e.g. recent_change_window_days). Without this conjunction, the "
            "pattern fires on any CVR collapse — including traffic quality issues "
            "that require completely different remediation. "
            f"Current trigger conditions: {trigger_conditions}"
        )

    def test_cba_002_analysis_path_starts_with_timeline_correlation(self, cba_002_meta):
        """SOP Section 10 (Proxy Trigger Discipline) HARD REQUIREMENT.

        MSM CRITICAL trigger for cba_002 uses mobile_below_degrading AND
        cvr_trending_down as proxy for site-wide compliance friction.
        analysis_path[0] MUST be timeline_correlation with must_run_first=true.

        This is a structural test — it reads the YAML, not the runtime output.
        If this test fails after YAML is written: the YAML violates SOP Section 10.
        Fix: ensure analysis_path[0].step == 'timeline_correlation' and
        analysis_path[0].must_run_first == True.
        """
        analysis_path = cba_002_meta.get("analysis_path", [])
        assert len(analysis_path) >= 1, (
            "cba_002 meta-pattern has no analysis_path. "
            "analysis_path is required (SOP Section 2)."
        )

        first_step = analysis_path[0]
        assert first_step.get("step") == "timeline_correlation", (
            f"cba_002 analysis_path[0].step must be 'timeline_correlation', "
            f"got '{first_step.get('step')}'. "
            "SOP Section 10 (Proxy Trigger Discipline): root cause analysis must "
            "NOT start with mobile vs desktop analysis for a proxy CRITICAL trigger. "
            "See docs/playbook_authoring_sop.md Section 10."
        )
        assert first_step.get("must_run_first") is True, (
            "cba_002 analysis_path[0].must_run_first must be True. "
            "This field signals to the LLM renderer that this step must appear "
            "first in the DecisionCard narrative. See SOP Section 10."
        )
        assert "rationale" in first_step, (
            "cba_002 analysis_path[0] must include a 'rationale' field explaining "
            "why timeline correlation must run first. This is read by the LLM renderer "
            "to generate the proxy-trigger explanation in the DecisionCard. "
            "See SOP Section 10."
        )
        # rationale must mention the proxy nature of the trigger
        rationale = str(first_step.get("rationale", ""))
        assert any(word in rationale.lower() for word in ["proxy", "compliance", "site-wide", "sitewide"]), (
            "cba_002 analysis_path[0].rationale must explain that the MSM CRITICAL "
            "trigger is a proxy for site-wide friction. Include at least one of: "
            "'proxy', 'compliance', 'site-wide', 'sitewide'. "
            f"Current rationale: {rationale!r}"
        )

    def test_cba_002_decision_card_narrative_mentions_timeline_first(self):
        """Runtime enforcement of SOP Section 10: LLM renderer output must mention
        timeline / recent changes BEFORE any mobile or user-segment language.

        This tests the REMOVE_COMPLIANCE_FRICTION template in llm_renderer.py.
        A verified decision with action_id=REMOVE_COMPLIANCE_FRICTION must produce
        a recommendation that mentions 'timeline' before 'mobile'.
        """
        from src.decision_engine.layer2_decision.pillar3_llm.llm_renderer import LLMRenderer
        from src.decision_engine.contracts import VerificationChain, VerificationStep

        renderer = LLMRenderer()

        # Build a minimal verified decision that passes verification
        # (all_passed=True is the gate — we mock the verification chain)
        mock_vc = VerificationChain(
            msm_trigger=VerificationStep(name="msm_trigger", passed=True, reason="conversion CRITICAL"),
            margin_gate=VerificationStep(name="margin_gate", passed=True, reason="margin ok"),
            inventory_gate=VerificationStep(name="inventory_gate", passed=True, reason="inventory ok"),
            conflict_check=VerificationStep(name="conflict_check", passed=True, reason="no conflict"),
            all_passed=True,
        )

        verified = {
            "action_id": "REMOVE_COMPLIANCE_FRICTION",
            "module": "conversion",
            "eligible": True,
            "final_score": 0.25,
            "verification_chain": mock_vc.model_dump(),
            "signals": {
                "mobile_atc_rate": 0.015,
                "desktop_atc_rate": 0.045,
                "mobile_traffic_pct": 0.68,
                "checkout_cvr": {"current": 0.008, "3d_ago": 0.025},
            },
        }

        result = renderer.render(verified)

        recommendation = result.get("recommendation", "")
        # Proxy-trigger discipline: timeline / recent changes must come BEFORE mobile
        timeline_pos = min(
            recommendation.lower().find(word)
            for word in ["timeline", "recent", "site change", "compliance"]
            if recommendation.lower().find(word) != -1
        ) if any(w in recommendation.lower() for w in ["timeline", "recent", "site change", "compliance"]) else -1

        mobile_pos = recommendation.lower().find("mobile")

        assert timeline_pos != -1, (
            "REMOVE_COMPLIANCE_FRICTION recommendation must mention 'timeline', "
            "'recent', 'site change', or 'compliance'. "
            f"Got recommendation: {recommendation!r}"
        )

        if mobile_pos != -1:
            assert timeline_pos < mobile_pos, (
                "REMOVE_COMPLIANCE_FRICTION recommendation must mention timeline/recent "
                f"changes (pos={timeline_pos}) BEFORE mobile (pos={mobile_pos}). "
                "This enforces SOP Section 10 (Proxy Trigger Discipline) at the "
                "LLM renderer output layer. "
                f"Full recommendation: {recommendation!r}"
            )

    def test_cba_002_audit_recent_changes_action_is_present(self, cba_002_meta):
        """The diagnose-before-execute pattern requires AUDIT_RECENT_CHANGES
        to be a first-class candidate action, not buried inside analysis_path."""
        actions = cba_002_meta.get("actions", [])
        action_ids = [a.get("id") for a in actions]
        assert "AUDIT_RECENT_CHANGES" in action_ids, (
            f"cba_002 must expose AUDIT_RECENT_CHANGES as a candidate action. "
            f"Currently has: {action_ids}"
        )
        audit_action = next(a for a in actions if a.get("id") == "AUDIT_RECENT_CHANGES")
        assert audit_action.get("type") == "DIAGNOSTIC"
        assert audit_action.get("requires_approval") is False

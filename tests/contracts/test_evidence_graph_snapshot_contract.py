# ── Contract Tests: EvidenceTraceEntry + EvidenceGraphSnapshot ────────────────
# Enforces ADR-0009 invariants on the two Evidence Graph types.
#
# Every test docstring names the invariant it guards and what to do on failure.
# ─────────────────────────────────────────────────────────────────────────────
import pytest
from datetime import datetime, timezone

from src.decision_engine.contracts import EvidenceTraceEntry, EvidenceGraphSnapshot


# ── EvidenceTraceEntry ────────────────────────────────────────────────────────

def test_evidence_trace_entry_frozen():
    """EvidenceTraceEntry must be immutable (frozen=True).

    Enforces: ADR-0009 — trace entries are append-only facts; mutation would
    allow downstream stages to silently alter the causal record.
    """
    entry = EvidenceTraceEntry(step="L1_State", finding="retention DEGRADING")
    with pytest.raises(Exception):
        entry.finding = "tampered"


def test_evidence_trace_entry_requires_step_and_finding():
    """EvidenceTraceEntry requires step and finding fields."""
    with pytest.raises(Exception):
        EvidenceTraceEntry()  # missing both

    with pytest.raises(Exception):
        EvidenceTraceEntry(step="L1_State")  # missing finding

    with pytest.raises(Exception):
        EvidenceTraceEntry(finding="retention DEGRADING")  # missing step


@pytest.mark.parametrize("step", [
    "L1_State", "L2_KG", "L3_Constraint", "L3_Scoring", "L3_Verification"
])
def test_evidence_trace_entry_accepts_all_valid_steps(step):
    """All 5 step literals must be accepted by EvidenceTraceEntry.step."""
    entry = EvidenceTraceEntry(step=step, finding="some finding")
    assert entry.step == step


@pytest.mark.parametrize("bad_step", [
    "L4_Serving", "L0_Signal", "l1_state", "SCORING", "unknown", "",
])
def test_evidence_trace_entry_rejects_invalid_step(bad_step):
    """EvidenceTraceEntry.step must only accept the 5 defined literals.

    If this fails: a new step type was added. Update the Literal in contracts.py
    AND write a new ADR if this represents an architectural change (e.g., adding
    an L4-level trace entry changes the evidence grounding contract).
    """
    with pytest.raises(Exception):
        EvidenceTraceEntry(step=bad_step, finding="some finding")


def test_evidence_trace_entry_source_data_defaults_empty():
    """source_data must default to empty dict (not None)."""
    entry = EvidenceTraceEntry(step="L2_KG", finding="playbook matched retention")
    assert entry.source_data == {}


def test_evidence_trace_entry_source_data_accepts_arbitrary_dict():
    """source_data must accept any dict — it is the raw backing data for grounding."""
    entry = EvidenceTraceEntry(
        step="L3_Constraint",
        finding="All constraints passed",
        source_data={
            "margin_pct": 0.33,
            "violations": [],
            "eligible": True,
            "nested": {"a": 1, "b": [1, 2, 3]},
        }
    )
    assert entry.source_data["margin_pct"] == 0.33
    assert entry.source_data["nested"]["b"] == [1, 2, 3]


def test_evidence_trace_entry_round_trip():
    """EvidenceTraceEntry must survive model_dump() → reconstruct cycle."""
    entry = EvidenceTraceEntry(
        step="L3_Scoring",
        finding="final_score=0.1706 (u_base=0.262, risk_penalty=0.050)",
        source_data={"u_base": 0.262, "u_ucb": 0.0, "risk_penalty": 0.050},
    )
    d = entry.model_dump()
    entry2 = EvidenceTraceEntry(**d)
    assert entry2.step == entry.step
    assert entry2.finding == entry.finding
    assert entry2.source_data == entry.source_data


# ── EvidenceGraphSnapshot ─────────────────────────────────────────────────────

def test_evidence_graph_snapshot_frozen():
    """EvidenceGraphSnapshot must be immutable (frozen=True).

    Enforces: ADR-0009 — snapshots are sealed decision records; once built,
    they must not be altered.
    """
    snap = EvidenceGraphSnapshot(
        candidate_id="cand_001",
        winner_action="DISCOUNT_10PCT",
    )
    with pytest.raises(Exception):
        snap.winner_action = "tampered"


def test_evidence_graph_snapshot_requires_candidate_id_and_winner_action():
    """EvidenceGraphSnapshot requires candidate_id and winner_action."""
    with pytest.raises(Exception):
        EvidenceGraphSnapshot()

    with pytest.raises(Exception):
        EvidenceGraphSnapshot(candidate_id="c1")  # missing winner_action

    with pytest.raises(Exception):
        EvidenceGraphSnapshot(winner_action="DISCOUNT_10PCT")  # missing candidate_id


def test_evidence_graph_snapshot_evidence_trace_defaults_empty():
    """evidence_trace defaults to empty list (no trace entries required at construction)."""
    snap = EvidenceGraphSnapshot(
        candidate_id="cand_001",
        winner_action="DISCOUNT_10PCT",
    )
    assert snap.evidence_trace == []


def test_evidence_graph_snapshot_accepts_empty_trace():
    """An empty evidence_trace is valid (e.g., for test stubs or placeholder snapshots)."""
    snap = EvidenceGraphSnapshot(
        candidate_id="cand_001",
        winner_action="REMINDER_ONLY",
        evidence_trace=[],
    )
    assert snap.evidence_trace == []


def test_evidence_graph_snapshot_accepts_populated_trace():
    """evidence_trace must accept a list of EvidenceTraceEntry objects."""
    entries = [
        EvidenceTraceEntry(
            step="L1_State",
            finding="Retention DEGRADING (urgency=0.75)",
            source_data={"retention_state": "DEGRADING", "urgency": 0.75},
        ),
        EvidenceTraceEntry(
            step="L2_KG",
            finding="Playbook retention_risk_v1 matched",
            source_data={"playbook_id": "retention_risk_v1"},
        ),
        EvidenceTraceEntry(
            step="L3_Constraint",
            finding="All constraints passed (margin 0.33 > floor 0.15)",
            source_data={"margin_pct": 0.33, "violations": [], "eligible": True},
        ),
        EvidenceTraceEntry(
            step="L3_Scoring",
            finding="final_score=0.1706 (β1·U_base=0.170, β2·U_ucb=0.0, β3·Risk=0.000)",
            source_data={"u_base": 0.262, "u_ucb": 0.0, "risk_penalty": 0.0},
        ),
        EvidenceTraceEntry(
            step="L3_Verification",
            finding="Verification passed (all 4 gates green)",
            source_data={"all_passed": True},
        ),
    ]
    snap = EvidenceGraphSnapshot(
        candidate_id="cand_brightskin_001",
        winner_action="DISCOUNT_10PCT",
        evidence_trace=entries,
    )
    assert len(snap.evidence_trace) == 5
    assert snap.evidence_trace[0].step == "L1_State"
    assert snap.evidence_trace[4].step == "L3_Verification"


def test_evidence_graph_snapshot_computed_at_is_utc_datetime():
    """computed_at must be a UTC datetime, auto-populated if not provided."""
    snap = EvidenceGraphSnapshot(
        candidate_id="c1",
        winner_action="DISCOUNT_10PCT",
    )
    assert isinstance(snap.computed_at, datetime)
    # Default is UTC
    assert snap.computed_at.tzinfo is not None


def test_evidence_graph_snapshot_computed_at_accepts_explicit_value():
    """computed_at must accept an explicit datetime."""
    ts = datetime(2026, 4, 10, 9, 0, 0, tzinfo=timezone.utc)
    snap = EvidenceGraphSnapshot(
        candidate_id="c1",
        winner_action="PAUSE_CHANNEL",
        computed_at=ts,
    )
    assert snap.computed_at == ts


def test_evidence_graph_snapshot_round_trip():
    """EvidenceGraphSnapshot must survive model_dump() → reconstruct cycle."""
    snap = EvidenceGraphSnapshot(
        candidate_id="cand_brightskin_001",
        winner_action="DISCOUNT_10PCT",
        computed_at=datetime(2026, 4, 10, 9, 0, 0, tzinfo=timezone.utc),
        evidence_trace=[
            EvidenceTraceEntry(
                step="L1_State",
                finding="Retention DEGRADING",
                source_data={"urgency": 0.75},
            ),
        ],
    )
    d = snap.model_dump()
    # Reconstruct requires re-wrapping the trace entries
    d["evidence_trace"] = [EvidenceTraceEntry(**e) for e in d["evidence_trace"]]
    snap2 = EvidenceGraphSnapshot(**d)
    assert snap2.candidate_id == snap.candidate_id
    assert snap2.winner_action == snap.winner_action
    assert len(snap2.evidence_trace) == 1
    assert snap2.evidence_trace[0].step == "L1_State"

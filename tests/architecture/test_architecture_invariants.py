# ── Architecture Invariant Tests ─────────────────────────────────────────────
# Automated detection of architectural drift — code that violates boundaries
# declared in ADRs. These tests use AST analysis so they are robust against
# refactoring (unlike grep-based checks that break on whitespace changes).
#
# Every test docstring includes:
#   1. The invariant in one sentence
#   2. The ADR or CLAUDE.md section it enforces
#   3. What to do if the test fails
#
# References:
#   V3/docs/adr/0001-adopt-policy-decision-unified-interface.md
#   V3/docs/adr/0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md
#   V3/docs/adr/0007-document-cross-layer-dependency-constraints-to-scoring.md
#   V3/CLAUDE.md — Cross-Layer Dependency Note
# ─────────────────────────────────────────────────────────────────────────────
import ast
import importlib
import re
from pathlib import Path

import pytest

# ── Path helpers ──────────────────────────────────────────────────────────────

_SRC = Path(__file__).parent.parent.parent / "src" / "decision_engine"


def _src_file(*parts: str) -> Path:
    return _SRC.joinpath(*parts)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _all_source_files() -> list[Path]:
    """Return all .py files under src/decision_engine/, excluding __pycache__."""
    return [
        p for p in _SRC.rglob("*.py")
        if "__pycache__" not in str(p)
    ]


# ── Helper: collect import names from an AST ──────────────────────────────────

def _imported_names(tree: ast.Module) -> set[str]:
    """Return all names imported (top-level and inline) in an AST."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _imported_modules(tree: ast.Module) -> list[str]:
    """Return all module paths referenced in import statements."""
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


# ── Test 1: scoring.py must not import ConstraintEngine ───────────────────────

def test_scoring_does_not_import_constraint_engine():
    """Scoring engine must not import ConstraintEngine directly.

    Enforces: ADR-0001 (PolicyDecision unified interface).
    The scoring formula consumes PolicyDecision.risk_penalty from the
    candidate dict — it must not call ConstraintEngine itself.
    Duplicate constraint evaluation was the original bug ADR-0001 fixed.

    If this test fails: either the refactor regressed (fix by removing
    the import and consuming PolicyDecision from the candidate dict), or
    the decision is being intentionally reversed (write a new ADR
    superseding ADR-0001 and update this test).
    """
    scoring_path = _src_file("layer2_decision", "scoring.py")
    tree = _parse(scoring_path)
    imported = _imported_names(tree)
    assert "ConstraintEngine" not in imported, (
        "scoring.py must not import ConstraintEngine. "
        "Consume PolicyDecision.risk_penalty from the candidate dict instead. "
        "See ADR-0001."
    )


# ── Test 2: ConstraintEngine.check_all must return PolicyDecision ─────────────

def test_constraints_check_all_returns_policy_decision():
    """ConstraintEngine.check_all must have return annotation PolicyDecision.

    Enforces: ADR-0001 — check_all() is the single L3.3 output interface.
    The return type annotation is the machine-checkable contract for this
    boundary. Removing or changing it breaks the ADR-0001 guarantee.

    If this test fails: either the annotation was removed (restore it),
    or the return type is being changed (write a new ADR superseding ADR-0001).
    """
    import inspect
    import typing
    from src.decision_engine.layer3_value.constraints import ConstraintEngine
    from src.decision_engine.contracts import PolicyDecision

    hints = typing.get_type_hints(ConstraintEngine.check_all)
    return_type = hints.get("return")
    assert return_type is PolicyDecision, (
        f"ConstraintEngine.check_all must return PolicyDecision, "
        f"got {return_type!r}. See ADR-0001."
    )


# ── Test 3: no layer imports from a higher-numbered layer ─────────────────────

# Layer number by directory name prefix
_LAYER_ORDER: dict[str, int] = {
    "layer0_data": 0,
    "layer1_msm": 1,
    "layer2_decision": 2,
    "layer3_value": 3,
    "layer4_serving": 4,
    "layer5_wsm": 5,
}

# Documented cross-layer exceptions (file → allowed higher layers it may import).
# Each entry is (source_file_suffix, permitted_target_layer).
# ADR-0007: constraints.py lives in L3 but is consumed by L2 scoring as the
# Risk(Constraints) term, and by L2 verifier for the single source-of-truth
# margin floor constant. Both exceptions are explicitly permitted by ADR-0007.
# No other L2→L3 import is allowed without a new ADR.
_CROSS_LAYER_ALLOWLIST: list[tuple[str, int]] = [
    # scoring.py may import _VIOLATION_WEIGHTS from layer3_value/constraints.py (ADR-0007)
    (str(Path("layer2_decision") / "scoring.py"), 3),
    # decision_verifier.py may import _MARGIN_FLOOR from layer3_value/constraints.py (ADR-0007)
    (str(Path("layer2_decision") / "pillar3_llm" / "decision_verifier.py"), 3),
]


def _layer_number(path: Path) -> int | None:
    """Return the layer number for a path, or None if not in a numbered layer."""
    for part in path.parts:
        if part in _LAYER_ORDER:
            return _LAYER_ORDER[part]
    return None


def _imported_layer_numbers(tree: ast.Module) -> list[int]:
    """Return all layer numbers referenced in import statements."""
    layers: list[int] = []
    for mod in _imported_modules(tree):
        for layer_name, num in _LAYER_ORDER.items():
            if layer_name in mod:
                layers.append(num)
    return layers


def test_no_layer_imports_from_higher_numbered_layer():
    """No file in layer N may import from layer M where M > N.

    Enforces: CLAUDE.md 6-Layer Architecture — data flows downward
    (L0 → L1 → L2 → L3 → L4 → L5). Upward imports create circular
    dependencies and couple higher-level concerns into lower layers.

    Documented exceptions (see _CROSS_LAYER_ALLOWLIST above):
    - layer2_decision/scoring.py → layer3_value/constraints.py
      (ADR-0007: PolicyDecision risk_penalty, _VIOLATION_WEIGHTS)
    - layer2_decision/pillar3_llm/decision_verifier.py → layer3_value/constraints.py
      (ADR-0007: _MARGIN_FLOOR single source of truth)

    If this test fails: either fix the import (restructure so it flows
    downward) or add a documented exception to _CROSS_LAYER_ALLOWLIST with
    a comment citing the ADR that permits the cross-layer dependency.
    """
    violations: list[str] = []

    for path in _all_source_files():
        src_layer = _layer_number(path)
        if src_layer is None:
            continue

        # Compute relative path suffix for allowlist matching
        rel = path.relative_to(_SRC)
        rel_str = str(rel)

        try:
            tree = _parse(path)
        except SyntaxError:
            continue

        for tgt_layer in _imported_layer_numbers(tree):
            if tgt_layer <= src_layer:
                continue  # lower or same layer — allowed
            # Higher layer: check allowlist
            allowed = any(
                rel_str.endswith(suffix) and tgt_layer == permitted
                for suffix, permitted in _CROSS_LAYER_ALLOWLIST
            )
            if not allowed:
                violations.append(
                    f"{rel_str} (L{src_layer}) imports from L{tgt_layer}"
                )

    assert not violations, (
        "Layer dependency violations detected:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nSee CLAUDE.md Cross-Layer Dependency Note and _CROSS_LAYER_ALLOWLIST."
    )


# ── Test 4: margin floor constant defined only in constraints.py ──────────────

def test_margin_floor_value_only_in_constraints():
    """_MARGIN_FLOOR = 0.15 must be defined only in layer3_value/constraints.py.

    Enforces: ADR-0001 — CPG hard constraints are the single authority for
    constraint thresholds. Any other file that assigns 0.15 to a margin-floor
    variable creates a second source of truth that can drift independently.

    Specifically looks for the assignment pattern `_MARGIN_FLOOR = 0.15`
    (not bare `0.15`, which appears legitimately in statistical parameters).

    If this test fails: the offending file is redefining the margin floor
    constant. Fix: import _MARGIN_FLOOR from layer3_value.constraints instead.
    """
    pattern = re.compile(r"_MARGIN_FLOOR\s*=\s*0\.15")
    violations: list[str] = []

    for path in _all_source_files():
        rel = str(path.relative_to(_SRC))
        # Only constraints.py may define the constant
        if rel.endswith(str(Path("layer3_value") / "constraints.py")):
            continue
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            violations.append(rel)

    assert not violations, (
        "_MARGIN_FLOOR = 0.15 found outside layer3_value/constraints.py:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nImport _MARGIN_FLOOR from layer3_value.constraints instead."
    )


# ── Test 5: V3.5 contracts are frozen ─────────────────────────────────────────

_V3_5_CONTRACT_NAMES = {
    "PolicyDecision",
    "DecisionState",
    "DecisionFeatureVector",
    "RawCandidate",
    "ScoredCandidate",
}


def _class_has_frozen_config(class_node: ast.ClassDef) -> bool:
    """Return True if a class body contains model_config = ConfigDict(frozen=True)."""
    for stmt in class_node.body:
        # Look for: model_config = ConfigDict(frozen=True)
        if not isinstance(stmt, ast.Assign):
            continue
        for target in stmt.targets:
            if not (isinstance(target, ast.Name) and target.id == "model_config"):
                continue
            # Check right side is ConfigDict(frozen=True)
            value = stmt.value
            if not isinstance(value, ast.Call):
                continue
            func = value.func
            func_name = (
                func.id if isinstance(func, ast.Name)
                else func.attr if isinstance(func, ast.Attribute)
                else None
            )
            if func_name != "ConfigDict":
                continue
            for kw in value.keywords:
                if kw.arg == "frozen" and isinstance(kw.value, ast.Constant):
                    if kw.value.value is True:
                        return True
    return False


def test_all_v3_5_contracts_are_frozen():
    """All 5 V3.5 core contract classes must have model_config = ConfigDict(frozen=True).

    Enforces: ADR-0001 and ADR-0005 — typed stage-boundary objects must be
    immutable. Mutable contracts allow downstream stages to silently alter
    upstream decisions, violating the deterministic pipeline invariant.

    Pre-V3.5 models (DecisionCard, WSMTransition, etc.) are exempt — they
    predate the frozen contract and have documented reasons to remain mutable.

    If this test fails for a V3.5 contract: add model_config = ConfigDict(frozen=True)
    to the class, or write a new ADR documenting why this contract must remain mutable.
    """
    contracts_path = _src_file("contracts.py")
    tree = _parse(contracts_path)

    found_frozen: set[str] = set()
    found_not_frozen: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in _V3_5_CONTRACT_NAMES:
            continue
        if _class_has_frozen_config(node):
            found_frozen.add(node.name)
        else:
            found_not_frozen.add(node.name)

    missing = _V3_5_CONTRACT_NAMES - found_frozen
    assert not missing, (
        f"V3.5 contracts missing frozen=True: {missing}. "
        "Add model_config = ConfigDict(frozen=True) to each. "
        "See ADR-0001 and ADR-0005."
    )
    assert not found_not_frozen, (
        f"V3.5 contracts have non-frozen config: {found_not_frozen}."
    )


# ── Test 6: ConstraintEngine instantiated only in pipeline.py ─────────────────

def test_constraint_engine_only_instantiated_in_pipeline():
    """ConstraintEngine must only be instantiated in layer4_serving/pipeline.py.

    Enforces: ADR-0001 — ConstraintEngine is a singleton orchestrated by
    the pipeline. Scattered instantiation would create independent constraint
    caches and make policy_version tracking unreliable.

    If this test fails: either a new file is instantiating ConstraintEngine
    (remove the instantiation and inject it from pipeline), or the ownership
    model is changing (write a new ADR).
    """
    pattern = re.compile(r"\bConstraintEngine\s*\(")
    violations: list[str] = []

    _allowed = {
        str(Path("layer3_value") / "constraints.py"),   # class definition
        str(Path("layer4_serving") / "pipeline.py"),    # sole instantiation point
    }

    for path in _all_source_files():
        rel = str(path.relative_to(_SRC))
        if any(rel.endswith(a) for a in _allowed):
            continue
        content = path.read_text(encoding="utf-8")
        if pattern.search(content):
            violations.append(rel)

    assert not violations, (
        "ConstraintEngine() instantiated outside the allowed files:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nOnly layer4_serving/pipeline.py may instantiate ConstraintEngine."
    )


# ── Test 7: V3.5 contracts importable from contracts module ───────────────────

_REQUIRED_EXPORTS = [
    "PolicyDecision",
    "DecisionState",
    "DecisionFeatureVector",
    "RawCandidate",
    "ScoredCandidate",
]


@pytest.mark.parametrize("name", _REQUIRED_EXPORTS)
def test_v3_5_contracts_exported_from_contracts_module(name):
    """All 5 V3.5 core contracts must be importable from src.decision_engine.contracts.

    Enforces: ADR-0001 and ADR-0005 — contracts.py is the single authoritative
    location for cross-layer data types. Moving a contract out of contracts.py
    breaks all downstream consumers without an explicit import-path change.

    If this test fails for {name}: either the class was moved (update the import
    path everywhere and add a re-export in contracts.py), or it was deleted
    (write an ADR documenting the removal).
    """
    from src.decision_engine import contracts
    assert hasattr(contracts, name), (
        f"{name!r} is not exported from src.decision_engine.contracts. "
        "Add it back or update this test with the new canonical location."
    )
    cls = getattr(contracts, name)
    assert isinstance(cls, type), f"{name!r} should be a class, got {type(cls)!r}"


# ── Test 8: Step 14 WSM write iterates all ranked candidates ──────────────────

def test_wsm_step14_iterates_all_candidates_not_gate_filtered():
    """Step 14 must write to WSM for every ranked candidate, including blocked ones.

    Enforces: pipeline.py Step 14 hard invariant — WSM is the learning substrate.
    Even rejected/blocked candidates are training data: they teach the bandit
    which (state, action) pairs lead to policy violations. Silently dropping
    blocked candidates would bias the training distribution toward approved
    actions only (survivorship bias).

    This test checks that the Step 14 loop iterates over 'ranked' (the full
    scored set), not over 'response_cards' (gate-passing candidates only) or
    any other filtered subset.

    If this test fails:
    - The pipeline was "optimized" to skip WSM writes for blocked candidates.
      Do not do this — write an ADR explaining why the learning layer can
      tolerate the bias instead, then update this test.
    - If the variable name changed (e.g. 'ranked' → 'all_candidates'), update
      the assertion below and document why.

    See: pipeline.py Step 14 comment, ADR-0001 (shadow mode design).
    """
    pipeline_path = _src_file("layer4_serving", "pipeline.py")
    content = pipeline_path.read_text(encoding="utf-8")

    # Find the Step 14 "Write ALL candidates to WSM" block and the immediately
    # following for-loop target.  The more specific anchor ("Write ALL") avoids
    # matching the module-level Step 14 mention in the file docstring.
    step14_pattern = re.compile(
        r"Step\s+14.*?Write\s+ALL.*?for\s+\w+\s+in\s+(\w+)\s*:",
        re.DOTALL,
    )
    match = step14_pattern.search(content)
    assert match is not None, (
        "Step 14 WSM write loop not found in pipeline.py. "
        "Either the step was removed or the comment text changed. "
        "Restore the loop or update this test with the new location."
    )

    loop_iterable = match.group(1)
    assert loop_iterable == "ranked", (
        f"Step 14 must iterate over 'ranked' (all scored candidates), "
        f"got '{loop_iterable}'. "
        "Iterating over a gate-filtered subset (e.g. response_cards) would "
        "drop blocked candidates from the WSM log, biasing bandit training. "
        "See pipeline.py Step 14 comment."
    )


# ── Test 9: LLM Renderer render_from_snapshot only references trace facts ─────

def test_llm_renderer_render_from_snapshot_uses_snapshot_input():
    """LLMRenderer.render_from_snapshot must accept an EvidenceGraphSnapshot.

    Enforces: ADR-0009 (Evidence Graph Snapshot).

    The renderer's new pathway must accept and process a snapshot without
    raising errors. The output must reference the snapshot's candidate_id
    or winner_action — confirming the snapshot is the actual input, not a
    fallback to some other data source.

    If this test fails:
    - render_from_snapshot() was removed or renamed: restore it (ADR-0009)
    - render_from_snapshot() raises on a valid snapshot: fix the renderer
    - Output does not reference snapshot facts: the renderer is not using
      the snapshot as its input. Fix by ensuring the method uses
      snapshot.evidence_trace, not an alternative data source.
    """
    from src.decision_engine.contracts import EvidenceGraphSnapshot, EvidenceTraceEntry
    from src.decision_engine.layer2_decision.pillar3_llm.llm_renderer import LLMRenderer

    snapshot = EvidenceGraphSnapshot(
        candidate_id="test_merchant_DISCOUNT_10PCT",
        winner_action="DISCOUNT_10PCT",
        evidence_trace=[
            EvidenceTraceEntry(
                step="L1_State",
                finding="Retention dimension is DEGRADING (urgency=0.75)",
                source_data={"module": "retention", "state": "DEGRADING", "urgency": 0.75},
            ),
            EvidenceTraceEntry(
                step="L3_Constraint",
                finding="All constraints passed",
                source_data={"eligible": True, "violations": [], "risk_penalty": 0.0},
            ),
            EvidenceTraceEntry(
                step="L3_Scoring",
                finding="final_score=0.1706 (β1·U_base=0.262, β2·U_ucb=0.0, β3·Risk=0.0)",
                source_data={"u_base": 0.262, "u_ucb": 0.0, "risk_penalty": 0.0, "final_score": 0.1706},
            ),
        ],
    )

    renderer = LLMRenderer()
    result = renderer.render_from_snapshot(snapshot)

    assert isinstance(result, dict), (
        "render_from_snapshot must return a dict. "
        "See ADR-0009 for the expected output contract."
    )
    # The output must reference the snapshot — either the action name or candidate_id
    result_str = str(result)
    assert "DISCOUNT_10PCT" in result_str or "test_merchant" in result_str, (
        "render_from_snapshot output must reference facts from the snapshot "
        "(winner_action or candidate_id). "
        "The renderer appears to be ignoring the snapshot input. "
        "See ADR-0009."
    )

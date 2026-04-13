#!/usr/bin/env python3
# ── KG Dry-Run Validation Script ────────────────────────────────────────────
# Run after translating any new KG playbook YAML to verify it will produce
# candidates correctly — no real merchant data required.
#
# Usage:
#   cd V3/
#   python scripts/kg_dryrun.py                    # all modules
#   python scripts/kg_dryrun.py --module retention # one module
#   python scripts/kg_dryrun.py --playbook-dir path/to/custom/playbooks
#
# Exit code: 0 = all checks passed, 1 = issues found (blocks CI)
# ────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running from V3/ root without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import PlaybookRegistry

# Default playbook dir = V3/playbooks/ (relative to this script's location)
_DEFAULT_PLAYBOOK_DIR = str(Path(__file__).resolve().parents[1] / "playbooks")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

# 4 CPG modules × 4 MSM states = all routing paths exercised
_MODULES = ["retention", "acquisition", "conversion", "promotion"]
_MSM_STATES = ["HEALTHY", "WATCH", "DEGRADING", "CRITICAL"]


def run_dryrun(playbook_dir: str | None, module_filter: str | None) -> int:
    """
    Loads all playbooks, runs structural validation, then simulates
    match_playbook() for every module × MSM state combination.

    Returns number of issues found (0 = clean).
    """
    registry = PlaybookRegistry(playbook_dir=playbook_dir or _DEFAULT_PLAYBOOK_DIR)
    registry._ensure_loaded()

    total_issues = 0
    modules_to_check = [module_filter] if module_filter else _MODULES

    print(f"\n{'─' * 60}")
    print(f"  KG Dry-Run — {len(registry._by_id)} playbooks loaded")
    print(f"{'─' * 60}")

    # ── 1. Structural validation for every loaded playbook ────────────────
    print("\n[1/2] Structural validation\n")
    for pb_id, pb in sorted(registry._by_id.items()):
        issues = registry._validate_playbook_structure(pb)
        src = pb.get("_source_file", pb_id)
        if issues:
            print(f"  ✗  {src}")
            for issue in issues:
                print(f"       → {issue}")
            total_issues += len(issues)
        else:
            actions = pb.get("actions", [])
            utilities = [a.get("expected_utility") for a in actions if a.get("expected_utility") is not None]
            print(f"  ✓  {src}  ({len(actions)} actions, "
                  f"utility range: {min(utilities):.2f}–{max(utilities):.2f}"
                  if utilities else f"  ✓  {src}  ({len(actions)} actions, no utility values)")

    # ── 2. Route simulation: module × MSM state ───────────────────────────
    print(f"\n[2/2] Route simulation (module × MSM state)\n")
    no_match: list[tuple[str, str]] = []

    for module in modules_to_check:
        row_parts = []
        for state in _MSM_STATES:
            match = registry.match_playbook(module, {"msm_state": state})
            if match:
                row_parts.append(f"{state[:3]}✓")
            else:
                row_parts.append(f"{state[:3]}✗")
                no_match.append((module, state))
        status = "  " + "  ".join(row_parts)
        print(f"  {module:<14} {status}")

    if no_match:
        print()
        for module, state in no_match:
            print(f"  ✗  No playbook match for module='{module}' msm_state='{state}'")
            total_issues += 1

    # ── 3. Summary ────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    if total_issues == 0:
        print(f"  ✓  All checks passed — KG is ready for pipeline use")
    else:
        print(f"  ✗  {total_issues} issue(s) found — fix warnings before connecting data")
    print(f"{'─' * 60}\n")

    return total_issues


def main() -> None:
    parser = argparse.ArgumentParser(description="KG playbook dry-run validation")
    parser.add_argument("--module", help="Only check this module (default: all 4)")
    parser.add_argument("--playbook-dir", help="Override playbook directory path")
    args = parser.parse_args()

    issues = run_dryrun(
        playbook_dir=args.playbook_dir,
        module_filter=args.module,
    )
    sys.exit(0 if issues == 0 else 1)


if __name__ == "__main__":
    main()

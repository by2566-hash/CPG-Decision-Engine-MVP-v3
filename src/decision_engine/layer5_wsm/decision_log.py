# ── Layer 5 · Decision Log — per-run record for ML training ──────────────────
#
# One record per pipeline run. Three consumers:
#   - Anomaly Detector:  feature_snapshot (needs HEALTHY runs too — baseline data)
#   - XGBoost Regression: candidates + user_response + outcome_delta pairing
#   - LinUCB Bandit:      full context → action → reward triple
#
# Write lifecycle (4 moments):
#   Time 1 — pipeline completion (synchronous, THIS FILE)
#             log_id, msm_state, feature_snapshot, candidates, scoring_snapshot
#             user_response="pending", outcome_status="pending"
#   Time 2 — merchant approval/rejection (MerchantApprovalGate, Phase 2)
#             update user_response + responded_at
#   Time 3 — T+24h proxy reward (RewardBackfill.backfill_proxy_rewards, Phase 3)
#             update outcome_status="proxy_collected", proxy_reward
#   Time 4 — T+7d final reward (RewardBackfill.backfill_final_rewards, Phase 3)
#             update outcome_status="final_collected", final_reward, outcome_delta
#
# Storage: JSONL append-only, one line per record.
#   Path: {settings.decision_log_dir}/{merchant_id}/{YYYY-MM-DD}.jsonl
#   Phase 2: batch-load to PostgreSQL decision_logs table, or write directly.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ..config import settings
from ..utils.path_utils import safe_merchant_id

log = logging.getLogger(__name__)


class DecisionLog(BaseModel):
    """Per-run decision record — one record per pipeline execution.

    Captures the full context needed by all three ML consumers (anomaly
    detector, regression model, LinUCB bandit). Immutable after Time 1 write;
    later moments update only the response/outcome fields via log_id lookup.
    """

    # ── Identity ──────────────────────────────────────────────────────
    log_id: str                         # UUID — unique key for this pipeline run
    merchant_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Input snapshot (anomaly detector training material) ───────────
    # Captured BEFORE candidate generation — present even on all-HEALTHY runs.
    # Anomaly detector needs normal/HEALTHY data as baseline, not only alerts.
    msm_state: dict                     # {acquisition: "WATCH", conversion: "HEALTHY", ...}
    feature_snapshot: dict              # DecisionFeatureVector.model_dump()

    # ── Decision snapshot (bandit context) ────────────────────────────
    pattern_matched: Optional[str] = None   # meta-pattern id, e.g. "acquisition_ugc_creative"
    candidates: list[dict] = Field(default_factory=list)
    # Each candidate entry (simplified summary — NOT full candidate dict):
    # {action_id, module, playbook_id, gmv_lift, final_score, eligible, violations}
    top_action: Optional[str] = None    # action_id of the #1 ranked eligible candidate
    scoring_snapshot: dict = Field(default_factory=dict)
    # {beta1, beta2, beta3, policy_version, u_base_weight}

    # ── User response (written by MerchantApprovalGate at Time 2) ─────
    user_response: str = "pending"      # pending → approved / rejected / ignored / expired
    responded_at: Optional[datetime] = None

    # ── Outcome (written by RewardBackfill at Times 3 and 4) ──────────
    # Three-state: anomaly detector can use proxy; LinUCB should wait for final.
    outcome_status: str = "pending"     # pending → proxy_collected → final_collected
    proxy_reward: Optional[float] = None    # T+24h short-term metric change
    final_reward: Optional[float] = None   # T+7d medium-term metric change
    outcome_delta: Optional[dict] = None   # {metric_name: {before, after}} concrete changes


def write_decision_log(record: DecisionLog) -> None:
    """Append one decision log record to the merchant's daily JSONL file.

    Creates directory structure on first write. Append-only — safe for
    concurrent writes from multiple pipeline processes to the same file.

    Path: {settings.decision_log_dir}/{merchant_id}/{YYYY-MM-DD}.jsonl
    """
    date_str = record.created_at.strftime("%Y-%m-%d")
    log_dir = Path(settings.decision_log_dir) / safe_merchant_id(record.merchant_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{date_str}.jsonl"

    # model_dump_json() handles datetime serialization correctly.
    # mode="json" ensures all types (datetime, Optional) serialize to JSON-native.
    line = record.model_dump_json() + "\n"

    with log_file.open("a", encoding="utf-8") as f:
        f.write(line)

    log.debug(
        "[decision_log] wrote log_id=%s merchant=%s to %s",
        record.log_id, record.merchant_id, log_file,
    )

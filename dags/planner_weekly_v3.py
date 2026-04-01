# ── DAG · Weekly Planner ──────────────────────────────────────────────────
# Airflow DAG: Runs weekly to generate Top-3 action plans per merchant.
# Deep Plane orchestration: MSM → Decision Engine → Planner → Cache.
# ───────────────────────────────────────────────────────────────────────────


def run_weekly_planner():
    """Weekly planner DAG entry point."""
    # TODO: 1. Iterate over active merchants
    # TODO: 2. Run full Deep Plane pipeline per merchant
    # TODO: 3. Generate Weekly Plan (Top 3 by $ impact)
    # TODO: 4. Write to Redis cache
    # TODO: 5. Trigger email digest / Slack push delivery
    pass


# TODO: Define Airflow DAG with weekly schedule

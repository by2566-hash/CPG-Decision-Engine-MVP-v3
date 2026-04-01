# ── Layer 0 · Data Foundation — Event Store ────────────────────────────────
# Append-only event log: DynamoDB (events) + S3 (archive) + Timestream (trends).
# Canonical tables: orders, products, customers, campaigns, funnel_metrics.
#
# Reference: V0/compute_rfm.py (feature computation from raw events)
# ───────────────────────────────────────────────────────────────────────────


class EventStore:
    """Append-only event store backed by DynamoDB + S3 archive."""

    async def append_event(self, merchant_id: str, event_type: str, payload: dict) -> str:
        """Append a raw event to the store. Returns event_id."""
        # TODO: Write to DynamoDB events table
        pass

    async def query_events(
        self, merchant_id: str, event_type: str, since: str | None = None
    ) -> list[dict]:
        """Query events by merchant and type, optionally filtered by timestamp."""
        # TODO: DynamoDB query with optional time range
        pass

    async def archive_to_s3(self, merchant_id: str, before: str) -> int:
        """Archive old events to S3. Returns count archived."""
        # TODO: Batch move old events to S3 cold storage
        pass

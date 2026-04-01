# ── Layer 0 · Data Foundation — GA4 Connector ─────────────────────────────
# Ingests conversion rate (CVR), funnel metrics, device segment data
# from Google Analytics 4 Data API.
# ───────────────────────────────────────────────────────────────────────────


class GA4Connector:
    """Google Analytics 4 connector for conversion and funnel metrics."""

    async def fetch_funnel_metrics(self, property_id: str, date_range: dict) -> dict:
        """Fetch funnel metrics: CVR, add-to-cart rate, checkout rate."""
        # TODO: Implement GA4 Data API runReport call
        pass

    async def fetch_device_segments(self, property_id: str, date_range: dict) -> dict:
        """Fetch device-segmented metrics (mobile vs desktop CVR)."""
        # TODO: Implement GA4 device segment breakdown
        pass

    async def fetch_traffic_sources(self, property_id: str, date_range: dict) -> dict:
        """Fetch traffic source attribution data."""
        # TODO: Implement GA4 traffic source report
        pass

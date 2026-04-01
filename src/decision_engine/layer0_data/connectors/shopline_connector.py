# ── Layer 0 · Data Foundation — Shopline Connector ─────────────────────────
# Ingests orders, products, customers from Shopline API.
# Phase 1: Read API (orders, products, customers)
# Phase 2: Write API (create_discount, tag_customer)
#
# Reference: V0/config/ for existing API patterns
# ───────────────────────────────────────────────────────────────────────────


class ShoplineConnector:
    """Shopline API connector — read (Phase 1) and write (Phase 2) operations."""

    async def fetch_orders(self, merchant_id: str, since: str | None = None) -> list[dict]:
        """Fetch orders from Shopline API."""
        # TODO: Implement Shopline orders API call
        pass

    async def fetch_products(self, merchant_id: str) -> list[dict]:
        """Fetch product catalog from Shopline API."""
        # TODO: Implement Shopline products API call
        pass

    async def fetch_customers(self, merchant_id: str) -> list[dict]:
        """Fetch customer records from Shopline API."""
        # TODO: Implement Shopline customers API call
        pass

    async def create_discount(self, merchant_id: str, params: dict) -> dict:
        """Phase 2: Create discount via Shopline write API."""
        # TODO: Implement write API — Phase 2 only
        pass

    async def tag_customer(self, merchant_id: str, customer_id: str, tags: list[str]) -> dict:
        """Phase 2: Tag customer via Shopline write API."""
        # TODO: Implement write API — Phase 2 only
        pass

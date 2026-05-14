# ── Path safety utilities ──────────────────────────────────────────────────
# Shared helpers for validating external-supplied identifiers used in
# file-system paths. Prevents directory traversal via merchant_id or similar
# caller-controlled strings.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import re

# Allowed characters: alphanumeric, underscore, hyphen. Max 64 chars.
# Explicitly rejects: '/', '..', null bytes, spaces, and all other path chars.
_SAFE_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def safe_merchant_id(merchant_id: str) -> str:
    """Validate merchant_id before using it as a filesystem path component.

    Raises ValueError if merchant_id contains path traversal characters,
    slashes, spaces, or exceeds 64 characters.

    Usage:
        log_dir = Path(settings.decision_log_dir) / safe_merchant_id(record.merchant_id)
    """
    if not _SAFE_ID_RE.match(merchant_id):
        raise ValueError(
            f"Invalid merchant_id {merchant_id!r}: must match [A-Za-z0-9_-]{{1,64}}"
        )
    return merchant_id

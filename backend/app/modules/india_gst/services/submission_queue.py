"""E-invoice submission queue — scaffolding only.

Structurally mirrors ``verifactu/services/submission_queue.py`` (a
periodic drain of pending records), but with no provider registered by
default in v1: :func:`drain` is a documented no-op. Never makes a fake
network call and never advances a submission's ``state`` on its own —
only the real hook path (``not_required``/``not_configured``, set at
issue time) and a future real provider adapter may do that.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .einvoice_provider import get_registered_provider

logger = logging.getLogger(__name__)


async def drain(db: AsyncSession, clinic_id: UUID) -> int:
    """Process pending e-invoice submissions for a clinic.

    Returns the count processed — always ``0`` in v1 since no provider
    is registered. Intentionally does not raise or mutate any rows in
    that case, so callers (a future scheduled job) can call this
    unconditionally without special-casing "not configured".
    """
    provider = get_registered_provider()
    if provider is None:
        logger.debug("india_gst submission_queue.drain: no provider registered, no-op")
        return 0

    # Unreachable in v1 (no provider is ever registered) — kept so the
    # code is honest about what happens once a real adapter ships.
    raise NotImplementedError("E-invoice provider submission not implemented")

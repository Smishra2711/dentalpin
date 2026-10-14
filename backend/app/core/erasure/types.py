"""GDPR erasure contributor contract (ADR 0038, issue #546)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class ErasureCoverage(BaseModel):
    """Per-scope outcome of one partial erasure (#546).

    ``status`` is ``erased`` when that scope's copy of the erased
    categories was removed, ``retained`` when a legal basis keeps it
    (Art. 17(3)), and ``not_applicable`` when the scope holds nothing for
    the erased categories. The list is the DSR's honest coverage: a
    completed erasure must never read as covering data it never touched.

    Lives in core (not in ``gdpr``) so contributor modules can return it
    without depending on the optional ``gdpr`` module.
    """

    scope: str
    status: Literal["erased", "retained", "not_applicable"]
    detail: str


class ErasureContributor(ABC):
    """One scope's erasure behavior, owned by the module holding the copies.

    A contributor redacts its own copies of the erased contact categories
    inside the erasure's transaction and reports what it did as an
    :class:`ErasureCoverage`. ``gdpr`` pulls every contributor registered
    for the active modules and assembles the DSR coverage list from their
    answers — a scope with no contributor produces no row, so an
    uninstalled module can never be reported as erased.

    A raising contributor rolls back the whole erasure (the caller runs
    all contributors before committing).
    """

    @property
    @abstractmethod
    def scope(self) -> str:
        """Coverage scope name, e.g. ``"notifications"`` (unique per registry)."""

    @abstractmethod
    async def erase(
        self,
        clinic_id: UUID,
        patient_id: UUID,
        erased: list[str],
        retained: list[str],
        db: AsyncSession,
    ) -> ErasureCoverage:
        """Redact this scope's copies of the erased categories.

        Runs inside the erasure's transaction (ADR 0019 semantics without
        the event bus): all queries filter by ``clinic_id`` (and
        ``patient_id``), no commit, no new rows outside the scope's own
        tables. ``erased``/``retained`` are the erasure run's category
        lists, so the contributor can distinguish ``erased`` from
        ``retained`` and ``not_applicable`` exactly like the DSR report.
        """

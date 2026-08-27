"""Planned-work provider contract (issue #309).

``agenda`` and ``treatment_plan`` genuinely depend on each other at the
product level: plans register into agenda's slots and consume its
events, while booking validates and eager-loads planned items. The
manifest graph must stay acyclic, and ``treatment_plan`` already
declares ``agenda`` — so agenda's side of the edge cannot become a
``manifest.depends`` entry (the loader raises
``CircularDependencyError``).

This registry inverts the remaining code edge instead, the same shape
as billing's ``BillingComplianceHook``: agenda owns the contract,
``treatment_plan`` (whose import direction is legal) registers an
implementation at boot, and ``agenda/service.py`` stops importing
``treatment_plan`` models. When no provider is registered — a fresh
process before module registration, never a running app, since
``treatment_plan`` is non-removable — planned-item features degrade to
explicit errors rather than silent misbehaviour.

Registration is idempotent (dev filesystem re-scan re-imports modules).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class PlannedWorkProvider(Protocol):
    """What agenda needs from the planned-work owner."""

    def appointment_loader_options(self) -> list[Any]:
        """ORM loader options that eager-load the graph behind
        ``AppointmentTreatment.planned_item`` (treatment → teeth /
        catalog item, and the owning plan) for appointment reads."""
        ...

    async def validate_bookable_items(
        self,
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        planned_item_ids: list[UUID],
    ) -> list[str]:
        """Return human-readable errors for any item that cannot be
        booked (missing, other clinic, other patient, terminal plan or
        item state). Empty list means all bookable."""
        ...

    async def catalog_item_id_for(self, db: AsyncSession, planned_item_id: UUID) -> UUID | None:
        """The catalog item behind a planned item's treatment, if any —
        used to snapshot ``AppointmentTreatment.catalog_item_id`` at
        booking time."""
        ...


class PlannedWorkRegistry:
    def __init__(self) -> None:
        self._provider: PlannedWorkProvider | None = None

    def register(self, provider: PlannedWorkProvider) -> None:
        self._provider = provider

    def get(self) -> PlannedWorkProvider | None:
        return self._provider


planned_work_registry = PlannedWorkRegistry()

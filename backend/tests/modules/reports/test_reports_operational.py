"""Operational report: the plan pipeline counts live plans only (#610).

`TreatmentPlan` is soft-deleted (`treatment_plan/service.py` stamps
`deleted_at`), and every read in the owning module filters on it — as do
twelve queries in this module's own billing report. The pipeline
aggregate did not, so a deleted plan went on being counted as work in
progress.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient
from app.modules.reports.services import OperationalReportService
from app.modules.treatment_plan.models import TreatmentPlan


async def _plan(
    db: AsyncSession, clinic: Clinic, patient: Patient, number: str, *, deleted: bool
) -> TreatmentPlan:
    created_by = (
        await db.execute(
            select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == clinic.id)
        )
    ).scalar_one()
    plan = TreatmentPlan(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        plan_number=number,
        created_by=created_by,
        status="active",
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(plan)
    await db.flush()
    return plan


def _pipeline(report: dict) -> dict[str, int]:
    return {row["status"]: row["count"] for row in report["plan_pipeline"]}


@pytest.mark.asyncio
async def test_plan_pipeline_ignores_soft_deleted_plans(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
) -> None:
    await _plan(db_session, test_clinic, test_patient, "PLAN-live", deleted=False)
    await _plan(db_session, test_clinic, test_patient, "PLAN-gone", deleted=True)
    await db_session.commit()

    report = await OperationalReportService.productivity(
        db_session, test_clinic.id, date(2026, 1, 1), date(2026, 12, 31)
    )
    assert _pipeline(report) == {"active": 1}


@pytest.mark.asyncio
async def test_plan_pipeline_counts_every_live_status(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
) -> None:
    """The filter must not swallow live rows along with the deleted one."""
    live_a = await _plan(db_session, test_clinic, test_patient, "PLAN-a", deleted=False)
    live_b = await _plan(db_session, test_clinic, test_patient, "PLAN-b", deleted=False)
    live_b.status = "completed"
    await _plan(db_session, test_clinic, test_patient, "PLAN-c", deleted=True)
    await db_session.commit()

    report = await OperationalReportService.productivity(
        db_session, test_clinic.id, date(2026, 1, 1), date(2026, 12, 31)
    )
    assert _pipeline(report) == {live_a.status: 1, "completed": 1}

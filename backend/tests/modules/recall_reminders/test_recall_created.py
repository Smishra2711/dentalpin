"""recall_reminders: RECALL_CREATED -> notification enqueue.

Covers the module's only real behavior: when a recall is created, the
handler enqueues a reminder via NotificationGateway, scoped to the
correct clinic, and does nothing for any other clinic's data.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.notifications.models import CommunicationMessage, NotificationTemplate
from app.modules.patients.models import Patient
from app.modules.recall_reminders.handlers import _on_recall_created


@pytest.mark.asyncio
async def test_recall_created_enqueues_reminder_for_correct_clinic_only(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
):
    db_session.add(
        NotificationTemplate(
            clinic_id=test_clinic.id,
            channel="email",
            template_key="recall_reminder",
            locale="en",
            subject="Recall due",
            body_html="Hi {{ patient_first_name }}, you're due for a recall.",
        )
    )
    await db_session.commit()

    other_clinic = Clinic(
        id=uuid4(), name="Other Clinic", tax_id="B99999999", address={}, settings={}
    )
    db_session.add(other_clinic)
    await db_session.commit()

    await _on_recall_created(
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
            "recall_id": str(uuid4()),
            "reason": "6-month checkup",
            "due_month": "2026-09",
        }
    )

    rows = (
        (
            await db_session.execute(
                select(CommunicationMessage).where(
                    CommunicationMessage.clinic_id == test_clinic.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].patient_id == test_patient.id

    other_rows = (
        (
            await db_session.execute(
                select(CommunicationMessage).where(
                    CommunicationMessage.clinic_id == other_clinic.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert other_rows == []


@pytest.mark.asyncio
async def test_recall_created_is_idempotent_on_dedup_key(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """Same recall_id firing twice (e.g. a redelivered event) must not
    enqueue two reminders — the handler always sets dedup_key from
    recall_id specifically to guard against this."""
    db_session.add(
        NotificationTemplate(
            clinic_id=test_clinic.id,
            channel="email",
            template_key="recall_reminder",
            locale="en",
            subject="Recall due",
            body_html="Hi {{ patient_first_name }}.",
        )
    )
    await db_session.commit()

    recall_id = str(uuid4())
    payload = {
        "clinic_id": str(test_clinic.id),
        "patient_id": str(test_patient.id),
        "recall_id": recall_id,
        "reason": "6-month checkup",
        "due_month": "2026-09",
    }

    await _on_recall_created(payload)
    await _on_recall_created(payload)

    rows = (
        (
            await db_session.execute(
                select(CommunicationMessage).where(
                    CommunicationMessage.clinic_id == test_clinic.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1

"""GDPR erasure fan-out: recalls clear contact-attempt notes (#546).

A contact-attempt note records what was dialled and can carry the erased
contact. The recall itself and its clinical ``reason_note`` are treatment
history and stay.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.patients.models import Patient
from app.modules.recalls.events import on_gdpr_erasure_executed
from app.modules.recalls.models import Recall, RecallContactAttempt


@pytest_asyncio.fixture
async def staff_id(db_session: AsyncSession) -> str:
    """``recall_contact_attempts.attempted_by`` is a NOT NULL FK to users."""
    from app.core.auth.service import hash_password

    staff = User(
        email=f"staff-{uuid4().hex[:8]}@test.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Ada",
        last_name="Lovelace",
    )
    db_session.add(staff)
    await db_session.flush()
    return str(staff.id)


async def _recall_with_attempt(
    db: AsyncSession, *, clinic_id, patient_id, attempted_by, note: str, channel: str = "phone"
):
    recall = Recall(
        clinic_id=clinic_id,
        patient_id=patient_id,
        due_month=date(2026, 6, 1),
        reason="hygiene",
        reason_note="Paciente prefiere tardes",
        status="contacted_no_answer",
    )
    db.add(recall)
    await db.commit()
    attempt = RecallContactAttempt(
        clinic_id=clinic_id,
        recall_id=recall.id,
        attempted_by=attempted_by,
        channel=channel,
        outcome="no_answer",
        note=note,
    )
    db.add(attempt)
    await db.commit()
    return recall, attempt


@pytest.mark.asyncio
async def test_contact_erasure_clears_attempt_notes_but_keeps_recall(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, staff_id: str
):
    recall, attempt = await _recall_with_attempt(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        attempted_by=staff_id,
        note="Llamado al +34666123456, sin respuesta",
    )

    await on_gdpr_erasure_executed(
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
            "erased_categories": ["phone"],
        },
        db=db_session,
    )
    await db_session.commit()

    assert attempt.note is None
    # Recall + its clinical reason_note are retained (treatment history).
    assert recall.reason_note == "Paciente prefiere tardes"
    assert recall.status == "contacted_no_answer"


@pytest.mark.asyncio
async def test_non_contact_erasure_leaves_attempt_notes(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, staff_id: str
):
    _, attempt = await _recall_with_attempt(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        attempted_by=staff_id,
        note="Llamado, sin respuesta",
    )

    await on_gdpr_erasure_executed(
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
            "erased_categories": ["identity"],
        },
        db=db_session,
    )
    await db_session.commit()

    assert attempt.note == "Llamado, sin respuesta"


@pytest.mark.asyncio
async def test_erasure_does_not_touch_another_patients_attempts(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, staff_id: str
):
    other = Patient(
        clinic_id=test_clinic.id,
        first_name="Otro",
        last_name="Paciente",
        phone="+34666000000",
    )
    db_session.add(other)
    await db_session.commit()
    _, other_attempt = await _recall_with_attempt(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=other.id,
        attempted_by=staff_id,
        note="Llamado al +34666000000",
    )
    _, mine = await _recall_with_attempt(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        attempted_by=staff_id,
        note="Mi nota",
    )

    await on_gdpr_erasure_executed(
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
            "erased_categories": ["phone"],
        },
        db=db_session,
    )
    await db_session.commit()

    assert other_attempt.note == "Llamado al +34666000000"
    assert mine.note is None


@pytest.mark.asyncio
async def test_email_erasure_keeps_phone_attempt_notes(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient, staff_id: str
):
    # Notes are cleared per channel: an email-only erasure must not discard a
    # note that records a phone call (#546).
    email_recall, email_attempt = await _recall_with_attempt(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        attempted_by=staff_id,
        note="Correo enviado",
        channel="email",
    )
    phone_recall, phone_attempt = await _recall_with_attempt(
        db_session,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        attempted_by=staff_id,
        note="Llamado al +34666123456",
        channel="phone",
    )

    await on_gdpr_erasure_executed(
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(test_patient.id),
            "erased_categories": ["email"],
        },
        db=db_session,
    )
    await db_session.commit()

    assert email_attempt.note is None
    assert phone_attempt.note == "Llamado al +34666123456"

"""patient_admin: tenant isolation on relationship lookups.

Covers the get_relationship hardening: a relationship_id from another
clinic must not be loadable, even by direct service call (previously
only the router's patient_id-match check enforced this — see
CHANGELOG.md for why that was fragile rather than actually broken).
Also covers the ordinary happy path: create + list a relationship
within one clinic.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patient_admin.service import PatientAdminService
from app.modules.patients.models import Patient


@pytest.mark.asyncio
async def test_create_and_list_relationship_happy_path(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    other_patient = Patient(clinic_id=test_clinic.id, first_name="Sibling", last_name="Patient")
    db_session.add(other_patient)
    await db_session.commit()

    await PatientAdminService.create_relationship(
        db_session,
        test_clinic.id,
        test_patient.id,
        {"related_patient_id": other_patient.id, "relationship_type": "sibling"},
    )
    await db_session.commit()

    rows = await PatientAdminService.list_relationships_for_patient(
        db_session, test_clinic.id, test_patient.id
    )
    assert len(rows) == 1
    assert rows[0]["related_patient_id"] == other_patient.id
    assert rows[0]["relationship_type"] == "sibling"


@pytest.mark.asyncio
async def test_get_relationship_is_clinic_scoped(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    other_clinic = Clinic(
        id=uuid4(), name="Other Clinic", tax_id="B88888888", address={}, settings={}
    )
    db_session.add(other_clinic)
    other_patient_a = Patient(clinic_id=other_clinic.id, first_name="Other", last_name="PatientA")
    other_patient_b = Patient(clinic_id=other_clinic.id, first_name="Other", last_name="PatientB")
    db_session.add_all([other_patient_a, other_patient_b])
    await db_session.commit()

    other_clinics_relationship = await PatientAdminService.create_relationship(
        db_session,
        other_clinic.id,
        other_patient_a.id,
        {"related_patient_id": other_patient_b.id, "relationship_type": "sibling"},
    )
    await db_session.commit()

    # test_clinic must not be able to load a relationship that belongs
    # to a different clinic, even with a valid relationship_id.
    result = await PatientAdminService.get_relationship(
        db_session, test_clinic.id, other_clinics_relationship.id
    )
    assert result is None

    # other_clinic can still load its own relationship.
    result = await PatientAdminService.get_relationship(
        db_session, other_clinic.id, other_clinics_relationship.id
    )
    assert result is not None
    assert result.id == other_clinics_relationship.id

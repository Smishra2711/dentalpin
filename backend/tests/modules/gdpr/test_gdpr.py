"""gdpr: DSR lifecycle, consents, erasure, breaches and tenant isolation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.gdpr.schemas import (
    ConsentCreate,
    DataBreachCreate,
    DataBreachUpdate,
    GdprRequestCreate,
    GdprRequestUpdate,
    RetentionPolicyCreate,
)
from app.modules.gdpr.service import (
    ConsentService,
    DataBreachService,
    ErasureService,
    ExportService,
    GdprService,
    RetentionService,
    SlaCalculator,
)
from app.modules.gdpr.tools import _record_consent
from app.modules.patients.models import Patient


@pytest.fixture
def erasure_contributors():
    """Mirror boot: collect the real contributors into the global registry.

    The loader only runs in app boot, so tests register explicitly. Always
    cleared afterwards so contributor state never leaks between tests.
    """
    from app.core.erasure.registry import erasure_registry
    from app.modules.billing import BillingModule
    from app.modules.budget import BudgetModule
    from app.modules.clinical_notes import ClinicalNotesModule
    from app.modules.documents import DocumentsModule
    from app.modules.media import MediaModule
    from app.modules.notifications import NotificationsModule
    from app.modules.patient_timeline import PatientTimelineModule
    from app.modules.recalls import RecallsModule

    erasure_registry.clear()
    for module in (
        BillingModule(),
        BudgetModule(),
        ClinicalNotesModule(),
        DocumentsModule(),
        MediaModule(),
        NotificationsModule(),
        PatientTimelineModule(),
        RecallsModule(),
    ):
        erasure_registry.register_from(module)
    yield
    erasure_registry.clear()


def _make_patient(db, clinic_id, **kw) -> Patient:
    p = Patient(
        clinic_id=clinic_id,
        first_name=kw.pop("first_name", "Test"),
        last_name=kw.pop("last_name", "Patient"),
        email=kw.pop("email", "patient@test.com"),
        phone=kw.pop("phone", "+34666123456"),
        national_id=kw.pop("national_id", "12345678A"),
        **kw,
    )
    db.add(p)
    return p


@pytest.mark.asyncio
async def test_dsr_create_sets_30_day_sla(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    row = await GdprService.create_request(
        db_session,
        test_clinic.id,
        GdprRequestCreate(
            patient_id=test_patient.id,
            requester_name="Test Patient",
            requester_email="patient@test.com",
            request_type="access",
        ),
    )
    assert row.status == "received"
    assert row.request_type == "access"
    assert (row.deadline_at - row.received_at).days == 30

    sla = SlaCalculator.deadline_from(row.received_at)
    assert row.deadline_at == sla

    fetched = await GdprService.get_request(db_session, test_clinic.id, row.id)
    assert fetched is not None
    assert fetched.id == row.id


@pytest.mark.asyncio
async def test_dsr_status_transition_completes(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    row = await GdprService.create_request(
        db_session,
        test_clinic.id,
        GdprRequestCreate(
            requester_name="Test Patient",
            requester_email="patient@test.com",
            request_type="erasure",
        ),
    )
    assert row.resolved_at is None

    updated = await GdprService.update_request(
        db_session, row, GdprRequestUpdate(status="completed")
    )
    assert updated.status == "completed"
    assert updated.resolved_at is not None


@pytest.mark.asyncio
async def test_consent_grant_withdraw_regrant_keeps_full_trail(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id)
    out = await _record_consent(
        ctx,
        type(
            "args",
            (),
            {
                "patient_id": str(test_patient.id),
                "purpose": "sms",
                "granted": True,
                "provided_text": "I accept receiving SMS.",
            },
        )(),
    )
    assert "error" not in out
    assert out["granted"] is True
    assert out["withdrawn_at"] is None

    items, total = await ConsentService.list_consents(
        db_session, test_clinic.id, patient_id=test_patient.id
    )
    assert total == 1
    assert items[0].granted is True
    assert items[0].purpose == "sms"

    # Withdraw appends a row; re-grant appends another — the withdrawal
    # event is never lost (append-only trail, latest first).
    await ConsentService.grant_or_withdraw(
        db_session,
        test_clinic.id,
        ConsentCreate(patient_id=test_patient.id, purpose="sms", granted=False),
    )
    await ConsentService.grant_or_withdraw(
        db_session,
        test_clinic.id,
        ConsentCreate(patient_id=test_patient.id, purpose="sms", granted=True),
    )
    items, total = await ConsentService.list_consents(
        db_session, test_clinic.id, patient_id=test_patient.id
    )
    assert total == 3
    assert items[0].granted is True
    assert items[0].withdrawn_at is None
    withdrawals = [c for c in items if not c.granted]
    assert len(withdrawals) == 1
    assert withdrawals[0].withdrawn_at is not None


@pytest.mark.asyncio
async def test_partial_erasure_blanks_identity_and_never_hard_deletes(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    erasure_contributors: None,
):
    # No retention policy → conservative default retains everything.
    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )

    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=test_patient.id,
        categories=["email"],
        rationale="Art.17 erasure request",
    )
    assert result.erased_categories == ["email"]
    assert result.retained_categories == []
    # The result records a per-scope coverage report (#546): a completed
    # run must never read as full DSR coverage.
    coverage = {c.scope: c.status for c in result.coverage}
    assert coverage["patient_record"] == "erased"
    assert coverage["notifications"] == "erased"
    assert coverage["recalls"] == "erased"
    # Retention scopes: every one of these holds an email copy, so an
    # email run reports what each of them keeps (#657).
    assert coverage["patient_timeline"] == "retained"
    assert coverage["budget"] == "retained"
    assert coverage["billing"] == "retained"
    assert coverage["clinical_notes"] == "retained"
    assert coverage["documents"] == "retained"
    assert coverage["media"] == "retained"
    assert set(coverage) == {
        "patient_record",
        "notifications",
        "recalls",
        "patient_timeline",
        "budget",
        "billing",
        "clinical_notes",
        "documents",
        "media",
    }

    # Row still exists (never hard-deleted).
    from sqlalchemy import select as sel

    patient = (
        await db_session.execute(
            sel(Patient).where(Patient.id == test_patient.id, Patient.clinic_id == test_clinic.id)
        )
    ).scalar_one_or_none()
    assert patient is not None
    assert patient.email is None  # identity blanked
    assert patient.first_name == "Test"  # retained: name is not a mapped erasure field

    # Audit log written.
    logs, _ = await ErasureService.list_audit(db_session, test_clinic.id)
    assert logs[0].erased_categories == ["email"]
    assert logs[0].patient_id == test_patient.id


@pytest.mark.asyncio
async def test_erasure_retained_when_retention_holds(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    erasure_contributors: None,
):
    # "clinical" has no field mapping, so it always retains (nothing to
    # blank) — the closed erasure vocabulary is email|phone|identity.
    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="clinical", retention_years=5),
    )
    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=test_patient.id,
        categories=["clinical"],
        rationale="Art.17",
    )
    assert result.erased_categories == []
    assert result.retained_categories == ["clinical"]
    # Nothing was erased, so every scope reports what it kept (#546).
    coverage = {c.scope: c.status for c in result.coverage}
    assert coverage["patient_record"] == "retained"
    # "clinical" is outside the closed vocabulary, so no scope holds a copy
    # of it: every contributor reports not_applicable rather than claiming
    # to retain something this run never looked at (#657).
    assert coverage["notifications"] == "not_applicable"
    assert coverage["patient_timeline"] == "not_applicable"
    assert coverage["budget"] == "not_applicable"
    assert coverage["billing"] == "not_applicable"
    assert coverage["clinical_notes"] == "not_applicable"
    assert coverage["documents"] == "not_applicable"
    assert coverage["media"] == "not_applicable"

    patient = (
        await db_session.execute(
            select(Patient).where(
                Patient.id == test_patient.id, Patient.clinic_id == test_clinic.id
            )
        )
    ).scalar_one_or_none()
    assert patient.email is not None  # not blanked


@pytest.mark.asyncio
async def test_erasure_omits_scope_without_contributor(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    # ADR 0038 honesty: a scope with no registered contributor produces no
    # row. Uninstall recalls and the DSR must NOT report recalls: erased.
    from app.core.erasure.registry import erasure_registry
    from app.modules.notifications import NotificationsModule

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    erasure_registry.clear()
    try:
        erasure_registry.register_from(NotificationsModule())
        result = await ErasureService.execute(
            db_session,
            test_clinic.id,
            patient_id=test_patient.id,
            categories=["email"],
            rationale="Art.17 erasure request",
        )
        coverage = {c.scope: c.status for c in result.coverage}
        assert coverage["notifications"] == "erased"
        assert "recalls" not in coverage
    finally:
        erasure_registry.clear()


@pytest.mark.asyncio
async def test_announcement_failure_does_not_fail_erasure(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    erasure_contributors: None,
):
    # The post-commit announcement must not fail the committed erasure:
    # a subscriber declaring db raises inside publish (bus rule), after
    # the audit log is already durable.
    from app.core.events import EventType, event_bus

    async def _db_subscriber(data, *, db):
        raise AssertionError("announcement must not run in-transaction")

    announced: list[dict] = []

    async def _recorder(data):
        announced.append(data)

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    # Subscribe the recorder first: the bus aborts the loop on the
    # db-subscriber's RuntimeError, so ordering decides what is recorded.
    event_bus.subscribe(EventType.GDPR_ERASURE_EXECUTED, _recorder)
    event_bus.subscribe(EventType.GDPR_ERASURE_EXECUTED, _db_subscriber)
    try:
        result = await ErasureService.execute(
            db_session,
            test_clinic.id,
            patient_id=test_patient.id,
            categories=["email"],
            rationale="Art.17 erasure request",
        )
    finally:
        event_bus.unsubscribe(EventType.GDPR_ERASURE_EXECUTED, _db_subscriber)
        event_bus.unsubscribe(EventType.GDPR_ERASURE_EXECUTED, _recorder)
    assert result is not None
    assert result.erased_categories == ["email"]
    coverage = {c.scope: c.status for c in result.coverage}
    assert coverage["notifications"] == "erased"
    # The announcement still went out (to the non-transactional subscriber)
    # even though the db-subscriber raised.
    assert [a["patient_id"] for a in announced] == [str(test_patient.id)]


@pytest.mark.asyncio
async def test_breach_create_and_report(db_session: AsyncSession, test_clinic: Clinic):
    row = await DataBreachService.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Backup exposed",
            data_involved=["patients", "billing"],
            affected_people=10,
        ),
    )
    assert row.status == "under_review"
    assert row.reported is False

    updated = await DataBreachService.update(
        db_session,
        row,
        DataBreachUpdate(status="reported"),
    )
    assert updated.status == "reported"
    assert updated.reported is True
    assert updated.notified_authority_at is not None


@pytest.mark.asyncio
async def test_export_returns_patient_data(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await GdprService.create_request(
        db_session,
        test_clinic.id,
        GdprRequestCreate(requester_name="P", requester_email="p@test.com", request_type="access"),
    )
    data = await ExportService.export(db_session, test_clinic.id, test_patient.id)
    assert data["identity"]["email"] == "patient@test.com"
    assert data["identity"]["first_name"] == "Test"
    assert isinstance(data["consents"], list)


@pytest.mark.asyncio
async def test_cross_clinic_isolation(db_session: AsyncSession, test_clinic: Clinic):
    from uuid import uuid4

    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()

    p_other = _make_patient(db_session, other.id)
    db_session.add(p_other)
    await db_session.flush()

    await GdprService.create_request(
        db_session,
        other.id,
        GdprRequestCreate(
            requester_name="Other", requester_email="o@test.com", request_type="access"
        ),
    )

    # A request created in clinic A must not be listable in clinic B.
    items, total = await GdprService.list_requests(db_session, test_clinic.id)
    assert total == 0

    # Export for a patient of clinic B queried under clinic A returns empty.
    data = await ExportService.export(db_session, test_clinic.id, p_other.id)
    assert data == {}


@pytest.mark.asyncio
async def test_erasure_unknown_patient_returns_none_and_writes_no_audit(
    db_session: AsyncSession, test_clinic: Clinic
):
    from uuid import uuid4

    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=uuid4(),
        categories=["email"],
        rationale="Art.17",
    )
    assert result is None
    logs, total = await ErasureService.list_audit(db_session, test_clinic.id)
    assert total == 0


@pytest.mark.asyncio
async def test_erasure_other_clinic_patient_returns_none(
    db_session: AsyncSession, test_clinic: Clinic
):
    from uuid import uuid4

    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999992",
        address={"street": "Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()
    p_other = _make_patient(db_session, other.id)
    await db_session.flush()

    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=p_other.id,
        categories=["email"],
        rationale="Art.17",
    )
    assert result is None


@pytest.mark.asyncio
async def test_erasure_rejects_unknown_category():
    from pydantic import ValidationError

    from app.modules.gdpr.schemas import ErasureRequest

    with pytest.raises(ValidationError):
        ErasureRequest(patient_id="12345678-1234-5678-1234-567812345678", categories=["clinical"])


@pytest.mark.asyncio
async def test_erasure_retention_window_uses_patient_updated_at_anchor(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update as sa_update

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="phone", retention_years=1),
    )
    # Fresh patient → 1-year window not passed → retained.
    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=test_patient.id,
        categories=["phone"],
        rationale="Art.17",
    )
    assert result is not None
    assert result.erased_categories == []
    assert result.retained_categories == ["phone"]

    # Backdate updated_at past the window (direct SQL skips the onupdate
    # bump) → erasable.
    old = datetime.now(UTC) - timedelta(days=400)
    await db_session.execute(
        sa_update(Patient).where(Patient.id == test_patient.id).values(updated_at=old)
    )
    await db_session.commit()
    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=test_patient.id,
        categories=["phone"],
        rationale="Art.17",
    )
    assert result is not None
    assert result.erased_categories == ["phone"]


@pytest.mark.asyncio
async def test_execute_erasure_tool_reports_missing_patient(
    db_session: AsyncSession, test_clinic: Clinic
):
    from uuid import uuid4

    from app.modules.gdpr.tools import _execute_erasure

    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id, agent_id=uuid4())
    out = await _execute_erasure(
        ctx,
        type(
            "args",
            (),
            {"patient_id": str(uuid4()), "categories": ["email"], "rationale": None},
        )(),
    )
    assert out == {"error": "patient not found"}

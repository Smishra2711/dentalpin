"""Tests for the GDPR erasure registry and contributor contract (ADR 0038, #546)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.erasure.registry import (
    ErasureRegistryError,
    SubjectErasureRegistry,
    erasure_registry,
)
from app.core.erasure.types import ErasureContributor, ErasureCoverage
from app.core.plugins.base import BaseModule
from app.modules.patients.models import Patient


class _StubContributor(ErasureContributor):
    def __init__(self, scope: str):
        self._scope = scope

    @property
    def scope(self) -> str:
        return self._scope

    async def erase(
        self,
        clinic_id: UUID,
        patient_id: UUID,
        erased: list[str],
        retained: list[str],
        db: AsyncSession,
    ) -> ErasureCoverage:
        return ErasureCoverage(scope=self._scope, status="erased", detail="stub")


class _FixtureModule(BaseModule):
    """Throwaway module used only in tests."""

    manifest = {
        "name": "fixture_erasure",
        "version": "0.0.1",
        "summary": "Throwaway fixture.",
        "category": "official",
        "installable": True,
        "auto_install": True,
        "removable": True,
    }

    def __init__(self, contributors: list | None = None):
        self._contributors = contributors or []

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_erasure_contributors(self) -> list:
        return self._contributors


def test_contributor_contract_is_abstract():
    with pytest.raises(TypeError):
        ErasureContributor()  # type: ignore[abstract]


def test_register_from_collects_scopes_sorted():
    registry = SubjectErasureRegistry()
    registry.register_from(_FixtureModule([_StubContributor("b"), _StubContributor("a")]))
    assert registry.scopes() == ["a", "b"]
    assert [c.scope for c in registry.contributors()] == ["a", "b"]


def test_duplicate_scope_raises():
    registry = SubjectErasureRegistry()
    registry.register_from(_FixtureModule([_StubContributor("a")]))
    with pytest.raises(ErasureRegistryError):
        registry.register_from(_FixtureModule([_StubContributor("a")]))


def test_unregister_module_drops_only_its_scopes():
    registry = SubjectErasureRegistry()
    registry.register_from(_FixtureModule([_StubContributor("a")]))
    other = SimpleNamespace(name="other", get_erasure_contributors=lambda: [_StubContributor("b")])
    registry.register_from(other)
    registry.unregister_module("fixture_erasure")
    assert registry.scopes() == ["b"]


def test_clear_resets():
    registry = SubjectErasureRegistry()
    registry.register_from(_FixtureModule([_StubContributor("a")]))
    registry.clear()
    assert registry.scopes() == []
    assert registry.get("a") is None


def test_global_registry_collects_real_modules():
    from app.modules.notifications import NotificationsModule
    from app.modules.recalls import RecallsModule

    erasure_registry.clear()
    try:
        erasure_registry.register_from(NotificationsModule())
        erasure_registry.register_from(RecallsModule())
        assert erasure_registry.scopes() == ["notifications", "recalls"]
    finally:
        erasure_registry.clear()


@pytest.mark.asyncio
async def test_raising_contributor_rolls_back_erasure(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    from app.modules.gdpr.schemas import RetentionPolicyCreate
    from app.modules.gdpr.service import ErasureService, RetentionService

    class _Boom(ErasureContributor):
        @property
        def scope(self) -> str:
            return "boom"

        async def erase(self, clinic_id, patient_id, erased, retained, db):
            raise RuntimeError("contributor failed")

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    # Capture plain ids first: the rollback below expires every ORM object
    # the session has loaded, so attribute access afterwards is MissingGreenlet.
    clinic_id = test_clinic.id
    patient_id = test_patient.id
    erasure_registry.clear()
    try:
        erasure_registry.register_from(_FixtureModule([_Boom()]))
        with pytest.raises(RuntimeError, match="contributor failed"):
            await ErasureService.execute(
                db_session,
                clinic_id,
                patient_id=patient_id,
                categories=["email"],
                rationale="Art.17",
            )
    finally:
        erasure_registry.clear()

    # Nothing committed: patient blanks and the audit log rolled back together.
    await db_session.rollback()
    patient = (
        await db_session.execute(
            select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    assert patient is not None
    assert patient.email is not None
    logs, _ = await ErasureService.list_audit(db_session, clinic_id)
    assert logs == []

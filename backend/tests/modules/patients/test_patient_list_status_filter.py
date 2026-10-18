"""patients list: the ``status`` filter selects exactly what was asked for (#473).

Before this, the endpoint only had ``include_archived``, a boolean that
could say "active" or "active *and* archived" but never "archived
alone". The UI's Archived chip therefore returned active patients too.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient


@pytest.fixture
async def mixed_patients(db_session: AsyncSession, test_clinic: Clinic) -> dict[str, Patient]:
    """One active and one archived patient in the same clinic."""
    active = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Ana",
        last_name="Activa",
        status="active",
    )
    archived = Patient(
        id=uuid4(),
        clinic_id=test_clinic.id,
        first_name="Arturo",
        last_name="Archivado",
        status="archived",
    )
    db_session.add_all([active, archived])
    await db_session.commit()
    return {"active": active, "archived": archived}


async def _list(client: AsyncClient, headers: dict, query: str = "") -> list[dict]:
    response = await client.get(f"/api/v1/patients?{query}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_status_archived_returns_archived_only(
    client: AsyncClient, auth_headers: dict, mixed_patients: dict[str, Patient]
) -> None:
    """The bug: asking for archived used to hand back the active ones too."""
    rows = await _list(client, auth_headers, "status=archived")

    ids = {row["id"] for row in rows}
    assert str(mixed_patients["archived"].id) in ids
    assert str(mixed_patients["active"].id) not in ids
    assert {row["status"] for row in rows} == {"archived"}


@pytest.mark.asyncio
async def test_status_active_returns_active_only(
    client: AsyncClient, auth_headers: dict, mixed_patients: dict[str, Patient]
) -> None:
    rows = await _list(client, auth_headers, "status=active")

    ids = {row["id"] for row in rows}
    assert str(mixed_patients["active"].id) in ids
    assert str(mixed_patients["archived"].id) not in ids


@pytest.mark.asyncio
async def test_repeated_status_unions_the_two(
    client: AsyncClient, auth_headers: dict, mixed_patients: dict[str, Patient]
) -> None:
    """Both chips selected → both kinds, which is what the UI sends."""
    rows = await _list(client, auth_headers, "status=active&status=archived")

    ids = {row["id"] for row in rows}
    assert str(mixed_patients["active"].id) in ids
    assert str(mixed_patients["archived"].id) in ids


@pytest.mark.asyncio
async def test_status_wins_over_include_archived(
    client: AsyncClient, auth_headers: dict, mixed_patients: dict[str, Patient]
) -> None:
    """An explicit list is exact; the older boolean must not widen it back."""
    rows = await _list(client, auth_headers, "status=archived&include_archived=false")

    ids = {row["id"] for row in rows}
    assert str(mixed_patients["archived"].id) in ids
    assert str(mixed_patients["active"].id) not in ids


@pytest.mark.asyncio
async def test_no_status_keeps_the_old_default(
    client: AsyncClient, auth_headers: dict, mixed_patients: dict[str, Patient]
) -> None:
    """Existing callers that send nothing still get active patients only."""
    rows = await _list(client, auth_headers)

    ids = {row["id"] for row in rows}
    assert str(mixed_patients["active"].id) in ids
    assert str(mixed_patients["archived"].id) not in ids


@pytest.mark.asyncio
async def test_no_status_with_include_archived_still_widens(
    client: AsyncClient, auth_headers: dict, mixed_patients: dict[str, Patient]
) -> None:
    """The cleared-filter case the first half of #473 fixed, unchanged."""
    rows = await _list(client, auth_headers, "include_archived=true")

    ids = {row["id"] for row in rows}
    assert str(mixed_patients["active"].id) in ids
    assert str(mixed_patients["archived"].id) in ids


@pytest.mark.asyncio
async def test_blank_status_value_is_ignored(
    client: AsyncClient, auth_headers: dict, mixed_patients: dict[str, Patient]
) -> None:
    """``?status=`` is an empty selection, not a filter on the empty string."""
    rows = await _list(client, auth_headers, "status=")

    ids = {row["id"] for row in rows}
    assert str(mixed_patients["active"].id) in ids
    assert str(mixed_patients["archived"].id) not in ids

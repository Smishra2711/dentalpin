"""HTTP coverage for the documents module (CRUD + generate + journal)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.activity_journal.models import ActivityJournalEntry


@pytest.mark.asyncio
async def test_document_crud_and_generate_flow(
    client, auth_headers, test_clinic: Clinic, test_patient
) -> None:
    """Create → get → patch → filter → generate → soft-delete."""
    patient_id = str(test_patient.id)

    response = await client.get("/api/v1/documents", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["data"] == []

    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "document_type": "prescription",
            "title": "Amoxicillin Rx",
            "content": {"diagnosis": "stomatitis", "medications": []},
        },
    )
    assert response.status_code == 201
    doc = response.json()["data"]
    assert doc["status"] == "draft"
    assert doc["created_by"] is not None
    assert doc["document_type"] == "prescription"
    doc_id = doc["id"]

    response = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == doc_id

    response = await client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers,
        json={"title": "Amoxicillin 500mg"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Amoxicillin 500mg"

    response = await client.get(
        "/api/v1/documents?document_type=prescription", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = await client.post(
        "/api/v1/documents/generate", headers=auth_headers, json={"document_id": doc_id}
    )
    assert response.status_code == 200
    generated = response.json()["data"]
    assert generated["status"] == "generated"
    assert generated["file_path"].endswith(".pdf")

    response = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 204
    response = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "archived"

    from uuid import uuid4

    response = await client.get(f"/api/v1/documents/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_writes_activity_journal_row(
    client, auth_headers, test_clinic: Clinic, test_patient, db_session: AsyncSession
) -> None:
    """``document.generated`` is published transactionally and the
    activity_journal subscription records an attributed row."""
    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
        json={
            "patient_id": str(test_patient.id),
            "document_type": "referral",
            "title": "Referred to ortho",
            "content": {"referred_to": "Dr. Ortho", "specialty": "orthodontics"},
        },
    )
    assert response.status_code == 201
    doc_id = response.json()["data"]["id"]

    response = await client.post(
        "/api/v1/documents/generate", headers=auth_headers, json={"document_id": doc_id}
    )
    assert response.status_code == 200

    stmt = select(ActivityJournalEntry).where(
        ActivityJournalEntry.clinic_id == test_clinic.id,
        ActivityJournalEntry.event_type == "document.generated",
    )
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1
    entry = rows[0]
    assert entry.source_table == "document"
    assert str(entry.source_entity_id) == doc_id
    assert entry.actor_id is not None
    assert entry.payload["title"] == "Referred to ortho"

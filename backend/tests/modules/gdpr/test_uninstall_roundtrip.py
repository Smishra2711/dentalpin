"""gdpr round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the gdpr tables and leave
every other module untouched. The module owns two revisions
(gdpr_0001, gdpr_0002), so the branch-scoped downgrade target is ``gdpr@-2``.
Marked ``alembic_roundtrip`` and excluded from the default pytest run.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

GDPR_TABLES = {
    "gdpr_requests",
    "patient_consents",
    "retention_policies",
    "gdpr_erasure_audit_logs",
    "data_breaches",
}


def _alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=BACKEND_ROOT,
        check=True,
    )


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _list_tables_async() -> set[str]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
        return {row["table_name"] for row in rows}
    finally:
        await conn.close()


def _list_tables() -> set[str]:
    return asyncio.run(_list_tables_async())


def test_gdpr_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert GDPR_TABLES.issubset(before), "gdpr tables missing after upgrade"

    _alembic("downgrade", "gdpr@-2")
    after_down = _list_tables()
    assert GDPR_TABLES.isdisjoint(after_down), "gdpr tables still present after downgrade"

    other_tables = before - GDPR_TABLES
    assert other_tables.issubset(after_down), "downgrade leaked beyond gdpr branch"

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert GDPR_TABLES.issubset(after_up), "gdpr tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"


async def _fetch_async(query: str, *args) -> list:
    conn = await asyncpg.connect(_dsn())
    try:
        return await conn.fetch(query, *args)
    finally:
        await conn.close()


async def _execute_async(query: str, *args) -> None:
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute(query, *args)
    finally:
        await conn.close()


def test_gdpr_0002_reconciles_duplicate_actives() -> None:
    """gdpr_0002's UPDATE must collapse pre-existing duplicate active
    policies (newest wins) before the partial unique index is created
    (#562 ADV-S1-01, advisory F1). Runs the real migration file against
    real duplicate rows — not the model metadata.
    """
    _alembic("upgrade", "heads")
    # Drop only the index so duplicates become insertable; tables and any
    # other data stay exactly as upgrade left them.
    _alembic("downgrade", "gdpr@-1")

    clinic_id = uuid.uuid4()
    other_clinic_id = uuid.uuid4()
    other_policy_id = uuid.uuid4()
    old_id, new_id = uuid.uuid4(), uuid.uuid4()
    old_stamp = datetime(2020, 1, 1, tzinfo=UTC)
    new_stamp = datetime.now(UTC)

    async def _setup() -> None:
        await _execute_async(
            "INSERT INTO clinics (id, name, tax_id, settings, created_at, updated_at) "
            "VALUES ($1, 'Mig Clinic', 'B00000002', '{}'::jsonb, now(), now())",
            clinic_id,
        )
        await _execute_async(
            "INSERT INTO clinics (id, name, tax_id, settings, created_at, updated_at) "
            "VALUES ($1, 'Other Mig Clinic', 'B00000003', '{}'::jsonb, now(), now())",
            other_clinic_id,
        )
        await _execute_async(
            "INSERT INTO retention_policies "
            "(id, clinic_id, data_category, retention_years, legal_hold_until, "
            "is_active, created_at, updated_at) "
            "VALUES ($1, $2, 'email', 5, NULL, true, $3, $3)",
            old_id,
            clinic_id,
            old_stamp,
        )
        await _execute_async(
            "INSERT INTO retention_policies "
            "(id, clinic_id, data_category, retention_years, legal_hold_until, "
            "is_active, created_at, updated_at) "
            "VALUES ($1, $2, 'email', 0, NULL, true, $3, $3)",
            new_id,
            clinic_id,
            new_stamp,
        )
        await _execute_async(
            "INSERT INTO retention_policies "
            "(id, clinic_id, data_category, retention_years, legal_hold_until, "
            "is_active, created_at, updated_at) "
            "VALUES ($1, $2, 'phone', 3, NULL, true, $3, $3)",
            other_policy_id,
            other_clinic_id,
            old_stamp,
        )

    async def _teardown() -> None:
        await _execute_async(
            "DELETE FROM retention_policies WHERE clinic_id = ANY($1::uuid[])",
            [clinic_id, other_clinic_id],
        )
        await _execute_async(
            "DELETE FROM clinics WHERE id = ANY($1::uuid[])", [clinic_id, other_clinic_id]
        )

    try:
        asyncio.run(_setup())
        _alembic("upgrade", "heads")
        rows = asyncio.run(
            _fetch_async(
                "SELECT id, is_active FROM retention_policies "
                "WHERE clinic_id = $1 AND data_category = 'email'",
                clinic_id,
            )
        )
        by_id = {r["id"]: r["is_active"] for r in rows}
        assert by_id == {old_id: False, new_id: True}
        # The other clinic's policy is untouched: the reconcile groups by
        # (clinic_id, data_category), never by category alone (#562 ADV-A3).
        other_rows = asyncio.run(
            _fetch_async(
                "SELECT id, is_active FROM retention_policies WHERE clinic_id = $1",
                other_clinic_id,
            )
        )
        assert [(r["id"], r["is_active"]) for r in other_rows] == [(other_policy_id, True)]
        # The backstop itself exists: deleting create_index from the
        # migration would leave this green, so pin it in pg_indexes.
        index_rows = asyncio.run(
            _fetch_async(
                "SELECT indexname FROM pg_indexes WHERE tablename = "
                "'retention_policies' AND indexname = "
                "'ix_retention_policies_clinic_category_active'"
            )
        )
        assert [r["indexname"] for r in index_rows] == [
            "ix_retention_policies_clinic_category_active"
        ]
    finally:
        asyncio.run(_teardown())

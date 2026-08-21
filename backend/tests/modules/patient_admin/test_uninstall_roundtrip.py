"""patient_admin round-trip uninstall test.

Mirrors recalls/schedules/whatsapp_kapso: install → uninstall → reinstall
must drop ONLY the patient_admin tables and leave every other module
untouched. The module owns two revisions (padm_0001, padm_0002), so the
branch-scoped downgrade target is ``patient_admin@-2`` — the same form
``_downgrade_target_for`` resolves for the real uninstall path. Marked
``alembic_roundtrip`` and excluded from the default pytest run.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import asyncpg
import pytest

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

# padm_0002 drops patient_admin_exemption_status again, so at heads the
# module owns exactly this one table.
PADM_TABLES = {"patient_admin_relationship"}


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


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


def test_patient_admin_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert PADM_TABLES.issubset(before), (
        f"expected patient_admin tables at heads; missing: {PADM_TABLES - before}"
    )
    baseline_other = before - PADM_TABLES

    _alembic("downgrade", "patient_admin@-2")
    after_down = _list_tables()
    assert PADM_TABLES.isdisjoint(after_down), (
        f"patient_admin tables survived downgrade: {PADM_TABLES & after_down}"
    )
    assert baseline_other <= after_down, (
        f"downgrade leaked into other modules; missing: {baseline_other - after_down}"
    )

    _alembic("upgrade", "patient_admin@head")
    after_up = _list_tables()
    assert before <= after_up, (
        f"reinstall did not restore every table; missing: {before - after_up}"
    )

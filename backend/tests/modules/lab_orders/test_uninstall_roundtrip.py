"""Branch-scoped uninstall/reinstall coverage for lab_orders."""

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
LAB_ORDER_TABLES = {"lab_orders"}


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _tables() -> set[str]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name != 'alembic_version'")
        return {row["table_name"] for row in rows}
    finally:
        await conn.close()


def test_lab_orders_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = asyncio.run(_tables())
    assert LAB_ORDER_TABLES.issubset(before)
    baseline = before - LAB_ORDER_TABLES

    _alembic("downgrade", "lab_orders@-2")
    after_down = asyncio.run(_tables())
    assert LAB_ORDER_TABLES.isdisjoint(after_down)
    assert baseline <= after_down

    _alembic("upgrade", "lab_orders@head")
    after_up = asyncio.run(_tables())
    assert before <= after_up

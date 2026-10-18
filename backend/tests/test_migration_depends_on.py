"""A cross-module FK must declare ``depends_on`` (#507).

Each module owns an Alembic branch. When a revision creates a foreign
key into a table another module owns, the two branches have to be
ordered, and ``depends_on`` is the only thing that says so — nothing
else makes Alembic run ``patients`` before a module that points at it.

``alembic upgrade heads`` happening to work today does not prove the
ordering is guaranteed rather than incidental, which is why this is a
test rather than a convention.

``LEGACY_WITHOUT_DEPENDS_ON`` freezes the revisions that predate the
rule. They are already applied in production databases, so editing
their ``depends_on`` is a separate and riskier decision than stopping
the list from growing. New revisions must not join it.
"""

from __future__ import annotations

import re
from pathlib import Path

MODULES_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules"

# Tables every branch may reference without declaring a dependency:
# they are created by the core revision chain, not by a module.
CORE_TABLES = {"clinics", "users"}

# Revisions that already shipped without ``depends_on``. Do not add to
# this list — fix the revision instead. Shrinking it is welcome when a
# module is being touched for another reason anyway.
# All but perio_0001 are ordered today anyway, by a down_revision threaded
# through another module's chain (the #56 anti-pattern); perio_0001
# (down_revision "0001", FKs patients) is the one with no ordering at all.
LEGACY_WITHOUT_DEPENDS_ON = {
    "ag_0001_initial.py",
    "bil_0001_initial.py",
    "bud_0001_initial.py",
    "med_0001_initial.py",
    "notif_0001_initial.py",
    "notif_0006_push_channel.py",
    "notif_0007_push_subscribe_tokens.py",
    "odo_0001_initial.py",
    "pay_0001_initial.py",
    "pc_0001_initial.py",
    "perio_0001_initial.py",
    "prel_0002_drop_exemption_status.py",
    "pt_0001_initial.py",
    "tp_0001_initial.py",
    "tp_0002_clinical_notes.py",
    "vfy_0004_vat_classifications.py",
}

_CREATE_TABLE = re.compile(r'op\.create_table\(\s*["\']([a-z_]+)["\']')
_FK_CONSTRAINT = re.compile(r'ForeignKeyConstraint\(\s*\[[^\]]+\],\s*\[["\']([a-z_]+)\.')
_FK_COLUMN = re.compile(r'ForeignKey\(\s*["\']([a-z_]+)\.')
# op.create_foreign_key(name, source_table, referent_table, ...)
_FK_OP = re.compile(r'op\.create_foreign_key\(\s*[^,]+,\s*["\'][a-z_]+["\'],\s*["\']([a-z_]+)["\']')
_DEPENDS_ON = re.compile(r"^depends_on[^=]*=\s*(.+)$", re.M)


def _revision_files() -> list[Path]:
    return sorted(MODULES_ROOT.glob("*/migrations/versions/*.py"))


def _table_owners() -> dict[str, str]:
    """Which module creates which table, across every revision."""
    owners: dict[str, str] = {}
    for path in _revision_files():
        module = path.parents[2].name
        for table in _CREATE_TABLE.findall(path.read_text()):
            owners.setdefault(table, module)
    return owners


def _cross_module_fk_targets(source: str, module: str, owners: dict[str, str]) -> set[str]:
    targets = (
        set(_FK_CONSTRAINT.findall(source))
        | set(_FK_COLUMN.findall(source))
        | set(_FK_OP.findall(source))
    )
    return {t for t in targets if t not in CORE_TABLES and owners.get(t, module) != module}


def test_every_cross_module_fk_declares_depends_on() -> None:
    owners = _table_owners()
    offenders: list[str] = []
    for path in _revision_files():
        source = path.read_text()
        if "branch_labels" not in source:
            continue
        if path.name in LEGACY_WITHOUT_DEPENDS_ON:
            continue
        targets = _cross_module_fk_targets(source, path.parents[2].name, owners)
        if not targets:
            continue
        declared = _DEPENDS_ON.search(source)
        if declared is None or declared.group(1).strip() == "None":
            offenders.append(f"{path.parents[2].name}/{path.name} -> {', '.join(sorted(targets))}")
    assert offenders == [], (
        "These revisions create a foreign key into another module's table without "
        "declaring depends_on, so nothing orders the two branches:\n  "
        + "\n  ".join(offenders)
        + '\nDeclare the revision this one must follow, e.g. depends_on = ("pat_0003",).'
    )


def test_the_legacy_allowlist_is_not_stale() -> None:
    """Every entry must still exist and still need the exemption.

    Otherwise the list quietly grants amnesty to revisions that were
    fixed, or to filenames that no longer exist.
    """
    owners = _table_owners()
    by_name = {p.name: p for p in _revision_files()}
    stale: list[str] = []
    for name in sorted(LEGACY_WITHOUT_DEPENDS_ON):
        path = by_name.get(name)
        if path is None:
            stale.append(f"{name}: no such revision any more")
            continue
        source = path.read_text()
        declared = _DEPENDS_ON.search(source)
        has_depends = declared is not None and declared.group(1).strip() != "None"
        targets = _cross_module_fk_targets(source, path.parents[2].name, owners)
        if has_depends or not targets:
            stale.append(f"{name}: no longer needs the exemption")
    assert stale == [], "Remove these from LEGACY_WITHOUT_DEPENDS_ON:\n  " + "\n  ".join(stale)

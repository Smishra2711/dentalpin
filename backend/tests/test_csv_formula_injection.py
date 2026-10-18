"""CSV exports must not hand a spreadsheet a live formula (#611).

Excel/LibreOffice/Sheets evaluate a cell starting with ``= + - @`` (or
tab/CR). CSV quoting does not prevent it — quoting is read by the CSV
parser, not the formula engine — so free-text cells are prefixed with an
apostrophe. Numbers must survive untouched: a credit note is a
legitimately negative amount and turning it into text would corrupt the
accountant's file.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.csv_safety import csv_cell, csv_row
from app.modules.accounting_export.service import _fmt


@pytest.mark.parametrize(
    "raw",
    [
        '=HYPERLINK("http://evil.example","click")',
        "+34600111222",
        "-2+3",
        "@SUM(1+1)",
        "\tlead-tab",
        "\rlead-cr",
    ],
)
def test_formula_leaders_are_neutralised(raw: str) -> None:
    out = csv_cell(raw)
    assert out == f"'{raw}"
    assert out[0] == "'"


@pytest.mark.parametrize("raw", ["Ana García", "", "revisión anual", "normal", "2026-10"])
def test_ordinary_text_is_untouched(raw: str) -> None:
    assert csv_cell(raw) == raw


def test_numbers_are_never_quoted() -> None:
    """The guard is type-aware so a credit note stays a number."""
    assert csv_cell(Decimal("-100.00")) == Decimal("-100.00")
    assert csv_cell(-5) == -5
    assert csv_cell(-1.5) == -1.5
    assert csv_cell(None) is None


def test_csv_row_mixes_both() -> None:
    row = ["=cmd", Decimal("-100.00"), 3, "Ana"]
    assert csv_row(row) == ["'=cmd", Decimal("-100.00"), 3, "Ana"]


def test_accounting_export_keeps_negative_amounts_numeric() -> None:
    """A credit note must not arrive as text in the accountant's file."""
    assert _fmt(Decimal("-100.00"), ",") == "-100.00"
    assert _fmt(Decimal("-100.00"), ";") == "-100,00"


def test_accounting_export_guards_free_text() -> None:
    assert _fmt('=HYPERLINK("http://evil","x")', ",") == '\'=HYPERLINK("http://evil","x")'
    assert _fmt("Clínica Ejemplo", ",") == "Clínica Ejemplo"
    assert _fmt(None, ",") == ""

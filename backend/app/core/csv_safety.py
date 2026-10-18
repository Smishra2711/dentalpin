"""Spreadsheet formula neutralisation for CSV exports (#611).

Excel, LibreOffice and Google Sheets evaluate a cell whose first
character is ``=``, ``+``, ``-``, ``@``, tab or CR. CSV quoting does not
help: it is read by the CSV parser, not by the formula engine, so
``"=HYPERLINK(...)"`` arrives as a live formula either way.

Our exports carry text people outside the clinic can write — a patient
name reaches the database through the public lead intake, and recall
notes and invoice descriptions are typed by staff — so every free-text
cell is prefixed with an apostrophe, which spreadsheets strip on display
and treat as "this is text".

Only ``str`` values are touched. Numbers stay numbers: a credit note's
``Decimal("-100.00")`` must not become text in the accountant's file,
which is why the guard is type-aware rather than applied to the rendered
string (the lesson ``india_gst`` wrote down when it solved this first,
in ``reports.py``).
"""

from __future__ import annotations

from typing import Any

_FORMULA_LEADERS = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value: Any) -> Any:
    """Return ``value`` safe to write into a spreadsheet-bound CSV."""
    if isinstance(value, str) and value[:1] in _FORMULA_LEADERS:
        return f"'{value}"
    return value


def csv_row(row: list[Any]) -> list[Any]:
    """``csv_cell`` over a whole row."""
    return [csv_cell(v) for v in row]

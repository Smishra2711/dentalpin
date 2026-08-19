"""Badge/filter severity for India GST invoices.

Writes into ``compliance_data['IN'].severity`` using billing's generic
``ok | warning | pending | error`` vocabulary (see
``verifactu/services/severity.py`` for the precedent) so billing's
existing ``compliance_severity`` list filter picks up GST invoices
without billing knowing anything India-specific.
"""

from __future__ import annotations

from typing import Literal

Severity = Literal["ok", "warning", "pending", "error"]


def severity_for(einvoice_state: str, *, has_sac_warning: bool) -> Severity:
    if einvoice_state in ("rejected", "error"):
        return "error"
    if einvoice_state == "pending":
        return "pending"
    if has_sac_warning:
        return "warning"
    return "ok"

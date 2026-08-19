"""India GST implementation of ``BillingComplianceHook``.

Wired in :func:`IndiaGstModule.__init__` (boot-time re-attach — the
in-memory ``BillingHookRegistry`` doesn't survive restarts) and
:func:`IndiaGstModule.install`. Billing discovers it through the
registry — no direct import in either direction.

Design notes (see the module ``CLAUDE.md`` for the full rationale):

* GSTIN has two owners: ``IndiaGstSettings.gstin`` (supplier / the
  clinic's own) and ``Invoice.billing_tax_id`` (recipient / patient or
  billing org — billing-owned, generic, optional).
* Tax math never duplicates billing's — ``compute_gst_breakdown``
  *splits* each line's already-computed ``line_tax`` into CGST+SGST or
  IGST; it never recomputes tax. This also makes it sign-agnostic, so
  the already-negative credit-note ``line_tax`` values split correctly
  without any extra negation (verified against
  ``InvoiceWorkflowService.create_credit_note``, which negates
  ``unit_price`` once and derives everything else from that).
* At issue time we snapshot supplier/recipient/place-of-supply into
  ``compliance_data['IN']`` — later edits to ``IndiaGstSettings`` never
  change how an already-issued invoice renders or audits.
* ``on_invoice_issued``/``on_credit_note_issued`` are idempotent:
  ``IndiaGstInvoiceItem`` rows are upserted keyed by ``invoice_item_id``,
  and the single ``IndiaGstEinvoiceSubmission`` row per invoice is
  get-or-created (unique constraint on ``invoice_id``).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.hooks import BillingComplianceHook

from .constants import is_valid_gstin, state_name
from .models import IndiaGstEinvoiceSubmission, IndiaGstInvoiceItem, IndiaGstSettings
from .service import GstLineInput, compute_fy_document_number, compute_gst_breakdown
from .services.severity import severity_for

if TYPE_CHECKING:
    from app.modules.billing.models import Invoice

logger = logging.getLogger(__name__)


def _gst_row(label: str, value: str) -> str:
    """One label/value row in the GST breakdown grid."""
    return (
        f'<div class="gst-row">'
        f'<span class="gst-label">{label}</span>'
        f'<span class="gst-value">{value}</span>'
        f"</div>"
    )


def _gst_amount_row(label: str, amount: str) -> str:
    """One amount row in the GST breakdown grid (right-aligned)."""
    return (
        f'<div class="gst-row gst-amount-row">'
        f'<span class="gst-label">{label}</span>'
        f'<span class="gst-value gst-amount">{amount}</span>'
        f"</div>"
    )


async def _get_settings(db: AsyncSession, clinic_id) -> IndiaGstSettings | None:
    result = await db.execute(
        select(IndiaGstSettings).where(IndiaGstSettings.clinic_id == clinic_id)
    )
    return result.scalar_one_or_none()


async def _load_items_with_sac(
    db: AsyncSession, invoice: Invoice
) -> tuple[list[GstLineInput], bool]:
    """Build ``GstLineInput`` per item, resolving SAC from any existing
    :class:`IndiaGstInvoiceItem` row (re-issue/idempotent path) or the
    clinic's catalog default. Returns ``(items, has_sac_warning)``.
    """
    from .models import IndiaGstCatalogItem

    existing_rows = await db.execute(
        select(IndiaGstInvoiceItem).where(
            IndiaGstInvoiceItem.invoice_item_id.in_([i.id for i in invoice.items])
        )
    )
    existing_by_item = {row.invoice_item_id: row for row in existing_rows.scalars()}

    catalog_ids = [i.catalog_item_id for i in invoice.items if i.catalog_item_id]
    defaults_by_catalog: dict = {}
    if catalog_ids:
        defaults_q = await db.execute(
            select(IndiaGstCatalogItem).where(IndiaGstCatalogItem.catalog_item_id.in_(catalog_ids))
        )
        defaults_by_catalog = {row.catalog_item_id: row for row in defaults_q.scalars()}

    lines: list[GstLineInput] = []
    has_sac_warning = False
    for item in invoice.items:
        existing = existing_by_item.get(item.id)
        sac_code = None
        if existing is not None and existing.sac_code:
            sac_code = existing.sac_code
        elif item.catalog_item_id in defaults_by_catalog:
            sac_code = defaults_by_catalog[item.catalog_item_id].sac_code
        if not sac_code:
            has_sac_warning = True
        lines.append(
            GstLineInput(
                invoice_item_id=item.id,
                vat_rate=item.vat_rate,
                line_tax=item.line_tax,
                sac_code=sac_code,
            )
        )
    return lines, has_sac_warning


class IndiaGstHook(BillingComplianceHook):
    @property
    def country_code(self) -> str:
        return "IN"

    def get_required_fields(self) -> list[str]:
        # Handled ourselves in validate_before_issue (place of supply
        # lives in compliance_data, not a plain Invoice column, so the
        # generic getattr-based required-fields check can't see it).
        return []

    async def validate_before_issue(self, invoice, db) -> tuple[bool, str | None]:
        settings = await _get_settings(db, invoice.clinic_id)
        if settings is None or settings.registration_type != "regular":
            return True, None

        # Credit notes inherit place of supply from the original invoice
        # (see _apply) — they never carry their own compliance_data
        # until issued, so this check only applies to regular invoices.
        if not invoice.credit_note_for_id:
            compliance_data = invoice.compliance_data or {}
            place_of_supply = (compliance_data.get("IN") or {}).get("place_of_supply")
            if not place_of_supply:
                return (
                    False,
                    "Select a place of supply to calculate GST — until then the invoice cannot be issued.",
                )

        if invoice.billing_tax_id and not is_valid_gstin(invoice.billing_tax_id):
            return (
                False,
                "The recipient GSTIN format is invalid. Check it before issuing.",
            )

        # Missing SAC is a warning in the design, not a hard block —
        # surfaced via severity on the issued invoice, not here.
        return True, None

    async def on_invoice_issued(self, invoice, db) -> dict[str, Any]:
        return await self._apply(invoice, db, is_credit_note=False, original_invoice=None)

    async def on_credit_note_issued(self, credit_note, original_invoice, db) -> dict[str, Any]:
        return await self._apply(
            credit_note, db, is_credit_note=True, original_invoice=original_invoice
        )

    def enhance_pdf_data(self, pdf_data: dict, invoice) -> dict:
        """Append the GST breakdown section to the PDF.

        Produces a ``compliance_section_html`` key rendered as a
        dedicated section in the invoice PDF (after totals, before
        footer) — matching the on-screen GST panel. Also appends a
        ``legal_notices`` entry for the "Tax Invoice — GST" header.

        Reads only from the immutable issue-time snapshot in
        ``compliance_data['IN']`` — never live settings, so an
        already-printed PDF always matches what was actually invoiced.
        """
        cd = (invoice.compliance_data or {}).get("IN") or {}
        if not cd:
            return pdf_data
        pdf_data = dict(pdf_data)

        notices = list(pdf_data.get("legal_notices", []))
        notices.append("Tax Invoice — GST")
        pdf_data["legal_notices"] = notices

        # Override VAT/Tax labels with GST terminology for Indian invoices
        pdf_data["label_overrides"] = {
            "vat": "GST",
            "tax": "GST",
        }

        # Build the GST breakdown section HTML
        show_gstin = cd.get("show_gstin_on_invoice", True)
        supplier = cd.get("supplier") or {}
        supplier_gstin = supplier.get("gstin") or ""
        recipient_gstin = (cd.get("recipient") or {}).get("gstin") or ""
        place_name = cd.get("place_of_supply_name") or ""
        place_code = cd.get("place_of_supply") or ""
        tax_type = cd.get("tax_type") or ""
        gst_doc = cd.get("gst_document_number") or ""
        original_ref = cd.get("original_reference") or ""
        einvoice_state = cd.get("einvoice_state") or ""

        cgst_total = cd.get("cgst_total", "0.00")
        sgst_total = cd.get("sgst_total", "0.00")
        igst_total = cd.get("igst_total", "0.00")

        # E-invoice status label
        einvoice_labels = {
            "not_required": "Not required",
            "not_configured": "Not configured",
            "pending": "Pending",
            "generated": "IRN generated",
            "rejected": "Rejected",
            "error": "Connection error",
        }
        einvoice_label = einvoice_labels.get(einvoice_state, einvoice_state)

        # E-invoice hint text
        einvoice_hints = {
            "not_required": (
                "Your clinic is below the turnover threshold configured in "
                "settings, so this invoice is not submitted to the e-invoice portal."
            ),
            "not_configured": (
                "E-invoicing applies to clinics above the turnover threshold "
                "set in India GST settings. Nothing is sent for this invoice."
            ),
        }
        einvoice_hint = einvoice_hints.get(einvoice_state, "")

        # Tax calculation label
        if tax_type == "intra":
            tax_calc_label = "Intra-state · CGST + SGST"
        elif tax_type == "inter":
            tax_calc_label = "Inter-state · IGST"
        else:
            tax_calc_label = tax_type.title() if tax_type else ""

        # Place of supply display
        place_display = place_name
        if place_code and place_name:
            place_display = f"{place_name} ({place_code})"
        elif place_code:
            place_display = place_code

        # GSTIN display
        gstin_display = "Not provided"
        if show_gstin and supplier_gstin:
            gstin_display = supplier_gstin
            if recipient_gstin:
                gstin_display += f" / {recipient_gstin}"

        # Build rows
        rows_html = ""

        # GST document number
        if gst_doc:
            rows_html += _gst_row("GST document number", gst_doc)

        # Corrects reference (credit notes)
        if original_ref:
            rows_html += _gst_row("Corrects document", original_ref)

        # Place of supply
        rows_html += _gst_row("Place of supply", place_display)

        # GSTIN on invoice
        rows_html += _gst_row("GSTIN on invoice", gstin_display)

        # Tax calculation header
        rows_html += _gst_row("GST calculation", tax_calc_label)

        # CGST / SGST / IGST amounts
        rows_html += _gst_amount_row("CGST", cgst_total)
        rows_html += _gst_amount_row("SGST", sgst_total)
        rows_html += _gst_amount_row("IGST", igst_total)

        # E-invoice status
        rows_html += _gst_row("E-invoice status", einvoice_label)
        if einvoice_hint:
            rows_html += f'<div class="gst-hint">{einvoice_hint}</div>'

        section_html = f"""
        <div class="gst-section">
            <div class="section-title">GST and e-invoice</div>
            <div class="gst-grid">
                {rows_html}
            </div>
        </div>
        """
        pdf_data["compliance_section_html"] = section_html
        return pdf_data

    async def _apply(
        self, invoice, db: AsyncSession, *, is_credit_note: bool, original_invoice
    ) -> dict[str, Any]:
        settings = await _get_settings(db, invoice.clinic_id)
        if settings is None or settings.registration_type != "regular":
            return {}

        # ``invoice.items`` is trusted pre-loaded by the caller (billing's
        # issue endpoint always fetches via
        # ``InvoiceService.get_invoice(..., include_items=True)`` before
        # calling into the hook) — mirrors verifactu's hook, which never
        # re-queries the invoice either.
        items, has_sac_warning = await _load_items_with_sac(db, invoice)
        # A credit note has no compliance_data of its own until this very
        # method writes it — it must always use the same place of supply
        # as the invoice it corrects (you can't rectify a transaction
        # into a different tax jurisdiction).
        source_for_place_of_supply = original_invoice if is_credit_note else invoice
        place_of_supply_code = (
            (source_for_place_of_supply.compliance_data or {}).get("IN") or {}
        ).get("place_of_supply")
        breakdown = compute_gst_breakdown(
            items, clinic_state=settings.clinic_state, place_of_supply=place_of_supply_code
        )

        # Upsert IndiaGstInvoiceItem rows, keyed by invoice_item_id —
        # idempotent so re-running the hook (defensive re-issue paths)
        # never duplicates rows.
        existing_rows = await db.execute(
            select(IndiaGstInvoiceItem).where(
                IndiaGstInvoiceItem.invoice_item_id.in_([i.id for i in invoice.items])
            )
        )
        existing_by_item = {row.invoice_item_id: row for row in existing_rows.scalars()}

        for line in breakdown.lines:
            row = existing_by_item.get(line.invoice_item_id)
            if row is None:
                row = IndiaGstInvoiceItem(
                    clinic_id=invoice.clinic_id, invoice_item_id=line.invoice_item_id
                )
                db.add(row)
            row.sac_code = line.sac_code
            row.tax_type = line.tax_type
            row.cgst_rate = line.cgst_rate
            row.cgst_amount = line.cgst_amount
            row.sgst_rate = line.sgst_rate
            row.sgst_amount = line.sgst_amount
            row.igst_rate = line.igst_rate
            row.igst_amount = line.igst_amount

        # Get-or-create the single e-invoice submission row (unique on
        # invoice_id). State never advances past not_required/
        # not_configured in v1 — no live provider is wired in.
        einvoice_q = await db.execute(
            select(IndiaGstEinvoiceSubmission).where(
                IndiaGstEinvoiceSubmission.invoice_id == invoice.id
            )
        )
        einvoice = einvoice_q.scalar_one_or_none()
        below_threshold = settings.turnover_threshold is None or Decimal(
            str(invoice.total or 0)
        ) < Decimal(str(settings.turnover_threshold))
        einvoice_state = "not_required" if below_threshold else "not_configured"
        if einvoice is None:
            einvoice = IndiaGstEinvoiceSubmission(
                clinic_id=invoice.clinic_id, invoice_id=invoice.id, state=einvoice_state
            )
            db.add(einvoice)
        else:
            einvoice.state = einvoice_state

        # Query the series prefix by id directly rather than trusting
        # ``invoice.series`` — the relationship was joinedload'd before
        # ``issue_invoice`` assigned ``series_id`` moments ago in this
        # same request and may not reflect that assignment yet.
        prefix = "CN" if is_credit_note else "GST"
        if invoice.series_id is not None:
            from app.modules.billing.models import InvoiceSeries

            series_prefix = await db.execute(
                select(InvoiceSeries.prefix).where(InvoiceSeries.id == invoice.series_id)
            )
            row = series_prefix.first()
            if row and row[0]:
                prefix = row[0]
        gst_document_number = compute_fy_document_number(
            prefix, invoice.sequential_number or 0, invoice.issue_date
        )

        snapshot: dict[str, Any] = {
            "supplier": {
                "trade_name": settings.trade_name,
                "gstin": settings.gstin,
                "state_code": settings.clinic_state,
                "state_name": state_name(settings.clinic_state),
            },
            "recipient": {"gstin": invoice.billing_tax_id},
            "place_of_supply": place_of_supply_code,
            "place_of_supply_name": state_name(place_of_supply_code),
            "tax_type": breakdown.is_intra and "intra" or "inter",
            "cgst_total": str(breakdown.cgst_total),
            "sgst_total": str(breakdown.sgst_total),
            "igst_total": str(breakdown.igst_total),
            "gst_document_number": gst_document_number,
            "einvoice_state": einvoice_state,
            "severity": severity_for(einvoice_state, has_sac_warning=has_sac_warning),
            # Snapshotted (not read live) so a later settings change never
            # alters how an already-issued invoice's PDF renders — same
            # invariant as everything else in this dict.
            "show_gstin_on_invoice": settings.show_gstin_on_invoice,
            "show_sac_on_invoice": settings.show_sac_on_invoice,
        }
        if is_credit_note and original_invoice is not None:
            original_cd = (original_invoice.compliance_data or {}).get("IN") or {}
            snapshot["original_reference"] = original_cd.get("gst_document_number")

        # Assign a genuinely NEW dict object here, not just return one for
        # the caller to `.update()` in place. `Invoice.compliance_data` is
        # a plain (non-``Mutable``) JSONB column, so SQLAlchemy only
        # detects a change on reassignment — never on in-place mutation.
        # The draft-time endpoint (``router.py::update_invoice_gst_fields``)
        # already left `compliance_data` non-empty (`{"IN": {"place_of_supply": ...}}`),
        # so billing's own `invoice.compliance_data = invoice.compliance_data or {}`
        # followed by `.update(...)` in `InvoiceWorkflowService.issue_invoice`
        # is a same-object no-op there and silently drops this write. Doing
        # the reassignment ourselves, before returning, guarantees the
        # column is marked dirty regardless of what the caller does next.
        invoice.compliance_data = {**(invoice.compliance_data or {}), "IN": snapshot}

        await db.flush()

        return {"IN": snapshot}

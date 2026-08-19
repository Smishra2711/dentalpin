"""India GST module database models.

Tables:

* ``india_gst_settings`` — per-clinic supplier GST profile, e-invoice
  config, display prefs (one row per clinic).
* ``india_gst_catalog_items`` — per-treatment SAC code defaults.
* ``india_gst_invoice_items`` — CGST/SGST/IGST split for an issued
  invoice line, derived from (never recomputed against)
  ``InvoiceItem.line_tax``.
* ``india_gst_einvoice_submissions`` — e-invoice scaffolding state
  (one row per invoice; no live GSP/IRP submission in v1).

None of these add columns to billing's own ``invoices``/``invoice_items``
tables — see ``hook.py`` and the module ``CLAUDE.md`` for the extension
strategy via ``Invoice.compliance_data['IN']``.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic
    from app.modules.billing.models import Invoice, InvoiceItem
    from app.modules.catalog.models import TreatmentCatalogItem

# Registration types / e-invoice states / tax types are documented in
# ``constants.py`` and validated at the Pydantic layer (``schemas.py``)
# — mirrors verifactu's ``RECORD_STATES``/``TIPO_FACTURA`` convention of
# not enforcing them as DB CHECK constraints.
TAX_TYPES = ("intra", "inter")


class IndiaGstSettings(Base, TimestampMixin):
    """Per-clinic India GST supplier profile. Exactly one row per clinic."""

    __tablename__ = "india_gst_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), unique=True, index=True
    )

    trade_name: Mapped[str | None] = mapped_column(String(200), default=None)
    # Supplier (clinic's own) GSTIN. NEVER the recipient's — that lives
    # on ``Invoice.billing_tax_id`` (billing-owned, generic column).
    gstin: Mapped[str | None] = mapped_column(String(15), default=None)
    registration_type: Mapped[str] = mapped_column(String(20), default="regular", nullable=False)
    # State/UT code (see constants.INDIA_STATES), not a display string.
    clinic_state: Mapped[str | None] = mapped_column(String(2), default=None)

    # E-invoice (scaffolding only — see services/einvoice_provider.py).
    turnover_threshold: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None)
    einvoice_provider_config: Mapped[dict] = mapped_column(
        JSONB, default=lambda: {"provider": None}
    )

    show_gstin_on_invoice: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_sac_on_invoice: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rounding_rule: Mapped[str] = mapped_column(String(20), default="nearest_rupee", nullable=False)

    # Clinic logo for printed GST invoices — stored directly (mirrors
    # verifactu's certificate storage: a clinic-scoped binary column,
    # not `media.AttachmentService`, which is patient-scoped and does
    # not fit a clinic-level asset).
    logo_image: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    logo_mime_type: Mapped[str | None] = mapped_column(String(50), default=None)

    clinic: Mapped["Clinic"] = relationship()

    __table_args__ = (Index("ix_india_gst_settings_clinic", "clinic_id"),)


class IndiaGstCatalogItem(Base, TimestampMixin):
    """Per-treatment SAC code default, overriding the catalog item's own.

    When no row exists for a catalog item, the invoice line has no SAC
    default and the settings "missing SAC" review table flags it.
    """

    __tablename__ = "india_gst_catalog_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), index=True
    )
    catalog_item_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("treatment_catalog_items.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    sac_code: Mapped[str] = mapped_column(String(10), nullable=False)
    default_gst_rate_override: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    catalog_item: Mapped["TreatmentCatalogItem"] = relationship()

    __table_args__ = (Index("ix_india_gst_catalog_items_clinic", "clinic_id"),)


class IndiaGstInvoiceItem(Base, TimestampMixin):
    """CGST/SGST/IGST split for one issued invoice line.

    Written once by :func:`hook.compute_gst_breakdown` at issue time
    (upserted — idempotent on re-run). Splits ``InvoiceItem.line_tax``
    after the fact; never recomputes tax independently, so
    ``cgst_amount + sgst_amount`` (or ``igst_amount``) always
    reconciles exactly to ``line_tax`` by construction — including for
    already-negative credit-note amounts, which are not re-negated.
    """

    __tablename__ = "india_gst_invoice_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="RESTRICT"), index=True
    )
    invoice_item_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoice_items.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
    )

    sac_code: Mapped[str | None] = mapped_column(String(10), default=None)
    tax_type: Mapped[str] = mapped_column(String(10), nullable=False)  # intra | inter

    cgst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    sgst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    igst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    sac_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_note: Mapped[str | None] = mapped_column(Text, default=None)

    invoice_item: Mapped["InvoiceItem"] = relationship()

    __table_args__ = (Index("ix_india_gst_invoice_items_clinic", "clinic_id"),)


class IndiaGstEinvoiceSubmission(Base, TimestampMixin):
    """E-invoice scaffolding state for one invoice. One row per invoice.

    v1 has no live GSP/IRP provider wired in — see
    ``services/einvoice_provider.py``. State only ever reaches
    ``not_required``/``not_configured`` through the real (hook-driven)
    path in v1; the other states exist so the UI/schema are complete
    once a provider adapter ships, exercised only by seeded test rows.
    """

    __tablename__ = "india_gst_einvoice_submissions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="RESTRICT"), index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), unique=True, index=True
    )

    state: Mapped[str] = mapped_column(String(20), default="not_required", nullable=False)
    irn: Mapped[str | None] = mapped_column(String(100), default=None)
    ack_number: Mapped[str | None] = mapped_column(String(50), default=None)
    ack_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    signed_qr_payload: Mapped[str | None] = mapped_column(Text, default=None)
    provider_error_message: Mapped[str | None] = mapped_column(Text, default=None)
    submission_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    clinic: Mapped["Clinic"] = relationship()
    invoice: Mapped["Invoice"] = relationship()

    __table_args__ = (
        Index("ix_india_gst_einvoice_clinic", "clinic_id"),
        Index("ix_india_gst_einvoice_state", "clinic_id", "state"),
    )

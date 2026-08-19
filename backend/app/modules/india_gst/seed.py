"""Demo data seed for the india_gst module.

Turns the demo clinic into an India/Tamil Nadu GST-registered clinic,
back-fills GST compliance data onto the invoices ``seed_demo.py``
already created, and adds purpose-built Tamil Nadu GST quotes (budgets)
and issued invoices — built through the real service layer
(``BudgetService``, ``InvoiceService``, ``InvoiceWorkflowService``,
``IndiaGstHook``) rather than duplicating any of their logic, exactly
like ``patient_timeline``'s and ``recalls``' seeds reuse their modules'
own services.

Only invoked by ``backend/scripts/seed_demo.py``, only when
``india_gst`` is installed in ``core_module``, and only for the Tamil
(``--lang ta``) demo persona — the seeded clinic is in Chennai, Tamil
Nadu, which is the only demo persona with an Indian address. Idempotent
for the given clinic: upserts settings/catalog defaults, and
``IndiaGstHook`` itself upserts the per-invoice rows — but the
purpose-built quotes/invoices are only created once (guarded by a
fixed budget-number check), matching ``seed_demo.py``'s own
whole-script "already exists" guard.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.billing.service import InvoiceItemService, InvoiceService
from app.modules.billing.workflow import InvoiceWorkflowService
from app.modules.budget.models import Budget
from app.modules.budget.service import BudgetService
from app.modules.budget.workflow import BudgetWorkflowService
from app.modules.catalog.models import TreatmentCatalogItem, VatType
from app.modules.patients.models import Patient

from .constants import DEFAULT_DENTAL_SAC_CODE
from .hook import IndiaGstHook
from .models import IndiaGstCatalogItem, IndiaGstSettings

# Dental SAC under GST, shared with the settings page's autoconfigure
# action (``constants.DEFAULT_DENTAL_SAC_CODE``) so both stamp the same
# code. Matches the source design mockup ("SAC 999312 · GST 18%").
DENTAL_SAC_CODE = DEFAULT_DENTAL_SAC_CODE

# The shared demo catalog defaults every treatment to 0%-rated VAT —
# realistic (routine dental/medical care is broadly GST-exempt in India
# too, Notification 12/2017-CT(Rate)), but an all-zero-tax demo doesn't
# show off the CGST/SGST/IGST split. Crowns, prosthetics, root-canal and
# composite restorative work are lab/specialist work, not exempt routine
# healthcare, so those specific treatments get a real GST slab —
# matching the source design mockup's own "Zirconia crown / Root canal
# ... GST 18%" examples.
TAXABLE_TREATMENT_CODES = {"REST-CROWN-MC", "PROT-PART-METAL", "ENDO-MULTI", "REST-COMP"}

# Only retax *already-existing* invoice lines on invoices that were
# never fully settled at the old (0%) total. A "paid" demo invoice
# already has payment rows summing exactly to its original total;
# raising the total after the fact would leave it flagged "paid" while
# actually short — a correctness bug, not just a cosmetic one.
# "issued"/"partial" invoices have no such equality to break. This does
# NOT apply to the purpose-built quotes/invoices below — those are
# created fresh, GST included from the start.
RETAXABLE_STATUSES = ("issued", "partial")

CLINIC_STATE_CODE = "33"  # Tamil Nadu
INTER_STATE_CODE = "29"  # Karnataka — arbitrary out-of-state example

# Fixed budget_number prefix so a second seed run (after a fresh
# ./scripts/reset-db.sh) doesn't collide, and so this function can tell
# whether it already ran without a separate flag column.
QUOTE_NUMBER_MARKER = "GST-Q-"


def _bilingual_label(names: dict, fallback: str) -> str:
    """ "English / Tamil" combined label.

    Real Tamil Nadu GST documents commonly show both languages
    together, and — unlike a treatment's catalog name, which is looked
    up per-viewer-locale at render time — an invoice/quote line
    ``description`` is a frozen snapshot (billing's own convention: the
    same wording forever, regardless of who later views it or in which
    locale). Combining both languages here means the snapshot reads
    correctly no matter which UI language the viewer picked.
    """
    en = (names or {}).get("en") or fallback
    ta = (names or {}).get("ta")
    return f"{en} / {ta}" if ta else en


async def seed_india_gst_demo(db: AsyncSession, clinic_id: UUID) -> dict[str, int]:
    """Populate india_gst settings + catalog defaults + invoice GST data
    + purpose-built Tamil Nadu GST quotes and invoices.

    Returns a stats dict consumed by the seed-demo summary.
    """
    stats = {
        "catalog_items": 0,
        "invoices": 0,
        "intra": 0,
        "inter": 0,
        "retaxed_items": 0,
        "quotes": 0,
        "new_invoices": 0,
    }

    clinic_q = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
    clinic = clinic_q.scalar_one()
    # Fresh dict reassignment, not in-place mutation — Clinic.settings is
    # a plain JSONB column (same gotcha as Invoice.compliance_data).
    clinic.settings = {**(clinic.settings or {}), "country": "IN"}

    settings_q = await db.execute(
        select(IndiaGstSettings).where(IndiaGstSettings.clinic_id == clinic_id)
    )
    settings = settings_q.scalar_one_or_none()
    if settings is None:
        settings = IndiaGstSettings(clinic_id=clinic_id)
        db.add(settings)
    settings.trade_name = clinic.name
    settings.gstin = "33ABCDE1234F1Z5"
    settings.registration_type = "regular"
    settings.clinic_state = CLINIC_STATE_CODE
    settings.show_gstin_on_invoice = True
    settings.show_sac_on_invoice = True
    await db.flush()

    # --- SAC defaults for every catalog item -----------------------------
    items_q = await db.execute(
        select(TreatmentCatalogItem.id).where(TreatmentCatalogItem.clinic_id == clinic_id)
    )
    catalog_item_ids = [row[0] for row in items_q.all()]

    existing_q = await db.execute(
        select(IndiaGstCatalogItem.catalog_item_id).where(
            IndiaGstCatalogItem.clinic_id == clinic_id
        )
    )
    existing_ids = {row[0] for row in existing_q.all()}

    for catalog_item_id in catalog_item_ids:
        if catalog_item_id in existing_ids:
            continue
        db.add(
            IndiaGstCatalogItem(
                clinic_id=clinic_id, catalog_item_id=catalog_item_id, sac_code=DENTAL_SAC_CODE
            )
        )
        stats["catalog_items"] += 1
    await db.flush()

    # --- A real GST slab (18%), and make it the catalog default for the
    # taxable treatments (root cause, not a per-transaction patch): any
    # budget/quote built from these treatments inherits it automatically
    # (BudgetItemService.create_item snapshots the catalog item's own
    # vat_type_id) — including quotes a user creates later in the running
    # demo, not just the ones seeded here. -----------------------------
    gst_18_vat_type = VatType(
        clinic_id=clinic_id,
        names={"en": "GST 18%", "es": "GST 18%", "fr": "GST 18%", "ta": "GST 18%"},
        rate=18.0,
    )
    db.add(gst_18_vat_type)
    await db.flush()

    taxable_catalog_q = await db.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == clinic_id,
            TreatmentCatalogItem.internal_code.in_(TAXABLE_TREATMENT_CODES),
        )
    )
    taxable_catalog_items = {i.internal_code: i for i in taxable_catalog_q.scalars().all()}
    for catalog_item in taxable_catalog_items.values():
        catalog_item.vat_type_id = gst_18_vat_type.id
    await db.flush()

    # --- Retax *already-existing* crown/prosthetic/root-canal/composite
    # invoice lines (created before the catalog default above existed) at
    # the same real GST slab. InvoiceItem snapshots vat_type_id/vat_rate
    # at creation time, so changing the catalog default just now does not
    # retroactively touch these rows — they need an explicit update. ----
    taxable_items_q = await db.execute(
        select(InvoiceItem)
        .join(TreatmentCatalogItem, TreatmentCatalogItem.id == InvoiceItem.catalog_item_id)
        .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
        .where(
            InvoiceItem.clinic_id == clinic_id,
            TreatmentCatalogItem.internal_code.in_(TAXABLE_TREATMENT_CODES),
            Invoice.status.in_(RETAXABLE_STATUSES),
        )
    )
    retaxed_invoice_ids: set[UUID] = set()
    for item in taxable_items_q.scalars().all():
        item.vat_type_id = gst_18_vat_type.id
        item.vat_rate = 18.0
        await InvoiceService.calculate_item_totals(item)
        retaxed_invoice_ids.add(item.invoice_id)
        stats["retaxed_items"] += 1
    await db.flush()

    for invoice_id in retaxed_invoice_ids:
        inv_q = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        await InvoiceService.recalculate_totals(db, inv_q.scalar_one())

    # --- Purpose-built Tamil Nadu GST quotes + invoices -------------------
    new_invoice_ids: set[UUID] = set()
    already_seeded_q = await db.execute(
        select(Budget.id).where(
            Budget.clinic_id == clinic_id, Budget.budget_number.like(f"{QUOTE_NUMBER_MARKER}%")
        )
    )
    if already_seeded_q.first() is None:
        quotes_stats, new_invoice_ids = await _seed_quotes_and_invoices(
            db, clinic_id, gst_18_vat_type.id, taxable_catalog_items
        )
        stats["quotes"] = quotes_stats["quotes"]
        stats["new_invoices"] = quotes_stats["invoices"]

    # --- GST breakdown for every non-draft invoice (skips the ones just
    # created above — those were already issued through the real hook
    # with a deliberate place of supply, not the fallback pattern here).
    invoices_q = await db.execute(
        select(Invoice)
        .where(
            Invoice.clinic_id == clinic_id,
            Invoice.status != "draft",
            Invoice.id.notin_(new_invoice_ids) if new_invoice_ids else True,
        )
        .options(selectinload(Invoice.items))
        .order_by(Invoice.invoice_number)
    )
    invoices = list(invoices_q.scalars().all())

    # Set a turnover threshold roughly at the median invoice total so the
    # demo shows both e-invoice states (not_required / not_configured)
    # instead of only one.
    totals = sorted((inv.total or Decimal("0")) for inv in invoices)
    settings.turnover_threshold = totals[len(totals) // 2] if totals else None

    # Deliberately alternate intra/inter *across the retaxed (non-zero)
    # invoices specifically* — sorted for determinism — so the demo always
    # shows at least one real CGST+SGST example and one real IGST example,
    # rather than leaving that to whichever invoice a blind modulo lands
    # on (which previously could — and did — put the only inter-state
    # example on a 0%-taxed invoice, making IGST look broken/zero).
    retaxed_sorted = sorted(retaxed_invoice_ids, key=str)
    inter_state_retaxed = set(retaxed_sorted[1::2])

    hook = IndiaGstHook()
    for idx, invoice in enumerate(invoices):
        if invoice.id in retaxed_invoice_ids:
            state_code = (
                INTER_STATE_CODE if invoice.id in inter_state_retaxed else CLINIC_STATE_CODE
            )
        else:
            state_code = INTER_STATE_CODE if (idx + 1) % 4 == 0 else CLINIC_STATE_CODE
        invoice.compliance_data = {
            **(invoice.compliance_data or {}),
            "IN": {"place_of_supply": state_code},
        }
        await hook.on_invoice_issued(invoice, db)
        stats["invoices"] += 1
        stats["inter" if state_code == INTER_STATE_CODE else "intra"] += 1

    await db.flush()
    return stats


async def cleanup_india_gst_demo(db: AsyncSession, clinic_id: UUID) -> dict[str, int]:
    """Remove all India GST demo seed data for a clinic.

    The inverse of :func:`seed_india_gst_demo`. Deletes:
    - IndiaGstInvoiceItem rows (CGST/SGST/IGST splits)
    - IndiaGstEinvoiceSubmission rows
    - IndiaGstCatalogItem rows (SAC defaults)
    - IndiaGstSettings row
    - Purpose-built GST quotes (budgets with ``GST-Q-`` prefix)
    - Purpose-built GST invoices (the two issued by the seed)
    - ``compliance_data['IN']`` key on all invoices
    - The seeded ``GST 18%`` VatType
    - Resets retaxed catalog items back to their original 0% VatType

    Returns a stats dict for logging.
    """
    from sqlalchemy import delete, update

    from .models import (
        IndiaGstCatalogItem,
        IndiaGstEinvoiceSubmission,
        IndiaGstInvoiceItem,
        IndiaGstSettings,
    )

    stats = {
        "invoice_items": 0,
        "einvoice_submissions": 0,
        "catalog_items": 0,
        "settings": 0,
        "quotes": 0,
        "invoices": 0,
        "compliance_cleared": 0,
        "vat_types": 0,
    }

    # --- GST invoice item splits -----------------------------------------
    q = await db.execute(
        delete(IndiaGstInvoiceItem).where(IndiaGstInvoiceItem.clinic_id == clinic_id)
    )
    stats["invoice_items"] = q.rowcount or 0

    # --- E-invoice submissions -------------------------------------------
    q = await db.execute(
        delete(IndiaGstEinvoiceSubmission).where(IndiaGstEinvoiceSubmission.clinic_id == clinic_id)
    )
    stats["einvoice_submissions"] = q.rowcount or 0

    # --- SAC catalog defaults --------------------------------------------
    q = await db.execute(
        delete(IndiaGstCatalogItem).where(IndiaGstCatalogItem.clinic_id == clinic_id)
    )
    stats["catalog_items"] = q.rowcount or 0

    # --- Settings --------------------------------------------------------
    q = await db.execute(delete(IndiaGstSettings).where(IndiaGstSettings.clinic_id == clinic_id))
    stats["settings"] = q.rowcount or 0

    # --- Purpose-built GST quotes (budgets with GST-Q- prefix) -----------
    gst_quote_q = await db.execute(
        select(Budget.id).where(
            Budget.clinic_id == clinic_id,
            Budget.budget_number.like(f"{QUOTE_NUMBER_MARKER}%"),
        )
    )
    gst_quote_ids = [row[0] for row in gst_quote_q.all()]
    if gst_quote_ids:
        from app.modules.budget.models import BudgetItem

        await db.execute(delete(BudgetItem).where(BudgetItem.budget_id.in_(gst_quote_ids)))
        await db.execute(delete(Budget).where(Budget.id.in_(gst_quote_ids)))
    stats["quotes"] = len(gst_quote_ids)

    # --- Clear compliance_data['IN'] on all invoices ---------------------
    # PostgreSQL JSONB `-` operator removes a key. We use a raw update
    # because SQLAlchemy's JSONB support doesn't expose `-` directly.
    clear_q = await db.execute(
        update(Invoice)
        .where(Invoice.clinic_id == clinic_id)
        .where(Invoice.compliance_data.op("?")("IN"))
        .values(compliance_data=Invoice.compliance_data.op("-")("IN"))
    )
    stats["compliance_cleared"] = clear_q.rowcount or 0

    # --- Remove the seeded GST 18% VatType and reset catalog items -------
    # The seed created a VatType named "GST 18%" and assigned it to
    # specific taxable treatments. Reset those catalog items to no
    # VatType (NULL) and delete the VatType.
    gst_vat_q = await db.execute(
        select(VatType.id).where(
            VatType.clinic_id == clinic_id,
            VatType.names.op("->>")("en") == "GST 18%",
        )
    )
    gst_vat_ids = [row[0] for row in gst_vat_q.all()]
    if gst_vat_ids:
        # Reset catalog items that point to this VatType
        await db.execute(
            update(TreatmentCatalogItem)
            .where(
                TreatmentCatalogItem.clinic_id == clinic_id,
                TreatmentCatalogItem.vat_type_id.in_(gst_vat_ids),
            )
            .values(vat_type_id=None)
        )
        # Reset invoice items that point to this VatType back to 0%
        await db.execute(
            update(InvoiceItem)
            .where(
                InvoiceItem.clinic_id == clinic_id,
                InvoiceItem.vat_type_id.in_(gst_vat_ids),
            )
            .values(vat_type_id=None, vat_rate=Decimal("0"))
        )
        await db.execute(delete(VatType).where(VatType.id.in_(gst_vat_ids)))
    stats["vat_types"] = len(gst_vat_ids)

    # --- Recalculate invoice totals for invoices whose items were retaxed -
    # We need to find invoices that had items retaxed from 18% to 0%.
    # The VatType was just deleted, so vat_type_id is already NULL on
    # those items. Recalculate totals for all invoices that had items
    # pointing to the deleted VatType (identified before deletion above).
    # Instead of a broad query, recalculate per invoice for affected items.
    # Since we already set vat_rate=0 and vat_type_id=NULL, we recalculate
    # all invoices that have any item with vat_type_id IS NULL and
    # vat_rate = 0 that previously had the GST VatType. The simplest
    # correct approach: recalculate all non-draft invoices for this clinic.
    all_inv_q = await db.execute(
        select(Invoice)
        .where(Invoice.clinic_id == clinic_id, Invoice.status != "draft")
        .options(selectinload(Invoice.items))
    )
    for inv in all_inv_q.scalars().all():
        needs_recalc = any(
            item.vat_type_id is None and item.vat_rate == Decimal("0") for item in inv.items
        )
        if needs_recalc:
            for item in inv.items:
                await InvoiceService.calculate_item_totals(item)
            await InvoiceService.recalculate_totals(db, inv)
            stats["invoices"] += 1

    # --- Remove country=IN from clinic settings --------------------------
    clinic_q = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
    clinic = clinic_q.scalar_one_or_none()
    if clinic and (clinic.settings or {}).get("country") == "IN":
        new_settings = dict(clinic.settings or {})
        new_settings.pop("country", None)
        clinic.settings = new_settings

    await db.flush()
    return stats


async def _seed_quotes_and_invoices(
    db: AsyncSession,
    clinic_id: UUID,
    gst_vat_type_id: UUID,
    taxable_catalog_items: dict[str, TreatmentCatalogItem],
) -> tuple[dict[str, int], set[UUID]]:
    """Two GST quotes (budgets) + two issued GST invoices, purpose-built
    for the Tamil Nadu persona — not retroactive patches. Built through
    the real service layer end to end: ``BudgetService.create_budget``,
    ``BudgetWorkflowService.send_budget``, ``InvoiceService.create_invoice``,
    ``InvoiceItemService.create_item``, ``InvoiceWorkflowService.issue_invoice``
    with the real ``IndiaGstHook`` wired in as the compliance hook —
    exactly the code path a live request takes.
    """
    stats = {"quotes": 0, "invoices": 0}
    new_invoice_ids: set[UUID] = set()

    crown = taxable_catalog_items.get("REST-CROWN-MC")
    root_canal = taxable_catalog_items.get("ENDO-MULTI")
    denture = taxable_catalog_items.get("PROT-PART-METAL")
    if not (crown and root_canal and denture):
        return stats, new_invoice_ids

    first_visit_q = await db.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == clinic_id,
            TreatmentCatalogItem.internal_code == "DX-VISIT",
        )
    )
    first_visit = first_visit_q.scalar_one_or_none()

    patients_q = await db.execute(
        select(Patient.id)
        .where(Patient.clinic_id == clinic_id)
        .order_by(Patient.created_at)
        .limit(2)
    )
    patient_ids = [row[0] for row in patients_q.all()]
    if len(patient_ids) < 2:
        return stats, new_invoice_ids

    admin_q = await db.execute(
        select(ClinicMembership.user_id)
        .where(ClinicMembership.clinic_id == clinic_id, ClinicMembership.role == "admin")
        .limit(1)
    )
    admin_user_id = admin_q.scalar_one_or_none()
    if admin_user_id is None:
        return stats, new_invoice_ids

    today = date.today()

    # --- Quote 1: crown (+ first visit), sent to the patient -------------
    quote1_items = [{"catalog_item_id": crown.id, "quantity": 1}]
    if first_visit:
        quote1_items.append({"catalog_item_id": first_visit.id, "quantity": 1})
    quote1 = await BudgetService.create_budget(
        db,
        clinic_id,
        admin_user_id,
        {
            "budget_number": f"{QUOTE_NUMBER_MARKER}0001",
            "patient_id": patient_ids[0],
            "valid_from": today,
            "valid_until": today + timedelta(days=30),
            "items": quote1_items,
        },
    )
    await db.refresh(quote1, ["items"])
    await BudgetWorkflowService.send_budget(db, quote1, sent_by=admin_user_id, send_method="manual")
    stats["quotes"] += 1

    # --- Quote 2: prosthetic + root canal, still a draft estimate --------
    await BudgetService.create_budget(
        db,
        clinic_id,
        admin_user_id,
        {
            "budget_number": f"{QUOTE_NUMBER_MARKER}0002",
            "patient_id": patient_ids[1],
            "valid_from": today,
            "valid_until": today + timedelta(days=30),
            "items": [
                {"catalog_item_id": denture.id, "quantity": 1},
                {"catalog_item_id": root_canal.id, "quantity": 1},
            ],
        },
    )
    stats["quotes"] += 1

    # ``InvoiceWorkflowService.issue_invoice`` does its own internal
    # ``BillingHookRegistry.get_for_clinic(clinic)`` lookup (independent
    # of the ``hook_callback`` below) to decide whether recipient
    # ``billing_tax_id`` is required. That registry is an in-memory,
    # per-process singleton normally populated by ``IndiaGstModule.
    # __init__`` at app boot — this seed script runs as its own
    # separate process (``python scripts/seed_demo.py``), which never
    # imports/instantiates the module class, so the registry starts
    # empty here regardless of what's installed in the DB. Register
    # explicitly so the real workflow code path behaves the same way
    # it does in the running backend.
    from app.modules.billing.hooks import BillingHookRegistry

    hook = IndiaGstHook()
    BillingHookRegistry.register(hook)

    async def _hook_callback(inv, session):
        return await hook.on_invoice_issued(inv, session)

    # --- Invoice 1: crown + root canal, intra-state (Tamil Nadu) ---------
    invoice1 = await InvoiceService.create_invoice(db, clinic_id, admin_user_id, patient_ids[0])
    for catalog_item in (crown, root_canal):
        await InvoiceItemService.create_item(
            db,
            clinic_id,
            invoice1,
            {
                "description": _bilingual_label(catalog_item.names, catalog_item.internal_code),
                "catalog_item_id": catalog_item.id,
                "unit_price": catalog_item.default_price,
                "quantity": 1,
                "vat_type_id": gst_vat_type_id,
            },
        )
    invoice1.compliance_data = {"IN": {"place_of_supply": CLINIC_STATE_CODE}}
    invoice1 = await InvoiceWorkflowService.issue_invoice(
        db, invoice1, admin_user_id, hook_callback=_hook_callback
    )
    new_invoice_ids.add(invoice1.id)
    stats["invoices"] += 1

    # --- Invoice 2: prosthetic, inter-state (Karnataka) -------------------
    invoice2 = await InvoiceService.create_invoice(db, clinic_id, admin_user_id, patient_ids[1])
    await InvoiceItemService.create_item(
        db,
        clinic_id,
        invoice2,
        {
            "description": _bilingual_label(denture.names, denture.internal_code),
            "catalog_item_id": denture.id,
            "unit_price": denture.default_price,
            "quantity": 1,
            "vat_type_id": gst_vat_type_id,
        },
    )
    invoice2.compliance_data = {"IN": {"place_of_supply": INTER_STATE_CODE}}
    invoice2 = await InvoiceWorkflowService.issue_invoice(
        db, invoice2, admin_user_id, hook_callback=_hook_callback
    )
    new_invoice_ids.add(invoice2.id)
    stats["invoices"] += 1

    await db.flush()
    return stats, new_invoice_ids

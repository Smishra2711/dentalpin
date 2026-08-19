"""India GST module — CGST/SGST/IGST billing compliance for India.

Extends the billing module via the ``BillingComplianceHook`` registry,
exactly like ``verifactu`` (Spain/AEAT); never imports billing internals
directly. Country-gated: inactive (and invisible) for clinics whose
``clinic.settings['country'] != 'IN'``.

Manual install only (``auto_install=False``). E-invoice integration is
scaffolding only in v1 — see ``services/einvoice_provider.py``.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import (
    IndiaGstCatalogItem,
    IndiaGstEinvoiceSubmission,
    IndiaGstInvoiceItem,
    IndiaGstSettings,
)
from .router import router


class IndiaGstModule(BaseModule):
    manifest = {
        "name": "india_gst",
        "version": "0.1.0",
        "summary": "CGST/SGST/IGST GST billing compliance for Indian clinics.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["billing", "catalog"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["reports.read"],
            "hygienist": [],
            "assistant": [],
            "receptionist": ["reports.read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.indiaGst",
                    "icon": "i-lucide-receipt-indian-rupee",
                    "to": "/reports/india-gst",
                    "permission": "india_gst.reports.read",
                    "order": 71,
                },
            ],
        },
    }

    def __init__(self) -> None:
        # Register the BillingComplianceHook on every backend boot — the
        # one-time ``install`` lifecycle only runs when the user clicks
        # Install in the admin UI; subsequent restarts wipe the
        # in-memory registry, so hooks must be re-attached at module
        # load time. Idempotent: BillingHookRegistry keys by
        # country_code. Mirrors verifactu/__init__.py exactly.
        from app.modules.billing.hooks import BillingHookRegistry

        from .hook import IndiaGstHook

        BillingHookRegistry.register(IndiaGstHook())

    def get_models(self) -> list:
        return [
            IndiaGstSettings,
            IndiaGstCatalogItem,
            IndiaGstInvoiceItem,
            IndiaGstEinvoiceSubmission,
        ]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return [
            "settings.read",
            "settings.configure",
            "catalog.manage",
            "reports.read",
        ]

    def get_event_handlers(self) -> dict:
        return {}

    def get_tools(self) -> list:
        from .tools import get_tools

        return get_tools()

    async def install(self, ctx) -> None:
        from sqlalchemy import select

        from app.core.auth.models import Clinic
        from app.modules.billing.hooks import BillingHookRegistry

        from .hook import IndiaGstHook

        BillingHookRegistry.register(IndiaGstHook())
        ctx.logger.info("india_gst hook registered for country=IN")

        # Backfill GST demo data for any existing Indian clinic (country=IN
        # in settings). This covers the case where the demo was seeded
        # before the module was installed — the user installs the module
        # and the GST data appears without needing a re-seed.
        from .seed import seed_india_gst_demo

        clinic_q = await ctx.db.execute(select(Clinic).order_by(Clinic.id))
        for clinic in clinic_q.scalars().all():
            country = (clinic.settings or {}).get("country")
            if country == "IN":
                stats = await seed_india_gst_demo(ctx.db, clinic.id)
                ctx.logger.info(
                    f"india_gst demo data seeded for clinic {clinic.id}: "
                    f"{stats['catalog_items']} SAC defaults, "
                    f"{stats['invoices']} invoices with GST data, "
                    f"{stats['quotes']} new GST quotes, "
                    f"{stats['new_invoices']} new GST invoices"
                )

    async def uninstall(self, ctx) -> None:
        from sqlalchemy import select

        from app.core.auth.models import Clinic
        from app.modules.billing.hooks import BillingHookRegistry

        from .seed import cleanup_india_gst_demo

        # Clean up India GST demo data for every clinic that has it.
        # ModuleContext has no clinic_id (modules are global), so we
        # find clinics with country=IN or existing GST settings.
        clinic_q = await ctx.db.execute(select(Clinic.id).order_by(Clinic.id))
        for row in clinic_q.all():
            clinic_id = row[0]
            stats = await cleanup_india_gst_demo(ctx.db, clinic_id)
            if stats["invoice_items"] or stats["catalog_items"] or stats["settings"]:
                ctx.logger.info(
                    f"india_gst seed data cleaned up for clinic {clinic_id}: "
                    f"{stats['invoice_items']} invoice items, "
                    f"{stats['catalog_items']} SAC defaults, "
                    f"{stats['settings']} settings, "
                    f"{stats['quotes']} quotes, "
                    f"{stats['compliance_cleared']} invoices cleared, "
                    f"{stats['vat_types']} VAT types removed"
                )

        BillingHookRegistry.unregister("IN")
        ctx.logger.info("india_gst hook unregistered")

# Changelog — india_gst module

## Unreleased

- PDF invoice integration: `enhance_pdf_data` now provides a structured
  GST breakdown section (`compliance_section_html`) with document number,
  place of supply, supplier/recipient GSTINs, and CGST/SGST/IGST totals.
  Label overrides replace "VAT"/"Tax" with "GST" for Indian clinics.
- Tamil locale (`ta`) support in PDF generation — Tamil labels and
  `Noto Sans Tamil` font in the CSS font-family stack.
- Uninstall guard: blocks uninstall if any non-draft invoice has GST
  line-item data, preventing orphaned CGST/SGST/IGST breakdowns.
- `install()` now backfills GST demo data for existing Indian clinics
  (country=IN), so installing the module after seeding populates GST
  data without needing a re-seed.
- Frontend tests: `useIndiaGstStates` and `gstBadgeLogic` unit tests
  (50 tests covering state mapping, badge logic, e-invoice labels).
- Full module documentation: `docs/modules/india_gst.md`.
- Settings page: one-click **Auto-configure** assigns the default dental SAC
  (`999312`) to every treatment still missing one
  (`POST /catalog-defaults/autoconfigure`). Additive only — an existing
  default is never overwritten, so it is safe to re-run.
- Fixed: the missing-SAC list rendered treatment names in Spanish
  regardless of the viewer's language. `GET /catalog-defaults` now returns
  the whole `names` translation dict and the page resolves it against the
  active UI locale (English fallback).
- Initial implementation: CGST/SGST/IGST tax-split engine, GSTIN capture
  (supplier via `IndiaGstSettings`, recipient via billing's
  `Invoice.billing_tax_id`), place-of-supply-driven intra/inter-state
  determination, SAC code defaults per treatment catalog item, credit-note
  reversal (inherits place of supply from the original invoice), FY-scoped
  GST document numbering (April–March), and a GST reconciliation report
  with CSV export.
- E-invoice integration shipped as scaffolding only: full data model,
  settings, and all UI states, but no live GSP/IRP provider — the retry
  endpoint always returns `409`, never a fabricated success.
- `BillingComplianceHook` implementation (`country_code="IN"`), mirroring
  the `verifactu` module's architecture: country-gated, no billing schema
  changes, extends via `Invoice.compliance_data['IN']`.
- Only `registration_type == "regular"` drives invoicing logic in v1;
  Composition/Unregistered/Exempt are stored settings with no tax
  calculation (documented limitation).

## 0.1.0 — 2026-08-19

- Initial release.

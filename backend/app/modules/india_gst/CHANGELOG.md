# Changelog — india_gst module

## Unreleased

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

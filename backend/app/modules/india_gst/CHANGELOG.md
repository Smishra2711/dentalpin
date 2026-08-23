# Changelog — india_gst module

## Unreleased

### Real-world GST validation pass (tresundios, post fix-up)

- **Fixed**: e-invoice applicability compared a single invoice's
  `total` against `turnover_threshold` — the statutory trigger is
  aggregate annual turnover (PAN-wide across relevant GSTINs), not a
  per-invoice amount. `einvoice_state` now derives from whether the
  clinic has declared a `turnover_threshold` at all (`not_configured`)
  vs not (`not_required`), never from the invoice being issued. Hint
  text on the invoice PDF updated to match.
- **Tests**: interstate credit-note regime preservation, missing
  `clinic_state` issue-block, e-invoice applicability (turnover vs
  invoice amount), CSV formula-injection neutralization, auto-configure
  `GST 18%` VAT-type idempotency and tenant scoping, cross-clinic FY
  counter independence, and a repeated-allocation test proving the
  `SELECT … FOR UPDATE` counter lock never drops or repeats a serial.
- **Demo fixtures**: added an explicit, isolated `seed_india_gst()` step
  to `scripts/seed_demo.py` (Tamil Nadu clinic, GSTIN
  `33ABCDE1234F1Z5` — structurally valid per the CBIC format regex,
  labelled test/demo data, not a real taxpayer's registration) that
  only runs for `--lang ta` and only when `india_gst` is already
  installed. `demo_data.py` sets `country=IN` on the Tamil clinic so
  the hook activates for it. Neither path runs from module install,
  auto-install, or any production tenant lifecycle.
- **Docs**: GSTIN validation clarified as format-only (no mod-36
  checksum); manual validation checklist and expanded CA-confirmation
  guidance for CGST/SGST rounding, FY numbering convention, and
  turnover-based e-invoice applicability added to
  `docs/modules/india_gst.md`.

### Maintainer fix-up on top of PR #210

- **Lifecycle made safe**: `install()` no longer runs any seed against
  real clinics (it used to overwrite `trade_name`, stamp a placeholder
  GSTIN, re-tax issued invoices and create fake invoices); it only
  registers the compliance hook. `uninstall()` keeps the guard and
  unregisters — no destructive cleanup. `seed.py` deleted; the
  `GST 18%` VatType get-or-create moved to the auto-configure endpoint.
- **FY-scoped numbering**: new `india_gst_document_sequences` counter
  (unique per clinic+prefix+FY, `SELECT … FOR UPDATE`). Numbers no
  longer derive from billing's calendar-year `sequential_number`, which
  duplicated GST serials between January and March.
- **Multi-tenancy**: added the missing `clinic_id` filter to 7 queries
  (hook, draft-update endpoint, reports/CSV);
  `UNIQUE(clinic_id, catalog_item_id)` on SAC defaults.
- **PDF contract hardened**: the hook now hands billing a structured
  `compliance_section` dict which billing renders and escapes —
  removes an HTML-injection vector via GSTIN/trade-name values.
- **CGST = SGST**: equal halves rounded HALF_UP per head (was
  remainder-absorption, which produced asymmetric heads GSTR-1
  reconciliation rejects).
- `validate_before_issue` requires `clinic_state` for regular
  registrants (missing state silently taxed everything as IGST).
- Role grants: `settings.read` for all clinical roles (invoice panels
  call tax-preview/e-invoice status); reports/settings pages
  permission-gated in the UI; CSV export via authenticated fetch.
- Dead e-invoice scaffolding deleted (provider ABC, submission queue,
  never-written IRN/ack columns, logo storage, inert `rounding_rule`).
  Retry still honestly answers `409`.
- Reports: SQL pagination + `PaginatedApiResponse`, typed date params
  (422 on malformed), CSV formula-injection guard.
- i18n: fr/pt locales added (host declares five).
- Tests: multi-tenant isolation, role permission matrix, PDF escaping,
  FY sequence continuity/reset.

### Original PR #210 (tresundios)

- PDF invoice integration: `enhance_pdf_data` provides a GST breakdown
  section with document number, place of supply, supplier/recipient
  GSTINs, and CGST/SGST/IGST totals. Label overrides replace
  "VAT"/"Tax" with "GST" for Indian clinics.
- Tamil locale (`ta`) support in PDF generation — Tamil labels and
  `Noto Sans Tamil` font in the CSS font-family stack.
- Uninstall guard: blocks uninstall if any non-draft invoice has GST
  line-item data, preventing orphaned CGST/SGST/IGST breakdowns.
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
- E-invoice applicability tracking (`not_required`/`not_configured`
  per invoice), no live GSP/IRP provider — the retry endpoint always
  returns `409`, never a fabricated success.
- `BillingComplianceHook` implementation (`country_code="IN"`), mirroring
  the `verifactu` module's architecture: country-gated, no billing schema
  changes, extends via `Invoice.compliance_data['IN']`.
- Only `registration_type == "regular"` drives invoicing logic in v1;
  Composition/Unregistered/Exempt are stored settings with no tax
  calculation (documented limitation).

## 0.1.0 — 2026-08-19

- Initial release.

# India GST module

CGST/SGST/IGST billing compliance for Indian clinics (GSTIN, place of
supply, SAC codes, credit-note reversal, e-invoice scaffolding).

## Public API

- Routes mounted at `/api/v1/india_gst/`.
- Key endpoints:
  - `GET/PUT  /india_gst/settings`                  — clinic GST profile; `india_gst.settings.read`/`.configure`
  - `GET/PUT  /india_gst/catalog-defaults`           — SAC defaults per treatment; `india_gst.catalog.manage`
  - `POST     /india_gst/tax-preview`                — stateless Decimal-safe breakdown; `india_gst.settings.read`
  - `PUT      /india_gst/invoices/{id}`              — draft-only GST fields (place of supply, SAC); `billing.write`
  - `GET      /india_gst/invoices/{id}/einvoice`      — e-invoice status; `india_gst.settings.read`
  - `POST     /india_gst/invoices/{id}/einvoice/retry` — always 409 in v1 (no provider); `india_gst.settings.configure`
  - `GET      /india_gst/reports/{summary,transactions,export}` — reconciliation report; `india_gst.reports.read`

## Dependencies

`manifest.depends = ["billing", "catalog"]`. Reads `TreatmentCatalogItem`
(catalog) for SAC-default resolution and `Invoice`/`InvoiceItem`
(billing) via the compliance hook — never imports billing's workflow
or router modules.

## Permissions

`india_gst.settings.read`, `india_gst.settings.configure`,
`india_gst.catalog.manage`, `india_gst.reports.read`. Editing GST
fields on a *draft* invoice reuses billing's own `billing.write`
(billing-owned data), matching verifactu's precedent of not gating
invoice fields behind its own permission.

## Tools exposed

None (`get_tools()` → `[]`), same as verifactu.

## Events emitted

None in v1 — GST compliance data is written synchronously via
`BillingComplianceHook`, not the event bus (see Gotchas).

## Events consumed

None in v1.

## Lifecycle

- `installable=True`, `auto_install=False` (activated from admin UI),
  `removable=True`.
- `uninstall()` blocks if **any** `IndiaGstInvoiceItem` is linked to a
  non-draft invoice (issued/partial/paid/credit-note), or any
  `IndiaGstEinvoiceSubmission` reached `generated` (IRN issued) —
  broader than "just block on generated e-invoices" because the module
  owns tax-split data needed to render/audit any issued invoice.
- Migrations on the `india_gst` Alembic branch (`igst_0001`).

## Gotchas / non-obvious invariants

- **GSTIN has two owners.** `IndiaGstSettings.gstin` is the clinic's
  own (supplier) GSTIN. `Invoice.billing_tax_id` (billing-owned,
  generic) is the *recipient's* GSTIN. Never conflate them.
- **Tax math never recomputes — it splits.** `compute_gst_breakdown`
  divides each line's already-computed `InvoiceItem.line_tax` into
  CGST+SGST (remainder-absorption: `sgst = tax_amount - cgst`, not two
  independent halvings) or IGST. This is sign-agnostic by construction,
  so credit-note amounts (already negative — billing negates
  `unit_price` once in `create_credit_note`) split correctly without
  re-negation.
- **`Invoice.compliance_data` is a plain JSONB column, not
  `MutableDict`.** SQLAlchemy only detects a change on reassignment,
  never on in-place mutation. Billing's own
  `invoice.compliance_data.update(...)` merge in
  `InvoiceWorkflowService.issue_invoice` is a same-object no-op
  whenever `compliance_data` was already non-empty — which it always is
  here, since the draft-time PUT endpoint pre-populates
  `compliance_data['IN']['place_of_supply']`. `hook.py::_apply`
  therefore reassigns `invoice.compliance_data` to a **new** dict
  itself before returning, rather than trusting the caller's merge.
- **Historical snapshot, not live settings.** At issue time the hook
  writes supplier/recipient/place-of-supply into
  `compliance_data['IN']` — later edits to `IndiaGstSettings` never
  change how an already-issued invoice renders.
- **Credit notes inherit place of supply from the original invoice**,
  not their own `compliance_data` (they have none until issued) — see
  `hook.py::_apply`'s `source_for_place_of_supply`.
- **Only `registration_type == "regular"` computes GST.**
  Composition/Unregistered/Exempt are stored but the hook returns `{}`
  (no GST rows) — Composition-scheme rules are materially different
  and out of scope for v1.
- **E-invoice is scaffolding only.** No live GSP/IRP provider is wired
  in (`services/einvoice_provider.py`). The retry endpoint always
  returns `409` — never a fake success. State only reaches
  `not_required`/`not_configured` through the real path; other states
  are seeded-row-only in tests.
- **State codes, never display strings.** `clinic_state`/
  `place_of_supply` are always the 2-digit codes from `constants.py`
  (`INDIA_STATES`), compared directly — never free-text names.
- **HTTPException `detail` must be a plain string.** The app's global
  handler (`app/main.py::http_exception_handler`) does `str(exc.detail)`
  — passing a dict silently becomes an ugly Python repr, not JSON.

## Frontend

- **Composables**: `useIndiaGst` (API client), `useIndiaGstStates`
  (state code/name mapping).
- **Components**: `IndiaGstBadge`, `IndiaGstInvoicePanel`,
  `IndiaGstInvoiceFormPanel`, `IndiaGstListFilter`,
  `IndiaGstUnregisteredBanner`, `SettingsCardsSlot`.
- **Pages**: `/reports/india-gst`, `/settings/india-gst`.
- **i18n**: English, Spanish, Tamil (`frontend/i18n/locales/`).
- **Utils**: `gstBadgeLogic.ts` — pure logic extracted from badge/panel
  components for unit testing (badge color/label, e-invoice color/label,
  Indian clinic detection).
- **Invoice screen**: billing's `invoices/[id]/index.vue` conditionally
  shows "GST" labels (instead of "Tax"/"VAT") via `isIndianClinic`
  computed property.
- **PDF**: `enhance_pdf_data` provides label overrides ("GST" instead of
  "VAT"/"Tax") and a structured GST breakdown HTML section. Tamil locale
  (`ta`) supported with `Noto Sans Tamil` font.

## Tests

- **Backend**: `tests/modules/india_gst/` — GST calculator, hook issue,
  uninstall guard, settings router, tax preview, reports, e-invoice
  scaffolding.
- **Frontend**: `frontend/tests/india_gst/` — `useIndiaGstStates`
  (state mapping), `gstBadgeLogic` (badge/panel pure logic).

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md` — module boundary.
- `docs/adr/0003-event-bus-over-direct-imports.md` — why this module
  uses the synchronous compliance hook instead, same exception as
  verifactu.

## Documentation

- `docs/modules/india_gst.md` — full installation & operation manual.

## CHANGELOG

See `./CHANGELOG.md`.

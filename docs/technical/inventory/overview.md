---
module: inventory
last_verified_commit: 15cd6def
---

# inventory — overview

**Stock list with cost tracking, movement ledger, audit trail and
consumable auto-deduction** (roadmap #220, core upgrade #226).

Per-item minimum quantities, atomic `SELECT … FOR UPDATE` row-locked
stock changes, an append-only `stock_movements` ledger (the audit
trail), `unit_cost` with a valuation endpoint, and automatic
deduction of linked consumables when a treatment is performed via
subscription inversion (#226).

## What it is

Clinic-scoped CRUD over the `InventoryItem` list plus several special
endpoints:

- `POST /{item_id}/adjust` applies a **relative** stock change
  (`+delta` restock / `-delta` consumption) through
  `_apply_movement` (the single write path): a `SELECT … FOR UPDATE`
  row lock, a Python-arithmetic floor check, and an append-only
  `stock_movements` row in the same transaction.
- `PATCH /{item_id}` with an absolute `stock_quantity` is a
  correction — the delta lands in the ledger too.
- `GET /valuation` totals on-hand value over active items with a
  known `unit_cost`.
- `GET /{item_id}/movements` returns the full audit trail with
  resolved actor names.

Concurrency (the PR #153 post-mortem): quantity changes go through
`SELECT … FOR UPDATE` row locking — the DB arbitrates, never app
code.  Two concurrent adjustments serialise at the row level; neither
can drive stock negative (CHECK constraint) nor lose an increment
(race-safe delta arithmetic).

## Auto-deduction (subscription inversion #226)

`inventory` exposes `apply_consumption` as a clean public primitive
that accepts pre-resolved `(item_id, quantity)` links.  The
`treatment_consumables` module owns the links table, resolves links
with its own ORM model, and calls `apply_consumption` — no raw SQL,
no inspector guard, no fail-soft branch.  Duplicate deductions for
the same treatment are silently ignored via a partial unique index
(`uq_stock_movements_consumption_ref`) and `ON CONFLICT DO NOTHING`.

## Audit trail

Every quantity change — opening stock, manual adjustments, absolute-set
corrections, auto-deductions — is recorded in the append-only
`stock_movements` ledger with reason, note, business reference and
actor.  The ledger sums exactly to on-hand stock.  Items with ledger
history can no longer be hard-deleted (409); they are deactivated
instead (`is_active`).

## Low-stock model

Each item carries a `min_quantity` threshold. An item is low when
`stock_quantity <= min_quantity` (computed property on the model; also
filterable server-side via `?low_stock=true`). The
`inventory.low_stock` event fires once per not-low → low crossing.

## Data model

- `inventory_items` — `id`, `clinic_id`, `name`, `category`
  (`consumables|equipment|office|other`, closed Literal set stored as
  `String(50)` so adding categories later is code-only),
  `unit`, `stock_quantity` numeric(12,2) with CHECK >= 0,
  `min_quantity` numeric(12,2), `unit_cost` numeric(12,2) nullable,
  `is_active` boolean (default true), `notes` (nullable),
  `created_by` (nullable FK `users.id`), timestamps.
- `stock_movements` — append-only ledger: `id`, `clinic_id`,
  `inventory_item_id` FK, `delta` numeric(12,2), `reason`
  (initial/restock/consumption/adjustment/correction), `note`,
  `reference_type`/`reference_id` (loose business reference),
  `created_by` FK, `created_at`.  Partial unique index
  `uq_stock_movements_consumption_ref` on
  `(reference_type, reference_id, inventory_item_id) WHERE
  reason = 'consumption'` for idempotent auto-deduction.

## Dependencies

`manifest.depends = []` — fully standalone. FKs point only at core
tables (clinics, users).  `treatment_consumables` FKs into this
module; the reverse subscription is handled by treatment_consumables
via subscription inversion.

## Tenancy

Every query, mutation and agent tool filters by the caller's
`clinic_id`; cross-clinic access surfaces as 404.

## Lifecycle

`installable=True`, `auto_install=False` (activated from the module
admin UI), `removable=True`. Own Alembic branch (`inventory`) rooted on
core `"0001"`. Uninstall round-trip covered by
`test_uninstall_roundtrip.py`.

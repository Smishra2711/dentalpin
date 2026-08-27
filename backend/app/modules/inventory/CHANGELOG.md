# Changelog — inventory module

## Unreleased

- fix(#101): the module's frontend adopts the useApi error contract — 400/409/422 failures the UI used to swallow now toast the backend's message; calls whose surrounding code already presents the error pass `errorToast: false` (single toast), and hand-built error reads use the shared `errorMessage`/`errorDetail` helpers.

- feat(#131): German (de) locale for the module's frontend layer.
- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.

## 0.1.0 — initial release

- Standalone stock list: clinic-scoped item CRUD with categories
  (consumables / equipment / office / other), units, per-item minimum
  quantities and notes.
- Atomic stock adjustments (`POST /{id}/adjust`) guarded at the DB
  level — CHECK constraint plus a single-UPDATE floor guard — so
  concurrent changes can never drive stock negative (PR #153 race
  post-mortem, roadmap #220).
- Low-stock awareness: `is_low_stock` per item (`stock <= min`),
  SQL-level `?low_stock=true` filter, and an
  `inventory.low_stock` event fired transactionally (ADR 0019) on each
  not-low → low crossing.
- Server-side pagination; whole-team read+write by default.
- `auto_install=False`, `removable=True`; own Alembic branch with
  uninstall round-trip and tenant-isolation tests.
- Agent tools: `list_inventory_items`, `create_inventory_item`,
  `adjust_inventory_stock` (free-prose marked).
- Review follow-ups (PR #277): fixed sidebar icon (`i-lucide-package`),
  `nav.inventory` in de/hu host locales, low-stock-event crossing test,
  error/success toasts, labelled form fields, clearable category filter,
  translated category cells, trimmed quantity decimals, arbitrary-delta
  adjust popover, responsive column hiding on narrow screens; dropped
  the unused `reason` field from the adjust payload (no movements table
  until #226).

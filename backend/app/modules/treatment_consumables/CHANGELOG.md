# Changelog — treatment_consumables module

## 0.1.0 — initial release

- Junction table linking catalog treatments to inventory items with a
  quantity per link. Pure mapping — no stock deduction (lands with the
  inventory core upgrade #226).
- DB-level FKs into `catalog` and `inventory` (CI-enforced against the
  `depends` declaration); unique (clinic, treatment, item) triple.
- Create validates both endpoints inside the caller's clinic (404 on
  foreign rows) and answers 409 on duplicate pairs.
- `/treatment-consumables` page: history table with resolved names from
  both modules, search-based pickers fed by one permission-gated
  `link-options` endpoint, quantity editing, unlink confirmation.
- Agent tool `get_treatment_consumables` (READ, cloud-eligible).
- `auto_install=False`, `removable=True`, own Alembic branch
  (`treatment_consumables`), uninstall round-trip + tenant isolation +
  duplicate-pair tests.
- Default roles: admin full, dentist read-only.
- Docs: technical overview/events/permissions pages, user manual en+es
  with real `last_verified_commit`, module CHANGELOG, CLAUDE.md tools
  section.

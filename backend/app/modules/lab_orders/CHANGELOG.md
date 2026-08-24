# Changelog — lab_orders module

## 0.1.0 — initial release

- Lab work order CRUD with status tracking (`sent` → `in_progress` →
  `ready` → `received` / `cancelled`), auto-stamping `received_date`.
- Patient + laboratory-contact linkage, clinic-scoped on every query,
  validation and agent tool; display-name enrichment.
- Prosthodontic fields: impression type, antagonist information and
  Vita Classical shade.
- Status changes publish `lab_order.status_changed` transactionally
  (ADR 0019); no bundled subscriber.
- Agent tools: `list_lab_orders`, `create_lab_order`,
  `update_lab_order_status`.
- `auto_install=False`, `removable=True`; own Alembic branch with
  uninstall round-trip, tenant-isolation coverage, HTTP date-free CRUD
  tests.
- EN/ES/FR/PT/TA locales; technical overview/events/permissions pages;
  bilingual user manual; searchable sidebar entries gated by role.


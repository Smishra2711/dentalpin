## Summary

Lab work orders (roadmap #221, phase 3): record work sent to an external dental laboratory for a patient and track it through `sent` -> `in_progress` -> `ready` -> `received` / `cancelled`.

- Backend: `lab_orders` table + CRUD/status API under `/api/v1/lab_orders/`, clinic-scoped service and agent tools, patient/contact linkage validated per-tenant.
- Frontend: `/lab-orders/new` form (patient search, lab contact picker, prosthodontic fields incl. Vita Classical shades) and `/lab-orders` status-tracking list with inline status changes. EN/ES/FR/PT/TA locales.
- Agent tools: `list_lab_orders`, `create_lab_order`, `update_lab_order_status` (READ/WRITE categories, clinic_id scoped).

## Checklist

- [x] One module per PR (template: patient_relationships)
- [x] `clinic_id` filter on every query and tool handler
- [x] Own Alembic branch (`branch_labels=("lab_orders",)`), `depends_on = ("pat_0003", "con_0001")` for the cross-module FKs; never touches another module's chain
- [x] Event published transactionally per ADR 0019 (inside the update transaction, publisher session passed as `db=`); `EventType.LAB_ORDER_STATUS_CHANGED` registered
- [x] Uninstall round-trip test (branch-relative `@-1` walk; asserts no other module's tables are affected)
- [x] `auto_install=False` — activated from the admin UI
- [x] Docs: `docs/technical/lab_orders/{overview,events,permissions}.md`, user manual en+es (`screens/index.md`, `screens/new.md`), module CHANGELOG.md + CLAUDE.md, modules/events catalogs updated
- [x] Green CI (verified locally: ruff check+format whole tree, eslint, nuxt typecheck host+all layers)

## Notes

- `manifest.depends = ["patients", "contacts"]`; migration ordering is declared separately via alembic `depends_on`.
- Agent-initiated orders set `created_by = null` (AgentContext carries no user identity); the actor trail lives in agent_audit_logs.

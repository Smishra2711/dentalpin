## Summary

Roadmap **#219 — phase 3: item tasks / staff handoff board**. Internal
tasks and handoff notes between clinic staff ("call patient X back",
"prepare implant kit for room 2"), tracked through a guarded status
lifecycle.

- Backend: `staff_tasks` table + CRUD/status API under
  `/api/v1/staff_tasks/` with a guarded state machine
  (`open → claimed → done`, `cancelled` escape hatch, 422 on illegal
  moves). Claiming an unassigned task assigns the claimer; `done`
  stamps `completed_at`.
- Events: `staff_task.created` / `staff_task.status_changed`
  (`EventType.STAFF_TASK_*`), published transactionally per ADR 0019 —
  after flush, inside the caller's transaction, publisher session as
  `db=`. No bundled subscriber.
- Agent tools: `list_staff_tasks` (READ), `create_staff_task`,
  `update_staff_task_status` (WRITE) — all clinic_id scoped, native
  UUID returns for the registry's jsonify.
- Frontend: `/tasks` board page — status filter, create modal
  (priority + due date), inline claim/close per row, delete with
  confirmation, server-side pagination. Sidebar entry gated on
  `staff_tasks.read`, label defined in all five HOST locale files.
- EN/ES/FR/PT/TA locales.

## Contribution checklist

- [x] One module per PR (template: patient_relationships)
- [x] `clinic_id` filter on every query and tool handler (isolation test included)
- [x] Own Alembic branch — `branch_labels=("staff_tasks",)`, rooted on core `0001`; FKs only to core tables so no `depends_on`; never touches another module's chain
- [x] Transactional events (ADR 0019): publish after flush, before commit, `db=` passed
- [x] Uninstall round-trip test (`removable=True`) — walks `staff_tasks@-1` until tables are gone, asserts nothing else is affected
- [x] `auto_install=False` — activated from the admin UI
- [x] Docs: `docs/technical/staff_tasks/{overview,events,permissions}.md`, user manual en+es (`index.md` + `screens/tasks.md`), module CHANGELOG.md (single initial-release entry) and CLAUDE.md; modules/events catalogs updated

## Design notes

- `role_permissions`: whole team read+write by default — the board is
  collaboration infrastructure and holds no sensitive data (same
  breadth precedent as patient_relationships).
- Agent-initiated tasks set `created_by = null` (AgentContext carries
  no user identity); actor trail lives in agent_audit_logs.
- Status transitions are validated server-side; `done` stamps
  `completed_at`, and re-opening from `done` is rejected with 422.

## Tests

- Service lifecycle (claim assigns claimer, done stamps completion,
  terminal-state guard), tenant isolation across clinics, status
  filters, delete.
- HTTP-level: POST/GET/PATCH over the router, filter narrowing, 422 on
  illegal transition.
- Alembic uninstall round-trip (branch-relative `@-1` walk).

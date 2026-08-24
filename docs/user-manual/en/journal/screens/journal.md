---
module: activity_journal
screen: journal
route: /journal
related_endpoints:
  - GET /api/v1/activity_journal
  - GET /api/v1/activity_journal/{entry_id}
related_permissions:
  - activity_journal.read
related_paths:
  - backend/app/modules/activity_journal/frontend/pages/journal/index.vue
last_verified_commit: 03f4c5f1
---

# Activity log

Read-only list of everything the journal recorded, newest first. Each
row shows when it happened, which event produced it, who performed it
(a dash means the source event carried no user attribution), the
affected patient and the event namespace (source).

## What you can do

- **Filter by event type** — type a value such as
  `appointment.scheduled` or `budget.sent`.
- **Filter by date range** — restrict to a `From` / `To` window.
- **Paginate** — 20 rows per page via the pagination bar.
- **Inspect a payload** — click a row to open a read-only view of the
  exact data the event carried.

Entries cannot be edited, deleted or created manually: they are written
automatically inside the transaction of the operation they describe, so
the log is always consistent with what actually happened.

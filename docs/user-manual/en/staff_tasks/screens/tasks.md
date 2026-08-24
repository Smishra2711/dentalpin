---
module: staff_tasks
screen: tasks
route: /tasks
related_endpoints:
  - GET /api/v1/staff_tasks/
  - POST /api/v1/staff_tasks/
  - PATCH /api/v1/staff_tasks/{task_id}
  - DELETE /api/v1/staff_tasks/{task_id}
related_permissions:
  - staff_tasks.read
  - staff_tasks.write
related_paths:
  - backend/app/modules/staff_tasks/router.py
  - backend/app/modules/staff_tasks/frontend/pages/tasks/index.vue
last_verified_commit: e4146c9b
---

# Staff task board

## What this screen does

- **Filter** by status (Open / Claimed / Done / Cancelled).
- **New task** — modal with title, optional details, priority
  (Low / Normal / High) and an optional due date.
- **Claim and close inline** — each row carries a status selector;
  claiming an unassigned task assigns you, and marking it **Done**
  stamps the completion time.
- **Delete** with a confirmation dialog.
- **Pagination** — server-side, 20 rows per page.

## Statuses

`Open → Claimed → Done`, with `Cancelled` as an escape hatch. An illegal
move returns `422`.

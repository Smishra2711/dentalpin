---
module: inventory
screen: inventory
route: /inventory
related_endpoints:
  - GET /api/v1/inventory/
  - GET /api/v1/inventory/{item_id}
  - POST /api/v1/inventory/
  - PATCH /api/v1/inventory/{item_id}
  - POST /api/v1/inventory/{item_id}/adjust
  - DELETE /api/v1/inventory/{item_id}
related_permissions:
  - inventory.read
  - inventory.write
related_paths:
  - backend/app/modules/inventory/router.py
  - backend/app/modules/inventory/frontend/pages/inventory/index.vue
last_verified_commit: INVENTORY_HEAD
---

# Stock list

## What this screen does

- **Filter** by category and toggle **low stock only**
  (`stock <= min`).
- **Add item** — modal with name, category, unit, initial stock,
  minimum threshold and optional notes.
- **Quick +/- adjustments** per row — each click is an atomic server-side
  change; an adjustment that would drive stock below zero is rejected
  with `409`.
- **Edit item** — opens the same modal pre-filled (absolute quantity
  set, e.g. after a manual count).
- **Delete** with confirmation.
- **Pagination** — server-side, 20 rows per page.

## Status badge

Each row shows `OK` or `Low` depending on whether current stock has
reached the minimum threshold.

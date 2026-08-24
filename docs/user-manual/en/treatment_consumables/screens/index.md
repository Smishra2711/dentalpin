---
module: treatment_consumables
screen: index
route: /treatment-consumables
related_endpoints:
  - GET /api/v1/treatment_consumables
  - POST /api/v1/treatment_consumables
  - PATCH /api/v1/treatment_consumables/{id}
  - DELETE /api/v1/treatment_consumables/{id}
  - GET /api/v1/treatment_consumables/link-options
related_permissions:
  - treatment_consumables.read
  - treatment_consumables.write
related_paths:
  - backend/app/modules/treatment_consumables/frontend/pages/treatment-consumables/index.vue
last_verified_commit: 47983b05
---

# Treatment consumables

Maps each catalog treatment to the inventory items it uses, and how
many of them (e.g. root canal → 2 anesthetic vials). Pure mapping:
stock is **not** deducted automatically.

## What you can do

- **Link a consumable**: search for a treatment, search for an
  inventory item, set the quantity, confirm. Both sides are validated
  against your clinic; duplicates of the same pair are rejected.
- **Edit quantity** on any existing link.
- **Unlink** with confirmation.
- The history table shows every link with resolved names from both
  modules, newest first, paginated.

## Who can use it

Admins manage links; dentists have read access. Requires the
`inventory` module to be installed.

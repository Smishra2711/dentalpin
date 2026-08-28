---
module: inventory
last_verified_commit: 15cd6def
---

# inventory — events

## Emitted

### `inventory.low_stock`

Fired once per **not-low → low crossing**: when an item is created
already at/below its threshold, or when the first update/adjustment
crosses it. Repeated adjustments while still low do not re-fire.
Constant: `EventType.INVENTORY_STOCK_LOW`. Payload:

- `clinic_id`
- `item_id`
- `name`
- `category`
- `stock_quantity` (float)
- `min_quantity` (float)

## Consumed

None — auto-deduction on `odontogram.treatment.performed` is handled
by the `treatment_consumables` module via subscription inversion
(#226): it reads its own links table, resolves links with its own ORM
model, and calls `InventoryService.apply_consumption` as a clean
public primitive.  See `docs/technical/treatment_consumables/events.md`.

## Transaction model

Published **inside** the creating/updating transaction — after flush,
before the caller's commit — with the publisher's session (`db=`) per
ADR 0019, so a future transactional subscriber (notifications,
procurement) sees the row and rolls back with it.

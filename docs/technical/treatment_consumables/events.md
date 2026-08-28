# treatment_consumables — events

## Emitted

None — link lifecycle needs no asynchronous reactions.

## Consumed

### `odontogram.treatment.performed`

Constant: `EventType.ODONTOGRAM_TREATMENT_PERFORMED`. Handler:
`events.on_treatment_performed` (#226).

Payload keys read: `clinic_id`, `catalog_item_id` (both required —
missing/malformed means no-op), `treatment_id` (idempotency reference;
malformed degrades to an unreferenced deduction), and
`performed_by`/`changed_by`/`user_id` (actor attribution, first match).

The handler resolves this module's own links for the performed catalog
item and calls `InventoryService.apply_consumption` with the resolved
`(inventory_item_id, quantity)` pairs — **subscription inversion**:
this module already depends on `inventory`, so subscribing here (rather
than inventory reading this module's table) avoids both a dependency
cycle and raw cross-module SQL that CI cannot see. Inventory has no
knowledge of treatment_consumables; it just applies pre-resolved
deductions, clamped at zero, idempotent per treatment (see
`docs/technical/inventory/events.md` and `overview.md`).

## Transaction model

Transactional handler (ADR 0019): runs on the publisher's session, so a
rolled-back treatment performance rolls its deductions back with it.

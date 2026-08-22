---
module: lab_orders
last_verified_commit: 0000000
---

# lab_orders — events

## Emitted

### `lab_order.status_changed`

Published after a lab order is committed with a different status. Payload:

- `clinic_id`
- `order_id`
- `patient_id`
- `status`
- `work_type`
- `tooth_reference`

The module ships no subscriber. Optional modules may consume the event without importing `lab_orders` directly.

## Transaction model

There are no bundled event handlers in this module, so ADR 0019's transactional-handler contract is not required here. The status-change event is published only after the status update transaction has committed.

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

# Lista de inventario

## Qué hace esta pantalla

- **Filtrar** por categoría y activar **solo stock bajo**
  (`stock <= min`).
- **Añadir artículo**: modal con nombre, categoría, unidad, stock
  inicial, mínimo y notas opcionales.
- **Ajustes rápidos +/-** por fila: cada pulsación es un cambio atómico
  en el servidor; un ajuste que llevaría el stock por debajo de cero se
  rechaza con `409`.
- **Editar artículo**: abre el mismo modal precargado (asignación
  absoluta de cantidad, p. ej. tras un recuento manual).
- **Eliminar** con confirmación.
- **Paginación** en servidor, 20 filas por página.

## Insignia de estado

Cada fila muestra `OK` o `Bajo` según si el stock actual ha alcanzado
el mínimo.

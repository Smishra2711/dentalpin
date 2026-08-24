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

# Consumibles por tratamiento

Asocia cada tratamiento del catálogo con los artículos de inventario
que utiliza, y cuántos (p. ej. endodoncia → 2 viales de anestésico).
Mapeo puro: el stock **no** se descuenta automáticamente.

## Qué puedes hacer

- **Vincular un consumible**: busca un tratamiento, busca un artículo
  de inventario, indica la cantidad y confirma. Ambos lados se validan
  contra tu clínica; los pares duplicados se rechazan.
- **Editar la cantidad** de cualquier vínculo existente.
- **Desvincular** con confirmación.
- La tabla histórica muestra todos los vínculos con los nombres
  resueltos de ambos módulos, del más reciente al más antiguo,
  paginados.

## Quién puede usarlo

Los administradores gestionan los vínculos; los dentistas tienen
acceso de lectura. Requiere el módulo `inventory` instalado.

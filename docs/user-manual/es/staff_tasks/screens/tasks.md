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

# Tareas del equipo

## Qué hace esta pantalla

- **Filtrar** por estado (Abierta / Reclamada / Hecha / Cancelada).
- **Nueva tarea**: modal con título, detalles, prioridad (Baja / Normal
  / Alta) y fecha límite opcional.
- **Reclamar y cerrar en línea**: cada fila tiene un selector de estado;
  reclamar una tarea sin asignar te asigna como responsable, y marcarla
  **Hecha** registra la hora de finalización.
- **Eliminar** con confirmación.
- **Paginación** en servidor, 20 filas por página.

## Estados

`Abierta → Reclamada → Hecha`, con `Cancelada` como salida. Un movimiento
no permitido devuelve 422.

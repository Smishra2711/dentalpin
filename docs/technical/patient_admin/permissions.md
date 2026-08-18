---
module: patient_admin
last_verified_commit: 0000000
---

# patient_admin — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `patient_admin.relationships.read` | View a patient's relationships | `GET /api/v1/patients/{patient_id}/relationships` |
| `patient_admin.relationships.write` | Create, update, delete a relationship | `POST /relationships`, `PUT /relationships/{id}`, `DELETE /relationships/{id}` |

Default role mapping:

| Role | Permissions |
|------|-------------|
| `admin` | all (`*`) |
| `dentist` | read, write |
| `hygienist` | read only |
| `assistant` | read, write |
| `receptionist` | read, write |

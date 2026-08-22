# Changelog — lab_orders module

## Unreleased

- Added lab work order CRUD and status tracking for external laboratory work.
- Added patient and contact linkage with clinic-scoped validation and display-name enrichment.
- Added prosthodontic fields: impression type, antagonist information, and Vita Classical shade.
- Added EN/ES/FR/PT/TA frontend locales and technical/user documentation.
- `auto_install` is disabled so the optional module is activated from the admin UI.
- Added tenant-isolation and Alembic uninstall round-trip coverage.
- POST now returns 201 and DELETE returns 204.

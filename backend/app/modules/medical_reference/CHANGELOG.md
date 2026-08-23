# Changelog — medical_reference module

## Unreleased (0.4.0)

- **patients_clinical integration** — the lists now have a real reader:
  - `patients_clinical` gained a nullable `reference_id` UUID on its four
    history tables (own migration, no DB-level FK), exposed in its
    schemas.
  - `MedicalHistoryForm.vue` exposes a slot per name input
    (`patients_clinical.medical_history.*_name`) with the plain input as
    fallback; this module registers its searchable combobox into the
    slots from its own plugin (dependency direction preserved — no
    core-module → community-component imports).
  - Per-patient flags surface by registering into the existing
    `patient.header.alerts` slot; patients_clinical's banner is untouched.
  - End-to-end regression test for `GET /patients/{id}/flags`
    (`test_patient_flags.py`) — two interacting reference-linked
    medications → flag returned.
- Dropped `is_apci` from `ReferenceDisease` (model/schema/migration/
  settings UI). CNAM/APCI is country-specific compliance hardcoded into a
  Spain-first product's disease model; may return as an optional
  follow-up modeled on india_gst's compliance_section approach (#210).
- `auto_install=False` — new optional modules ship manual-install;
  activated from the admin UI.

## Prior review fixes (same release)

- `get`, `get_interaction`, and `get_contraindication` now filter by
  `clinic_id` in addition to the row's own id. These back every
  update/deactivate endpoint in the module (allergies, medications,
  surgeries, diseases, interactions, contraindications) — previously
  any clinic could rename or deactivate another clinic's reference data
  by guessing/enumerating an id.
- `depends` now declares `patients` explicitly — `router.py` imports
  `patients.service.PatientService` directly, which needs its own
  declared entry regardless of `patients_clinical`'s own transitive
  dependency on it.
- `dentist` now has `write` (was read-only). The frontend's reference
  search already called `create()` when a dentist typed a new allergy
  that wasn't in the list yet — with write restricted to admin, that
  silently 403'd with no fallback. Matches the precedent already set
  by `patients_clinical`'s own role permissions for the same category
  of clinical data.
- Added `CLAUDE.md` and this file (module had neither).
- Added `tests/modules/medical_reference/test_tenant_isolation.py`.

## 0.3.0 (prior)

- Interaction and contraindication tables, plus `get_patient_flags` for
  active per-patient warnings.

## 0.2.0 (prior)

- Surgery reference list.

## 0.1.0 (prior)

- Initial schema: allergy, medication, disease reference lists.

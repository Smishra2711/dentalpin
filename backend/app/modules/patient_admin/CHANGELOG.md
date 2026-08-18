# Changelog — patient_admin module

## Unreleased

- `get_relationship` now filters by `clinic_id` in addition to
  `relationship_id`, matching every other lookup in this module. Not
  previously exploitable (the router's own `patient_id` match check
  blocked it), but a future caller that reached `get_relationship`
  directly would have inherited an unscoped lookup — closed as
  defense in depth.
- `padm_0001`'s migration now declares `depends_on = ("pat_0003",)`
  for its FK to `patients.id`, and its docstring's claim of "no
  dependency on another module's branch" is corrected — `patients`
  lives on the unlabeled/core chain, not inside `patient_admin`'s own
  branch, so this dependency needed to be explicit.
- Added `CLAUDE.md` and this file.
- Added a tenant-isolation test for `list_relationships`.

## 0.2.0 (prior)

- `padm_0002`: dropped the insurance exemption status table —
  exemption is now a computed flag off systemic-disease reference
  data, not manually entered here.
- Initial schema (`padm_0001`): patient-to-patient relationships with
  a derived inverse label at read time.

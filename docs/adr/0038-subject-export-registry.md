# 0038 — GDPR subject export registry for provably complete exports

- **Status:** accepted
- **Date:** 2026-09-29
- **Deciders:** maintainers (@martinezsalmeron, @ZoliQua)
- **Tags:** gdpr, compliance, registry, export, architecture

## Context

Issue #475 identifies a real gap: employee personal data in payroll, staff tasks, activity traces, and staff attendance has no served export or erasure path. Article 15 does not distinguish patients from employees, so the product cannot serve a complete subject-access request for a non-patient today.

The existing `gdpr` module is a patient-shaped DSR, consent, retention, erasure-audit, and breach register. `GdprRequest.patient_id` and `ErasureAuditLog.patient_id` are already nullable; only `PatientConsent.patient_id` is non-nullable. `RetentionPolicy` already exists and already gates erasure eligibility. The follow-up design therefore has to generalize a table with substantially the right shape, not invent patient-only tracking from nothing.

## Decision

Portability exports are assembled through a `SubjectExportRegistry` that enumerates registered per-module contributors and pulls their data; a missing or failing contributor fails the export loudly rather than producing a silently partial artefact.

The contributor contract lives in core, not in `gdpr`, following the `get_tools()` shape:

- `BaseModule` gains an optional `get_subject_export_contributors()` (default `[]`). Core collects it from **active** modules (ADR 0020), the same way `ToolRegistry` collects `get_tools()` (`backend/app/core/agents/tools/registry.py:41`).
- `gdpr` pulls from that core registry. Contributor modules (`payroll`, `staff_attendance`, `staff_tasks`, `activity_journal`, …) keep `depends: []`; none of them is forced to install `gdpr`, which stays optional.
- **"Missing" is defined by a manifest declaration, not by registration.** A module that stores personal data about a subject declares it in its manifest (e.g. `"personal_data_subjects": ["employee"]`). A declared subject with no matching contributor is a missing contributor: a CI test fails, and the export refuses at runtime.

Scope: this ADR fixes the export contract. Erasure (including the recorded "retained under legal obligation" outcome via `RetentionPolicy.legal_hold_until`) reuses the same contributors and is specified when it is implemented.

The event bus keeps its existing job: announcing completed GDPR actions. It is not the export assembly mechanism.

## Consequences

### Good

- An export can state its own completeness: every registered holder for the subject answered, or there is no export.
- `gdpr` never imports contributor modules, preserving the module boundary.
- The existing retention machinery can be reused or generalized instead of duplicated.
- Contributor modules take no dependency on `gdpr`, so installing payroll does not force GDPR tooling on a clinic.
- The same pull-shaped precedent already exists in `BillingComplianceHook`, `PrescriptionComplianceHook`, tool registration, and provider registration; tool registration (`get_tools()`) is the one whose dependency direction matches.

### Bad / accepted trade-offs

- This adds a core hook and a contributor contract for a feature that does not exist yet.
- Completeness is only as good as the manifest declaration: a module that stores personal data without declaring it stays invisible. Review of new models must check the declaration.
- Export assembly becomes synchronous pull work, so contributor failures block the response by design.

## Alternatives considered

- **Event-bus fan-out for export assembly** — rejected. A fan-out cannot prove that every holder answered: an unregistered, slow, or raising subscriber produces a partial artefact indistinguishable from a complete one.
- **Registry inside `gdpr` (the `BillingHookRegistry` shape)** — rejected. Contributors would need `depends: ["gdpr"]` to register, turning an optional compliance module into a de facto requirement of payroll, attendance, and activity journal. The billing precedent works because country modules naturally depend on billing; here the dependency would point the wrong way.
- **A separate employee-data module** — rejected. It would duplicate DSR tracking, retention policy shape, audit semantics, and consent-adjacent concepts instead of generalizing the existing records.

## How to verify the rule still holds

- After implementation: `rg "class SubjectExportRegistry"` must resolve to one canonical registry under `backend/app/core/`.
- `rg '"gdpr"' backend/app/modules/*/__init__.py` finds no contributor module that lists `gdpr` in `depends` for this purpose.
- A test fails when an active module declares `personal_data_subjects` without a matching contributor.
- Tests cover a missing contributor and a raising contributor; both must refuse the export loudly.
- No new event names are introduced by this ADR.

## References

- Issue #475.
- `backend/app/modules/gdpr/models.py`
- `backend/app/modules/gdpr/migrations/versions/gdpr_0001_initial.py`
- `backend/app/modules/billing/hooks.py`
- `backend/app/modules/prescriptions/hooks.py`
- `backend/app/core/plugins/base.py` (`get_tools()`, `on_activate()`)
- `backend/app/core/agents/tools/registry.py:41`
- ADR 0020 (module live iff installed)
- `backend/app/core/llm/registry.py`

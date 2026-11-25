# Patient Treatment Relationship Source Decision

**Decision ID:** PH0-WP-01-DEC-PTCR-01  
**Status:** APPROVED  
**Approved:** 25 November 2026  
**Scope:** Phase 0 practitioner-to-patient treatment relationship evidence

## Decision

For MedAeterna Phase 0, `public.patient_care_team` is the authoritative source of an **active practitioner treatment assignment** between a patient, a verified practitioner profile, and an organization.

This decision is deliberately narrow. It does not make `patient_care_team` a patient-approved read-grant table, a consent record, a general role-assignment table, or an emergency/break-glass mechanism.

## Source schema

The reviewed repository migration `backend/supabase/migrations/20261118135846_remote_schema.sql` defines `patient_care_team` with:

- `id`
- `patient_id`
- `practitioner_id`
- `organization_id`
- `role`
- `status` (allowed values: `active`, `inactive`, `suspended`)
- `start_date` (timestamp with time zone)
- `end_date` (timestamp with time zone)
- `assigned_by`, `notes`, `metadata`, `fhir_resource`, `created_at`

The table has a unique constraint on `(patient_id, practitioner_id, organization_id)`. The migration enables RLS. Runtime authorization must read it through the trusted backend/service-role client; this decision does not grant client-side table access or replace RLS.

## Evidence construction and decision rules

The trusted authorization adapter may construct `RelationshipEvidence(kind="active_treatment", ...)` only after all of the following have been verified:

1. The requested patient exists and the evidence row's `patient_id` exactly matches the requested patient.
2. The authenticated actor has exactly one unambiguous practitioner profile linked by `practitioners.profile_id = authenticated user id`. Do not accept `practitioners.id = user id` as an alternate identity link and do not select an arbitrary first row. Missing or multiple matches deny access.
3. The evidence row's `practitioner_id` exactly matches that verified practitioner profile's `id`.
4. The evidence row's `organization_id` exactly matches the organization context authorized for the request. Where the patient record has a non-null `organization_id`, it must also match the relationship row's organization.
5. `status` is exactly `active`.
6. The decision time is timezone-aware; `start_date` is absent or not later than the decision time; `end_date` is absent or strictly later than the decision time. An end date is exclusive.
7. The row was fetched from `public.patient_care_team` using the trusted backend client and all identifiers/lifecycle fields were validated. Only then may the adapter set `source_verified=True`.

A missing, malformed, ambiguous, future-dated, ended, inactive, or suspended relationship is not qualifying evidence. Authorization must fail closed. A patient-care-team row does not by itself override SPEC-03 role/action permissions, SPEC-05 consent requirements, workflow constraints, field filtering, or database controls.

## Separation from other evidence

- `public.patient_access_grants` remains the separately selected canonical source for patient-approved, resource-family-scoped **read grants** under SPEC-06. Its migration/runtime integration remains separate and pending. Do not infer its existence or query it before its schema is installed and verified.
- `consent_records` is not an independent treatment assignment and must not be used as a substitute for an active treatment relationship. Consent evaluation remains governed by SPEC-05 and must be enforced separately where applicable.
- `clinicians_patients`, `care_teams`, and other legacy representations are not fallback treatment authority. Remove the legacy authorization fallback after all callers have been reconciled.
- Emergency/break-glass evidence remains prohibited for Phase 0 under the applicable security policy.

## Lifecycle and schema limitations

The reviewed schema supports effective periods through `start_date` and `end_date`, and non-active states through `inactive` and `suspended`. It does not define a distinct `revoked` status or `revoked_at` field. The implementation must not invent either. A revocation/termination workflow must use an approved transition to a non-active state and/or set `end_date` in accordance with the domain lifecycle. If the product requires an auditable explicit revocation timestamp/reason, that is a separately reviewed schema change and migration; it is not implied by this decision.

The unique constraint on the patient/practitioner/organization tuple also means this schema is not yet a full historical assignment ledger for repeated assignments of the same tuple. Do not silently weaken or work around that constraint. If historical episodes are required, propose a separate schema evolution with explicit migration and data-retention semantics.

## Implementation work authorized on the patient-relationship branch

1. Make `authorize_patient_access()` the trusted evidence-loading adapter and delegate the final SPEC-04 relationship decision to `evaluate_patient_relationship()`.
2. Resolve practitioner identity only through a unique `profile_id` link to the authenticated actor.
3. Load and validate active treatment evidence from `patient_care_team`, including organization and effective-period checks.
4. Keep patient grants and consent evaluation separate; do not query an uninstalled grant table.
5. Reconcile all call sites before removing legacy relationship fallback.
6. Add positive and negative tests, including identity ambiguity, patient/organization mismatch, future start, exclusive end, inactive/suspended (revoked/terminated) evidence, and patient self-access.
7. Preserve the independent follow-up for the invalid-token classifier: a credential-like error code with HTTP 5xx must map to 503, not 401.

## Environment and release boundary

This approval authorizes local code, tests, and documentation changes on `security/ph0-wp01-patient-relationship-integration` only. It does **not** authorize a production migration, production data access, Storage change, deployment, or closure of any SEC finding. Phase 0 remains STOP / NOT ACCEPTED pending the existing release gates and separate exact-scope production authorization.

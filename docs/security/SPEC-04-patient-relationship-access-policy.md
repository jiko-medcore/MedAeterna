# SPEC-04: Patient Relationship Access Policy

**Status:** Patient-to-practitioner relationship semantics and an executable reference evaluator are complete. Route-by-route enforcement and database policy verification remain remediation work; this specification does not claim those controls are deployed.

**Order 5 approval (21 November 2026):** Approved for implementation by the designated MedAeterna technical/security owner for the documented decisions only; not production acceptance. Undocumented choices remain fail-closed. See [PH0-WP-06 policy approval record](PH0-WP-06-SPEC-approval-and-consent-access-model.md).

## Purpose and boundaries

SPEC-04 defines when a practitioner has a relationship to a patient that can satisfy the relationship gate in SPEC-03. It applies to clinical history, encounters, observations, conditions, prescriptions, laboratory results, and clinical documents.

This policy is independent of role/action permission. A relationship does not grant an action that SPEC-03 denies. Authentication, current role assignment and organization scope (SPEC-01/02), consent (SPEC-05), clinical workflow, purpose, field filtering, and database grants/RLS are separate required checks. Every layer must allow the request.

Organization membership, employment, a practitioner profile, an organization-admin role, prior treatment, patient search results, or a client-supplied patient/practitioner/organization ID do not establish a patient-care relationship. System administrators and organization administrators receive no clinical relationship by virtue of their administrative role. SPEC-08 prohibits system-administrator patient access and break-glass access in the current Phase 0 policy; no emergency clinical relationship is inferred.

## Relationship decisions

### Patient self-access

- The authenticated patient may read only clinical resources linked to that patient's verified patient identity, and only the permitted resource representation defined by SPEC-03 and the resource workflow.
- A patient relationship never authorizes a patient to create, update, delete, administer, or retry a clinical record. Patient-entered profile/history workflows are separate resources and require their own SPEC-03 rule.
- A patient identifier in a URL or request body is not proof of ownership. The backend must resolve the authenticated user-to-patient identity and compare it to the resource's persisted patient ID.

### Practitioner access

Two relationship paths can satisfy practitioner **read** access:

1. **Active treatment assignment:** an active assignment designates this practitioner as part of the patient's treating team for the exact organization associated with the resource.
2. **Approved patient read grant:** the patient has approved a grant for this practitioner, this organization, the specific clinical resource family, and read. The grant must be active at decision time and must not be revoked or expired.

Only an active treatment assignment can satisfy the relationship gate for ordinary clinical **create** or **update**. The action must still pass the role/action policy and the resource's workflow, authorship, provenance, and consent checks. A patient read grant is read-only and cannot become a treatment assignment or authorize a write.

An active treatment assignment must match the authenticated practitioner's verified practitioner identity, the exact patient, and the exact organization on the stored resource. If the resource has a persisted patient, practitioner, organization, encounter, order, or author reference, the backend must load and validate it before authorization; request payload values cannot replace stored relationships. A practitioner assignment in Organization A never authorizes access to Organization B.

### Resource/action relationship matrix

The table describes relationship eligibility only. “Role/action + workflow” means SPEC-03 must also allow the action, and its required resource workflow and consent checks must pass.

| Clinical resource | Patient read | Practitioner read | Practitioner create/update relationship gate | Delete/administer/retry |
|---|---|---|---|---|
| Clinical history | Verified owner | Active treatment assignment or resource-scoped approved patient read grant | Active treatment assignment + SPEC-03 workflow | No relationship grants these actions |
| Encounter | Verified owner | Active treatment assignment or resource-scoped approved patient read grant | Active treatment assignment; actor, patient, organization, encounter status, and permitted fields must match the workflow | No relationship grants these actions |
| Observation | Verified owner | Active treatment assignment or resource-scoped approved patient read grant | Active treatment assignment + author/workflow validation; corrections preserve provenance | No relationship grants these actions |
| Condition | Verified owner | Active treatment assignment or resource-scoped approved patient read grant | Active treatment assignment + author/workflow validation; resolution/correction is an update, not deletion | No relationship grants these actions |
| Prescription / medication request | Verified owner | Active treatment assignment or resource-scoped approved patient read grant | Active treatment assignment plus prescribing authority/workflow; updates are constrained to the permitted medication workflow | No relationship grants these actions |
| Laboratory result | Verified owner | Active treatment assignment or resource-scoped approved patient read grant | Active assignment to the exact laboratory order/specimen for the performing or ordering workflow; a general treatment assignment alone is insufficient | No relationship grants these actions |
| Clinical document | Verified owner | Active treatment assignment or resource-scoped approved patient read grant | Active treatment assignment + document purpose, ownership, and workflow validation | No relationship grants these actions |

An approved read grant is valid only for `read`, only for resource families and organization explicitly present in trusted grant data, and only for the named practitioner and patient. It does not override required consent under SPEC-05. Missing grant scope, patient, recipient, organization, approval, or time validity fails closed.

Laboratory result creation or update requires a relationship bound to the exact laboratory order or specimen being handled, in addition to a permitted laboratory role/action and workflow. A practitioner who can read the patient's other records does not thereby gain result-writing authority.

## Lifecycle and evidence requirements

- Relationship evidence must be loaded from an approved server-side source and tied to the current authenticated actor. Evidence copied from request fields or user-editable metadata is untrusted.
- Treatment assignments must be active at the time of the decision, not future-dated, and not ended. Revoked, inactive, expired, future, malformed, ambiguous, or mismatched assignments do not authorize access.
- Patient grants must be approved and effective now, must identify one patient, one practitioner, one organization, resource-family scope, and read action. Pending, revoked, expired, unscoped, recipient-mismatched, and organization-mismatched grants deny.
- A missing/ambiguous patient identity link or practitioner profile link denies. An assignment's validity is not inferred from a practitioner role or organization membership.
- A patient-care relationship does not replace consent. If consent is required for the requested purpose/resource/recipient, SPEC-05 must independently pass; a relationship or patient grant cannot silently override that decision.
- Relationship lookup and protected resource access must use a trusted execution path. Service-role access does not itself satisfy the relationship check.
- Database access controls remain an independent layer: table grants decide which operations a database role can perform, while RLS restricts which rows those operations may affect. Supabase's guidance requires both for exposed tables and notes that `service_role` bypasses RLS ([RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security)).

## Relationship source reconciliation

The repository contains incompatible relationship representations: application code references `patient_access`, while a standalone SQL file defines `patient_access_grants`; local Supabase has neither grant table installed. Local Supabase also contains `patient_care_team`, `clinicians_patients`, and `care_teams` with differing columns and lifecycle fields. SPEC-06 selects `public.patient_access_grants` as the canonical explicit patient-approved read-grant table and defines a migration path. It does not select a canonical treatment-assignment table or claim the grant table is installed.

Until that reconciliation, no legacy row is assumed to be approved, active, scoped, or equivalent to another source merely because it exists. Emergency grant values in the legacy schema are specifically not accepted by this policy; SPEC-08 prohibits break-glass access in the current Phase 0 policy.

## Executable policy and tests

The pure reference evaluator is `backend/app/core/patient_relationship_policy.py`. It accepts normalized evidence supplied by trusted backend logic and denies by default. It does not query Supabase, resolve identity links, verify role assignment, evaluate consent, filter fields, or secure a FastAPI route by itself.

Focused tests are in `backend/tests/core/test_patient_relationship_policy.py`. The suite checks the defined resource/action combinations, patient self-read boundaries, patient-grant read scoping, identity and organization matching, assignment status/time validity, source verification, emergency/membership denial, practitioner identity linking, laboratory order binding, and unsupported actions/roles.

## Acceptance criteria

- [x] The qualifying relationship types and their required patient, practitioner, organization, status, and time boundaries are explicit.
- [x] Relationship requirements are defined per clinical resource and action, including the stricter laboratory-result write relationship.
- [x] Patient self-access requires a verified owner link and grants read only.
- [x] Practitioner access requires an active treating assignment or an explicitly scoped approved read grant; read grants cannot authorize writes.
- [x] Organization membership alone, client-supplied IDs, administrative roles, inactive/expired/revoked evidence, and emergency access do not authorize clinical access.
- [x] SPEC-03 action policy, SPEC-05 consent, and workflow checks remain independent and required.
- [x] SPEC-06 selects the canonical explicit grant table; care-team source reconciliation and migration remain separately tracked.
- [x] Focused tests pass for positive, negative, cross-patient, cross-organization, and privilege-escalation cases.

## Verification record

Command: `.venv/Scripts/python.exe -m pytest tests/core/test_patient_relationship_policy.py -q -p no:cacheprovider` (run from `backend/`).

Result: **30 passed**. The interpreter reported 12 dependency deprecation warnings from installed `pyiceberg`/Pydantic packages; there were no test failures.

Regression command: `.venv/Scripts/python.exe -m pytest tests/core/test_patient_relationship_policy.py tests/core/test_action_authorization.py -q -p no:cacheprovider` (run from `backend/`).

Result: **43 passed** (30 SPEC-04 cases and 13 SPEC-03 cases); the same 12 dependency deprecation warnings were reported.

These are policy unit tests. Route-level allow/deny tests, live RLS/grant tests, relationship-source reconciliation, and deployment evidence remain open. Per the Phase 0 plan, SEC findings are not closed by this SPEC or by reference-evaluator tests.

## Deferred work

- SPEC-05 defines consent scope, purpose, status, expiry, revocation, and precedence.
- SPEC-06 defines the canonical explicit grant schema and migration path; implementation remains pending.
- SPEC-08 prohibits system-administrator access and break-glass in the current Phase 0 policy. A future clinical emergency workflow would require a separate approved specification.
- Remediation integrates the evaluator or equivalent central policy into every protected route and tests privileged backend queries, RLS, and grants.

### PH0-WP-01 implementation progress (20 November 2026, local, unmerged)

On `security/phase-0-db-storage-release` @ `421d28a` (not pushed), `backend/app/core/security.py` implemented a canonical, trusted server-side `authorize_patient_access`/`require_patient_access` path that resolves target patient and organization context, fails closed on missing/ambiguous evidence, enforces patient self-access boundaries, denies system-administrator patient-data access, and evaluates practitioner relationship evidence from available trusted sources (active care-team/consent records in organization context with legacy assignment fallback only when organization context is absent), consistent with current schema-drift constraints. Touched clinical/care-team/record/consent/dashboard routes were migrated to require this resource-derived authorization. This does not complete relationship-source reconciliation, `patient_access_grants` migration/service integration, SPEC-05 consent enforcement, integration into every protected route/service, or live RLS/grant/route-runtime verification.

### PH0-WP-02 implementation progress (20 November 2026, local, unmerged)

`backend/app/core/clinical_authorization.py` uses the canonical relationship path after resolving patient/organization/encounter/appointment/care-team context from stored resources. Encounter-scoped medication, observation and condition reads now resolve the relationship target from the encounter row before any service query. Practitioner appointment-list access requires the authenticated practitioner identity and exact organization context; care-team reads require an active care-team membership for practitioners or exact-organization care authority for organization administrators.

Relationship-source reconciliation, `patient_access_grants` integration, full SPEC-05 consent evaluation, legacy-source removal, and live RLS/grant/route-runtime verification remain open. See the [PH0-WP-02 completion record](PH0-WP-02-completion-record.md) for the positive/negative evidence recorded for these six routers.

### Order 9 local relationship evidence (24 November 2026)

The [Order 9 route record](PH0-WP-02-route-authorization-order-9-record.md) maps all 45 mounted sensitive routes. Practitioner IDs on clinical create payloads are bound to the verified actor; `/patients/mine` derives practitioner identity and one organization from trusted role state and returns only active organization-scoped `patient_care_team` relationships; QR generation no longer requires a full patient/clinical fetch. These are local application controls only. Canonical grants, full consent evaluation, relationship-source reconciliation, and hosted verification remain open.

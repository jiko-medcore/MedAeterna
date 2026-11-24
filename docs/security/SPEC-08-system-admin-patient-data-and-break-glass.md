# SPEC-08: System-Administrator Patient Data and Break-Glass Boundary

**Status:** System-administrator patient-data access and break-glass are explicitly prohibited for the current Phase 0 policy. The pure reference guard and policy tests are in place. Existing routes and database enforcement remain remediation work.

**Order 5 approval (21 November 2026):** Approved for implementation by the designated MedAeterna technical/security owner for the documented decisions only; not production acceptance. Any future emergency workflow remains out of scope. See [PH0-WP-06 policy approval record](PH0-WP-06-SPEC-approval-and-consent-access-model.md).

## Decision

A `super_admin` assignment authorizes defined platform operations only. It does not grant access to patient profiles, administrative patient views, appointments, clinical records, consent, patient grants, care-team data, or patient-linked audit/event payloads.

There is **no break-glass path in the current Phase 0 policy**, for system administrators or any other administrative role. A purpose string, incident ticket, patient consent flag, `consent_type='emergency'`, `emergency_access=true`, or event type does not create an exception. Requests for patient data through a system-administrator path deny, including in an incident.

This is an explicit prohibition, not an incomplete approval workflow. A future clinical emergency-access capability would need a separately approved specification with its own clinical actor eligibility, patient/resource/purpose scope, approval, short expiry, audit alerting, and post-access review. It cannot be enabled by changing an incident ticket or role assignment.

## Multi-role users

Authorization remains contextual under SPEC-01. A user who also has a separate, valid practitioner assignment may access a patient only through that practitioner role and the complete SPEC-03/04/05 clinical checks. A separate, organization-scoped `org_admin` assignment may use only the limited SPEC-07 administrative view. The `super_admin` assignment contributes no patient-data authority to either decision; the route must evaluate the actual selected, scoped role path rather than treating `super_admin` as a hierarchy override.

This specification does not grant practitioners or organization administrators emergency access. SPEC-04/05 continue to deny emergency access until a separate clinical workflow is approved.

## Permitted system-administrator operations involving operational metadata

System administrators may use the SPEC-03/SPEC-09 operational event and audit capabilities only for an explicit, server-allowlisted platform/security purpose, with resource-specific visibility and audit controls. Before any system-administrator response or retry control is exposed, patient identifiers, clinical content, consent details, patient-linked audit fields, and event payloads must be redacted. Opaque event references may be used only when they cannot be resolved by the administrator to a patient record; SPEC-09 additionally suppresses patient event types and aggregate identifiers.

Redaction is a trusted server-side/data-layer condition, not a UI-only display rule. A privileged backend query must apply the same projection and must not return a patient payload to code that can serialize it. Event retry may operate on a trusted opaque event reference, but the administrator does not receive the underlying patient payload. SPEC-09 still defines exact operational-event visibility and retry authority.

Every permitted operation records a protected audit event with the actor, explicit purpose, operation, opaque resource reference, scope, timestamp, and outcome. Do not copy patient identifiers, clinical values, or raw payloads into system-administrator audit views. Denied patient-data and break-glass attempts must also be auditable and should alert the security owner; the alert should avoid including patient payload data.

## Current code boundary review

The SPEC-03 reference matrix already denies `system_administrator` on patient-profile and clinical-record actions. The admin audit and event route modules inspected for this decision depend on `get_current_user` and call their query/replay services; this does not establish that patient data is exposed, because service projections, effective grants, and RLS are separate. It does show that route-level system-admin checks and redaction are not demonstrated by the current route code. No query results, patient rows, or hosted project were inspected for SPEC-08.

The reference guard is `backend/app/core/system_admin_patient_access.py`. It expressly denies the system-admin role for patient-related resources regardless of action or a requested break-glass flag. SPEC-03 requires `event_payload_redacted` and `patient_data_redacted` for system-admin operational event read/retry and audit read. SPEC-09 defines the exact operational metadata projection. These checks are pure policy code; they do not resolve roles, redact data, secure routes, or alter database permissions by themselves.

## Acceptance criteria

- [x] System-administrator role alone is explicitly denied for patient and clinical data.
- [x] The current Phase 0 break-glass decision is an explicit prohibition, not a permissive or unspecified override.
- [x] Emergency consent flags and legacy emergency grant values do not override the prohibition.
- [x] Multi-role users may only use a separately scoped practitioner or organization-admin path under its own SPEC-03/04/05/07 checks.
- [x] Operational event and audit visibility for system administrators requires trusted patient-data redaction, explicit purpose, visibility/authority, and audit controls.
- [x] Tests cover patient-data resources, actions, break-glass denial, multi-role boundary expectations, and redaction gates.
- [x] Existing routes and database state are recorded as outside the reference-policy proof; no database or hosted state is changed by this specification.

## Verification record

Focused command: `.venv/Scripts/python.exe -m pytest tests/core/test_system_admin_patient_access.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **184 passed**.

Security-policy regression command: `.venv/Scripts/python.exe -m pytest tests/core/test_system_admin_patient_access.py tests/core/test_action_authorization.py tests/core/test_role_catalogue.py tests/core/test_organization_admin_patient_access.py tests/core/test_patient_relationship_policy.py tests/core/test_consent_policy.py tests/core/test_patient_access_grants_schema.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **338 passed**. Both runs reported 12 dependency deprecation warnings from installed `pyiceberg`/Pydantic packages; no tests failed.

`git diff --check` is clean. Tests prove only reference-policy behavior. Route-level authorization/redaction tests, RLS and grants tests, audit delivery, and deployed configuration review remain required to close implementation findings.

SPEC-09's latest security-policy regression command re-ran the system-admin redaction gates together with the neighboring SPEC-03 through SPEC-08 policy suites: **373 passed**, with 12 dependency deprecation warnings and no test failures.

### Order 9 local route evidence (24 November 2026)

The [Order 9 route record](PH0-WP-02-route-authorization-order-9-record.md) includes a negative route test showing that a system administrator is denied a patient-scoped clinical read before the service is called. No break-glass path was added; all clinical patient-data routes remain default-deny for system administrators.

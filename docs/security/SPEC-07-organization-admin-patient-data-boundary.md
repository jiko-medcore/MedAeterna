# SPEC-07: Organization-Administrator Patient Data Boundary

**Status:** Administrative data boundary selected and covered by a reference policy. Production routes, database access, and audit integration remain remediation work.

**Order 5 approval (21 November 2026):** Approved for implementation by the designated MedAeterna technical/security owner for the documented decisions only; not production acceptance. Undocumented choices remain fail-closed. See [PH0-WP-06 policy approval record](PH0-WP-06-SPEC-approval-and-consent-access-model.md).

## Decision

An organization-administrator assignment does not grant access to a patient's full profile, clinical record, consent, or care relationship. The default is deny. A separate, read-only `patient_admin_data` view may return only the fields listed below, for one verified patient and one server-defined administrative purpose within the exact organization.

This is not a patient-care permission. It does not establish treatment authority, consent, emergency authority, or permission to create, update, delete, administer, or retry patient data. A patient's consent grant under SPEC-05 and relationship evidence under SPEC-04 do not expand this administrative field boundary.

## Approved purposes and fields

The purpose is selected by the server-side workflow or strictly validated against it. A client-provided purpose string is not proof of authorization. Each request has exactly one purpose, one patient, and one organization.

| Purpose | Permitted fields | Example permitted use |
|---|---|---|
| `registration_identity` | `patient_reference`, `patient_name` | Resolve a patient already registered with this organization. |
| `appointment_coordination` | `patient_reference`, `patient_name`, `contact_phone`, `contact_email` | Contact a patient for an organization-specific appointment workflow. Appointment data itself is governed by its own SPEC-03 rule. |
| `billing_administration` | `patient_reference`, `patient_name`, `contact_phone`, `contact_email`, `billing_reference`, `billing_status` | Resolve and communicate about the organization's administrative billing account. |

These are logical response fields, not a direction to select all columns from `patients`. Before a route uses them, each field must be mapped to a verified source and projected explicitly. If the source does not support a field or purpose, that field or purpose remains unavailable until separately reviewed.

The following are never included in this view: date of birth, gender, blood group, diagnoses, observations, conditions, medication or prescription data, laboratory results, encounter details or notes, clinical documents, consent records, emergency contacts, profile images, and any other clinical or sensitive field not expressly listed above. Unknown fields, mixing fields from multiple purposes, and empty field requests deny.

## Required authorization evidence

Every allow decision requires all of these checks:

1. The authenticated actor has a current `org_admin` assignment for the exact organization, resolved through SPEC-01/02 role handling.
2. Trusted backend logic verifies a current patient-to-organization administrative link for the selected workflow. Examples are a current registration, an organization appointment workflow, or a billing account. Organization membership, a care-team role, search result, client-supplied IDs, or the administrator role alone is not such a link.
3. The server-selected purpose is one of the three values above, and the actual response projection is a subset of that purpose's field allowlist.
4. The request is for a single patient record. Bulk enumeration, export, and background extraction are denied by this policy.
5. A protected audit record is emitted with actor, organization, patient reference, purpose, requested fields, outcome, and timestamp. Do not copy patient data values into the audit event.

Any missing trusted evidence is conditional/deny at the endpoint. A conflicting identity, organization, or unsupported field is a hard denial. Patient IDs and purpose values in the request never establish the required link or authority.

## Separation from existing access

- `patient_profile` remains self-service for the patient only; an organization administrator cannot use this rule to read the full profile.
- `clinical_record` stays denied to organization administrators under SPEC-03, irrespective of organization membership, care-team administration, or patient grant.
- Appointment records, organization membership, role assignments, and audit records retain their own resource-specific policies.
- System-administrator access to patient or clinical data is prohibited under SPEC-08.
- This policy grants no patient-data update, create, delete, administer, or retry action.

## Data-access implementation requirements

An implementing route must authorize before querying, use the trusted role and patient-link resolver, select only the approved field projection, and record the audit event. It must not call a broad patient profile/FHIR/timeline query and filter the result afterward. Responses must not include nested clinical data.

If a database view or table is exposed through Supabase Data API, RLS and explicit table grants must independently constrain it; application checks still apply to privileged backend queries because service-role access bypasses RLS. Supabase's current guidance requires RLS for exposed tables and treats grants and policies as separate access controls ([RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security)). No view, table, policy, route, or database state was changed for this specification.

## Executable policy and tests

`backend/app/core/organization_admin_patient_access.py` enforces the purpose-to-field mapping and delegates role/action/scope checks to `backend/app/core/action_authorization.py`. Its inputs represent trusted server-side evidence; the module does not query the database, resolve assignments, verify patient links, or emit audit events. The SPEC-03 matrix contains `patient_admin_data/read` as the only organization-administrator action for this resource.

Focused tests are in `backend/tests/core/test_organization_admin_patient_access.py`; the SPEC-03 matrix regression tests remain in `backend/tests/core/test_action_authorization.py`. They cover the positive allowlist per purpose, missing evidence, exact organization scope, wrong roles, unsupported purposes and fields, clinical/sensitive field denial, bulk denial, and the absence of non-read actions.

## Acceptance criteria

- [x] The organization administrator's patient-data boundary is explicit and default-deny.
- [x] Full patient profiles, clinical records, consent, and care data do not become accessible through the admin role.
- [x] Each allowed administrative purpose has an exact, distinct field allowlist.
- [x] Access requires exact organization role scope, a separately verified patient-organization link, purpose, minimum fields, and audit.
- [x] Bulk enumeration and non-read access are denied.
- [x] SPEC-03 is updated to distinguish full patient profiles from the restricted administrative view.
- [x] Focused and neighboring policy tests pass and are recorded below.

## Verification record

Focused command: `.venv/Scripts/python.exe -m pytest tests/core/test_organization_admin_patient_access.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **20 passed**.

Regression command: `.venv/Scripts/python.exe -m pytest tests/core/test_organization_admin_patient_access.py tests/core/test_action_authorization.py tests/core/test_role_catalogue.py -q --tb=short -p no:cacheprovider` (run from `backend/`). Result: **52 passed**. Both runs reported 12 dependency deprecation warnings from installed `pyiceberg`/Pydantic packages; no tests failed.

`git diff --check` is clean. Tests validate pure policy behavior; they do not prove route wiring, RLS/grants, database views, field-source mapping, audit delivery, or deployed configuration. Those remain open implementation checks before SEC findings can be closed.

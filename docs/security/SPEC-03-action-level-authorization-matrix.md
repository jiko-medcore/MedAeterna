# SPEC-03: Action-Level Authorization Matrix

**Status:** The role/resource/action decisions and executable reference policy are complete. Route-by-route adoption remains a Phase 0 remediation task and is not claimed by this specification.

## Purpose and boundaries

SPEC-03 defines what each principal category may do for each resource family. It applies the role categories and scopes from SPEC-01 and the role lifecycle/delegation rules from SPEC-02.

This matrix does not make organization membership a patient-care relationship. SPEC-07 defines a separate, minimum-field administrative patient-data view; full profile and clinical access remain denied to organization administrators. SPEC-04 and SPEC-05 still govern clinical relationships and consent, SPEC-08 governs system-administrator patient-data access, and SPEC-09 governs operational-event visibility.

The policy registry in backend/app/core/action_authorization.py is an executable reference for the role/action part of a decision. It does not access the database, verify relationship facts, or secure a route by itself. A future route guard must obtain required condition results from trusted application logic and apply this decision before using a privileged backend client. Phase 0 SEC findings for missing or incomplete route authorization remain open until route-level tests and evidence close them.

## Decision rules

- A role is evaluated by its SPEC-01 category and exact scope. Unmapped roles confer no action.
- Organization-scoped practitioner and organization-administrator roles apply only when the role assignment organization equals the validated resource organization.
- A patient role applies only to the authenticated patient's own records. A system-administrator role is platform-scoped and does not imply clinical-care access.
- Multiple roles may contribute separate permissions, but permissions do not cross organization scope or resource relationship boundaries.
- Each action is evaluated independently. Read does not imply create, update, delete, administer, or retry; update does not imply delete.
- Administer means a separately authorized administrative operation. It does not stand in for all CRUD actions.
- Delete means removing a resource. Where history or auditability matters, deletion is denied; an approved soft-deactivation workflow is separately gated.
- An unlisted role/resource/action combination is denied. Unknown resource/action names, unmapped roles, and failed scope checks deny; missing context remains conditional and can never authorize the request.
- A conditional entry is denied until every named condition is verified by trusted server-side logic. Client-supplied identifiers, flags, or metadata are not evidence that a condition passed.
- Database grants and RLS remain a separate enforcement layer. Supabase documents that grants decide whether an operation is possible and RLS decides which rows it may affect; both are required for exposed tables (https://supabase.com/docs/guides/database/postgres/row-level-security).

## Actions

| Action | Meaning |
|---|---|
| read | Retrieve a permitted representation of a resource. Field filtering remains mandatory. |
| create | Create a resource or invitation. Role assignment uses administer and the SPEC-02 workflow. |
| update | Change permitted fields on an existing resource under its workflow. |
| delete | Remove a resource. This does not include revocation, cancellation, or deactivation unless a row below explicitly allows a gated soft-deactivation workflow. |
| administer | Perform a privileged management operation, including controlled role delegation or configuration management. |
| retry | Re-execute a failed operational event. This is distinct from event read access and always requires explicit authority and audit. |

## Matrix

The entries below list the only permissions that may be considered. Every action omitted from a role/resource cell is denied. Conditional permissions are fail-closed until all named gates are verified.

| Resource family | Patient | Practitioner | Organization administrator | System administrator |
|---|---|---|---|---|
| Patient profile | read own profile; update own permitted fields | None defined here | None; full patient profiles remain denied | None; clinical/profile access awaits SPEC-08 |
| Patient administrative data | None | None | read only for a verified organization-linked patient and one approved administrative purpose, with purpose-specific fields and audit under SPEC-07 | None pending SPEC-08 |
| Practitioner profile | None | read own profile | None; member-directory fields are limited by the membership row below | None |
| Clinical records: medical history, observations, conditions, medication requests, prescriptions, lab results, encounters | read own permitted resources, conditional on resource being patient-readable | read, create, and update, conditional on organization scope, verified patient relationship, consent when required, and the clinical workflow | Denied | Denied; platform role alone never grants clinical access |
| Appointments | read own appointments | read assigned/authorized appointments; create or update only through an approved appointment workflow and verified patient relationship | Denied pending a defined organization-level view | Denied pending a defined operational purpose |
| Reminders | read own reminders | None | None | None |
| Consent preferences and records | read, create, update, and administer own preferences; writes must be audited | read only for the relevant patient and consent scope, conditional on verified relationship and recipient rules | None | None |
| Care-team assignments | None until patient-facing visibility is approved | read relevant assignments only with a verified patient relationship and organization scope; no arbitrary or self-assignment | read, create, update, and administer organization care-team configuration only with relationship checks, organization care authority, and audit | None pending explicit operational authority |
| Organization configuration: profile, departments, healthcare services, hours, branding | None unless a separate public-read rule is approved | None unless a separate organization-read rule is approved | read, create, update, and administer own organization; delete only supported child configuration through audited soft deactivation, never hard-delete the organization | No cross-organization override is implied; platform operations belong to platform configuration |
| Organization membership | None | None | read minimum member data and create invitations in own organization, subject to inviter authority and audit | None through this resource; use the SPEC-02 role-assignment path |
| Role assignments | None | None | read minimum role data and administer practitioner-category grants/revocations in own organization under SPEC-02; no self-grant or privileged-role delegation | read and administer only the SPEC-02 system path for org_admin/super_admin; no self-grant or patient-role assignment |
| Operational events | None | None | read only organization-scoped event data explicitly approved by SPEC-09; no retry | read for explicit purpose and approved visibility; retry only with retry authority, explicit purpose, and audit |
| Audit records | None | None | read only approved records for own organization and permitted fields | read for a defined security/platform purpose; no change or deletion |
| Platform configuration | None | None | None | read, create, update, and administer for explicit platform purposes with audit. Delete is denied; use a reviewed replacement/deactivation workflow. |

## Required conditions

| Condition | Trusted evidence required |
|---|---|
| subject_is_actor | Authenticated subject ID equals the resource owner ID. |
| permitted_fields | The endpoint limits writes to the approved self-service field allowlist. |
| permitted_resource_scope | The resource family and fields are in the patient's approved self-read scope. |
| organization_scope | The actor has the required organization-scoped role for the validated resource organization. |
| patient_relationship | An approved SPEC-04 relationship check validates actor, patient, organization, resource, and action. |
| consent_if_required / consent_scope_verified | SPEC-05 confirms consent applies to purpose, resource, recipient, status, and period, or that consent is not required. |
| clinical_workflow | The specific clinical workflow permits create/update and records provenance. |
| appointment_assigned_to_actor / authorized_appointment_workflow | The appointment is assigned to the practitioner or an approved workflow grants the action. |
| care_team_membership / organization_care_authority | Care-team or organization authority is independently verified, not taken from client-supplied IDs. |
| inviter_authority / role_delegation_policy | Current authority and allowed target-role delegation are revalidated under SPEC-02. |
| no_self_grant | For a grant, actor and target differ. Self-revocation remains allowed under SPEC-02. |
| minimal_member_data | The response contains only member/role fields needed for the stated management action. |
| event_visibility_approved / event_retry_authority | SPEC-09 approves visible event fields/organizations and who may retry. |
| audit_visibility_approved | The audit view purpose, organization boundary, and returned fields are approved. |
| explicit_admin_purpose | A server-defined, allowlisted workflow purpose is present and recorded; an administrator role alone is insufficient. SPEC-07 defines patient-administration purposes; SPEC-08/09 define platform/security purposes. |
| patient_admin_link_verified | Trusted backend verifies a current registration, appointment-coordination, or billing relationship between this patient and the exact organization. Membership, care-team role, search result, or client ID alone is insufficient. |
| minimum_patient_fields | The response projection is restricted to the SPEC-07 field allowlist for the selected purpose; unknown or mixed-purpose fields deny. |
| audit_recorded | The action emits a protected audit record with actor, operation, resource, scope, time, and outcome. |
| soft_deactivation | The resource supports reversible deactivation and retains required history. |

Conditions may be supplied to the evaluator only after trusted checks pass. The evaluator returns conditional when a rule exists but evidence is absent, and deny when no rule matches or identity/scope fails. Only a fully satisfied rule returns allow.

## Resource mapping

- patient_profile: patient profile, summary, and patient-facing profile fields.
- patient_admin_data: SPEC-07's limited organization-administrator administrative view; never a clinical record or full patient profile.
- practitioner_profile: practitioner profile and self-service fields.
- clinical_record: medical history, observations, conditions, medication resources, prescriptions, laboratory results, and encounters.
- appointment, reminder, consent_preference, and care_team: their corresponding modules.
- organization_configuration: organization profile, departments, healthcare services, operating hours, and branding.
- organization_membership and role_assignment: invitations, memberships, and SPEC-02 grant/revocation operations.
- operational_event: event queues, dead letters, and replay/retry operations.
- audit_record: audit-log reads.
- platform_configuration: system-level configuration and platform administration.

Each endpoint must map to one resource family and one action, or to multiple explicit checks when it changes multiple resources. HTTP method alone is insufficient: POST invite is organization_membership/create, while POST event replay is operational_event/retry.

## Executable policy and tests

The reference evaluator is backend/app/core/action_authorization.py. It is pure policy code with no database calls. It covers all 14 resource families and six actions; requires exact organization scope for organization-scoped roles; requires self-ownership for self-service; returns missing gates for conditional access; and denies unknown values, unmapped roles, cross-organization requests, self-grants, and clinical-record deletion. SPEC-07's purpose and field allowlists are enforced by backend/app/core/organization_admin_patient_access.py.

Focused tests are in backend/tests/core/test_action_authorization.py. In addition to scenario checks, data-driven tests exercise every declared matrix rule with its gates satisfied and verify every empty role/action cell denies. Other tests cover unknown/unmapped denial, owner-only self-service, field restrictions, patient clinical-resource limits, practitioner relationship/workflow conditions, tenant isolation, role self-grant/revocation behavior, system-admin clinical denial, and audited event retry.

## Acceptance criteria

- [x] Read, create, update, delete, administer, and retry have independent semantics.
- [x] Every listed resource family has an entry for every action and role category; unlisted cells deny by default.
- [x] Patient, practitioner, organization-administrator, and system-administrator boundaries follow the Phase 0 plan and SPEC-01/02.
- [x] Organization scope, self-service ownership, clinical relationship, workflow, purpose, consent, and audit gates are explicit.
- [x] System-admin status grants no patient clinical access; organization-admin status grants no cross-tenant access.
- [x] The reference evaluator fails closed for unknown/unmapped roles, missing context, and unsatisfied conditions.
- [x] Focused policy tests pass.

## SPEC-07 amendment verification

Command: `.venv/Scripts/python.exe -m pytest tests/core/test_organization_admin_patient_access.py tests/core/test_action_authorization.py tests/core/test_role_catalogue.py -q --tb=short -p no:cacheprovider` (run from `backend/`).

Result: **52 passed**, with 12 dependency deprecation warnings from installed `pyiceberg`/Pydantic packages and no test failures. This run verifies the updated 14-resource matrix, purpose-to-field limits, role scope, and administrative patient-data denial cases.

## Deferred enforcement work

This specification completes the action-policy decision milestone in Phase 0. It does not close SEC findings for route authentication, resource authorization, service-role query context, RLS/grants, storage, or event endpoints. Route-level allow/deny tests and database/storage tests are required before those findings can be closed. Existing require_permission and role-permission data are not proof that this matrix is enforced; review them during the related SEC remediation.

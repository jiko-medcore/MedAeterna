# MedAeterna — Phase 0 Backend Security Baseline and Remediation Plan

**Document version:** 2.0  
**Status:** Active remediation baseline — NOT ACCEPTED  
**Review date:** 20 November 2026  
**Repository:** `jiko-medcore/MedAeterna`  
**Audited branch / commit:** `main` / `1aff95b0ab7e15733a72d440ee6cbcf323d5e8ad`  
**Scope:** FastAPI backend, Supabase Auth, PostgreSQL, authorization, RLS, SQL grants/functions, Storage, auditability, backend API contracts and verification  
**Out of scope:** Flutter/Dart implementation and frontend UI testing

> Version 2.0 consolidates the original detailed baseline and the version 1.1 review amendment. It preserves the existing architecture and SEC-01–SEC-24 finding identifiers, adds implementation evidence from the current repository, separates local from hosted verification, and establishes a traceable work/acceptance sequence. This document does not itself remediate vulnerabilities or prove production security.

---

## Document control

| Version | Summary |
|---|---|
| 1.0 | Original baseline, source/database findings, target model and detailed remediation phases |
| 1.1 | Clarified the existing architecture, contextual authorization, conditional decision matrix and unresolved policy specifications |
| 2.0 | Consolidated 1.0 and 1.1; refreshed repository evidence at `1aff95b0ab7e15733a72d440ee6cbcf323d5e8ad`; recorded local SPEC-11/SPEC-12 progress and remaining runtime/hosted gaps; added work-package traceability, CI and branch-protection acceptance |

**Evidence discipline:** “Implemented locally”, “deployed”, “runtime verified”, and “accepted” are different states. A migration file or passing unit test is not proof that the hosted Supabase project has the same configuration. A finding is not closed solely because its policy has been documented.

---

# 1. Executive summary

MedAeterna has made substantial progress since the original security baseline. Twelve security policy documents now exist under `docs/security/`. Role assignment lifecycle work, a declarative table-access inventory, least-privilege grants, hardened database functions, and storage bucket/object controls have been implemented and locally verified to varying degrees.

The current blocker is no longer the absence of a security architecture. It is the incomplete and inconsistent enforcement of the approved policy at runtime, combined with incomplete proof that the deployed Supabase environment matches the reviewed local state.

**Overall status: AMBER, with RED/P0 authorization blockers. Phase 0 is NOT ACCEPTED.**

The main reasons are:

1. The current `backend/app/core/security.py` still contains two `require_patient_access()` definitions with incompatible contracts.
2. `require_permission()` still assumes an `org_id` path parameter and uses the global `supabase` client for its role/permission lookup.
3. `GET /medication-requests/encounter/{encounter_id}` still has no authentication or patient/resource authorization dependency.
4. Administrative event routes authenticate the caller but do not enforce the role-specific event visibility/retry policy.
5. Caller-scoped RLS execution is not consistently propagated across all existing query call sites.
6. Patient-access grant migration and complete consent lifecycle enforcement remain outstanding.
7. The SPEC-11 table inventory covers 26 local public tables, but clinical tables including appointments, encounters, observations, conditions and medication requests were not present in the reviewed catalog and must be reconciled with application routes and hosted schema.
8. SPEC-11 and SPEC-12 local verification is not equivalent to hosted/staging verification.
9. Backend CI is not yet a required merge check, and `main` has no branch protection recorded in the review.

## 1.1 Completion model

Track every control against these stages:

1. **Specified** — policy and expected behavior are documented.
2. **Implemented** — code/migration/configuration exists.
3. **Locally verified** — focused and regression tests pass against the local test environment.
4. **Staging verified** — deployed staging configuration and effective access paths are tested.
5. **Production verified** — production configuration is checked through approved, non-destructive evidence and controlled tests.
6. **Closed/accepted** — evidence is reviewed, linked, and accepted by the project owner.

A stage must not be inferred from an earlier stage.

## 1.2 Current status by domain

| Domain | Current evidence | Status |
|---|---|---|
| Architecture | FastAPI modular monolith, Supabase/PostgreSQL, centralized authn/authz direction retained | Established |
| Role catalogue | Scoped role categories and deterministic multi-role context improved | Partially implemented |
| Role assignment lifecycle | Lifecycle controls and audit model implemented; local/production ACL state differs | Partial |
| Action-level authorization | Matrix and reference evaluator documented; route adoption incomplete | Partial |
| Patient relationship access | Policy/evaluator exists; duplicate dependency and route enforcement remain | Blocked |
| Consent | Policy defined; schema/provenance/lifecycle enforcement incomplete | Blocked |
| Patient-access grants | Canonical table selected; migration not yet implemented | Not implemented |
| Organization/system admin boundaries | Policy defined; runtime adoption incomplete | Partial |
| Event access | Authentication present; role-specific authorization incomplete | Blocked |
| Caller-scoped database access | Execution modes and reference gate documented; call-site migration incomplete | Blocked |
| RLS and grants | SPEC-11 local migration/catalog evidence recorded for 26 tables | Locally verified; hosted pending |
| Storage | SPEC-12 local catalog/API/test evidence recorded for 3 image buckets | Locally verified; hosted pending |
| Audit | Append-only database controls improved; application-level audit completeness remains | Partial |
| Backend tests | Large local regression results recorded; CI not yet a required check | Partial |
| Staging/production | Latest RLS/storage changes not verified against hosted environment | Not verified |
| Phase 0 acceptance | Critical runtime and hosted evidence gaps remain | NOT ACCEPTED |

---

# 2. Scope, architecture and security principles

## 2.1 Scope

Included:
- FastAPI routers, dependencies, services and repositories.
- JWT validation and user/role resolution.
- Organization, patient, practitioner and resource-level authorization.
- PostgreSQL schemas, constraints, grants, RLS and database functions.
- Supabase Storage buckets, object paths and access policies.
- Consent, patient-access grants, care-team relationships and audit records.
- Event monitoring/retry and background worker execution.
- API contracts where contract defects affect secure operation.
- Backend unit, integration, database and storage verification.
- CI, release gates and environment verification.

Excluded:
- Flutter/Dart code, frontend UI, widget tests and frontend state management.
- Microservice extraction or replacement of FastAPI, Supabase or PostgreSQL.
- Unrelated FHIR mapping work.

## 2.2 Architecture to preserve

Retain the existing modular monolith:
- FastAPI backend.
- Supabase Auth and PostgreSQL.
- Shared authentication and authorization components.
- Service/repository separation.
- Organization isolation.
- Database constraints and RLS.
- Storage policies.
- Protected audit logging.

Do not introduce a new architecture merely to solve the current implementation gaps. Strengthen the shared security primitives and apply them consistently.

## 2.3 Security principles

1. **Authentication is not authorization.** A valid JWT establishes identity, not permission to access a particular resource.
2. **Deny by default.** Missing, ambiguous or failed authorization context must not grant access.
3. **Resource-level authorization.** Evaluate the actual resource and action, not just a role or organization membership.
4. **Organization isolation.** Client-supplied organization IDs are not proof of membership.
5. **Least privilege.** Ordinary database roles receive only required privileges; service-role access is reserved for trusted server operations.
6. **Defense in depth.** Application authorization, database constraints, RLS, grants, Storage policies and audit records are complementary.
7. **Auditable privileged operations.** Role changes, consent lifecycle, access grants, event retries and sensitive data operations require attributable records.
8. **No secret/PHI leakage.** Tokens, keys, credentials and unnecessary clinical payloads must not enter logs or test output.

## 2.4 Contextual authorization model

`Authenticated User + Applicable Role Assignment + Validated Organization Context + Resource Relationship + Requested Action`

- Resolve the role assignment applicable to the requested organization/resource; do not choose an arbitrary primary role.
- Distinguish system-scoped roles from organization-scoped roles.
- Resolve organization context from the target resource or an explicitly validated operation context.
- Evaluate patient ownership, care-team relationship, canonical access grant and consent only as allowed by the policy for that resource/action.
- Separate read, create, update, delete, administer and retry permissions.
- Fail closed when required evidence cannot be established.
- A privileged Supabase client does not authorize the caller. Application authorization must happen before privileged access.
- Where caller-scoped RLS is intended, deliberately propagate and verify the caller JWT; do not assume that a verified JWT on the FastAPI request automatically changes the database client identity.

## 2.5 Four principal authorization categories

| Category | Intended boundary |
|---|---|
| Patient | Own profile and permitted own clinical resources; own consent preferences; no access to other patients or admin operations |
| Practitioner | Own practitioner profile and patients/resources within an authorized clinical relationship, organization and workflow |
| Organization administrator | Administration within own organization; no automatic unrestricted clinical access or system-wide authority |
| System administrator | Explicit platform operations; current policy prohibits general patient clinical-data access and break-glass access unless a future approved policy changes this |

These are functional authorization categories, not a requirement that the database contain exactly four role strings. Stored roles and scopes must map through the role catalogue.

## 2.6 Patient relationship, access grants and consent are distinct

- **Care-team assignment** is an operational/clinical relationship; only an authorized actor may create or change it.
- **Patient-access grant** is a patient-approved, scoped grant to a defined grantee and organization context, with status and effective/expiry/revocation lifecycle.
- **Consent** records permission/preferences for a defined purpose, recipient and resource scope; it is not a universal authorization token.
- **Authorization decision** evaluates the role, resource, action, organization, relationship, consent requirements and workflow together.

Do not implement assumptions about which relationship is sufficient for a resource/action until the applicable policy is explicit. If unclear, deny.

---

# 3. Security finding register — SEC-01 to SEC-24

The original finding IDs are retained for audit continuity. Status below reflects the repository review at `1aff95b0ab7e15733a72d440ee6cbcf323d5e8ad`, plus the implementation evidence recorded in the current SPEC documents. “Local mitigation” is not closure.

| ID | Finding / risk | Severity | Current disposition | Remaining closure evidence |
|---|---|---:|---|---|
| SEC-01 | Ambiguous/non-deterministic role selection for multi-role users | High | Partially mitigated in role context | Route/service tests for organization-scoped decisions |
| SEC-02 | Inconsistent organization-admin recognition | High | Partially mitigated by role catalogue | Verify every admin dependency and route |
| SEC-03 | Organization context not consistently enforced | High | Open | Resource-derived context and cross-org tests |
| SEC-04 | `require_permission()` assumes `org_id` in URL path | Critical | Open; visible in current source | Correct contract, call-site migration and tests |
| SEC-05 | Duplicate/incompatible `require_patient_access()` definitions | Critical | Open; two definitions visible in current source | One canonical dependency, all callers migrated and tested |
| SEC-06 | `patient_access` vs `patient_access_grants` mismatch | High | Canonical table selected; migration outstanding | Migration, service integration and lifecycle tests |
| SEC-07 | Permission lookup may not use caller JWT/RLS context | High | Open; current helper uses global `supabase` client | Explicit execution mode and identity propagation tests |
| SEC-08 | Medication requests by encounter unauthenticated | Critical | Open; route still lacks dependency | Authn + encounter resolution + patient/org authorization |
| SEC-09 | Administrative event access/retry insufficiently protected | Critical | Partially mitigated: authentication present | Role-specific visibility/retry policy and audit tests |
| SEC-10 | Unrestricted authenticated role-assignment path | Critical | Local lifecycle/ACL remediation recorded; production follow-up pending | Verify effective production policy/grants and negative Data API tests |
| SEC-11 | Encounter ownership/resource authorization gaps | Critical | Open/partial | Route/service tests for create/read/update and cross-patient/org |
| SEC-12 | Care-team assignment authority gaps | Critical | Open/partial | Authorized actor, target relationship, scope and audit tests |
| SEC-13 | Practitioner-role administration gaps | Critical | Lifecycle controls improved; route adoption needs verification | Organization/system delegation tests and direct-write denial |
| SEC-14 | Practitioner appointment retrieval disclosure | Critical | Open | Caller ownership/assignment and cross-practitioner tests |
| SEC-15 | Appointment create/update trusts client-supplied IDs/fields | High | Open | Relationship validation, field allowlist and transition tests |
| SEC-16 | Encounter-scoped observation/condition retrieval lacks patient access proof | High | Open | Shared access dependency at every route/service |
| SEC-17 | Incomplete RLS policy coverage | High | Local SPEC-11 inventory covers 26 tables; clinical relations missing from reviewed catalog | Reconcile all application relations and hosted schema |
| SEC-18 | Organization-level RLS isolation not demonstrated | High | Partial local model; hosted/effective proof pending | Cross-organization tests under real DB roles |
| SEC-19 | Consent grants insufficiently validate patient/org/practitioner context | High | Policy defined; implementation incomplete | Schema, lifecycle, provenance and negative tests |
| SEC-20 | Excessive SQL grants, including TRUNCATE/TRIGGER/REFERENCES | Critical/High | Local SPEC-11 least-privilege migration and catalog checks recorded | Hosted grant snapshot and effective role tests |
| SEC-21 | SECURITY DEFINER functions insufficiently hardened | High | Local SPEC-11 records 4 reviewed hardened functions | Hosted owner/search_path/EXECUTE verification |
| SEC-22 | Image bucket size/MIME controls incomplete | Medium–High | Mitigated locally for 3 installed image buckets under SPEC-12 | Hosted bucket catalog and effective upload tests |
| SEC-23 | Duplicate patient SELECT policy | Low | Addressed/covered by SPEC-11 cleanup review; verify hosted state | Hosted policy inventory and duplicate check |
| SEC-24 | Storage access-policy/effective object access not proven | High | Direct client deny and public retrieval locally verified under SPEC-12 | Hosted Storage policy and effective-access verification |

### 3.1 Important current-source observations

The review of `1aff95b0ab7e15733a72d440ee6cbcf323d5e8ad` confirms the following remain visible:

- `backend/app/core/security.py` contains two definitions of `require_patient_access()`. Python's later definition shadows the earlier one, so behavior depends on the final definition and its callers.
- `require_permission(permission_name, org_id_param="org_id")` reads only `request.path_params`; it returns a 400 if the path parameter is absent. Its permission lookup uses the global `supabase` client.
- `backend/app/modules/medications/router.py` still exposes `GET /encounter/{encounter_id}` without `Depends(get_current_user)` or a patient-access check.
- `backend/app/api/admin/events_router.py` applies `get_current_user` but passes any authenticated user through to event read/replay functions without SPEC-09 role checks.

These are source observations, not claims that an exploit has been executed. The required tests must demonstrate the actual request behavior and ensure privileged database functions are not called before authorization.

---

# 4. Implementation and verification already recorded

## 4.1 Role catalogue and lifecycle

The current role catalogue resolves multiple assignments and avoids assigning an arbitrary scalar “primary role” when more than one recognized role exists. System and organization scope are distinguished.

The role-assignment lifecycle specification records:
- active/revoked assignments;
- prevention of self-granting;
- scoped delegation;
- separate system administrator delegation;
- protection against revoking the final active system administrator;
- append-only audit events;
- transactional role changes.

The initial lifecycle migration was reported applied to production. A later least-privilege follow-up was applied and verified locally, not yet verified in production. A two-session concurrency test was recorded for simultaneous attempts to revoke the final system administrator. The latest ACL follow-up used direct DB checks because Docker/Podman was unavailable for the standard pgTAP runner.

**Disposition:** meaningful progress; do not close SEC-10 or the lifecycle work until production grants/policies and effective role behavior are verified.

## 4.2 Policy specifications

Twelve documents exist under `docs/security/`:

1. `SPEC-01-role-catalogue-and-scopes.md`
2. `SPEC-02-role-assignment-lifecycle-and-delegation.md`
3. `SPEC-03-action-level-authorization-matrix.md`
4. `SPEC-04-patient-relationship-access-policy.md`
5. `SPEC-05-consent-evaluation-policy.md`
6. `SPEC-06-canonical-patient-access-grants.md`
7. `SPEC-07-organization-admin-patient-data-boundary.md`
8. `SPEC-08-system-admin-patient-data-and-break-glass-boundary.md`
9. `SPEC-09-operational-event-visibility-and-retry.md`
10. `SPEC-10-trusted-backend-and-caller-rls-access.md`
11. `SPEC-11-table-level-rls-and-grants.md`
12. `SPEC-12-storage-bucket-and-object-access.md`

These are policy specifications; they are not implementation work-package IDs. GitHub work packages use `PH0-WP-xx` to avoid the previous SPEC numbering collision.

## 4.3 SPEC-11 — RLS, grants and SQL functions

The local declarative inventory covers 26 public tables and distinguishes:
- `caller_rls`;
- `public_reference`;
- `service_only`;
- `append_only_audit`.

Recorded local evidence:
- RLS enabled and forced on all 26 reviewed tables;
- 18 approved policies;
- exact grant matching for `anon`, `authenticated` and `service_role`;
- removal of unnecessary client `TRUNCATE`, `MAINTAIN`, `TRIGGER` and `REFERENCES` privileges;
- four reviewed SECURITY DEFINER functions with restricted execution and fixed search paths;
- supporting indexes verified;
- 10/10 catalog assertions passed;
- 110 focused Python checks passed;
- 1,248 full backend tests passed, one skipped.

The migration and evidence are recorded as local. Hosted deployment and effective access verification remain outstanding.

**Coverage gap:** appointments, encounters, observations, conditions and medication_requests were absent from the reviewed local catalog. Confirm whether these relations are absent, named differently, in another schema, or not yet migrated. Reconcile application query paths, migration history, Supabase Data API exposure and hosted catalog before claiming complete coverage.

## 4.4 SPEC-12 — Storage

The installed image buckets recorded by SPEC-12 are:

| Bucket | Public retrieval | Max size | MIME allowlist |
|---|---:|---:|---|
| `organization-logos` | Yes | 2 MiB | JPEG, PNG, WebP |
| `patient-avatars` | Yes | 2 MiB | JPEG, PNG, WebP |
| `practitioner-photos` | Yes | 2 MiB | JPEG, PNG, WebP |

The implementation includes bucket classification, content-signature validation, size/MIME restrictions, owner-scoped paths, deterministic object names, trusted service-role upload paths and direct-client object access denial.

Recorded local evidence:
- 8/8 storage catalog assertions passed;
- anonymous upload denied;
- service-role upload succeeded;
- public GET returned HTTP 200 with byte-for-byte match;
- temporary verification object removed;
- 76 focused storage/avatar/organization tests passed;
- 1,272 full backend tests passed, one skipped;
- OpenAPI generation succeeded with 81 paths.

Hosted verification remains outstanding. Public patient-avatar retrieval is a product/privacy decision and should be explicitly confirmed; patient association with a healthcare platform can be sensitive. The planned `patient-documents` bucket is not installed and must be private with authorization-gated, short-lived signed URLs when introduced.

## 4.5 Tests and evidence integrity

The test counts above are recorded in the repository specifications and commit history. They were not independently rerun as part of this document update. The project must preserve exact command, environment, commit SHA, test count, skipped count and artifact/evidence location for each run.

---

# 5. Prioritized remediation roadmap

Work packages are numbered `PH0-WP-xx`; policy documents remain `SPEC-01` through `SPEC-12`. Existing GitHub issues #34–#36 are to be retitled to the work-package convention, not renumbered.

## Phase 0A — Contain critical authorization risks (P0, first)

### PH0-WP-01 — Authentication, role resolution and authorization foundations
**GitHub:** #34  
**Policy references:** SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-10  
**SEC:** SEC-01 through SEC-10

Order:
1. Inspect every current `require_patient_access` import/call site and both definitions.
2. Define one canonical dependency/service contract; do not merely delete one function without migrating callers.
3. Resolve patient, organization and practitioner context from the target resource or validated route parameters.
4. Correct `require_permission` so organization scope is explicit and resource-derived where required; remove the implicit path-only assumption.
5. Ensure permission lookups use a deliberately selected execution mode and do not silently depend on a global client with unknown caller identity.
6. Add authentication and authorization to medication-request encounter retrieval.
7. Apply SPEC-09 role-specific event visibility and retry guards to every event route (coordinate #35).
8. Verify the effective `user_roles` policy/grant state and role assignment RPC/API path.
9. Remove secrets/token/key logging.
10. Add focused positive and negative tests before moving to dependent clinical route work.

**Exit criteria:** one dependency contract, no unauthenticated protected route, no authenticated-but-unauthorized path to privileged reads, organization context fails closed, role assignment escalation is denied.

## Phase 0B — Clinical resource and relationship authorization (P0/P1)

### PH0-WP-02 — Clinical resource and relationship authorization
**GitHub:** #35  
**Policy references:** SPEC-03 through SPEC-09  
**SEC:** SEC-11 through SEC-16, SEC-19

Cover:
- Encounters: patient, practitioner, organization and resource ownership on create/read/update.
- Care teams: only authorized actors can assign/remove practitioners; no self-assignment to arbitrary patients.
- Practitioner roles: organization-scoped delegation; system role boundary; no self-escalation.
- Appointments: practitioner-specific list ownership; patient/practitioner/org relationship checks; role-specific mutable fields and status transitions.
- Observations/conditions: encounter-to-patient resolution and patient access before query.
- Medication requests: patient/encounter/organization relationship after WP-01 dependency.
- Consent: validated patient authority, recipient, resource-family scope, purpose, effective period, expiry, revocation and actor provenance.
- Audit every sensitive assignment, mutation and retry.

**Exit criteria:** every sensitive route has an authorization map; service/domain boundary prevents unguarded privileged repository calls; positive/negative cross-patient and cross-organization tests pass.

## Phase 0C — Canonical access grants, consent and database security (P1)

### PH0-WP-03 — PostgreSQL/Supabase RLS, grants and function hardening
**GitHub:** #36  
**Policy references:** SPEC-05, SPEC-06, SPEC-10, SPEC-11  
**SEC:** SEC-06, SEC-07, SEC-10, SEC-17, SEC-18, SEC-20, SEC-21, SEC-23

1. Implement `patient_access_grants` migration after schema review; define grantor/grantee, patient, organization, resource scope, status, effective time, expiry, revocation actor/time and audit.
2. Reconcile consent schema and service. Consider backend/RPC-only writes or narrowly scoped column grants/constraints so a patient-owned row cannot contain forged recipient/scope/grantor/lifecycle fields.
3. Inventory all schemas and relation types, not only a filtered list of ordinary public tables.
4. Reconcile all clinical relations used by application code with migration and hosted catalogs.
5. Review table grants, RLS policies, sequences, functions, triggers and Data API exposure for anon/authenticated/service_role.
6. Verify SECURITY DEFINER ownership, schema-qualified object references, fixed safe search_path and EXECUTE privileges.
7. Document every service-role call site and why bypass is necessary; verify app authorization precedes privileged execution.
8. Apply migrations only through reviewed migration workflow with before/after snapshots and rollback notes.

**Exit criteria:** complete table-by-table inventory; no unintended client privilege; cross-patient and cross-org Data API tests pass; canonical grant/consent lifecycle is enforced.

## Phase 0D — Storage and audit hardening (P1)

**Policy references:** SPEC-09, SPEC-12; GitHub #3, #16  
- Verify all installed buckets and effective object access in staging and production.
- Explicitly approve public patient-avatar retrieval or change it to private/opt-in.
- Keep clinical documents private; use short-lived authorized signed URLs.
- Verify upload/update/delete ownership and organization paths.
- Confirm audit schema captures actor, action, resource, timestamp, outcome and correlation ID without duplicating unnecessary PHI.
- Ensure audit records cannot be changed/deleted by ordinary roles and event/audit visibility is role-scoped.

## Phase 0E — Backend CI and release controls (P1)

**GitHub:** new #38  
- Add automated backend verification on pull requests and pushes to main.
- Required baseline: Python compile check and full backend pytest suite.
- Use dummy non-production configuration values for import-time settings; no production secrets in CI.
- Add separate database/Storage integration job when a safe ephemeral Supabase environment and deterministic test fixtures are available.
- Require successful status check before merging.
- Protect main against direct pushes, force pushes and deletion.
- Require PR review when a second reviewer is available; if the repository is single-maintainer, do not configure an approval rule that makes merging impossible.

## Phase 0F — Runtime verification and acceptance (P1)

**GitHub:** #31  
- Run focused authorization tests, full backend regression, database catalog checks and effective Storage API checks.
- Deploy reviewed migrations to staging first.
- Test using distinct anonymous, patient, practitioner, organization-admin and system-admin identities.
- Verify denied requests do not call privileged repositories/services.
- Compare staging/production catalogs with reviewed migration inventory.
- Record sanitized evidence, commit SHA, environment, timestamp, commands and results.
- Close each SEC finding only when its own evidence is complete.

---

# 6. Minimum security test matrix

For every protected resource family, include:

| Scenario | Expected result |
|---|---|
| No bearer token | 401 |
| Invalid/expired token | 401 |
| Authenticated user without required role | 403 or documented non-disclosing 404 |
| Correct role, wrong organization | Denied |
| Correct organization, no patient/resource relationship | Denied |
| Authorized owner/relationship holder | Only permitted records/fields returned |
| Read permission used for write/admin/retry | Denied |
| Client forges patient/practitioner/org/encounter/resource ID | Denied |
| Role assignment/grant revoked, expired or inactive | Denied |
| Ambiguous role or missing context | Denied |
| Privileged service-role query before authorization | Must not occur |
| Sensitive change/retry/access | Attributable audit record |

Tests must cover API-mediated access and direct database/Storage paths where those are enabled. Include concurrency tests for sensitive role lifecycle invariants.

---

# 7. Backend verification workflow and branch protection

## 7.1 CI baseline

The proposed GitHub Actions workflow is `.github/workflows/backend-ci.yml`. It should:
- run for pull requests targeting `main`, pushes to `main`, and manual dispatch;
- use a supported Python 3.13 runtime;
- install the backend's declared requirements;
- provide dummy CI-only environment values for settings that validate at import time;
- run compile checks and the full backend pytest suite;
- use read-only repository permissions, bounded runtime and concurrency cancellation;
- never use production Supabase/Resend credentials.

The CI check is a regression gate, not proof of hosted RLS or Storage security. Database catalog and effective-access verification remain separate acceptance evidence.

## 7.2 Branch protection recommended settings

After the workflow has run successfully on a pull request at least once, configure a ruleset or branch protection rule for `main`:

- Require a pull request before merging.
- Require the status check **Backend verification**.
- Require branches to be up to date before merging (recommended once CI is stable).
- Require conversation resolution.
- Dismiss stale approvals when new commits are pushed.
- Require at least one approval only if a second reviewer is available. Do not make the sole maintainer unable to merge.
- Block force pushes.
- Block branch deletion.
- Do not allow bypass for ordinary contributors; reserve any bypass for a documented emergency administrator process.

The GitHub connector used for this update does not expose a branch-protection/ruleset mutation operation. An authorized repository administrator must apply these settings in GitHub UI or via GitHub's repository rulesets/branch-protection API. The workflow file can be proposed in a PR, but branch protection must be configured separately.

---

# 8. GitHub tracking and traceability

## 8.1 Identifier convention

- `SEC-01`–`SEC-24`: security findings.
- `SPEC-01`–`SPEC-12`: policy documents under `docs/security/`.
- `PH0-WP-01` onward: implementation work packages/GitHub issues.

This resolves the previous collision where policy SPEC-02 and GitHub issue #35 both used the same SPEC identifier for different things.

## 8.2 Traceability register

| Work package / issue | Main scope | Current state |
|---|---|---|
| PH0-WP-01 / #34 | Authn, role resolution, authorization primitives, medication/events entry points | Open — P0 blockers remain |
| PH0-WP-02 / #35 | Clinical resources, relationships, appointments, consent enforcement | Open — local 45-route map and tests complete; hosted/runtime proof and closure remain |
| PH0-WP-03 / #36 | RLS, grants, functions, table inventory | Open — local work done; clinical coverage/hosted proof pending |
| Phase 0 index / #37 | Overall acceptance and links | Open — NOT ACCEPTED |
| Storage / #3 | Avatar/image uploads and object access | Open — local SPEC-12 progress; hosted/privacy verification pending |
| Audit / #16 | Audit completeness and access | Open — database protections do not prove application audit coverage |
| Consent / #17 | Consent and emergency contacts | Open — policy defined, lifecycle implementation incomplete |
| Platform / #20 | Deployment, migrations, secrets, operational hardening | Open — hosted verification and CI/branch controls pending |
| Verification / #31 | Security regression and runtime verification | Open — order 10 records local/CI evidence; hosted runtime evidence pending; NOT ACCEPTED |
| CI / #38 | Backend Actions workflow and main protection | Open — workflow exists and local CI-equivalent passes; required `Backend verification` status check not yet configured (owner action) |

Trace every closure as:

`SEC Finding → Policy SPEC → PH0 Work Package → Code/Migration → Focused Test → Full Regression → Staging/Production Evidence → Review → Closure`

Do not close the parent index while any critical/high finding is open or unverified.

---

# 9. Phase 0 acceptance criteria

Phase 0 may be accepted only when all of the following are demonstrated:

1. No unresolved critical authorization or privilege-escalation finding remains.
2. Every sensitive route has authentication and resource/action authorization.
3. One canonical patient-access dependency contract is used by all callers.
4. Organization context is validated from the resource or explicit operation context.
5. Role resolution is deterministic, scoped and resistant to self-escalation.
6. The patient-access grant and consent lifecycle are implemented, attributable and enforced.
7. Patient, practitioner, organization-admin and system-admin boundaries are tested.
8. All application relations, including clinical relations, are inventoried and reconciled with migrations and hosted schema.
9. RLS policies and grants are reviewed table by table and verified under real role contexts.
10. SECURITY DEFINER functions have reviewed ownership, search_path, object qualification and EXECUTE rights.
11. Service-role call sites are documented and guarded by application authorization.
12. Storage buckets have explicit public/private classification and tested object-level access.
13. Sensitive operations produce protected, attributable audit records.
14. Positive and negative security regression tests pass in CI.
15. Staging verification is complete; production configuration is compared against approved migrations before release.
16. Every SEC finding has a documented disposition and supporting evidence.
17. Branch protection requires the backend verification check for merges to main.

**Current acceptance decision: NOT ACCEPTED.** Progress can continue on non-sensitive work only where it does not depend on unresolved authorization controls. New clinical features and production release should wait until Phase 0A P0 blockers are closed.

---

# 10. Immediate execution order

1. PH0-WP-01: inspect and consolidate `security.py` dependency contracts, then update all callers.
2. Secure medication-request encounter retrieval.
3. Apply SPEC-09 role authorization to all administrative event operations.
4. Add focused negative tests and prove no privileged query occurs before authorization.
5. Complete caller-scoped RLS integration and inventory all query execution modes.
6. Implement patient-access grants and complete consent schema/lifecycle.
7. Reconcile missing clinical tables and apply reviewed RLS/grant policies.
8. Verify SPEC-11/SPEC-12 against staging and production.
9. Complete route-by-route clinical authorization.
10. Complete audit evidence, CI, branch protection and final acceptance review.

**Order 9 local status (24 November 2026):** the [route-by-route record](PH0-WP-02-route-authorization-order-9-record.md) maps all 45 mounted sensitive routes and records local positive/negative evidence. This does not close PH0-WP-02 or make Phase 0 accepted; hosted/runtime verification and the remaining SEC dispositions are still required.

**Order 10 status (24 November 2026):** the [final acceptance evidence record](PH0-WP-10-order-10-final-acceptance-evidence-record.md) records the 1,438-test local CI-equivalent run, the `Backend verification` workflow check, the current GitHub ruleset gap, read-only hosted drift evidence, and the 17-criterion review. The owner will apply the required status check; order 10 is finalized as evidence + STOP under the controlled release guide. Criterion 17 and the hosted verification/release gates remain unmet, so Phase 0 is **NOT ACCEPTED**.

**Do not mark a finding complete based only on documentation or local unit tests. Do not start another feature that expands sensitive data access while the P0 authorization blockers remain open.**

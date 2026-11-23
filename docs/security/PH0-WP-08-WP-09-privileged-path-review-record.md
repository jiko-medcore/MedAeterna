# PH0-WP-08/WP-09 Review Record — Audit Integrity and Privileged Path Coverage

**Work packages:** PH0-WP-08 (audit integrity and sensitive-operation coverage) and PH0-WP-09 (API contract, service-role and background-task review)

**Plan order:** order 8 in `backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md` and `PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md`

**Exit condition:** “Sensitive operations and privileged paths covered”

**Branch:** `security/phase-0-db-storage-release`

**Review base:** `e88cf31877abcd887bbbdcd9cc2be6a2782bddb2` plus the local working-tree changes described in this record

**Review date:** 23 November 2026

**Status:** **LOCAL REVIEW COMPLETE — NOT CLOSED, NOT ACCEPTED**

> This record documents source review, local catalog evidence, read-only production metadata evidence, and focused/full local regression results. It does not deploy anything, change hosted data, close a SEC finding, or accept Phase 0. No patient row data, token, secret, database connection string, SQL dump, or Storage object content was read or emitted. The three read-only baseline/plan/release-guide files were not modified.

---

## 1. Review method and target distinction

The required Supabase and Supabase Postgres best-practice skills were loaded, the Supabase changelog was checked, and current API-key/RLS documentation was reviewed. The current guidance is explicit that secret/service-role keys bypass RLS, identify the calling component rather than the human user, and must be used only in trusted servers, workers, and admin tools with their own authorization checks. It also confirms that Postgres checks grants before RLS policies. These points are the reason this review treats every privileged client call as requiring separate caller/worker evidence.

| Environment | Use in this record |
|---|---|
| Local backend source at `e88cf31` plus working-tree changes | Authoritative for code call sites, authorization gates, audit emission, OpenAPI declarations, and response projections. |
| Local Supabase stack (`127.0.0.1:58561` API, `127.0.0.1:58562` DB) | Read-only catalog evidence for applied audit/event table grants, RLS, definer functions, and triggers. It is a staging proxy only. |
| Hosted production `iyueixtpmzznyffshqon` | Read-only MCP metadata evidence to identify residual drift. No hosted mutation or effective-access test was performed. |
| Hosted staging/preview | None exists; `list_branches` previously returned `[]`. Local evidence is not staging evidence. |

No `--remote` CLI mutation, `db push`, `config push`, `apply_migration`, `migration repair`, object upload/delete, SEC closure, or Phase 0 acceptance was performed.

---

## 2. Code changes made during this review

Two narrow defects were found in the sensitive-path review and fixed locally.

| Change | Files | Reason |
|---|---|---|
| Audit service now accepts an optional `organization_id` and records it inside `metadata` without mutating the caller’s dictionary. | `backend/app/core/audit/service.py`, `backend/tests/core/test_audit_service.py` | Four organization modules (`branding`, `departments`, `healthcare_services`, `operating_hours`) already called `log_audit_event(organization_id=...)`, but the shared audit function did not accept that keyword. Those audit writes would have raised `TypeError` at runtime. The audit table has no `organization_id` column, so the scope is stored in the existing `metadata` JSONB field. |
| Disabled legacy `/events/*` routes are hidden from OpenAPI while continuing to return 404. | `backend/app/core/events/router.py`, `backend/tests/api/admin/test_spec09_event_authorization.py`, `backend/tests/core/test_openapi_security_contract.py` | The routes were already operationally disabled, but generated clients still advertised seven unauthenticated event read/retry operations. The hardened admin event router remains intentionally unmounted; hiding dead routes reduces false security surface without expanding HTTP behavior. |

The audit change is a local application-code fix only. It does not alter the database schema or depend on a new migration.

---

## 3. Audit coverage matrix

The matrix covers every sensitive-operation family named in PH0-WP-08. “Local” means source/catalog evidence in this workspace; “hosted” means read-only production metadata only.

| Sensitive operation | Local audit path | Fields/outcome evidence | Hosted status |
|---|---|---|---|
| Role assignment / role changes | SPEC-02 `change_user_role_assignment()` definer RPC and `role_assignment_audit`; admin role-assignment router | Dedicated audit table captures user, role, organization, action, actor, reason, timestamp. Local definer function is service-role-only with fixed `search_path`. | `role_assignment_audit` is service INSERT/SELECT only, but the function is client-executable in production metadata. Do not treat protected persistence as hosted-verified. |
| Membership / invitations | Organization onboarding and invitation services call `log_audit_event`; organization-configuration services record attributable actions | Actor, action, resource type/id and organization metadata are emitted for reviewed organization operations. | Production audit table drift applies; not hosted-verified. |
| Care-team assignment | `backend/app/modules/care_team/service.py` calls `audit_clinical_write()` for create, participant add/update, and assignment | Actor, action, resource type/id, patient id and organization id from the verified authorization context. Negative route/service tests prove authorization before the privileged write. | Not hosted-verified. |
| Consent | Consent routes/services are gated through the canonical clinical authorization path; consent decisions are policy-tested | Consent records are caller-RLS in the approved local model. Consent persistence and audit behavior remain fail-closed where full SPEC-05 lifecycle evidence is absent. | Production contains legacy table/policy drift; no hosted claim. |
| Patient grants | Local `patient_access_grant_audit` plus `record_patient_access_grant_audit()` definer function | Local audit table is service INSERT/SELECT only, RLS enabled and forced, with no client grants; grants are service-only in the reviewed model. | Table and function absent from production metadata. Explicit gap. |
| Clinical writes | `audit_clinical_write()` is the shared care-team audit helper; migrated clinical routes require an authorization context before service queries | Care-team mutations emit attributable records. Other clinical writes are covered by route/service authorization tests but not all emit dedicated audit rows. | Not hosted-verified. |
| Appointments | Appointment routes require relationship/workflow authorization; no dedicated appointment audit row was found in this review | Access control is evidenced; audit coverage is a residual gap rather than a claimed pass. | Not hosted-verified. |
| File operations | Organization branding service audits logo updates/removal through `_record_activity()` and emits organization events; Storage path/MIME/size rules are covered by WP-07 evidence | The `organization_id` keyword mismatch in this path is fixed. Direct client object access is denied locally by the SPEC-12 Storage policy. | Production Storage drift remains documented in the SPEC-11/SPEC-12 preflight record. |
| Administrative access | `backend/app/api/admin/{events,audit,metrics,role_assignments}_router.py` | System-admin purpose gates, safe projections, and audit-before-read where the hardened routes are used. Audit failure denies the sensitive read/retry. | Admin event/audit/metrics routers remain intentionally unmounted by `backend/main.py`; no new hosted surface is claimed. |
| Event retries / replay | `backend/app/api/admin/events_router.py`, `backend/app/core/events/{replay,service,dead_letter,monitoring}.py` | Replay writes attempted plus outcome audit records; audit failure before the CAS claim denies the operation. No payload or raw error text is audited. Retry-safety allowlist is intentionally empty. | Production event tables have broad client grants and no policies; hosted audit protection is not demonstrated. |

### 3.1 Audit persistence and integrity

Local read-only catalog checks after the reviewed local stack showed:

| Table | RLS enabled / forced | Policies | Relevant grants |
|---|---|---|---|
| `audit_logs` | true / true | 0 | `service_role`: INSERT, SELECT only |
| `role_assignment_audit` | true / true | 0 | `service_role`: INSERT, SELECT only |
| `patient_access_grant_audit` | true / true | 0 | `service_role`: INSERT, SELECT only |
| `events` | true / true | 0 | `service_role`: DELETE, INSERT, SELECT, UPDATE |
| `events_dead_letter` | true / true | 0 | `service_role`: DELETE, INSERT, SELECT, UPDATE |

No user-triggered UPDATE/DELETE/TRUNCATE audit triggers were found on those local tables; integrity is enforced by the grant set and forced RLS, not by a trigger. Ordinary client roles have no privilege on the local audit tables.

Read-only production metadata showed materially different state:

- `audit_logs`, `events`, and `events_dead_letter`: RLS enabled but **not forced**, no policies, and `anon`/`authenticated` hold DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE and UPDATE. `service_role` also retains those broad privileges.
- `role_assignment_audit`: service INSERT/SELECT only.
- `patient_access_grant_audit`: absent.
- No triggers on the checked audit/event tables.

Therefore **PH0-WP-08 protected-persistence acceptance is met only for the local reviewed model**. Production would permit ordinary roles to rewrite or delete audit history under its current grants; this is a blocking §8.3 drift item, not a new deployment action.

### 3.2 Audit failure behavior and redaction

- Hardened admin event/audit/metrics reads call audit before the sensitive query and deny on audit failure. Replay attempts audit before the CAS claim and audit the final outcome; pre-claim audit failure prevents replay.
- The dead-letter helper suppresses its own audit exception to avoid sensitive logging, and its callers/monitors surface the failed-operation state instead. This is not equivalent to a transactional audit guarantee.
- `backend/app/core/events/{emitter,dispatcher,dead_letter}` and inspected handlers use normalized error codes and opaque identifiers rather than credential prefixes, payloads, raw exception text, or patient identifiers, as recorded under SPEC-09.
- The central audit service writes only actor, actor type, action, resource type/id, and metadata; it does not log credentials or response bodies. Individual callers remain responsible for keeping metadata free of unnecessary clinical payloads.

---

## 4. Privileged execution modes and sensitive-path coverage

SPEC-10 defines three permitted modes: caller-scoped RLS, trusted service-role backend, and authenticated background worker. The reference evaluator and SDK wiring tests are already recorded in SPEC-10. This review checked the real call-site categories against those modes.

### 4.1 Client construction

| Pattern | Location | Intended mode | Evidence / limitation |
|---|---|---|---|
| Process-wide publishable-key client | `backend/app/core/supabase_client.py` (`supabase`) | Caller RLS only if a verified caller JWT is propagated; not automatic | Most existing shared-client call sites cannot be assumed to run with caller identity. No per-request DB dependency exists. |
| Process-wide privileged client | `backend/app/core/supabase_admin.py` (`supabase_admin`) | Trusted service-role backend / background worker | Used by audit, authorization lookups, clinical services, organization services, event helpers, and Storage helpers. Each call needs route/service authorization evidence. |
| Per-request caller-scoped client | `backend/app/core/supabase_client.py:create_caller_scoped_client()` | Caller RLS | Available and SDK-tested, but not generally adopted by existing query services. No global session mutation. |
| Storage admin writes | Organization branding storage helper and WP-07 service-role upload path | Trusted service-role | Application authorization must precede object mutation. Effective local Storage denials for clients were re-verified under WP-07. |

### 4.2 Sensitive-path groups

| Path group | Representative files | Authorization gate | Resource scope | Privilege reason / residual |
|---|---|---|---|---|
| Authentication, role and permission resolution | `app/core/security.py`, `app/api/admin/role_assignments_router.py` | Verified JWT plus resource-derived/fail-closed role, permission, patient and organization checks | Stored role rows, active organization assignment, resolved patient/encounter | Privileged reads are needed because role tables are service-only. Every touched route is gated; repository-wide caller-scoped migration remains open. |
| Clinical resource and relationship checks | `app/core/clinical_authorization.py`, six PH0-WP-02 routers/services | `ensure_authorized_context()` rejects missing/mismatched action, patient, organization, and resource before service queries | Resource loaded from trusted storage; client IDs are not relationship evidence | Service role is justified for service-only clinical/access tables. Direct service calls without context fail closed. |
| Care-team and organization mutations | `app/modules/care_team/service.py`, `app/modules/organizations/**` | Route dependencies and service-boundary checks; audit before/around mutation | Stored patient/organization/resource row | Privileged writes are required by service-only tables. Fixed `organization_id` audit keyword mismatch; several non-clinical organization writes still need route-by-route completeness evidence. |
| Patient onboarding and profile | `app/modules/patients/service.py`, `onboarding.py` | Authentication plus patient-scoped authorization on migrated routes | Patient id from verified context | Audit emission exists; full caller-RLS adoption is not claimed. |
| Operational event reads/retries | `app/api/admin/events_router.py`, `app/core/events/monitoring.py`, `service.py`, `replay.py` | System-admin role, approved purpose, retry safety allowlist, single-event state gates, audit-before-access | Opaque event reference or allowlisted aggregate; no payload/raw error projection | Event tables are service-only, so privileged reads are expected. Hardened router is not mounted; no handler is approved for manual retry; CAS claim is not a single DB transaction. |
| Event emission / dead-letter | `app/core/events/emitter.py`, `dispatcher.py`, `dead_letter.py`, `bootstrap.py` | Worker/process context, not a human caller; handler registry and bounded retry state | Event aggregate and opaque event reference | Privileged writes are expected for service-only event tables. Worker identity/purpose evidence remains weaker than the SPEC-10 model. |
| Audit writes | `app/core/audit/service.py` | Caller route gate occurs before the audit call in migrated sensitive paths | Actor/resource/scope from trusted context | Privileged INSERT is required; local audit table is append-only by grants. Production drift blocks hosted claim. |

The grouped inventory above is the review artifact for this order; exact call sites remain in the cited source files and are exercised by the focused tests recorded in section 6. No service-role call was treated as authorized merely because a JWT was verified or because the service client exists.

---

## 5. Background-task and tenant-isolation review

| Area | Finding |
|---|---|
| Event bootstrap / handlers | `app/core/events/bootstrap.py` registers handlers; no Celery/Redis/RQ/APScheduler worker was found. Work is in-process/event-driven rather than an independently authenticated queue consumer. |
| FastAPI `BackgroundTasks` | `POST /organizations/register`, `GET /patients/me` on first creation, and an unused `POST /auth/login` parameter schedule/declare background work. `process_events_task()` calls `process_pending_events()`, which uses the privileged client to recover stuck work, requeue eligible failures, and process pending/failed events across the queue. Human-triggered scheduling does not retain the original actor/authorization decision in protected audit metadata. |
| Retry / replay | Background retries are separated from human retry authorization. Manual replay is single-event, state-limited, purpose-bound, and CAS-claimed, but the retry-safety allowlist is empty and the claim plus queue insert is not one transaction. |
| Tenant isolation | Migrated clinical routes derive patient/organization scope from stored resources and reject mismatches in route dependencies and service boundaries. The global event processor consumes all tenants server-side rather than returning cross-tenant rows to an operator, but it has no worker purpose allowlist or per-job target constraint. Event org-admin visibility remains fail-closed because no trusted event-to-organization resolver exists. |
| Worker identity | No project-specific worker identity or purpose credential was found for in-process event helpers. `process_pending_events()` selects full event rows internally for dispatch (not for operator responses), but the worker has no allowlisted purpose/target gate. This is a residual SPEC-10 gap; local service-role capability must not be mistaken for worker authentication. |
| Trusted inputs | Event payloads, client filters, and client-supplied organization IDs are not accepted as ownership/membership proof in the hardened paths. Raw payloads are never returned by safe projections. |

---

## 6. Verification evidence

All Python commands ran from `backend/` with `.venv/Scripts/python.exe`; all Supabase CLI commands used the local stack default and did not pass `--remote`.

| ID | Check | Result |
|---|---|---|
| E-08/09-01 | Focused audit, OpenAPI, SPEC-09 route, branding and organization service tests | **223 passed** |
| E-08/09-02 | Full backend regression: `-m pytest -q --tb=no -p no:cacheprovider` | **1,372 passed, 1 skipped, 18 warnings** |
| E-08/09-03 | OpenAPI generation after fix | **74 paths, 89 operations, 83 secured, 6 intentionally public**; no `/events` paths |
| E-08/09-04 | Intentionally public operations | `POST /auth/signup`, `POST /auth/login`, `POST /organizations/register`, `POST /organizations/accept-invite`, `GET /`, `GET /health` |
| E-08/09-05 | Local database tests | `supabase test db`: **3 files, 36 tests, PASS** |
| E-08/09-06 | Local WARN-level advisories | `supabase db advisors --type all --level warn`: **No issues found** |
| E-08/09-07 | Local read-only catalog | Audit/event tables forced RLS with service-only grants; seven definer functions pinned to `pg_catalog, public` and executable only by `postgres`/`service_role`; no audit/event triggers |
| E-08/09-08 | Read-only production metadata | Audit/event grants and definer-function exposure drift confirmed; no production data, object content, or logs read |
| E-08/09-09 | Patch hygiene | `git diff --check` clean at review time |

The full suite count increased from the previously recorded 1,368 to 1,372 because four new focused tests were added in this review (two audit-service tests and two OpenAPI contract tests).

---

## 7. Residual gaps and disposition

| Gap | Disposition |
|---|---|
| Production `audit_logs`, `events`, and `events_dead_letter` allow ordinary client CRUD/TRUNCATE and are not forced | Blocking drift. Must be fixed only through the reviewed release plan after backup/recovery and exact deployment authorization. |
| Production `patient_access_grant_audit` and three local definer functions are absent; three legacy definer functions remain client-executable with two mutable search paths | Blocking drift. No repair or revocation attempted here. |
| Hosted effective anon/authenticated/service-role audit and event tests not run | Production verification remains order 10 / PH0-WP-10 work. |
| Hardened admin event/audit/metrics routers are not mounted | Intentional in this slice; no expanded deployed surface is claimed. Mounting needs an explicit reviewed decision. |
| Caller-scoped RLS client exists but is not generally used by query services | SPEC-10 service-role call-site justification remains local and incomplete for the full repository. |
| No dedicated authenticated worker identity/purpose credential for in-process event helpers; human-triggered `BackgroundTasks` do not retain actor/authorization metadata | SPEC-10 background-worker evidence gap; no new worker is invented in this review. |
| Manual retry allowlist is empty and replay claim/insert is not one database transaction | Fail-closed behavior is correct; full atomicity and handler approval remain remediation work. |
| Organization-admin scoped event reads require a trusted resolver | Remain disabled/fail-closed; no policy guessing. |
| Backup export, Storage object backup, restore test, recovery owners, dry-run, and full §8.5 authorization are incomplete | Production deployment remains blocked under the controlled guide and PH0-WP-10 gate record. |

---

## 8. Outcome

The order 8 review is complete for the local release candidate: audit emission, privileged client construction, sensitive-route groups, event/background paths, OpenAPI declarations, local audit persistence, and read-only production drift are documented. The two concrete defects found in this review were fixed and regression-tested locally.

This record does **not** claim that privileged paths are production-safe. Hosted audit history remains unprotected under current production grants, caller-scoped RLS adoption is incomplete, background-worker identity evidence is incomplete, and event retry remains fail-closed. SEC findings remain open, production remains unchanged, and Phase 0 remains **NOT ACCEPTED**.

---

## 9. Cross-references

- [Backend plan — recommended execution order 8](../../backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md)
- [Controlled Supabase database and Storage release guide](../../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- [SPEC-03 — action-level authorization matrix](SPEC-03-action-level-authorization-matrix.md)
- [SPEC-09 — operational-event visibility and retry](SPEC-09-operational-event-visibility-and-retry.md)
- [SPEC-10 — trusted backend and caller-RLS access](SPEC-10-trusted-backend-and-caller-rls-access.md)
- [SPEC-11 — table-level RLS and grants](SPEC-11-table-level-rls-and-grants.md)
- [SPEC-11/SPEC-12 hosted read-only preflight record](SPEC-11-SPEC-12-hosted-read-only-preflight-record.md)
- [PH0-WP-02 completion record](PH0-WP-02-completion-record.md)
- [PH0-WP-05 completion record](PH0-WP-05-completion-record.md)
- [PH0-WP-07 completion record](PH0-WP-07-completion-record.md)
- [PH0-WP-10 backup and recovery gate record](PH0-WP-10-backup-recovery-gate-record.md)

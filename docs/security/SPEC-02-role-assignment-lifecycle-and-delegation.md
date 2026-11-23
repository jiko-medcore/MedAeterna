# SPEC-02: Role Assignment Lifecycle and Delegation

**Status:** Lifecycle behavior is implemented. A local least-privilege follow-up has been applied and verified; that follow-up has not been deployed to production.

**Order 5 approval (21 November 2026):** Approved for implementation by the designated MedAeterna technical/security owner for the documented decisions only; not production acceptance. Undocumented choices remain fail-closed. See [PH0-WP-06 policy approval record](PH0-WP-06-SPEC-approval-and-consent-access-model.md).

## Decisions

### Lifecycle

- A persisted `user_roles` assignment has `active` or `revoked` status. Existing rows are backfilled as active by the migration; authorization ignores assignments unless the row status is active and the role definition is active.
- Assignments take effect immediately and remain active until revoked. Scheduled activation and automatic expiry are out of scope for this iteration.
- Revocation records `revoked_at`, `revoked_by`, and a reason. Revocation is terminal for that assignment cycle. Regranting the same role/scope reactivates the unique assignment row and appends another audit event; `assigned_at` and `assigned_by` are reset for the current active cycle.
- Duplicate active grants are rejected. Revoking a missing or already revoked assignment is rejected.
- The final active `super_admin` cannot be revoked. No second approver is required in this iteration; all grant/revoke events are recorded in an append-only audit table, self-grant is prohibited, and the final system administrator is protected. Revisit dual approval before broad production role delegation.

### Delegation

| Actor | May grant/revoke | Must not grant/revoke |
|---|---|---|
| Organization administrator | Practitioner-category assignments (`practitioner`, `doctor`, `clinician`, `nurse`, `laboratory scientist`, `lab-tech`) in the same organization | Any role in another organization; `org_admin`; `super_admin`; patient roles; unmapped roles; a role for themselves |
| System administrator (`super_admin`) through the separate system path | Organization-scoped `org_admin` and system-scoped `super_admin` assignments for other users; org role IDs and scope must match | Patient roles; a role for themselves; inactive or unmapped roles |
| Trusted onboarding code | `patient` at global scope; initial `org_admin` assignment during organization registration; organization invitation acceptance after revalidating the inviter | Arbitrary roles or caller-supplied delegation |
| Ordinary user/practitioner | None | Any assignment or revocation through the role-management APIs |

Self-revocation is permitted because it only reduces authority. The last active system administrator is protected at the database write boundary.

**Order 8 follow-up (23 November 2026, local):** organization-scoped `practitioner_roles` records are now gated by the same SPEC-02 delegation rule (`authorize_practitioner_role_change` / `authorize_practitioner_role_read`): an org administrator for the exact target organization is required, self-assignment is denied, and writes are audit-before-mutation. `POST /practitioner-roles/` now requires a `practitioner_id` for the target practitioner; the previous self-assignment behavior was an authorization bypass. See the [PH0-WP-08/WP-09 review record](PH0-WP-08-WP-09-privileged-path-review-record.md) §10. Not deployed; production unchanged.

### Enforcement and audit

- Role assignment writes use the `change_user_role_assignment` database function. Direct `INSERT`, `UPDATE`, and `DELETE` by `anon` or `authenticated` are revoked; DML is limited to the trusted `service_role` path.
- The database function validates active role definitions, role/assignment organization scope, lifecycle transitions, and self-grant prohibition, then changes the assignment and appends its audit record in one transaction.
- Anonymous clients have no `user_roles` privileges. Authenticated clients may SELECT only rows allowed by the existing RLS policy and cannot write or truncate the table. The trusted `service_role` receives only the SELECT and DML privileges required by the backend workflow; it cannot truncate or maintain the table.
- Application policy validates the actor's current scoped category, permitted delegation, target account, and requested organization before invoking the trusted function.
- Organization administrators use `/organizations/{org_id}/assign-role` to grant and `DELETE /organizations/{org_id}/assign-role` to revoke. System administrators use `/admin/role-assignments` for grants and revocations. Both require a reason on revocation.
- Invitations are limited to roles the inviter may delegate; the inviter must still hold organization-admin authority when the invitation is accepted. An inviter cannot invite their own email.
- Patient role assignment is restricted to trusted signup/onboarding. Database RLS/grants prevent direct client role writes even if an API check is bypassed.

## Acceptance criteria and verification

- [x] Assignment scope, lifecycle, and allowed delegations are explicit.
- [x] Self-assignment and organization-to-organization escalation are denied in the application policy.
- [x] Org administrators cannot grant admin or system roles; only the dedicated system path can.
- [x] Inactive roles, malformed scopes, and unmapped roles are rejected.
- [x] Assignment and revocation are transactional with an append-only audit event.
- [x] Revoked assignments are excluded from authorization and active permission lookup.
- [x] Database client roles cannot directly create, update, or delete role assignments.
- [x] Local ACL verification confirms `anon` and `authenticated` cannot truncate `user_roles`, and `service_role` has no TRUNCATE, MAINTAIN, REFERENCES, or TRIGGER privilege.
- [x] pgTAP suite passes locally: 37 assertions covering database grants, policy structure, lifecycle transitions, audit events, scope checks, and the final-system-admin guard.
- [x] SPEC-02 migration is applied to production project `iyueixtpmzznyffshqon`; Supabase migration history confirms it is applied.
- [x] Independently inspect effective role privileges and RLS configuration against production; findings are recorded below. Runtime RLS behavior under client JWT identities remains untested.
- [x] Run a two-session concurrency test for simultaneous final-system-admin revocations against the local database.

### Production verification (2026-11-18)

Read-only verification was performed against production project `iyueixtpmzznyffshqon` through project-scoped Supabase MCP. Migration history contains `20261117150000` (`role_assignment_lifecycle`). The live `change_user_role_assignment` definition matches the migration's guard: it takes a transaction advisory lock before counting active system administrators, and the database reports `READ COMMITTED` isolation. RLS policies and effective grants were inspected from PostgreSQL catalogs; no client JWT behavior test was run.

The SPEC-02-specific protections are partially present: RLS is enabled on `user_roles` and `role_assignment_audit`; `anon` and `authenticated` lack INSERT, UPDATE, DELETE, and TRUNCATE on `user_roles`; the `user_roles` SELECT policy is limited to `auth.uid() = user_id`; and only `service_role` can execute `change_user_role_assignment`. `role_assignment_audit` gives clients no table privileges, while `service_role` has SELECT and INSERT but no UPDATE, DELETE, or TRUNCATE. However, the effective `service_role` ACL on `user_roles` still includes TRUNCATE (as well as MAINTAIN, REFERENCES, and TRIGGER), so the trusted database write boundary is not fully enforced at the table privilege layer.

The broader production database does not meet the Phase 0 least-privilege baseline. All 26 public tables have RLS enabled, but 21 have no RLS policies. Effective ACL checks show `anon` and `authenticated` each have TRUNCATE on 24 public tables and MAINTAIN on 25; RLS does not restrict TRUNCATE. In addition, `get_user_permissions(uuid)`, `can_manage_roles()`, and `is_admin_user()` are SECURITY DEFINER functions executable by `anon` and `authenticated`; the permission lookup accepts an arbitrary user ID. These are production remediation findings, not successful acceptance results. Supabase security advisors also report these function grants and broad GraphQL table visibility.

No concurrency test was run against production. The local test and outcome are recorded below; production administrators were not modified.

### Local SPEC-02 re-review (2026-11-18)

The local Supabase MCP endpoint at `http://127.0.0.1:58561/mcp` was initialized successfully. It exposed the local database tools, returned the public schema, and executed read-only catalog queries against the local Postgres database. The local `user_roles` table had RLS enabled and denied client DML, but effective ACL inspection found that `service_role` still had TRUNCATE, REFERENCES, TRIGGER, and MAINTAIN. RLS does not constrain those table-level capabilities.

Migration `20261118150000_role_assignment_least_privilege` was applied to the local database and recorded in its migration history. It clears inherited/direct privileges on `user_roles`, grants authenticated SELECT subject to the existing RLS policy, and grants the trusted backend SELECT/INSERT/UPDATE/DELETE only. Migration `20261118160000_role_assignment_anon_read` removes anonymous SELECT. Follow-up catalog checks confirmed anonymous role access and client TRUNCATE are false, authenticated RLS-filtered SELECT is retained, service-role DML is retained, and service-role TRUNCATE/REFERENCES/TRIGGER/MAINTAIN are false. The existing schema snapshot was marked applied after confirming that its role-assignment schema already existed locally; the two historical migrations whose files were removed in this checkout were marked reverted so the local migration history matches the current squashed baseline.

The focused pgTAP file is present at `backend/supabase/tests/database/spec02_role_assignment_privileges.test.sql`. The standard `supabase test db` command could not run because Docker/Podman is not installed. All ten equivalent ACL conditions were checked through one local MCP SQL query and returned true. A direct two-session test at READ COMMITTED concurrently revoked two fixture system-admin assignments: one revocation succeeded, the other was rejected with SQLSTATE `23514`, and exactly one active system-admin assignment remained. Test fixtures were removed. The reproducible test is `backend/tests/auth/test_role_assignment_concurrency.py`, which requires `SPEC02_TEST_DATABASE_URL` and rejects non-local database hosts. No production migration was applied.

## Implementation references

- `backend/app/core/role_assignment_policy.py`
- `backend/app/modules/auth/role_assignment_service.py`
- `backend/app/api/admin/role_assignments_router.py`
- `backend/supabase/migrations/20261118135846_remote_schema.sql` (current local baseline snapshot)
- `backend/supabase/migrations/20261118150000_role_assignment_least_privilege.sql` (local follow-up migration)
- `backend/supabase/migrations/20261118160000_role_assignment_anon_read.sql` (anonymous access removal)
- `backend/supabase/tests/database/spec02_role_assignment_privileges.test.sql`
- `backend/sql/Security/role_assignment_lifecycle.sql` (source mirror)
- `backend/tests/auth/test_role_assignment_policy.py`
- `backend/tests/auth/test_role_assignment_service.py`
- `backend/tests/auth/test_role_assignment_concurrency.py`

The initial lifecycle implementation and its pgTAP suite were completed in prior work. This re-review added narrowly scoped local ACL migrations, verified all effective privilege conditions through MCP SQL, and passed the two-session concurrency test. The standard pgTAP runner remains open because Docker/Podman is unavailable. The production lifecycle migration remains applied; the new least-privilege follow-up has not been applied to production. Broader production privilege/RLS findings remain documented above.

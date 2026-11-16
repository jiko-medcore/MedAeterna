# SPEC-02: Role Assignment Lifecycle and Delegation

**Status:** Implemented. Database migration must be applied before deploying the updated backend.

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

### Enforcement and audit

- Role assignment writes use the `change_user_role_assignment` database function. Direct `INSERT`, `UPDATE`, and `DELETE` by `anon` or `authenticated` are revoked; DML is limited to the trusted `service_role` path.
- The database function validates active role definitions, role/assignment organization scope, lifecycle transitions, and self-grant prohibition, then changes the assignment and appends its audit record in one transaction.
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
- [ ] Apply the migration in the controlled Supabase environment and verify role privileges/RLS there.
- [ ] Run API/database integration tests against a controlled Supabase environment, including concurrency and last-system-admin checks.

## Implementation references

- `backend/app/core/role_assignment_policy.py`
- `backend/app/modules/auth/role_assignment_service.py`
- `backend/app/api/admin/role_assignments_router.py`
- `backend/sql/Security/role_assignment_lifecycle.sql`

The application/unit-test acceptance checks can run without production credentials. Database-policy and transactional guarantees require applying the migration to a controlled Supabase test project; they are not established by static inspection alone.

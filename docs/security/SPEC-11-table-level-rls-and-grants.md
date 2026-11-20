# SPEC-11: Table-by-Table RLS and SQL Grants

**Status:** The intended access model, least-privilege migration, and catalog tests are defined. The migration has been applied to the local Supabase database and the live catalog matches the model. Hosted/deployed verification and route-level integration remain separate remediation work.

## Decision

Every relation in `public` must have one reviewed access class, an explicit grant set for `anon`, `authenticated`, and `service_role`, and an explicit RLS policy set. Enablement alone is not a policy. A relation that is absent from the inventory is denied by default: no grants and no policies are issued for it.

`service_role` has `BYPASSRLS`; it is a capability, not caller authorization. Every service-role operation still needs the evidence required by SPEC-10. Client roles never receive `TRUNCATE`, `MAINTAIN`, `TRIGGER`, or `REFERENCES` on an application table.

## Access classes

| Class | Meaning | Execution mode (SPEC-10) |
|---|---|---|
| `caller_rls` | Direct client access allowed only for the caller's own rows; the caller JWT must be propagated to PostgREST. | `caller_rls` |
| `public_reference` | Non-sensitive reference data that may be read before sign-in. Writes remain service-only. | `caller_rls` |
| `service_only` | No client table privilege and no policy; all access goes through an authorized backend path. | `service_role` |
| `append_only_audit` | No client privilege and no policy; service role may SELECT/INSERT only, never UPDATE/DELETE/TRUNCATE. | `service_role` |

## Reviewed catalog snapshot

The model was written against the local Supabase catalog on 2026-11-20: 26 relations in `public`, 21 with zero policies, client `TRUNCATE`/`MAINTAIN`-equivalent broad grants on 24 tables, and three client-executable SECURITY DEFINER functions. No patient data was read.

## Table-by-table inventory

| Table | Class | `anon` | `authenticated` | `service_role` | Policies | Required indexes | Notes |
|---|---|---|---|---|---|---|---|
| `audit_logs` | `append_only_audit` | — | — | INSERT, SELECT | — | `audit_logs(actor_id)`<br>`audit_logs(created_at)` | No client privileges; no UPDATE/DELETE/TRUNCATE for any role. |
| `care_teams` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `care_teams(patient_id, clinician_id)`<br>`care_teams(clinician_id)` |  |
| `clinicians_patients` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `clinicians_patients(patient_id)`<br>`clinicians_patients(clinician_id)` |  |
| `consent_records` | `caller_rls` | — | INSERT, SELECT, UPDATE | INSERT, SELECT, UPDATE | `Patients read own consent` (SELECT, authenticated)<br>`Patients insert own consent` (INSERT, authenticated)<br>`Patients update own consent` (UPDATE, authenticated) | `consent_records(patient_id)`<br>`consent_records(organization_id)`<br>`consent_records(practitioner_id)`<br>`consent_records(status)` | Revocation is an UPDATE; DELETE is never granted. |
| `departments` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `departments(organization_id)`<br>`departments(deleted_at)` |  |
| `events` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `events(status)`<br>`events(aggregate_type, aggregate_id)` | Event payloads may contain patient data (SPEC-09). |
| `events_dead_letter` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `events_dead_letter(original_event_id)`<br>`events_dead_letter(replayed)`<br>`events_dead_letter(failed_at)` |  |
| `healthcare_services` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `healthcare_services(organization_id)` |  |
| `invitations` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `invitations(organization_id)`<br>`invitations(token)` | Invitation tokens are secrets; no direct client access. |
| `lab_results` | `caller_rls` | — | SELECT | INSERT, SELECT, UPDATE | `Patients read own lab results` (SELECT, authenticated) | `lab_results(patient_id)`<br>`lab_results(clinician_id)` |  |
| `medical_records` | `caller_rls` | — | SELECT | INSERT, SELECT, UPDATE | `Patients read own medical records` (SELECT, authenticated) | `medical_records(patient_id)` | Practitioner writes use service role with SPEC-03/04/05 evidence. |
| `organization_operating_hours` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `organization_operating_hours(organization_id)` |  |
| `organizations` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `organizations(id)` |  |
| `patient_care_team` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `patient_care_team(patient_id)`<br>`patient_care_team(practitioner_id)`<br>`patient_care_team(organization_id)` |  |
| `patients` | `caller_rls` | — | INSERT, SELECT, UPDATE | DELETE, INSERT, SELECT, UPDATE | `Patients read own record` (SELECT, authenticated)<br>`Patients insert own record` (INSERT, authenticated)<br>`Patients update own record` (UPDATE, authenticated) | `patients(id)`<br>`patients(organization_id)` | Consolidate the two legacy duplicate SELECT policies into one. |
| `permissions` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `permissions(name)` |  |
| `practitioner_roles` | `caller_rls` | — | SELECT | INSERT, SELECT, UPDATE | `Practitioners read own roles` (SELECT, authenticated) | `practitioner_roles(practitioner_id)`<br>`practitioners(profile_id)` |  |
| `practitioners` | `caller_rls` | — | SELECT | INSERT, SELECT, UPDATE | `Practitioners read own profile` (SELECT, authenticated) | `practitioners(id)`<br>`practitioners(profile_id)` |  |
| `prescriptions` | `caller_rls` | — | SELECT | INSERT, SELECT, UPDATE | `Patients read own prescriptions` (SELECT, authenticated) | `prescriptions(patient_id)` |  |
| `profiles` | `caller_rls` | — | INSERT, SELECT, UPDATE | DELETE, INSERT, SELECT, UPDATE | `Users read own profile` (SELECT, authenticated)<br>`Users insert own profile` (INSERT, authenticated)<br>`Users update own profile` (UPDATE, authenticated) | `profiles(id)` |  |
| `reminders` | `caller_rls` | — | SELECT | INSERT, SELECT, UPDATE | `Patients read own reminders` (SELECT, authenticated) | `reminders(patient_id)` |  |
| `role_assignment_audit` | `append_only_audit` | — | — | INSERT, SELECT | — | `role_assignment_audit(user_id)` | Already restricted by SPEC-02 migration; preserved here. |
| `role_permissions` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `role_permissions(role_id)`<br>`role_permissions(permission_id)` |  |
| `roles` | `service_only` | — | — | DELETE, INSERT, SELECT, UPDATE | — | `roles(organization_id)`<br>`roles(is_active)` |  |
| `terminology_codes` | `public_reference` | SELECT | SELECT | DELETE, INSERT, SELECT, UPDATE | `Read-only terminology` (SELECT, anon, authenticated) | `terminology_codes(system, code)` |  |
| `user_roles` | `caller_rls` | — | SELECT | DELETE, INSERT, SELECT, UPDATE | `Users read own roles` (SELECT, authenticated)<br>`Trusted service manages assignments` (ALL, service_role) | `user_roles(user_id)`<br>`user_roles(organization_id)` | Writes must go through public.change_user_role_assignment (SPEC-02). |

## Trusted SECURITY DEFINER functions

| Signature | Required `search_path` | Allowed EXECUTE | Notes |
|---|---|---|---|
| `can_manage_roles()` | `pg_catalog, public` | service_role | Legacy helper; retained only for trusted backend compatibility. |
| `change_user_role_assignment(p_user_id uuid, p_role_id uuid, p_organization_id uuid, p_actor_id uuid, p_actor_type text, p_action text, p_reason text)` | `pg_catalog, public` | service_role | SPEC-02 trusted role assignment RPC; already hardened. |
| `get_user_permissions(uid uuid)` | `pg_catalog, public` | service_role | Accepts an arbitrary user ID; must never be client-callable. |
| `is_admin_user()` | `pg_catalog, public` | service_role | Uses unmapped legacy role name 'admin'; retained only for service role. |

`generate_patient_medical_id()` and `update_updated_at_column()` are invoker functions and are not part of the trusted-definer inventory.

## Planned but not yet installed

These relations are committed to by earlier SPECs/findings but are absent from the reviewed catalog. They are **not covered** by this migration. The migration that creates each one must add it to `DATABASE_ACCESS_INVENTORY` in the same change.

| Table | Required decision |
|---|---|
| `appointments` | SPEC-03/04: patient self-read plus trusted backend workflow access |
| `conditions` | SPEC-03/04/05: patient self-read plus trusted backend clinical access |
| `encounters` | SPEC-03/04: patient self-read plus trusted backend clinical access |
| `medication_requests` | SEC-08: patient self-read plus trusted backend clinical access |
| `observations` | SPEC-03/04/05: patient self-read plus trusted backend clinical access |
| `patient_access_grants` | SPEC-06: patient-owned read grants, patient self-service plus service-role expiry worker |
| `patient_admin_data` | SPEC-07: view with security_invoker = true in a private schema, service_role only |

## Policy construction rules

- Predicates use `(select auth.uid())` so the JWT lookup is evaluated once.
- Policies name their target role explicitly with `TO authenticated` or `TO anon, authenticated`; no policy relies on the implicit `public` role.
- `INSERT` policies use only `WITH CHECK`. `UPDATE` policies use both `USING` and `WITH CHECK`.
- Historical duplicate policies are dropped, not layered. The two legacy `patients` SELECT policies and the weak `medical_records` clinician INSERT policy are removed.
- Clinical writes are not granted to clients. A policy that only checks `clinician_id = auth.uid()` cannot enforce organization scope, treatment relationship, consent, or workflow, so those writes must use the service-role path with SPEC-03/04/05 evidence.
- `FORCE ROW LEVEL SECURITY` is applied to every reviewed table. Roles with `BYPASSRLS` still bypass; table owners do not silently bypass.

## Files

- Reference model: `backend/app/core/table_access_inventory.py`
- Migration: `backend/supabase/migrations/20261120095915_spec11_table_rls_and_grants.sql`
- Python tests: `backend/tests/core/test_table_access_inventory.py`
- Catalog tests: `backend/supabase/tests/database/spec11_table_privileges_and_policies.test.sql`

## Acceptance criteria

1. Every deployed public relation has an entry in `DATABASE_ACCESS_INVENTORY`; `coverage_gaps([])` over the catalog is empty.
2. `anon` has no table privilege except SELECT on `terminology_codes`.
3. `authenticated` has only the SELECT/INSERT/UPDATE commands listed above; no `TRUNCATE`, `MAINTAIN`, `TRIGGER`, `REFERENCES`, or `DELETE` on any reviewed table.
4. `service_role` has no `TRUNCATE`, `MAINTAIN`, `TRIGGER`, or `REFERENCES`; audit tables are SELECT/INSERT only.
5. RLS is enabled and forced on all 26 reviewed tables.
6. Policy names, commands, roles, and predicates match the inventory; no legacy duplicate or weak clinical-write policy remains.
7. Predicates wrap `auth.uid()` in `SELECT` and are backed by the listed indexes.
8. All SECURITY DEFINER functions have fixed `search_path = pg_catalog, public` and only `service_role` can execute them.
9. Focused Python and pgTAP/catalog checks pass, and the results are recorded with no patient data in output.
10. Planned-but-uninstalled tables remain explicitly uncovered until their creation migration updates the inventory.

## Verification evidence (local, 2026-11-20)

The migration was applied through the Supabase MCP `apply_migration` endpoint. `apply_migration` assigns its own version timestamp, so it is recorded in `supabase_migrations.schema_migrations` and the repository migration file as `20261120095915 / spec11_table_rls_and_grants` to reconcile local release history drift. The applied SQL is byte-for-byte reproducible from `app/core/table_access_inventory.py`.

Live catalog checks against the applied database:

- 26 reviewed tables exist with `relrowsecurity = true` and `relforcerowsecurity = true`.
- Grants for `anon`, `authenticated`, and `service_role` match the inventory exactly for all 26 tables (no extra or missing table privilege).
- All 18 approved policies exist with matching name, command, role, `USING`, and `WITH CHECK` expressions; no legacy or duplicate policy remains.
- Every `auth.uid()` occurrence in a policy expression is inside a wrapped `(select auth.uid())` subquery.
- `anon`/`authenticated` hold no `TRUNCATE`, `MAINTAIN`, `TRIGGER`, `REFERENCES`, or `DELETE` privilege; audit tables are `SELECT`/`INSERT` only even for `service_role`.
- All four reviewed `SECURITY DEFINER` functions are pinned to `search_path = pg_catalog, public` and executable only by `service_role`.
- All 18 supporting indexes exist.

Because pgTAP is not installed in the local container, the 10 assertions in `spec11_table_privileges_and_policies.test.sql` were extracted and executed directly against the live catalog: **10/10 passed**. Python checks: **110 passed** for the focused inventory/execution-policy suites and **1248 passed, 1 skipped** for the full backend suite. No patient data was read or emitted.

## Residual security-advisor findings (accepted with rationale)

The Supabase security advisor still reports 29 findings after the migration, all expected from this model:

- `rls_enabled_no_policy` (15 INFO): service-only and audit tables. They are deliberately policy-free because clients have no table privilege; `service_role` bypasses RLS and is governed by SPEC-10 evidence.
- `pg_graphql_authenticated_table_exposed` (11 WARN): the `caller_rls` tables intentionally grant `SELECT` to `authenticated`; those rows are constrained by the policies above.
- `pg_graphql_anon_table_exposed` (1 WARN): `terminology_codes` is the single approved public reference table.
- `function_search_path_mutable` (2 WARN): `generate_patient_medical_id()` and `update_updated_at_column()` are invoker functions, not SECURITY DEFINER. The first only calls `nextval` and the second only calls `NOW()`; neither can escalate privileges. Pinning their `search_path` is a separate hardening item and is not required by this SPEC.

## Deferred enforcement work

This SPEC closes the policy/grant design and database catalog controls. It does not prove route-level authorization, caller-JWT propagation, service-role call-site evidence, or hosted production deployment. Those remain part of v2 step 6–8 and are required before SEC-17/18/20/21 can be closed or Phase 0 can be accepted.

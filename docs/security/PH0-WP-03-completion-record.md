# PH0-WP-03 Completion Record — Complete Local Database Release Candidate

**Work package:** PH0-WP-03 / local database, RLS, grants and function inventory

**Plan order:** order 6 / PH0-WP-03 in `PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md` and `backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md`

**Branch:** `security/phase-0-db-storage-release`

**Execution base:** `3a79e2a` (local HEAD before this work)

**Implementation commit:** `619a6c7` (local, committed, not pushed)

**Review date:** 22 November 2026

**Status:** **Complete local database release candidate — NOT CLOSED, NOT ACCEPTED**

> This record documents a clean, reproducible local database release candidate only. It does not claim staging or production deployment, hosted migration application, hosted RLS/grant effectiveness, SEC closure, or Phase 0 acceptance. No `--remote` CLI command, hosted mutation, production verification, or push was performed. The three read-only baseline/plan/release-guide files were not modified.

---

## 1. Scope completed

The local schema/RLS/grant/function inventory is complete against 34 reviewed `public` relations. Missing active SPEC-11/SPEC-12 statements and app-referenced clinical relations were replayed and reconciled in a new local migration, with fail-closed grants and policies.

| Surface | Local outcome |
|---|---|
| `backend/supabase/migrations/20261122062921_ph0_wp03_local_database_release_candidate.sql` | New local release-candidate migration. Replays the active SPEC-11/SPEC-12 SQL recovered from git blob `8c249e0^`, because the committed SPEC-11/SPEC-12 migration files are comment-only no-ops. Adds eight clinical/grant/audit relations, additive care-team columns, canonical grant lifecycle and audit triggers, consent provenance constraints, function search-path hardening, sequence grant cleanup, default-privilege cleanup, duplicate-index cleanup, and `auto_expose_new_tables = false` compatibility. |
| `backend/supabase/config.toml` | `auto_expose_new_tables = false`. New tables are not automatically exposed through the Data API. |
| `backend/app/core/table_access_inventory.py` | Inventory expanded from 26 to 34 tables; consent client writes reduced to `SELECT`; new clinical, grant, audit and function rules added; expected indexes aligned with the local catalog. |
| `backend/tests/core/test_table_access_inventory.py` | Updated expected catalog model. |
| `backend/supabase/tests/database/spec11_table_privileges_and_policies.test.sql` | Rewritten to `plan(18)` with full catalog assertions for RLS, policies, grants, functions, sequences and default privileges. |
| `backend/app/modules/consents/schemas.py` | `expires_at` is required and timezone-aware; finite future expiry is enforced; `emergency_access` is constrained to `false`. |
| `backend/app/modules/consents/service.py` | Grant/revoke require an authenticated actor and persist `granted_by`, `granted_at`, `effective_from`, `revoked_by` and `revoked_at`; expired or emergency payloads are denied. |
| `backend/app/modules/consents/router.py` | Passes `actor_user_id=str(current_user["id"])` into the consent service. |
| `backend/app/core/security.py` | `_active_consent_access()` now denies revoked rows, emergency consent, missing/future grant provenance, future effective dates, invalid/non-finite/expired expiry, and unknown timestamps. No purpose or resource-scope meaning is inferred. |
| `backend/tests/core/test_consent_trusted_path.py` | New suite for trusted grant/revoke provenance, schema constraints, emergency denial and expired-payload denial. |
| `backend/tests/core/test_security_phase0_wp01.py` | New fail-closed consent-read cases. |

The tables covered by the final 34-table inventory are the 26 previously reviewed relations plus `appointments`, `encounters`, `observations`, `conditions`, `medication_requests`, `care_team_participants`, `patient_access_grants` and `patient_access_grant_audit`. `patient_admin_data` remains a planned private-schema view and is not implemented by this release candidate.

---

## 2. Authorization and fail-closed decisions applied

| Decision | Applied behavior |
|---|---|
| Table exposure | Every reviewed `public` table has RLS enabled and forced. Client grants are exactly those in the inventory; all other tables are service-role-only. |
| New relations | Relations added by this migration receive no anon/authenticated grant and no client policy unless a reviewed inventory rule exists. |
| Consent writes | `consent_records` grants only `SELECT` to `authenticated`. Direct client INSERT/UPDATE/DELETE is denied; application writes use the trusted service-role path with authenticated actor provenance. |
| Consent reads | App-side consent evaluation requires a finite, future, valid `expires_at`, non-null `granted_by`/`granted_at`, non-future grant and effective time, no revocation, and no emergency marker. Missing purpose codes or resource-scope fields do not cause an inferred grant. |
| Canonical patient grants | SPEC-06 grant lifecycle constraints, validation trigger, append-only audit trigger and service-role-only execution are enforced locally. |
| Privileged functions | SECURITY DEFINER helpers are pinned to `search_path=pg_catalog, public` and executable only by `service_role`. `generate_patient_medical_id()` remains `SECURITY DEFINER=false` because it is a column default; it is pinned and executable only by `authenticated` and `service_role`, with no `anon`/`PUBLIC` EXECUTE. |
| Sequence privileges | `patient_medical_id_seq` is limited to `postgres` and `service_role` in its active ACL. |
| Future objects | `postgres` default privileges are restricted. `supabase_admin` default privileges remain a documented platform residual because they could not be altered as `postgres`. |
| Advisories | Two local duplicate-index WARNs were removed in the migration; the final advisory run reported no issues. |

No canonical purpose codes, recipient-kind storage, resource-scope storage, treatment/care-team source, legacy-row promotion, migration cutover or other unapproved SPEC detail was guessed. Those items remain fail-closed.

---

## 3. Local catalog evidence

All catalog results below came from the local stack only. A clean reset was run before the checks, and the read-only catalog query was run after the local Data API fixtures.

| Assertion | Local result |
|---|---|
| Supabase CLI | `3.2.0` |
| Local stack | DB `127.0.0.1:58562`, API `127.0.0.1:58561`; CLI output explicitly said `Target: local stack ... pass --remote for MedAeterna` |
| Public tables | **34** |
| Tables missing RLS enabled/forced | **0** (`tables_missing_rls = []`) |
| Public policies | **16** |
| Storage policies | **1** |
| `patient_medical_id_seq` ACL | `{postgres=rwU/postgres,service_role=rwU/postgres}` |
| Client table grants | `anon`: `terminology_codes=SELECT`; `authenticated`: `consent_records=SELECT`, `lab_results=SELECT`, `medical_records=SELECT`, `patients=INSERT,SELECT,UPDATE`, `practitioner_roles=SELECT`, `practitioners=SELECT`, `prescriptions=SELECT`, `profiles=INSERT,SELECT,UPDATE`, `reminders=SELECT`, `terminology_codes=SELECT`, `user_roles=SELECT`. No other client table grants. |
| SECURITY DEFINER functions | `can_manage_roles()`, `change_user_role_assignment(...)`, `get_user_permissions(uuid)`, `is_admin_user()`, `validate_patient_access_grant_record()`, `record_patient_access_grant_audit()` and `enforce_consent_record_immutability()` all have `search_path=pg_catalog, public` and ACL `{postgres=X/postgres,service_role=X/postgres}`. |
| Utility functions | `generate_patient_medical_id()` is non-definer, pinned and ACL `{postgres=X/postgres,authenticated=X/postgres,service_role=X/postgres}`; `update_updated_at_column()` is non-definer, pinned and service-role-only. No anon/PUBLIC EXECUTE. |
| `postgres` default ACLs | `{postgres=X/postgres}` functions, `{postgres=arwdDxtm/postgres}` tables, `{postgres=rwU/postgres}` sequences. |
| `supabase_admin` default ACLs (residual) | Functions `{postgres=X/supabase_admin,anon=X/supabase_admin,authenticated=X/supabase_admin,service_role=X/supabase_admin}`; tables `{postgres=arwdDxtm/supabase_admin,anon=arwdDxtm/supabase_admin,authenticated=arwdDxtm/supabase_admin,service_role=arwdDxtm/supabase_admin}`; sequences `{postgres=rwU/supabase_admin,anon=rwU/supabase_admin,authenticated=rwU/supabase_admin,service_role=rwU/supabase_admin}`. |

Migration history after the clean reset contained all six local migrations, including `20261122062921`, with local/applied entries matching. No hosted target was contacted.

---

## 4. Verification evidence

All Python commands were run from `backend/` using the Windows virtualenv interpreter `.venv/Scripts/python.exe`. Supabase CLI commands were run from `backend/` with `/home/linuxbrew/.linuxbrew/bin` on `PATH`, always against the local stack default and without `--remote`.

| Evidence ID | Check | Command | Result |
|---|---|---|---|
| E-WP03-01 | Clean local reset | `supabase db reset --yes --no-seed` | Pass. All six migrations applied; local buckets updated; no seed data loaded. |
| E-WP03-02 | Local pgTAP suite | `supabase test db` | **PASS — 3 files, 36 tests**. `spec02` ok, `spec11` ok, `spec12` ok. |
| E-WP03-03 | Full backend regression | `.venv/Scripts/python.exe -m pytest -q` | **1,364 passed, 1 skipped, 18 warnings** |
| E-WP03-04 | Focused consent/security/inventory regression | `.venv/Scripts/python.exe -m pytest tests/core/test_consent_trusted_path.py tests/core/test_security_phase0_wp01.py tests/core/test_table_access_inventory.py -q` | **132 passed, 12 warnings** |
| E-WP03-05 | Local security advisories | `supabase db advisors --output-format json` | Final run: **No issues found**, 0 findings. Initial run found 2 WARN duplicate indexes; both were removed in the migration. |
| E-WP03-06 | Read-only catalog snapshot | `supabase db query --read-only -f /tmp/opencode/order6_catalog_snapshot.sql -o json` | Pass; results summarized in section 3. |
| E-WP03-07 | Local Data API effective access | `.venv/Scripts/python.exe "$(wslpath -w /tmp/opencode/order6_data_api_check.py)"` | **9/9 checks passed** against API `http://127.0.0.1:58561`. |
| E-WP03-08 | Patch sanity | `git diff --check` | Clean |
| E-WP03-09 | CLI version | `supabase --version` | **3.2.0** |
| E-WP03-10 | Local migration history | `supabase migration list` | Six local migrations, all matching applied local history; local target only. |

### 4.1 Local Data API effective-access checks

Synthetic local-only fixture rows were inserted after the clean reset for two patients in different organizations and two practitioners. The Data API check used the local anon key and locally signed `authenticated` JWTs. Results:

| Check | Result |
|---|---|
| anon read `patients` | **401**, `permission denied for table patients` |
| patient A read own patient row | **200**, one row |
| patient A read patient B | **200**, zero rows |
| practitioner A read own practitioner row | **200**, one row |
| practitioner A read practitioner B in another org | **200**, zero rows |
| authenticated POST to `consent_records` | **403**, permission denied |
| authenticated read `organizations` | **403**, permission denied |
| authenticated read `encounters` | **403**, permission denied |
| authenticated read `patient_access_grants` | **403**, permission denied |

These checks are local effective-access evidence for the tested identities and paths only. They do not cover the full SPEC role matrix, hosted PostgREST behavior, Storage object operations, or production identity providers.

---

## 5. Evidence limits and residual risk

This work package does not close a SEC finding and does not constitute Phase 0 acceptance.

1. **No hosted verification.** No staging or production migration, catalog query, policy test, advisory run, or role-based Data API check was performed.
2. **Open SPEC policy details.** Trusted purpose codes, recipient-kind storage, resource-scope storage, treatment/care-team source, legacy consent/grant promotion, and migration/cutover remain human decisions. Fail-closed behavior is intentional.
3. **`supabase_admin` defaults.** Broad default privileges granted by `supabase_admin` remain. They could not be altered as `postgres` (`can_alter_supabase_admin_defaults=false`) and must be handled by a reviewed platform-level change before any production release.
4. **API trust boundary.** Consent grant/revoke provenance comes from the authenticated API actor and is written through the trusted backend path. The database does not independently attest the upstream JWT for that application write path.
5. **Partial effective-access matrix.** The local Data API checks cover selected cross-patient/cross-org and service-only cases. Full role-by-role production verification remains outstanding.
6. **Storage behavior.** The SPEC-12 pgTAP test validates bucket/policy catalog state only. Direct anon/authenticated upload, download and public-retrieval behavior was not exercised in this order.
7. **Planned relation.** `patient_admin_data` remains unimplemented and protected by the unregistered-table deny rule.
8. **Migration replay caveat.** The new migration replays active SQL from local history because the committed SPEC-11/SPEC-12 files are no-ops. Hosted drift review and an approved forward migration are still required before deployment.
9. **Local duplicate-index removal.** Drops are applied to the local release candidate only. Hosted index state was not inspected or changed.

---

## 6. Acceptance handoff

Before any production release:

- obtain human decisions on every open SPEC detail listed in section 5;
- resolve or formally accept the `supabase_admin` default-privilege residual at the platform level;
- review hosted schema drift and prepare an approved forward migration;
- repeat catalog, pgTAP, advisory and effective-access checks in staging with explicit approval;
- obtain human approval before any production deployment;
- repeat the same evidence in production with distinct role identities;
- link the resulting evidence to both plans’ traceability registers and obtain reviewer acceptance.

**Current decision: NOT ACCEPTED.**

---

## 7. Cross-references

- [Phase 0 plan — PH0-WP-03 / order 6](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [Backend plan — PH0-WP-03 / order 6](../backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md)
- [Controlled Supabase database and storage release guide](../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- [PH0-WP-06 SPEC approval and consent access model](PH0-WP-06-SPEC-approval-and-consent-access-model.md)
- [SPEC-05 — consent evaluation policy](SPEC-05-consent-evaluation-policy.md)
- [SPEC-06 — canonical patient access grants](SPEC-06-canonical-patient-access-grants.md)
- [SPEC-11 — table-level RLS and grants](SPEC-11-table-level-rls-and-grants.md)
- [SPEC-12 — storage bucket and object access](SPEC-12-storage-bucket-and-object-access.md)

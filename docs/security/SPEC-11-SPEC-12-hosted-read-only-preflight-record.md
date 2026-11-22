# SPEC-11/SPEC-12 Hosted Verification Record — Read-Only Preflight

**Plan order:** order 8 in `docs/security/PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md` (“Verify SPEC-11/SPEC-12 against staging and production”). The corresponding backend execution gate is order 10 / PH0-WP-10 in `backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md`.

**Controlled procedure:** `backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md`, especially §§8.1–8.3 (identification, read-only preflight, drift decision) and §9.1–9.4 (verification gates).

**Branch:** `security/phase-0-db-storage-release`

**Release commit under review:** `861e1cf` (local, unpushed)

**Review date:** 22 November 2026

**Status:** **BLOCKED — production drift found; SPEC-11/SPEC-12 NOT HOSTED-VERIFIED; NOT ACCEPTED**

> This record reports read-only inspection only. It does not deploy, repair, push, mutate, or verify a hosted release. No `--remote` command, `db push`, `config push`, `apply_migration`, `migration repair`, object upload/delete, or hosted effective-access test was performed. No patient row data or object content was read or emitted. The three read-only baseline/plan/release-guide files were not modified.

---

## 1. Decision summary

| Environment | Outcome | Interpretation |
|---|---|---|
| Local stack (used as a staging proxy at the operator’s direction) | **PASS for the reviewed local model** | Local pgTAP, focused Python checks, local advisories, and 22 effective Storage API checks pass. This is still local evidence, not staging evidence. |
| Hosted staging/preview | **NOT PERFORMED** | No Supabase branches exist for this project (`list_branches` returned `[]`). No staging target was supplied. |
| Hosted production | **READ-ONLY PREFLIGHT DONE; VERIFICATION FAILED/BLOCKED** | Production does not match the approved local SPEC-11/SPEC-12 state. Multiple §8.3 STOP conditions are present. |
| Production mutation | **NOT AUTHORIZED / NOT PERFORMED** | The controlled guide requires a human-approved exact change set and backup/PITR gate before mutation. None was provided. |
| Phase 0 | **NOT ACCEPTED** | Resolved authorization gaps, hosted evidence, and reviewer acceptance remain outstanding. |

The most important finding is that remote production has only one migration record (`20261118135846 / remote_schema`) while the reviewed local stack has six. The five later local migrations, including the SPEC-11 and SPEC-12 migrations, are pending remotely. Production still contains the legacy broad grants, legacy policies, mutable/exposed definer functions, and incomplete Storage settings that the local remediation was written to replace.

---

## 2. Target identification and access path

| Item | Evidence |
|---|---|
| Production project reference | `iyueixtpmzznyffshqon` — independently confirmed by the operator for this read-only verification. It was not inferred from `.env` for authorization. |
| API URL | `https://iyueixtpmzznyffshqon.supabase.co` — returned by read-only MCP `get_project_url`. |
| Environment label | `production` for this verification. The operator must still independently confirm the project in the Supabase Dashboard before any deployment. |
| Local project metadata | `supabase status -o json` reported linked project name `MedAeterna`, ref `iyueixtpmzznyffshqon`; this was treated as supporting metadata only. |
| Database identity | `current_database() = postgres`, `current_user = supabase_read_only_user`, server `17.6`. |
| CLI version | `supabase 3.2.0`. |
| CLI hosted auth | `supabase whoami` and `supabase projects list` returned `AccessTokenRequiredError`. No `SUPABASE_ACCESS_TOKEN` was set. |
| MCP auth | A read-only MCP server for the confirmed ref was added and reported `connected`. The explicit browser OAuth attempt ended with `Authorization expired`, but the read-only MCP tools were available and all SQL below ran as `supabase_read_only_user`. No tokens or secrets were written into repository evidence. |
| Safety mode | All hosted SQL was `SELECT`/read-only MCP metadata. No hosted write path was used. |

---

## 3. Commands and evidence

All CLI commands were run from `backend/`, with `/home/linuxbrew/.linuxbrew/bin` on `PATH`, and without `--remote`. Python commands used `backend/.venv/Scripts/python.exe`. Hosted catalog checks used the read-only Supabase MCP tools.

| ID | Check | Command / method | Result |
|---|---|---|---|
| E-01 | Skills/docs/changelog | Loaded `supabase` and `supabase-postgres-best-practices` skills; reviewed Supabase changelog and current Storage/CLI docs via MCP `search_docs` | No relevant breaking change found for this read-only verification. Current docs confirm `migration list` compares local files with remote history and that `db push` applies pending migrations. |
| E-02 | CLI discovery | `supabase --version`, `supabase --help`, `supabase db --help`, `supabase migration --help`, `supabase storage --help`, `supabase config --help` | CLI `3.2.0`; local is the default target, `--remote` selects hosted. |
| E-03 | CLI hosted identity | `supabase whoami --output-format json`, `supabase projects list --output-format json` | `AccessTokenRequiredError`. No hosted CLI mutation attempted. |
| E-04 | MCP target | `get_project_url`, `execute_sql` identity query | Confirmed production URL and read-only DB role. |
| E-05 | Staging discovery | `list_branches` | `[]` — no Supabase staging/preview branch available. |
| E-06 | Production migration history | `list_migrations` and `select ... from supabase_migrations.schema_migrations` | One record: `20261118135846 / remote_schema`. |
| E-07 | Local migration history | `supabase migration list` | Six local migrations applied; CLI reported `Target: local stack (127.0.0.1:58562)`, not hosted. |
| E-08 | Local pgTAP (staging proxy) | `supabase test db` | **PASS — 3 files, 36 tests**; SPEC-02, SPEC-11 and SPEC-12 suites all ok. |
| E-09 | Local advisories (staging proxy) | `supabase db advisors --type all --level warn` | **No issues found**, 0 findings. |
| E-10 | Focused Python checks (staging proxy) | `.venv/Scripts/python.exe -m pytest -q tests/core/test_table_access_inventory.py tests/core/test_storage_access_inventory.py tests/core/test_storage_upload_validation.py tests/core/test_verify_local_storage_effective_access.py tests/patients/test_avatar_upload.py tests/organizations/branding/test_storage.py` | **162 passed, 12 warnings**. |
| E-11 | Effective Storage checks (staging proxy) | `supabase status -o json > /tmp/opencode/order8_status.json`, then `.venv/Scripts/python.exe scripts/verify_local_storage_effective_access.py --status-json "$(wslpath -w /tmp/opencode/order8_status.json)" --output-json "$(wslpath -w /tmp/opencode/order8_storage_results.json)"` | **22/22 passed** against `http://127.0.0.1:58561` using synthetic objects and identities. |
| E-12 | Production advisories | `get_advisors` for `security`, `performance`, `health` | Many WARN/INFO findings; health clean. Key findings summarized below. |
| E-13 | Catalog comparison | Read-only catalog SQL against production MCP and local MCP (`58561`), comparing tables, RLS flags, policies, ACLs via `aclexplode`, functions, indexes, views, sequences, default ACLs, roles, Storage buckets/policies/ACLs/RLS | Large, blocking drift; summarized below. |
| E-14 | Patch sanity | `git diff --check` | Clean before evidence commit. |

### 3.1 Local proxy detail

The local stack is not a staging environment. At the operator’s direction it was used only as a proxy to re-establish that the reviewed release candidate is internally consistent:

- API `http://127.0.0.1:58561`, DB `127.0.0.1:58562`, MCP `http://127.0.0.1:58561/mcp`.
- 6 applied migrations: `20261118135846`, `20261118150000`, `20261118160000`, `20261120095915`, `20261120110644`, `20261122062921`.
- 34 public tables: the 26 original SPEC-11 tables plus 8 clinical/access tables added by later reviewed local migrations.
- 16 public policies, RLS enabled and forced, least-privilege ACLs for `anon`, `authenticated`, and `service_role`.
- 3 Storage buckets with exact reviewed public flags, 2 MiB limits and JPEG/PNG/WebP allowlists; 1 `Deny direct client object access` policy.
- 22/22 effective API checks covered anon/authenticated denial, service-role write/list/sign/delete, public retrieval, cross-tenant listing denial, MIME/size rejection, deterministic upsert, and cleanup.

This evidence does **not** substitute for staging verification or production verification.

---

## 4. Production read-only catalog findings

### 4.1 Migration history

| Environment | Migration records |
|---|---|
| Production | `20261118135846 / remote_schema` only |
| Local reviewed candidate | `20261118135846`, `20261118150000`, `20261118160000`, `20261120095915_spec11_table_rls_and_grants`, `20261120110644_spec12_storage_bucket_policy`, `20261122062921_ph0_wp03_local_database_release_candidate` |

Pending remotely: the five later local migrations, including SPEC-11, SPEC-12, and the PH0-WP-03 release-candidate migration. This is classified as “local migration pending remotely” under guide §8.3 and must be part of a reviewed release plan, not applied opportunistically.

### 4.2 Tables, RLS, policies, and grants

| Surface | Production | Local reviewed candidate |
|---|---|---|
| Public tables | 26 | 34 |
| Production-only tables | None | — |
| Local-only tables | — | `appointments`, `care_team_participants`, `conditions`, `encounters`, `medication_requests`, `observations`, `patient_access_grant_audit`, `patient_access_grants` |
| RLS enabled | All 26 production tables | All 34 local tables |
| RLS forced | **0 of 26** | All 34 |
| Public policies | 11 legacy policies | 16 approved policies |
| ACL entries for client/service roles | 76 broad entries | 46 least-privilege entries |

Production policy examples that differ from the approved model:

- `patients` has duplicate SELECT policies (`Patients can read own data`, `Patients can read own record`) and uses unwrapped `auth.uid() = id`.
- `profiles`, `patients`, and `medical_records` use unwrapped `auth.uid()` and role `public`.
- `medical_records` retains `Clinicians insert records`, a weak clinician INSERT policy.
- `terminology_codes.Read-only terminology` targets `public`, not the approved explicit `anon, authenticated`.
- Approved local policies such as `Patients read own consent`, `Patients read own lab results`, `Patients read own medical records`, `Practitioners read own roles`, and `Patients read own reminders` are absent.

Production ACL examples that differ from the approved model:

- `anon` and `authenticated` hold `DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE` on nearly every reviewed table.
- `service_role` also retains `TRUNCATE`, `TRIGGER`, `REFERENCES`, and `MAINTAIN` on most tables.
- `user_roles` retains `anon`/`authenticated` `MAINTAIN, SELECT`.
- Local model allows `anon` only `SELECT` on `terminology_codes`; `authenticated` only the reviewed SELECT/INSERT/UPDATE sets; audit tables are INSERT/SELECT only; no client role has TRUNCATE, TRIGGER, REFERENCES, MAINTAIN, or DELETE where not explicitly approved.

This is a direct failure of SPEC-11 acceptance criteria 2–6 and 8–9 for production.

### 4.3 Functions, sequences, defaults, and indexes

| Surface | Production finding |
|---|---|
| SECURITY DEFINER functions | `can_manage_roles()`, `get_user_permissions(uid uuid)`, and `is_admin_user()` are executable by `anon` and `authenticated`. `can_manage_roles()` and `is_admin_user()` also have mutable `search_path`. |
| Other mutable search paths | `generate_patient_medical_id()` and `update_updated_at_column()` are invoker functions with mutable `search_path`; locally they are pinned. |
| Missing local functions | `enforce_consent_record_immutability()`, `record_patient_access_grant_audit()`, and `validate_patient_access_grant_record()` are absent in production. |
| Sequence ACL | `patient_medical_id_seq` is executable/updatable by `anon` and `authenticated` in production; locally restricted to `postgres` and `service_role`. |
| Default ACLs | Production default privileges for `public` tables, functions, and sequences grant to `anon`, `authenticated`, and `service_role`; locally restricted to `postgres`. |
| Indexes | Production lacks 18 locally reviewed supporting indexes; production has two duplicate indexes (`idx_patients_medical_id`, `terminology_codes_system_idx1`) absent from the reviewed candidate. |
| Views | No public views/materialized views/foreign tables in either environment. |
| Role capability | `service_role` has `rolbypassrls = true` in both; this is unchanged and is not caller authorization. |

This is a direct failure of SPEC-11 acceptance criteria 7–9 for production.

### 4.4 Storage

| Bucket / policy | Production | Local reviewed candidate |
|---|---|---|
| `organization-logos` | `public=true`, 2 MiB, JPEG/PNG/WebP | Match |
| `practitioner-photos` | `public=true`, but `file_size_limit = null` and `allowed_mime_types = null` | `public=true`, 2 MiB, JPEG/PNG/WebP |
| `patient-avatars` | **Absent** | `public=true`, 2 MiB, JPEG/PNG/WebP |
| `patient-documents` | Absent | Absent (correctly deferred) |
| Storage policies | **0** | 1: `Deny direct client object access`, `FOR ALL TO anon, authenticated`, `USING (false) WITH CHECK (false)` |
| Storage RLS | `storage.objects` and `storage.buckets` enabled, not forced | Match |
| Storage ACLs | Broad platform grants on `objects`/`buckets` | Match; effective local denial depends on RLS policy |

With no production deny policy and an unhardened public `practitioner-photos` bucket, the approved SPEC-12 object boundary is not present in production. Production object contents were not queried, and no hosted upload/list/delete test was attempted.

### 4.5 Production advisor findings

Advisor snapshot observed at `2026-11-22T13:48:55Z`:

| Advisor | Count | Level | Relevance |
|---|---:|---|---|
| `rls_enabled_no_policy` | 21 | INFO | Production has RLS enabled without policies on service-only/audit tables; expected only if grants are also locked down, which they are not. [Lint 0008](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy) |
| `function_search_path_mutable` | 4 | WARN | Includes 3 definer functions and 2 invoker functions; local candidate pins all. [Lint 0011](https://supabase.com/docs/guides/database/database-linter?lint=0011_function_search_path_mutable) |
| `pg_graphql_anon_table_exposed` | 25 | WARN | Nearly every table is visible to `anon`; local reduces this to the approved reference table. [Lint 0026](https://supabase.com/docs/guides/database/database-linter?lint=0026_pg_graphql_anon_table_exposed) |
| `pg_graphql_authenticated_table_exposed` | 25 | WARN | Signed-in users see nearly every table; local limits this to the reviewed caller-RLS set. [Lint 0027](https://supabase.com/docs/guides/database/database-linter?lint=0027_pg_graphql_authenticated_table_exposed) |
| `anon_security_definer_function_executable` | 3 | WARN | `can_manage_roles`, `get_user_permissions`, `is_admin_user`. [Lint 0028](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable) |
| `authenticated_security_definer_function_executable` | 3 | WARN | Same three functions. [Lint 0029](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable) |
| `auth_rls_initplan` | 9 | WARN | Unwrapped `auth.uid()` in production policies. [Lint 0003](https://supabase.com/docs/guides/database/database-linter?lint=0003_auth_rls_initplan) |
| `multiple_permissive_policies` | 6 | WARN | Duplicate `patients` SELECT policies across roles. [Lint 0006](https://supabase.com/docs/guides/database/database-linter?lint=0006_multiple_permissive_policies) |
| `duplicate_index` | 2 | WARN | `patients` and `terminology_codes`. [Lint 0009](https://supabase.com/docs/guides/database/database-linter?lint=0009_duplicate_index) |
| `unindexed_foreign_keys` | 19 | INFO | Performance advisory; not an authorization control. [Lint 0001](https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys) |
| `unused_index` | 35 | INFO | Performance advisory. [Lint 0005](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index) |
| `auth_leaked_password_protection` | 1 | WARN | Auth configuration outside this order; [password security docs](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection). |
| Health | 0 | — | No health advisories. |

---

## 5. Drift classification per controlled guide §8.3

| Drift observed | Classification | Required action / current decision |
|---|---|---|
| Five local migrations pending remotely | Local migration pending remotely | Include in a reviewed release plan only after approval. Do not push ad hoc. |
| Production has 26 legacy tables with RLS enabled but not forced, broad ACLs, and legacy policies | Local remediation pending; known legacy baseline | Include in reviewed migration set; verify application compatibility before any revocation/policy change. |
| Production policies use `public` role and unwrapped `auth.uid()`, with duplicate `patients` SELECT and weak `medical_records` INSERT | Legacy policy drift | STOP: reconcile through reviewed migrations; no policy guessing. |
| Three definer functions callable by `anon`/`authenticated`; four mutable search paths | Unknown/unsafe function and grant state relative to approved model | STOP: plan reviewed function hardening and EXECUTE revocation; verify backend compatibility. |
| Production `patient_medical_id_seq` and default ACLs grant to client roles | Privilege drift | STOP: include in reviewed grant migration; verify application paths. |
| Production Storage has `practitioner-photos` with no size/MIME limits, no `patient-avatars`, and no deny policy | Unknown/incomplete Storage configuration and policy | STOP: classify and plan under §8.7/§8.8; no `config push` or policy deployment without approval. |
| No production-only tables observed | No remote-only table drift | Continue recording; still blocked by the other items. |
| `20261118135846` recorded remotely with its baseline effect apparently present | Expected remote migration history | No repair performed. |
| No migration history for pre-existing Storage buckets | History/config reconciliation required | Do not use `migration repair`; prove state and plan a reviewed reconciliation. |
| No destructive operation performed | N/A | Backup/PITR and recovery gate remain unopened. |

**Guide outcome: STOP before any production mutation.**

---

## 6. Gate outcome and handoff

### Completed in this order

- Confirmed the production target for read-only verification.
- Loaded the required Supabase skills and checked current documentation/changelog.
- Re-verified the local release candidate as a staging proxy: 36 pgTAP tests, 162 focused Python checks, 0 local WARN-level advisories, 22/22 effective Storage checks.
- Inspected production through read-only MCP only.
- Recorded exact migration, RLS, policy, grant, function, sequence, default-ACL, index, and Storage drift.
- Classified the drift under the controlled guide and stopped before deployment.

### Not completed / explicitly not claimed

- No hosted staging verification: no staging/preview branch exists.
- No production verification of SPEC-11 or SPEC-12: the hosted state does not match the approved model.
- No effective hosted upload/list/update/delete/signed-URL test: no approved synthetic production identity/object set, and no mutation was authorized.
- No backup/PITR confirmation, final deployment authorization, migration push, config push, policy deployment, SEC closure, or Phase 0 acceptance.
- No production data or object content was exported or inspected.

### Required before continuing

1. Human operator independently confirms the production project in the Supabase Dashboard.
2. Decide whether a real hosted staging/preview branch will be created and verified; otherwise formally accept that local proxy evidence is not staging evidence.
3. Prepare an exact reviewed release change set: commit `861e1cf` or a later approved SHA, the five pending migrations, SPEC-12 bucket changes, and the `storage.objects` policy migration.
4. Reconcile the production-only Storage history/config condition without `migration repair` until actual state and intent are proven.
5. Complete the controlled guide §8.4 backup/PITR and recovery gate.
6. Complete §8.5 final deployment authorization with exact target, commit, migrations, Storage changes, window, operator, and approval timestamp.
7. Only then, under explicit human authorization, deploy and perform §9 verification with separate synthetic identities and evidence.

**Current decision: BLOCKED / NOT ACCEPTED.**

---

## 7. Cross-references

- [Phase 0 plan — immediate execution order item 8](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [Backend plan — recommended execution order](../../backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md)
- [Controlled Supabase database and storage release guide](../../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- [SPEC-11 — table-level RLS and grants](SPEC-11-table-level-rls-and-grants.md)
- [SPEC-12 — storage bucket and object access](SPEC-12-storage-bucket-and-object-access.md)
- [PH0-WP-03 completion record](PH0-WP-03-completion-record.md)
- [PH0-WP-07 completion record](PH0-WP-07-completion-record.md)

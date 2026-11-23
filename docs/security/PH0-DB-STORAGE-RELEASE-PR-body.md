# Draft PR body — `security/phase-0-db-storage-release`

Copy the content below into the GitHub PR description. This is a drafting artifact only; no PR was created and no branch was pushed by this work.

---

## Proposed title

`Phase 0 DB/Storage security release candidate — SPEC-11/SPEC-12 local implementation and evidence`

## Target

- **Base:** `main`
- **Head:** `security/phase-0-db-storage-release`
- **Implementation commit:** `e5bb6ef` (followed by evidence and whitespace-cleanup commits)
- **Production status:** no production change; no deployment authorization implied by this PR

> **Correction to GitHub state:** PR #41 was created with `head=main` and `base=docs/phase-0-security-plan-v2-and-backend-ci`, which is the reverse of the intended release PR. It merged `main` into the docs branch; it did **not** merge `security/phase-0-db-storage-release` into `main`. GitHub currently reports `main = 4a5941c859ce6b1197c9cc2689715f08eb2f24ed` and remote `security/phase-0-db-storage-release = 0066602afac41662eb6c79f877049d0b6fb39ed9`, with the branches diverged 19/3. Do not treat PR #41 as the release merge; close or supersede it and open a correctly oriented PR after pushing the local cleanup commits.

---

## Summary

This PR collects the local Phase 0 application, database, and Storage security remediation for review. It covers backend plan recommended orders 2–7 and the local evidence portion of order 9. It also records the read-only hosted preflight performed for order 8.

The change set replaces legacy permissive policies and grants with the reviewed SPEC-11 model, installs the reviewed SPEC-12 bucket configuration and direct-client object deny policy, and hardens the affected backend authorization paths with negative tests. All evidence in this PR is **local**. Production remains unchanged and is **NOT VERIFIED / NOT ACCEPTED**.

---

## 1. Reason

The work addresses the Phase 0 findings tracked under SEC-01–SEC-24 and the PH0-WP-01, WP-02, WP-03, WP-05, WP-06 and WP-07 work packages:

- shared authorization defects on sensitive and administrative routes;
- missing clinical route/service authorization context;
- weak operational event visibility and retry controls;
- unresolved policy decisions for consent and patient access;
- legacy broad table grants, unwrapped `auth.uid()` policies, unsafe definer-function exposure and mutable search paths;
- incomplete Storage bucket limits/MIME allowlists and no `storage.objects` deny policy.

Policy decisions are taken only from the approved SPEC-01–SPEC-10 documents. Undocumented decisions remain fail-closed.

---

## 2. Scope

### Application authorization

- `backend/app/core/security.py`
- `backend/app/core/clinical_authorization.py`
- `backend/app/core/table_access_inventory.py`
- clinical and administrative routers/services under `backend/app/modules/` and `backend/app/api/admin/`
- operational event/retry modules under `backend/app/core/events/`
- focused negative and regression tests under `backend/tests/`

### Database

Migration files present in the reviewed local stack:

- `20261118135846_remote_schema.sql` — baseline already present in production; not a pending remote migration
- `20261118150000_role_assignment_least_privilege.sql`
- `20261118160000_role_assignment_anon_read.sql`
- `20261120095915_spec11_table_rls_and_grants.sql`
- `20261120110644_spec12_storage_bucket_policy.sql`
- `20261122062921_ph0_wp03_local_database_release_candidate.sql`

### Storage

- `backend/supabase/config.toml`
- `backend/scripts/verify_local_storage_effective_access.py`
- `backend/tests/core/test_verify_local_storage_effective_access.py`

### Documentation/evidence

- `docs/security/SPEC-01` through `docs/security/SPEC-12`
- PH0-WP-02, PH0-WP-03, PH0-WP-05, PH0-WP-06 and PH0-WP-07 records
- `docs/security/SPEC-11-SPEC-12-hosted-read-only-preflight-record.md`

No patient row data, patient object content, production secret, or production token is included.

---

## 3. Exact migrations pending remotely

Production read-only preflight found only `20261118135846 / remote_schema` in hosted migration history. The following five reviewed migrations are pending remotely and must not be applied without separate human authorization:

1. `20261118150000_role_assignment_least_privilege.sql`
2. `20261118160000_role_assignment_anon_read.sql`
3. `20261120095915_spec11_table_rls_and_grants.sql`
4. `20261120110644_spec12_storage_bucket_policy.sql`
5. `20261122062921_ph0_wp03_local_database_release_candidate.sql`

No `db push`, `config push`, `apply_migration`, `migration repair`, or `--remote` mutation was performed.

---

## 4. Storage configuration and policy

| Bucket | Public | Size limit | MIME allowlist | Change |
|---|---|---:|---|---|
| `organization-logos` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Keep reviewed settings |
| `patient-avatars` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Install reviewed settings |
| `practitioner-photos` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Add reviewed limits/allowlist |
| `patient-documents` | N/A | N/A | N/A | Not implemented; remains planned/private |

Storage object policy installed locally by `20261120110644_spec12_storage_bucket_policy.sql`:

- policy: `Deny direct client object access`
- table: `storage.objects`
- command: `ALL`
- roles: `anon`, `authenticated`
- `USING (false)` and `WITH CHECK (false)`
- service-role writes remain server-side and are not a client grant

No hosted upload, download, list, update, signed-URL issuance, or delete was performed.

---

## 5. Tests and local evidence

Verified after a clean local rebuild of the whitespace-normalized tree:

| Check | Command / method | Result |
|---|---|---|
| Clean rebuild | `supabase db reset --yes --no-seed` | All 6 migrations reapplied |
| Migration inventory | `supabase migration list` | 6/6 local migrations applied |
| Database catalog tests | `supabase test db` | **36/36 passed**; SPEC-02, SPEC-11, SPEC-12 ok |
| Advisories | `supabase db advisors --type all --level warn` | **No issues found** |
| Backend regression | `.venv/Scripts/python.exe -m pytest -q` | **1,368 passed, 1 skipped, 18 warnings** |
| Effective Storage checks | `scripts/verify_local_storage_effective_access.py` | **22/22 passed** against local API `http://127.0.0.1:58561`, synthetic identities/objects only |
| Patch hygiene | `git diff --check origin/main...HEAD` | Clean |
| CLI | `supabase --version` | `3.2.0` |

Local catalog snapshot after reset:

- 3 reviewed image buckets with exact public flags, 2 MiB limits and JPEG/PNG/WebP allowlists
- 1 `storage.objects` deny policy
- 34 public tables, all with RLS enabled and forced
- 16 public policies
- 0 tables missing RLS enforcement

The local stack is not staging. The GitHub Actions `Backend verification` check will run for this PR because the workflow triggers on `pull_request` to `main`.

---

## 6. Risk and compatibility

Deployment of this change set is security-sensitive and may affect application compatibility:

- broad `anon`/`authenticated` table privileges are revoked;
- legacy policies are replaced with reviewed caller-scoped policies;
- definer-function `EXECUTE` is restricted to `service_role`;
- `patient_medical_id_seq` and default ACLs are restricted;
- `practitioner-photos` gains size/MIME limits;
- `patient-avatars` is added;
- direct client object access is denied by RLS.

Application paths that relied on legacy broad client privileges must be reviewed before any rollout. Production drift is documented in `docs/security/SPEC-11-SPEC-12-hosted-read-only-preflight-record.md` and includes broad grants, legacy policies, mutable search paths, client-executable definer functions, missing migrations, unhardened Storage settings and a missing deny policy.

---

## 7. Rollout

This PR does not authorize rollout. Any future rollout must follow `backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md` §§8–10:

1. Human Dashboard confirmation of the exact production project.
2. Decide whether a hosted staging/preview branch will be used; none currently exists.
3. Complete the backup/PITR and recovery gate.
4. Record the full §8.5 authorization, including exact commit, migrations, Storage changes, window, operator, recovery owner and approval timestamp.
5. Run the read-only `supabase db push --dry-run --remote=...` and compare it to the approved list.
6. Run `supabase config diff --remote=...` and review every bucket change.
7. Apply only the reviewed migrations and Storage policy migration under explicit human authorization.
8. Perform §9 database, Storage, application and evidence verification with separate synthetic identities and objects.

---

## 8. Rollback / recovery

Do not assume an automatic reverse migration exists. For each migration, the release operator must choose between a reviewed forward fix and a restored point, as required by controlled guide §10. A schema rollback is not automatically safe for destructive or data-affecting changes. No production rollback action is part of this PR.

---

## 9. Production status

- Production project: `iyueixtpmzznyffshqon`
- Hosted verification scope used so far: **read-only only**
- Production migration history observed: `20261118135846` only
- Production RLS/policies/grants/functions/Storage: **do not match the approved local model**
- SPEC-11/SPEC-12 hosted verification: **BLOCKED / NOT VERIFIED**
- SEC findings: **not closed**
- Phase 0: **NOT ACCEPTED**

This PR is for code/design/evidence review only. It is not a production deployment request and does not satisfy the controlled guide’s final authorization gate.

---

## 10. Reviewer checklist

- [x] Requirement maps to the v2.0 baseline
- [x] Policy decisions are documented in SPEC-01–SPEC-10
- [x] No broad grants or permissive RLS policies are approved for the target model
- [x] Exposed tables and dependent policies/functions were reviewed locally
- [x] `SECURITY DEFINER` use is justified and hardened locally
- [x] Storage public/private status is explicit
- [x] Storage operations are independently authorized
- [x] No production secrets or patient data are included
- [x] Local rebuild is reproducible
- [x] Local tests and evidence pass on the reviewed tree
- [ ] GitHub CI passes on this PR
- [ ] Human review approval is recorded
- [ ] Rollout and recovery plan are approved separately
- [x] Production has not been modified

---

## 11. Related tracking

Related Phase 0 issues: #31, #34, #35, #36, #37, #38.

No issue or SEC finding is closed by this PR. Closure requires environment-specific evidence and reviewer acceptance.

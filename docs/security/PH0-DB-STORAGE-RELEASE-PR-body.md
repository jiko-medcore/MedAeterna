# PR body — `security/phase-0-db-storage-release` (historical PR #42 description)

This repository file records the title and description used for PR #42. It is a drafting artifact; it does not create or update a PR. Post-merge SEC and issue dispositions are in the [order 11 reconciliation record](PH0-WP-10-order-11-sec-and-issue-reconciliation-record.md).

---

## Title

`Phase 0 DB/Storage security release candidate — local implementation, evidence, and controlled-release gate`

---

## Description

**Base:** `main`<br>
**Head:** `security/phase-0-db-storage-release`<br>
**PR #42 head SHA:** `59d69ce0e4e467ae0a7668df119db282ee1b7c52`<br>
**Merge commit:** `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0`<br>
**Merge date:** 2026-11-24T08:17:05Z<br>
**Release status:** code/design/evidence PR merged; no production mutation, no SEC closure, Phase 0 **NOT ACCEPTED**

> PR #42 merged the release branch into `main`. `Backend verification` passed on the PR head and on the merge commit. PR #41 was historically mis-oriented (`head=main`, `base=docs/phase-0-security-plan-v2-and-backend-ci`) and was not the Phase 0 release merge. Code merge and CI success do not authorize deployment or close any SEC finding or GitHub issue.

---

### 1. Summary

This PR collects the local Phase 0 application, database, and Storage security remediation for review. It covers the controlled-plan recommended orders 2–10 evidence work: local backend authorization hardening, the reviewed SPEC-11 table RLS/grant model, the reviewed SPEC-12 Storage bucket/direct-client deny model, the order 8 audit and privileged-path review, the order 9 45-route clinical authorization map, and the order 10 final acceptance evidence review.

All implementation and verification in this PR is **local** or **read-only hosted evidence**. Production code, schema, Storage configuration, and object data were not changed by this work. Two synthetic audit rows were accidentally written to hosted production by an early test iteration; they are disclosed in §8 and in the [order 8 review record](PH0-WP-08-WP-09-privileged-path-review-record.md) §11.

The owner has now supplied database backup/export and recovery-setup evidence outside the repository under `C:\Users\jeffrey\MedAeterna-Backups`. Metadata-only details are recorded in §6. This completes the owner-reported backup artifact portion of the gate; it does **not** by itself authorize deployment, close a SEC finding, or accept Phase 0.

---

### 2. Reason

The work addresses Phase 0 findings tracked under SEC-01–SEC-24 and PH0-WP-01, WP-02, WP-03, WP-05, WP-06, WP-07, WP-08, WP-09, and WP-10:

- shared authorization defects on sensitive and administrative routes;
- missing clinical route/service authorization context;
- weak operational event visibility and retry controls;
- unresolved policy decisions for consent and patient access;
- legacy broad table grants, unwrapped `auth.uid()` policies, unsafe definer-function exposure, and mutable search paths;
- incomplete Storage bucket limits/MIME allowlists and no `storage.objects` deny policy;
- audit-service organization-scope keyword mismatch, disabled legacy event routes still advertised in OpenAPI, and incomplete privileged-path/background-task evidence;
- missing final CI/branch-protection acceptance evidence and controlled-release gate closure.

Policy decisions are taken only from approved SPEC-01–SPEC-10 documents. Undocumented decisions remain fail-closed.

---

### 3. Scope

#### Application authorization

- `backend/app/core/security.py`
- `backend/app/core/clinical_authorization.py`
- `backend/app/core/table_access_inventory.py`
- clinical and administrative routers/services under `backend/app/modules/` and `backend/app/api/admin/`
- operational event/retry modules under `backend/app/core/events/`
- focused negative and regression tests under `backend/tests/`

#### Database

Migration files present in the reviewed local stack:

- `20261118135846_remote_schema.sql` — baseline already present in production; not a pending remote migration
- `20261118150000_role_assignment_least_privilege.sql`
- `20261118160000_role_assignment_anon_read.sql`
- `20261120095915_spec11_table_rls_and_grants.sql`
- `20261120110644_spec12_storage_bucket_policy.sql`
- `20261122062921_ph0_wp03_local_database_release_candidate.sql`

#### Storage

- `backend/supabase/config.toml`
- `backend/scripts/verify_local_storage_effective_access.py`
- `backend/tests/core/test_verify_local_storage_effective_access.py`

#### Documentation/evidence

- `docs/security/SPEC-01` through `docs/security/SPEC-12`
- PH0-WP-02, PH0-WP-03, PH0-WP-05, PH0-WP-06, PH0-WP-07, PH0-WP-08/WP-09, and PH0-WP-10 records
- [SPEC-11/SPEC-12 hosted read-only preflight](SPEC-11-SPEC-12-hosted-read-only-preflight-record.md)
- [Order 9 route authorization record](PH0-WP-02-route-authorization-order-9-record.md)
- [Order 10 final acceptance evidence record](PH0-WP-10-order-10-final-acceptance-evidence-record.md)
- [Backup, recovery, and release gate](PH0-WP-10-backup-recovery-gate-record.md)

No patient row data, patient object content, production secret, production token, or SQL dump content is included in this PR.

---

### 4. Exact migrations pending remotely

Read-only hosted preflight found only `20261118135846 / remote_schema` in production migration history. The following five reviewed migrations remain pending remotely and must not be applied without separate human authorization:

1. `20261118150000_role_assignment_least_privilege.sql`
2. `20261118160000_role_assignment_anon_read.sql`
3. `20261120095915_spec11_table_rls_and_grants.sql`
4. `20261120110644_spec12_storage_bucket_policy.sql`
5. `20261122062921_ph0_wp03_local_database_release_candidate.sql`

No `db push`, `config push`, `apply_migration`, `migration repair`, or `--remote` mutation was performed by this work.

---

### 5. Storage configuration and policy

| Bucket | Public | Size limit | MIME allowlist | Change |
|---|---|---:|---|---|
| `organization-logos` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Keep reviewed settings |
| `patient-avatars` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Install reviewed settings; absent in production |
| `practitioner-photos` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Add reviewed limits/allowlist |
| `patient-documents` | N/A | N/A | N/A | Not implemented; remains planned/private |

Direct client object policy installed locally by `20261120110644_spec12_storage_bucket_policy.sql`:

- policy: `Deny direct client object access`
- table: `storage.objects`
- command: `ALL`
- roles: `anon`, `authenticated`
- `USING (false)` and `WITH CHECK (false)`
- service-role writes remain server-side and are not a client grant

No hosted upload, download, list, update, signed-URL issuance, or delete was performed.

---

### 6. Backup, export, and recovery evidence supplied by owner

The owner reports that database backup/export and recovery setup were completed according to [PH0-WP-10-backup-recovery-gate-record.md](PH0-WP-10-backup-recovery-gate-record.md) and are stored outside the Git repository at:

```text
C:\Users\jeffrey\MedAeterna-Backups\production\20261123-073111
```

Metadata-only inspection confirmed:

| Artifact | Observed metadata |
|---|---|
| `BACKUP-MANIFEST.txt` | Project `MedAeterna`; environment `Production`; backup timestamp `2026-11-23 08:24:02 +01:00`; method `Supabase CLI logical export`; CLI `3.2.0`; files `roles.sql`, `schema.sql`, `data.sql` |
| `roles.sql`, `schema.sql`, `data.sql` | Present in the backup directory; contents were not read or emitted |
| `storage/storage-inventory.md` | Project ref `iyueixtpmzznyffshqon`; captured `2026-11-23`; two confirmed buckets (`organization-logos`, `practitioner-photos`) with **0 active objects**; `patient-avatars` absent; recursive CLI listing returned no objects; no object downloads necessary |

Manifest limitations remain explicit: the standard CLI dump does not include the `auth` schema or Storage object bytes, and PITR/automatic backups are unavailable on the Free plan. The Storage inventory states that bucket configuration and Storage RLS policies require separate evidence. Restore-test execution and primary/backup recovery-owner names are owner-reported; they were not independently replayed in this workspace. No dump content, object bytes, secret, connection string, or patient data was read.

---

### 7. Tests and local/read-only evidence

Verified on the reviewed local tree, with the order 10 evidence consolidated in [PH0-WP-10-order-10-final-acceptance-evidence-record.md](PH0-WP-10-order-10-final-acceptance-evidence-record.md):

| Check | Command / method | Result |
|---|---|---|
| Clean rebuild | `supabase db reset --yes --no-seed` | All 6 migrations reapplied |
| Migration inventory | `supabase migration list` | 6/6 local migrations applied |
| Database catalog tests | `supabase test db` | **36/36 passed**; SPEC-02, SPEC-11, SPEC-12 ok |
| Advisories | `supabase db advisors --type all --level warn` | **No issues found** locally |
| Compile check | `python -m compileall -q app tests` with CI-equivalent environment | PASS |
| Backend regression | `python -m pytest -q` with CI-equivalent environment | **1,438 passed, 1 skipped, 18 warnings** |
| Order 9 route authorization | Focused order 9 plus neighboring security suites | **107 passed**, including 44 new route-level tests |
| OpenAPI contract | `app.openapi()` and `tests/core/test_openapi_security_contract.py` | **74 paths / 89 operations**; 83 secured, 6 intentionally public; disabled `/events` routes not published |
| Effective Storage checks | `scripts/verify_local_storage_effective_access.py` | **22/22 passed** against local API, synthetic identities/objects only |
| Hosted evidence | Read-only Supabase MCP | 26 hosted public tables, 26 RLS-enabled but **0 forced**, 0 `storage.objects` policies, only migration `20261118135846`, no hosted branches |
| CLI | `supabase --version` | `3.2.0` |

Local catalog snapshot after reset:

- 3 reviewed image buckets with exact public flags, 2 MiB limits, and JPEG/PNG/WebP allowlists
- 1 `storage.objects` deny policy
- 34 public tables, all with RLS enabled and forced
- 16 public policies
- 0 tables missing RLS enforcement

The local stack is not staging. The workflow `.github/workflows/backend-ci.yml` defines job display name **`Backend verification`** and triggers on `pull_request` to `main`, `push` to `main`, and `workflow_dispatch`. That exact check name is the one that must be enforced by branch protection.

---

### 8. Risk and compatibility

Deployment of this change set is security-sensitive and may affect application compatibility:

- broad `anon`/`authenticated` table privileges are revoked;
- legacy policies are replaced with reviewed caller-scoped policies;
- definer-function `EXECUTE` is restricted to `service_role`;
- `patient_medical_id_seq` and default ACLs are restricted;
- `practitioner-photos` gains size/MIME limits;
- `patient-avatars` is added;
- direct client object access is denied by RLS.

The order 8 review found that many query services still execute as the shared anon client with no caller JWT (F-3); those paths will fail under the hardened grants and require caller-scoped migration or justified service-role gating first. F-1/F-2 practitioner-role self-assignment and unowned updates were remediated locally under owner approval using the SPEC-02 org-admin delegation rule; this is a **breaking API change**: `POST /practitioner-roles/` now requires a target `practitioner_id`. F-4 org-profile PATCH authority, F-5 authorize-before-fetch ordering, and F-6 dead privileged-helper removal were also remediated locally. F-3, F-8, F-9, invite/departments ordering gaps, unmounted admin routers, worker-identity evidence, and hosted drift still block the order 8 exit condition.

**Incident disclosure:** two synthetic audit rows were written to hosted production by an initial, insufficiently isolated version of the practitioner-role tests; they were read-only verified, left in place per owner decision (23 November 2026), and documented only. Hosted production drift is documented in the [SPEC-11/SPEC-12 preflight record](SPEC-11-SPEC-12-hosted-read-only-preflight-record.md): missing migrations, 0 forced RLS on 26 tables, legacy policies/grants, mutable search paths, client-executable definer functions, unhardened Storage settings, missing `patient-avatars`, and no `storage.objects` deny policy.

---

### 9. Rollout / deployment gate

This PR does **not** authorize rollout. Any future rollout must follow `backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md` §§8–10 and remain at STOP until all gates are closed:

1. Human Dashboard confirmation of the exact production project.
2. Decide whether a hosted staging/preview branch will be used; none currently exists.
3. Backup/PITR/recovery gate — owner evidence supplied as described in §6; reviewer acceptance and §8.5 recording still required.
4. Record the full §8.5 authorization: exact commit, migrations, Storage changes, expected impact, deployment window, operator, recovery owner, and approval timestamp.
5. Run the read-only `supabase db push --dry-run --remote=...` and compare it to the approved list.
6. Run `supabase config diff --remote=...` and review every bucket change.
7. Apply only the reviewed migrations and Storage policy migration under explicit human authorization.
8. Perform §9 database, Storage, application, and evidence verification with separate synthetic identities and objects.

No production migration, configuration push, Storage change, or object operation is part of this PR.

---

### 10. Rollback / recovery

Do not assume an automatic reverse migration exists. For each migration, the release operator must choose between a reviewed forward fix and a restored point, as required by controlled guide §10. A schema rollback is not automatically safe for destructive or data-affecting changes. No production rollback action is part of this PR.

---

### 11. CI, branch protection, and production status

#### CI / branch protection

- PR head `59d69ce…` was pushed; PR #42 merged at `ac28aa8…`.
- GitHub Actions `Backend verification`: **passed** on PR head `59d69ce…` (run `45353172296`) and on merge commit `ac28aa8…` (run `45354774540`).
- Public API returned 0 reviews on PR #42; human approval is not evidenced here.
- Current ruleset `Test` (ID `11701421`) is active, covers all branches, and has `deletion`, `non_fast_forward`, and `pull_request` rules (1 approval + conversation resolution).
- Ruleset `Test` still lacks `required_status_checks` for **`Backend verification`**.
- Owner action is required in GitHub UI/API; exact JSON and UI steps are in [order 10 record §5](PH0-WP-10-order-10-final-acceptance-evidence-record.md#5-branch-protection--exact-owner-action).
- No GitHub token was requested or used by this work.

#### Production

- Production project: `iyueixtpmzznyffshqon`
- Hosted verification scope used so far: **read-only only**
- Production migration history observed: `20261118135846` only
- Production RLS/policies/grants/functions/Storage: **do not match the approved local model**
- SPEC-11/SPEC-12 hosted verification: **BLOCKED / NOT VERIFIED**
- SEC findings: **not closed**
- Phase 0: **NOT ACCEPTED**

PR #42 was for code/design/evidence review only. Its merge does not constitute a production deployment request and does not satisfy the controlled guide’s final authorization gate.

---

### 12. Acceptance review

The order 10 record reviews all 17 baseline acceptance criteria. Phase 0 remains **NOT ACCEPTED** until criteria **1, 6, 8, 9, 10, 12, 14, 15, and 17** are satisfied and all critical/high findings have complete evidence and owner acceptance.

Notably:

- **14** is partial: CI passed on PR head `59d69ce…` and merge commit `ac28aa8…`, but the criterion is not met as a merge gate because `Backend verification` is not enforced and no review approval is recorded.
- **15** is not met because no hosted staging branch exists and release comparison/verification gates remain incomplete; the backup evidence in §6 closes only the owner-supplied artifact portion.
- **17** is not met because ruleset `Test` still lacks `required_status_checks` for `Backend verification`.

Zero SEC findings are closed by this PR.

---

### 13. Reviewer checklist

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
- [x] Audit and privileged-path review recorded; disabled legacy event routes removed from OpenAPI
- [x] Order 10 final evidence record completed
- [x] Owner-supplied backup/export manifest and Storage inventory metadata reviewed
- [ ] Order 8 exit condition met — blocked by F-3, F-8, F-9, invite/departments gaps, worker identity, unmounted admin routers, hosted drift, and remaining review acceptance
- [x] GitHub `Backend verification` check passed on this PR’s exact HEAD and on the merge commit
- [ ] Required `Backend verification` check enforced in ruleset `Test`
- [ ] Human review approval is recorded
- [ ] Rollout and recovery plan are approved separately under controlled guide §8.5
- [ ] Production schema/code confirmed unchanged — true for code/schema/config; two synthetic audit rows were accidentally written to production by a test; see §8 and order 8 §11

---

### 14. Related tracking

Related Phase 0 issues: #31, #34, #35, #36, #37, #38, #3, #10, #16, #17, #20.

No issue or SEC finding is closed by this PR. Order 11 reconciled all 24 SEC findings and the tracking issues to **0 CLOSE**; closure requires environment-specific evidence and reviewer acceptance. See [order 11 reconciliation](PH0-WP-10-order-11-sec-and-issue-reconciliation-record.md).

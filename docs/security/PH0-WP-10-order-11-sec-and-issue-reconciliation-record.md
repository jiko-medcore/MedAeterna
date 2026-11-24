# PH0-WP-10 / Order 11 — SEC Finding and GitHub Issue Reconciliation

**Plan order:** 11 in `PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md` (“Reconcile SEC findings and GitHub issues — Only evidence-backed closures”)

**Work package:** PH0-WP-10 / GitHub #31, #38<br>
**Reconciliation branch:** `security/phase-0-order-11-reconciliation`<br>
**Evidence base:** `origin/main` merge commit `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0` (PR #42)<br>
**PR #42 head:** `59d69ce0e4e467ae0a7668df119db282ee1b7c52`<br>
**Release branch head merged by #42:** `cd203e83b058b516b46084d856410bace9f37ce2`<br>
**Review date:** 24 November 2026<br>
**Status:** **RECONCILIATION COMPLETE — 0 SEC FINDINGS CLOSED — 0 GITHUB ISSUES CLOSED — PHASE 0 NOT ACCEPTED**

**Owner decisions and authority:**

- Closure of SEC findings and GitHub issues remains an owner/reviewer decision. No GitHub token or `gh` CLI was available; no issue, PR, label, comment, or SEC state was mutated by this work.
- Production remains at STOP under the controlled release guide. No hosted migration, configuration push, Storage change, object operation, or SEC closure was performed.
- Local and CI evidence is recorded as local/CI evidence only. It is not treated as hosted or staging proof.

**Controlled procedure:** `backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md`, especially §§8–12.

> This record reconciles SEC-01–SEC-24 and the Phase 0 tracking issues against the code merged by PR #42, CI results, local checks, and fresh read-only hosted evidence. It does not close a finding or issue, accept Phase 0, or authorize deployment. No patient row data, object content, token, secret, connection string, or SQL dump content was read or emitted.

---

## 1. Evidence discipline and controls followed

| Control | Evidence |
|---|---|
| Skills loaded | Official `supabase` and `supabase-postgres-best-practices` skills were loaded before Supabase work. |
| Changelog checked | `https://supabase.com/changelog.md` reviewed. No new breaking change invalidates this reconciliation. Known relevant items remain CLI v3 local-by-default/hosted confirmation (2026-11-04) and branch-merge permission change (2026-11-16); neither authorizes production mutation here. |
| CLI syntax/version | `supabase --version` = **3.2.0**. CLI help and local status were used; no hosted `--remote` mutation was run. |
| Hosted access path | Read-only Supabase MCP on the confirmed production ref. SQL identity was `supabase_read_only_user` on PostgreSQL 17.6. No write tool, `db push`, `config push`, `apply_migration`, `migration repair`, or object operation was used. |
| GitHub access | Public read-only REST API. No token was requested or used. Protected-branch API would require authentication; public ruleset state was read. |
| Environment separation | Local, CI, and hosted evidence are labelled separately. Local success does not imply hosted verification. |
| Stop condition | Hosted drift, absent staging branch, missing required status check, and incomplete §8.5 deployment authorization keep the controlled guide STOP in force. |

Worktree note: `backend/supabase/snippets/db and storage checks.sql` remains a modified local Studio artifact. It is not evidence and is excluded from this reconciliation commit.

---

## 2. PR #42, CI, and branch-protection state

| Item | Evidence |
|---|---|
| PR #42 state | Closed and **merged** at `2026-11-24T08:17:05Z`. |
| PR #42 title | `Phase 0 DB/Storage security release candidate — local implementation, evidence, and controlled-release gate` |
| Base / head | `main` `4a5941c859ce6b1197c9cc2689715f08eb2f24ed` ← `security/phase-0-db-storage-release` `59d69ce0e4e467ae0a7668df119db282ee1b7c52` |
| Merge commit | `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0`; `origin/main` now equals this SHA. |
| CI on PR head | `Backend verification` = **success**, run `45353172296`. |
| CI on merge commit / `main` | `Backend verification` = **success**, run `45354774540`. |
| Review evidence | Public API returned **0 reviews** and 0 issue comments on PR #42. Human review approval is therefore **not evidenced** by public API. |
| Ruleset `Test` | ID `11701421`, active, all branches. Rules: `deletion`, `non_fast_forward`, `pull_request` (1 approval, conversation resolution, no stale-review dismissal, all merge methods). |
| Missing rule | `required_status_checks` for **`Backend verification`** is still absent from the public ruleset. |
| Owner action | Repository administrator must add/enforce the check and verify classic branch protection if used. Exact steps/JSON remain in [order 10 record §5](PH0-WP-10-order-10-final-acceptance-evidence-record.md#5-branch-protection--exact-owner-action). |

CI passing on the exact release head satisfies the test-execution portion of acceptance criterion 14. It does not satisfy criterion 17 because the check is not yet enforced as a merge gate.

---

## 3. Local verification evidence

All commands ran on the exact merged `main` tree at `ac28aa8…` unless noted. Python commands used the backend virtual environment with CI-equivalent environment values from `.github/workflows/backend-ci.yml`.

| ID | Command / method | Result |
|---|---|---|
| L-11-01 | `python -m compileall -q app tests` | PASS |
| L-11-02 | `python -m pytest -q` with CI-equivalent environment | **1,438 passed, 1 skipped, 18 warnings** |
| L-11-03 | `supabase migration list` | 6/6 local migrations applied |
| L-11-04 | `supabase test db` | 3 files, **36 tests, PASS** |
| L-11-05 | `supabase db advisors --type all --level warn` | **No issues found** locally |
| L-11-06 | `scripts/verify_local_storage_effective_access.py` | **22/22 passed** against local API, synthetic objects only |
| L-11-07 | Local stack status | Running at loopback; auxiliary imgproxy/edge-runtime/pooler services reported stopped; no stack mutation during reconciliation |
| L-11-08 | GitHub REST read of PR #42, checks, reviews, ruleset | Merged; CI success on head and merge commit; 0 reviews; required status check missing |

The local Storage script created and deleted only synthetic objects under the test owner prefix and left no orphan object. No hosted URL was accepted by that script.

---

## 4. Read-only hosted evidence

Target: project ref `iyueixtpmzznyffshqon`. All hosted queries were `SELECT`/catalog/advisor reads.

| ID | Check | Result |
|---|---|---|
| H-11-01 | Identity | `current_database=postgres`, `current_user=supabase_read_only_user`, PG 17.6 |
| H-11-02 | Migration history | Only `20261118135846 / remote_schema` |
| H-11-03 | Hosted branches | `[]` — no staging/preview branch |
| H-11-04 | Public relations / RLS | 26 relations, 26 RLS-enabled, **0 forced** |
| H-11-05 | Public policies | 11 policies on 5 tables: `patients` 4, `profiles` 2, `user_roles` 2, `medical_records` 2, `terminology_codes` 1 |
| H-11-06 | Storage buckets | `organization-logos` public, 2 MiB, JPEG/PNG/WebP; `practitioner-photos` public with `file_size_limit=null`, `allowed_mime_types=null`; `patient-avatars` absent |
| H-11-07 | `storage.objects` policies | 0 |
| H-11-08 | Definer functions | 4 public `SECURITY DEFINER` functions; 2 lack fixed `search_path`; 3 anon-executable and 3 authenticated-executable per advisors |
| H-11-09 | Security advisors | 7 lint types: `rls_enabled_no_policy` INFO 21; `function_search_path_mutable` WARN 4; `pg_graphql_anon_table_exposed` WARN 25; `pg_graphql_authenticated_table_exposed` WARN 25; anon/authenticated definer-executable WARN 3 each; `auth_leaked_password_protection` WARN 1 |
| H-11-10 | Performance advisors | 5 lint types, including `unindexed_foreign_keys` INFO 19, `auth_rls_initplan` WARN 9, `unused_index` INFO 35, `multiple_permissive_policies` WARN 6, and `duplicate_index` previously recorded |
| H-11-11 | Health advisors | 0 |

No effective hosted anon/authenticated/service-role data-plane test and no hosted Storage object test was run. Hosted production does **not** match the approved local model.

---

## 5. Evidence keys used in the SEC disposition table

| Key | Meaning |
|---|---|
| **E-A** | Application-local evidence: orders 1–5 and 8–9 records, canonical authorization dependencies, 45-route map, 44 new route tests, full 1,438-test local suite, and PR #42 CI success. |
| **E-D** | Database-local evidence: SPEC-11 candidate, 6 migrations, 34 reviewed local relations, forced RLS, reviewed grants/policies/functions, 36/36 pgTAP, clean local advisors. |
| **E-S** | Storage-local evidence: SPEC-12 buckets/policy, 22/22 effective local Storage checks, no patient objects. |
| **E-H** | Read-only hosted evidence in §4: production schema/policy/grant/function/Storage drift and no staging branch. |
| **E-G** | PR #42 merge and CI evidence in §2: code is in `main` and CI passed; hosted application deployment/runtime is still unproven. |

---

## 6. SEC-01–SEC-24 disposition

**Disposition rule:** `CLOSE` only when the required outcome is fully evidenced in the environment where the finding applies. `KEEP OPEN` includes findings with local mitigation, because plan principle 13 states that code completion alone does not close a finding and §11 requires environment-specific evidence. `RISK-ACCEPT` requires explicit owner acceptance of residual risk; none was supplied for a SEC finding.

| ID | Finding | Evidence | Disposition | Closure blocker |
|---|---|---|---|---|
| SEC-01 | Non-deterministic role selection | E-A, E-G | **KEEP OPEN** | Local deterministic role-resolution tests; hosted runtime/DB evidence absent. |
| SEC-02 | Inconsistent org-admin recognition | E-A, E-G, E-H | **KEEP OPEN** | Local SPEC-02 distinction; hosted role grants/policies still drifted. |
| SEC-03 | Organization context not consistently enforced | E-A, E-G | **KEEP OPEN** | Local resource-derived context tests; hosted cross-org runtime tests not run. |
| SEC-04 | `require_permission()` assumes `org_id` in path | E-A, E-G | **KEEP OPEN** | Local contract/call-site tests; hosted deployment/runtime unproven. |
| SEC-05 | Duplicate `require_patient_access()` definitions | E-A, E-G | **KEEP OPEN** | Local canonical dependency and tests; hosted deployment/runtime unproven. |
| SEC-06 | `patient_access` vs `patient_access_grants` mismatch | E-A, E-G | **KEEP OPEN** | Canonical model selected; migration/service integration and lifecycle tests remain open. |
| SEC-07 | Permission lookup may not propagate caller JWT | E-A, E-G | **KEEP OPEN** | Local caller-scoped client test passes; hosted execution identity unverified. |
| SEC-08 | Medication-request encounter route unauthenticated | E-A, E-G | **KEEP OPEN** | Local authn/resource authorization tests; hosted effective test absent. |
| SEC-09 | Event visibility/retry/audit controls | E-A, E-G | **KEEP OPEN** | Local controls and OpenAPI cleanup; F-8 post-write audit compensation still open. |
| SEC-10 | Unrestricted authenticated role-assignment path | E-A, E-D, E-G, E-H | **KEEP OPEN** | Local lifecycle/ACL work; hosted `user_roles` policy/grants and negative Data API tests outstanding. |
| SEC-11 | Encounter ownership/resource authorization gaps | E-A, E-G | **KEEP OPEN** | Local create/read/update tests; hosted effective tests absent. |
| SEC-12 | Care-team assignment authority gaps | E-A, E-G | **KEEP OPEN** | Local tests; F-3 anon data-plane operations still open. |
| SEC-13 | Practitioner-role administration gaps | E-A, E-G, E-H | **KEEP OPEN** | Local SPEC-02 gating/F-1/F-2 fixes; hosted direct-write denial unverified. |
| SEC-14 | Practitioner appointment-list disclosure | E-A, E-G | **KEEP OPEN** | Local ownership tests; hosted effective tests absent. |
| SEC-15 | Appointment create/update trust of client IDs/fields | E-A, E-G | **KEEP OPEN** | Local field/relationship tests; hosted effective tests absent. |
| SEC-16 | Observation/condition patient-access proof | E-A, E-G | **KEEP OPEN** | Local route/service tests; hosted effective tests absent. |
| SEC-17 | Incomplete RLS policy coverage | E-D, E-H | **KEEP OPEN** | Local 34 relations reconciled; hosted has 26 relations, 0 forced RLS, 21 tables with no policies. |
| SEC-18 | Organization RLS isolation not demonstrated | E-D, E-H | **KEEP OPEN** | Local org-scope tests; hosted cross-tenant role-context tests not run and RLS not forced. |
| SEC-19 | Consent grant lifecycle/provenance incomplete | E-A, E-G | **KEEP OPEN** | SPEC-04–06 policy defined; full purpose/recipient/resource/expiry/revocation implementation incomplete. |
| SEC-20 | Excessive SQL grants including TRUNCATE/TRIGGER/REFERENCES | E-D, E-H | **KEEP OPEN** | Local least-privilege migration; hosted broad exposure advisories remain. |
| SEC-21 | SECURITY DEFINER functions not hardened | E-D, E-H | **KEEP OPEN** | Local 4 functions hardened; hosted 4 definer functions, 2 without fixed search_path, 3 anon-executable. |
| SEC-22 | Image bucket size/MIME controls incomplete | E-S, E-H | **KEEP OPEN** | Local buckets hardened; hosted `practitioner-photos` unbounded and `patient-avatars` absent. |
| SEC-23 | Duplicate patient SELECT policy | E-D, E-H | **KEEP OPEN** | Local cleanup; hosted `patients` still has two permissive SELECT policies. |
| SEC-24 | Storage access policy/effective object access unproven | E-S, E-H | **KEEP OPEN** | Local 22/22; hosted 0 object policies and no hosted object test. |

**Totals:** **24 KEEP OPEN**, **0 CLOSE**, **0 RISK-ACCEPT**. No SEC finding is closed by this order.

---

## 7. GitHub issue reconciliation

All listed issues were read through the public GitHub API and remain **open**. No issue was closed, commented on, or labelled by this work.

| Issue | Scope | Evidence now available | Recommended action |
|---|---|---|---|
| #31 | Security/regression and runtime verification | Local 1,438 tests, 36 pgTAP, 22/22 Storage checks, PR #42 CI success | **Keep open**; add comment with §3/§4 evidence; hosted runtime verification still required. |
| #34 | PH0-WP-01 authorization foundations | PR #42 merged; local role/dependency/route tests and CI pass | **Keep open**; hosted proof and SEC-01–07/10 closure still required. |
| #35 | PH0-WP-02 clinical authorization | 45-route local map, 44 new route tests, CI pass | **Keep open**; hosted/runtime proof, F-3, consent/grant lifecycle and SEC dispositions remain. |
| #36 | PH0-WP-03 RLS/grants/functions | Local 34-relation candidate, 36 pgTAP, clean advisors | **Keep open**; hosted drift is blocking. |
| #37 | Phase 0 index | PR #42 merged; orders 8–11 evidence recorded | **Keep open**; parent index must not close while any critical/high SEC finding is open. |
| #38 | Backend CI and `main` protection | Workflow exists; CI passed on PR head and merge commit | **Keep open**; owner must enforce `Backend verification` in ruleset/branch protection and verify blocked merge behavior. No approvals recorded on PR #42. |
| #3 | Avatar upload / Storage integration | Local SPEC-12 object rules and 22/22 effective checks | **Keep open**; hosted bucket/object verification pending. |
| #10 | Profile avatar upload validation | Local image validation and Storage policy tests | **Keep open**; hosted evidence pending. |
| #16 | Audit logging and compliance | Local audit tables/events and service tests | **Keep open**; F-8 post-write audit compensation and hosted audit-policy drift remain. |
| #17 | Consent and emergency contacts | SPEC-04–06 policy documents approved | **Keep open**; lifecycle implementation/provenance tests incomplete. |
| #20 | Deployment, operations, security hardening | Backup manifest/inventory evidence supplied; CI passes | **Keep open**; hosted verification, §8.5 authorization, branch protection, and staging gates remain. |

### Suggested issue comment text for the owner/reviewer

```text
Evidence update (24 November 2026): PR #42 is merged at main ac28aa8. Backend verification passed on PR head 59d69ce (run 45353172296) and merge commit ac28aa8 (run 45354774540). Local verification at ac28aa8: compileall pass; pytest 1,438 passed/1 skipped/18 warnings; migration list 6/6; supabase test db 36/36; local advisors clean; local Storage effective-access 22/22. Read-only hosted evidence still shows only migration 20261118135846, 26 public relations with 0 forced RLS, 11 policies on 5 tables, 0 storage.objects policies, unhardened practitioner-photos, no patient-avatars, and definer-function exposure. Required status check Backend verification is not yet present in ruleset Test (ID 11701421). Order 11 reconciliation: 0 SEC findings closed; this issue remains open pending hosted/runtime evidence, branch protection, and owner acceptance. See PH0-WP-10-order-11-sec-and-issue-reconciliation-record.md.
```

---

## 8. Residual gap register after order 11

| Gap | Source | Disposition |
|---|---|---|
| Hosted application deployment/runtime evidence | E-G | Unknown / not verified; blocks all application SEC closures. |
| Hosted schema, RLS, grants, functions, Storage drift | H-11-02–H-11-09 | Blocking; reviewed migrations/config are not deployed. |
| Hosted staging branch | H-11-03 | None exists; formal decision still required. |
| Required `Backend verification` status check | §2 | Owner action pending; public ruleset lacks rule. |
| Human review approval on PR #42 | §2 | 0 reviews via public API; not evidenced. |
| F-3 anon data-plane operations | Order 8/9 records | Still open. |
| F-8 post-write audit compensation | Order 8/9 records | Still open. |
| F-9 raw-SQL bootstrap utility | Order 8 record | Still open. |
| Consent/grant full lifecycle | SPEC-04–06, order 9 | Still open. |
| §8.5 exact deployment authorization | Controlled guide | Still incomplete; STOP remains. |
| Backup artifact acceptance and recovery-owner names | Order 11 §7 / gate record | Owner evidence received; reviewer acceptance and §8.5 recording required. |

---

## 9. Controlled guide §11.3 report

```text
Phase: Recommended execution order 11 / PH0-WP-10 SEC and GitHub issue reconciliation
Git branch: security/phase-0-order-11-reconciliation
Evidence base commit: ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0 (PR #42 merge into main)
Supabase CLI version: 3.2.0
Local stack status: running at loopback; 6/6 migrations; 36/36 pgTAP; 0 WARN local advisories; auxiliary services stopped
Remote project inspected: yes, read-only MCP
Remote project reference: iyueixtpmzznyffshqon
Files changed: order 11 reconciliation record; docs-side v2.0 baseline order 11 note; order 10 post-merge update; backup/recovery gate update; historical PR #42 body update
Migration IDs: local 20261118135846, 20261118150000, 20261118160000, 20261120095915, 20261120110644, 20261122062921; hosted only 20261118135846
Storage config changes: NONE
Policies changed: NONE
Tests run: compileall; full backend pytest; supabase migration list; supabase test db; supabase db advisors; local Storage effective-access script; GitHub REST reads; read-only MCP catalog/advisors
Tests passed/failed/skipped: 1438 passed / 0 failed / 1 skipped; database 36/36; Storage 22/22; local advisors clean
Advisors: hosted security 7 lint types; performance 5 lint types; health 0
Drift found: yes — migrations, RLS force, policies, grants, functions, indexes, Storage buckets and Storage policies
Risks: CI success and merged code are not hosted proof; required check not enforced; no approval evidenced; hosted deployment unauthorized
Approval required: owner must enforce Backend verification, record review approval, close/keep-open issues with evidence comments, complete §8.5 authorization, and accept any closure
Production mutations performed: NONE
Next permitted action: owner applies branch-protection and issue-closure decisions; separately complete controlled guide gates before any authorized deployment
```

---

## 10. Cross-references

- [Phase 0 baseline — order 11 and acceptance criteria](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [Order 10 final acceptance evidence](PH0-WP-10-order-10-final-acceptance-evidence-record.md)
- [Order 8 audit and privileged-path review](PH0-WP-08-WP-09-privileged-path-review-record.md)
- [Order 9 route authorization record](PH0-WP-02-route-authorization-order-9-record.md)
- [SPEC-11/SPEC-12 hosted read-only preflight](SPEC-11-SPEC-12-hosted-read-only-preflight-record.md)
- [Backup, recovery, and release gate](PH0-WP-10-backup-recovery-gate-record.md)
- [Controlled Supabase database and Storage release guide](../../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- [PR #42](https://github.com/jiko-medcore/MedAeterna/pull/42)

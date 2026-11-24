# PH0-WP-10 / Order 12 — Formal Phase 0 Acceptance Review

**Plan order:** 12 in `PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md` (“Formal Phase 0 acceptance review”; exit condition: **“All acceptance gates met”**)

**Work package:** PH0-WP-10 / GitHub #31, #37, #38<br>
**Review branch:** `security/phase-0-order-12-acceptance-review`<br>
**Evidence base:** local commit `5a32da5e7cca77cff0b1c3da7ae0a1359510dcac` on top of PR #42 merge `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0`<br>
**Review date:** 24 November 2026<br>
**Status:** **FORMAL REVIEW COMPLETED — EXIT CONDITION NOT MET — PHASE 0 NOT ACCEPTED — 0 CLOSURES / 0 DEPLOYMENT AUTHORIZATIONS**

**Owner prerequisite state:** the six owner actions listed before this request were re-checked and remain **not done** or **incomplete**. This formal review was performed before those actions, as requested. It records the current evidence-based decision; it does not convert incomplete gates into accepted gates.

**Controlled procedure:** `backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md`, especially §§8–12.

> This record answers the order 12 exit condition directly: **all acceptance gates are not met**. Local implementation and CI evidence is strong, but hosted production still does not match the approved model, PR review/branch-protection gates are incomplete, §8.5 deployment authorization is not recorded, and no production deployment or production verification exists. No SEC finding or GitHub issue was closed by this review, and no hosted mutation was performed.

---

## 1. Evidence discipline and controls followed

| Control | Evidence |
|---|---|
| Skills loaded | Official `supabase` and `supabase-postgres-best-practices` skills were loaded before this review. |
| Changelog checked | `https://supabase.com/changelog.md` was re-fetched. Relevant breaking changes remain CLI v3 local-by-default/hosted confirmation (2026-11-04) and branch-merge permission requiring Production Branches read-write (2026-11-16). Neither authorizes a hosted mutation here. Other 2026-11 changes (custom OIDC providers, backup sign-in options, correlated logs, Flutter v3) do not affect this review. |
| CLI syntax/version | `supabase --version` = **3.2.0**. CLI v3 targets local by default; `--remote` selects hosted. |
| CLI authentication | `supabase whoami` returned `AccessTokenRequiredError`. Authenticated CLI dry-run/config push and remote migration commands were therefore **not independently reproduced** in this workspace. Read-only MCP was used for hosted inspection. |
| Hosted access path | Supabase MCP read-only tools only. SQL identity was `supabase_read_only_user` on PostgreSQL 17.6. No write tool, `db push`, `config push`, `apply_migration`, `migration repair`, or object operation was used. |
| GitHub access | Public read-only REST API. No token or `gh` CLI was used. Protected-branch API returned an empty public list; repository ruleset details were read through the public rulesets endpoint. |
| Environment separation | Local, CI, and hosted evidence are labelled separately. Local success is not treated as staging or production proof. |
| Data handling | No patient row data, object bytes, token, secret, connection string, or SQL dump content was read or emitted. Hosted SQL used catalog/advisor queries only. |
| Stop condition | Controlled guide §§8.3–8.5, 10.1 and 12 require STOP while drift, authorization, backup/recovery, approval, deployment, and Gate G evidence are incomplete. |

Worktree note: `backend/supabase/snippets/db and storage checks.sql` remains a modified local Studio artifact. It is not evidence and is excluded from this review commit.

---

## 2. Order 12 exit-condition decision

| Requirement | Decision |
|---|---|
| Order 12 exit condition: **All acceptance gates met** | **NOT MET** |
| Formal Phase 0 acceptance review recorded | **MET** by this record |
| Phase 0 acceptance | **NOT ACCEPTED** |
| SEC findings closed | **0** |
| GitHub issues closed | **0** |
| Production mutations performed | **NONE** |
| Deployment authorized | **NO** |

The review is formally recorded, but the exit condition fails because gates D, E, F, and G are not met and seven of the 20 baseline acceptance criteria are not met. A release is not complete until controlled guide Gate G passes; it has not.

---

## 3. Live GitHub evidence

| ID | Check | Result |
|---|---|---|
| G-12-01 | PR #42 state | Merged into `main` at `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0` on 2026-11-24T08:17:05Z. |
| G-12-02 | CI on merge commit | `Backend verification` = **completed / success**, run `45354774540`. PR head `59d69ce…` also passed in run `45353172296`. |
| G-12-03 | PR reviews | Public API returned **0 reviews**. Human approval is not evidenced. |
| G-12-04 | Repository ruleset | `Test`, ID `11701421`, active, all branches. Rules: `deletion`, `non_fast_forward`, `pull_request` (1 approval, conversation resolution, no stale-review dismissal). |
| G-12-05 | Missing rule | **`required_status_checks` for `Backend verification` is absent.** Owner action 1 remains not done. |
| G-12-06 | Public branch-protection API | `GET /rules/branches/main` returned `[]` publicly; this is not positive evidence of classic branch protection. |
| G-12-07 | Issues | All Phase 0 tracking issues remain open: #31, #34, #35, #36, #37, #38, #3, #10, #16, #17, #20. Public API showed all repository issues #1–#38 open. |

CI passing on the exact merged code satisfies only the test-execution part of acceptance criterion 12/14. It does not satisfy required-check enforcement, human approval, hosted deployment, or production verification.

---

## 4. Local CLI and regression evidence

All commands ran from `backend/` on the current review branch. Python checks used CI-equivalent placeholder environment values from `.github/workflows/backend-ci.yml`.

| ID | Command / method | Result |
|---|---|---|
| L-12-01 | `supabase --version` | 3.2.0 |
| L-12-02 | `supabase status -o json` (non-secret fields only) | Local API `http://127.0.0.1:58561`, DB `127.0.0.1:58562`, linked project ref `iyueixtpmzznyffshqon`, name `MedAeterna`. Auxiliary imgproxy/edge-runtime/pooler services reported stopped. |
| L-12-03 | `supabase whoami` | `AccessTokenRequiredError`; authenticated remote CLI operations unavailable. |
| L-12-04 | `supabase migration list` | 6/6 local migrations applied. |
| L-12-05 | `supabase test db` | 3 files, **36 tests, PASS**. |
| L-12-06 | `supabase db advisors --type all --level warn` | **No issues found** locally. |
| L-12-07 | `python -m compileall -q app tests` | PASS. |
| L-12-08 | `python -m pytest -q` with CI-equivalent environment | **1,438 passed, 1 skipped, 18 warnings**. |
| L-12-09 | `scripts/verify_local_storage_effective_access.py` | **22/22 passed** against local API with synthetic identities/objects only; no orphan object remained. |
| L-12-10 | `git rev-parse HEAD` | `5a32da5e7cca77cff0b1c3da7ae0a1359510dcac`. |

Local database and Storage evidence is reproducible but is **not** staging or production evidence.

---

## 5. Read-only hosted evidence

Target: project ref `iyueixtpmzznyffshqon`. All hosted queries were `SELECT`/catalog/advisor reads.

| ID | Check | Result |
|---|---|---|
| H-12-01 | Identity | `current_database=postgres`, `current_user=supabase_read_only_user`, PG 17.6. |
| H-12-02 | Migration history | Only `20261118135846 / remote_schema`. The five reviewed migrations remain absent. |
| H-12-03 | Hosted branches | `[]` — no staging/preview branch. |
| H-12-04 | Public relations / RLS | 26 relations, 26 RLS-enabled, **0 forced**. |
| H-12-05 | Public policies | 11 policies on 5 tables: `patients` 4, `profiles` 2, `user_roles` 2, `medical_records` 2, `terminology_codes` 1. The security advisor reports 21 tables with RLS enabled and no policy. |
| H-12-06 | Storage buckets | `organization-logos` public, 2 MiB, JPEG/PNG/WebP. `practitioner-photos` public with `file_size_limit=null` and `allowed_mime_types=null`. `patient-avatars` absent. |
| H-12-07 | `storage.objects` policies | 0. |
| H-12-08 | Definer functions | 4 public `SECURITY DEFINER` functions; 2 lack fixed `search_path`; 3 are anon-executable and 3 authenticated-executable per advisors. |
| H-12-09 | Security advisors | 7 lint types: `rls_enabled_no_policy` INFO 21, `function_search_path_mutable` WARN 4, `pg_graphql_anon_table_exposed` WARN 25, `pg_graphql_authenticated_table_exposed` WARN 25, anon/authenticated definer-executable WARN 3 each, `auth_leaked_password_protection` WARN 1. |
| H-12-10 | Performance advisors | 5 lint types: `unindexed_foreign_keys` INFO 19, `auth_rls_initplan` WARN 9, `unused_index` INFO 35, `multiple_permissive_policies` WARN 6, plus previously recorded duplicate/other drift. |
| H-12-11 | Health advisors | 0. |
| H-12-12 | Hosted deployment verification | **NOT DONE**. No hosted data-plane, cross-tenant, Storage object, application smoke, or monitoring evidence exists. |

Hosted production does **not** match the reviewed local database and Storage model. This alone blocks acceptance criteria 15, 16, 17 and 19, and controlled guide Gates E–G.

---

## 6. Controlled guide release gates A–G

| Gate | Requirement | Status | Evidence / blocker |
|---|---|---|---|
| A — Policy/design approval | Finding/spec identified; access matrix and classification approved; scope and recovery approach reviewed | **PARTIAL** | SPEC-01–SPEC-12 and owner policy decisions are recorded in `PH0-WP-06-SPEC-approval-and-consent-access-model.md`, SPEC-11/SPEC-12 records, and order 8 review. Owner approval covers the documented design decisions only; implementation and production deployment approval remain separate and unrecorded, and residual recovery choices are open. |
| B — Implementation review | Feature branch, migrations, Storage config/policy SQL, least-privilege review, tests | **MET (local scope)** | PR #42 merged the reviewed implementation; migrations `20261118150000`–`20261122062921`, `config.toml`, Storage policy SQL, and tests are in `main`. This does not extend to hosted implementation. |
| C — Local verification | Local stack, clean reset, migrations, DB tests, catalog assertions, advisors, Storage tests, backend regression, exact commit | **PARTIAL / MET LOCALLY** | §4. Local migration list, 36/36 pgTAP, clean advisors, 22/22 Storage checks, and 1,438 backend tests pass at the reviewed commit. A clean `db reset` was evidenced in earlier records, and the single skipped backend test is not identified here; this is local evidence only. |
| D — PR approval | Review completed; CI passes; no unresolved critical/high issue; deployment/rollback approved; PR merged and SHA frozen | **NOT MET** | CI and merge are evidenced, but 0 reviews, required status check missing, 24 SEC findings open, and §8.5 deployment/rollback not approved. |
| E — Production preflight | Human project identity; migration history; schema/grant/RLS/function drift; Storage audit; dry-run; backup/recovery; exact authorization | **NOT MET** | Read-only drift and backup metadata exist, but authenticated dry-run/config diff is not reproduced, no staging branch exists, restore/recovery owner names and §8.5 fields are incomplete. |
| F — Production deployment | Migrations/config/policies applied to exact target; no unexpected changes; evidence captured | **NOT MET** | Hosted migration history still contains only `20261118135846`; no Storage policy deployed. |
| G — Production verification | DB catalog assertions; Storage assertions; synthetic authz tests; cross-tenant denials; app smoke; monitoring; evidence reviewed and finding status updated | **NOT MET** | No hosted verification evidence exists; all SEC findings remain open. |

**Controlled guide §12 statement:** a release is not complete until Gate G passes. Gate G has not passed, so the release is not complete.

---

## 7. Baseline 20-criterion acceptance matrix

Statuses: **MET** = fully evidenced; **LOCAL/PARTIAL** = some required evidence exists but environment-specific or lifecycle evidence is missing; **NOT MET** = required evidence is absent or contradicted.

| # | Acceptance criterion | Status | Evidence / residual |
|---:|---|---|---|
| 1 | No unresolved critical authorization or privilege-escalation finding | **NOT MET** | Order 11 kept all 24 SEC findings open; F-3, F-8, F-9, invite/departments ordering, unmounted hardened routers, worker identity, and hosted drift remain. |
| 2 | Every sensitive route has authentication and resource-level authorization | **LOCAL/PARTIAL** | 45-route local map and 44 focused tests pass; hosted effective behavior not verified. |
| 3 | Role resolution is deterministic, scoped and resistant to self-escalation | **LOCAL/PARTIAL** | SPEC-02/practitioner-role tests pass; hosted role policy/grants drifted. |
| 4 | Patient-access and consent models are documented and consistently implemented | **PARTIAL** | SPEC-04–SPEC-06 approved; full purpose/recipient/resource/expiry/revocation provenance and canonical grant lifecycle incomplete. |
| 5 | Organization isolation is tested across organizations | **LOCAL/PARTIAL** | Local cross-org tests pass; hosted cross-tenant role-context tests not run and RLS not forced. |
| 6 | Every sensitive table is inventoried; grants and RLS reviewed table by table | **LOCAL/PARTIAL** | Local 34-relation candidate reviewed; hosted has 26 relations, 0 forced RLS, 21 tables without policies. |
| 7 | All SECURITY DEFINER functions have reviewed ownership, execution privileges, schema qualification and trusted search path | **LOCAL/PARTIAL** | Local functions hardened; hosted still exposes 3 definer functions to anon/authenticated and 2 have mutable search paths. |
| 8 | Service-role call sites are inventoried and justified | **PARTIAL** | Inventory exists; F-3, F-8, F-9, worker identity and unmounted routers remain open. |
| 9 | Storage buckets have explicit public/private classification and tested object-level access | **LOCAL/PARTIAL** | Local 22/22 effective checks pass; hosted `practitioner-photos` unbounded, `patient-avatars` absent, 0 object policies. |
| 10 | Clinical documents are private before feature enablement | **NOT MET** | `patient-documents` is not implemented; hosted `practitioner-photos` is public and unbounded; no hosted object policy. |
| 11 | Sensitive operations produce protected, attributable audit records | **LOCAL/PARTIAL** | Local audit tables/services tested; hosted audit/event tables retain broad client exposure; F-8 compensation open; two synthetic audit rows remain by owner decision. |
| 12 | Positive and negative authorization tests pass | **LOCAL/CI PARTIAL** | 1,438 local tests and CI success on PR head/merge; no hosted runtime verification. |
| 13 | CI is required on `main`; branch protection is verified | **NOT MET** | Ruleset `Test` lacks `required_status_checks`; 0 reviews on PR #42; protected-branch API not publicly readable. |
| 14 | Local database and Storage migrations are reviewed and reproducible | **MET (local)** | 6/6 migrations, 36/36 pgTAP, 22/22 Storage, clean local advisors. |
| 15 | Remote production database and Storage are deployed from approved migrations/policies | **NOT MET** | Hosted migration history contains only the baseline migration; no Storage policy deployed. |
| 16 | Production grants, RLS, functions, buckets and object policies are independently verified | **NOT MET** | Read-only inspection shows unresolved drift; no effective production verification passed. |
| 17 | Controlled production authorization and Storage tests pass | **NOT MET** | §8.5 authorization incomplete; hosted Storage object tests not run. |
| 18 | Each SEC finding has a documented disposition and supporting evidence | **PARTIAL** | Order 11 documented all 24 dispositions but kept all 24 open; hosted closure evidence absent. |
| 19 | No unresolved high-risk drift remains between migrations, local and production | **NOT MET** | Migration, RLS force, policy, grant, function, index, bucket and Storage-policy drift remains. |
| 20 | Formal Phase 0 acceptance review is recorded | **MET** | This record. Note: recording the review does not mean acceptance was granted. |

**Tally:** 2 of 20 criteria fully MET (one local-only), 11 LOCAL/PARTIAL, and 7 NOT MET. Overall decision remains **NOT ACCEPTED**.

---

## 8. Owner prerequisite checklist status

| Owner action listed before this request | Current status from live re-check |
|---|---|
| 1. Enforce `Backend verification` as required status check for `main` and verify blocked merge | **NOT DONE** — ruleset `Test` has no `required_status_checks` rule. |
| 2. Record human review approval | **NOT DONE** — public API returned 0 reviews on PR #42. |
| 3. Post evidence comments to issues #31, #34, #35, #36, #37, #38, #3, #10, #16, #17, #20 | **NOT DONE / NOT AVAILABLE HERE** — no GitHub token or `gh` CLI; all issues remain open. Template is in order 11 record §7. |
| 4. Keep all SEC findings and those issues open until environment-specific evidence exists | **DONE** — 0 SEC findings and 0 issues closed by orders 10–12. |
| 5. Complete §8.5 authorization: window, operator, recovery owners, approval timestamp, expected impact, evidence acceptance | **INCOMPLETE** — controlled guide fields remain unrecorded. |
| 6. Separately authorize and verify hosted deployment | **NOT DONE / BLOCKED** — hosted drift remains; no deployment or production verification evidence. |

---

## 9. Residual gap register after order 12

| Gap | Source | Disposition |
|---|---|---|
| Required `Backend verification` status check | G-12-04/G-12-05 | Owner action pending; criterion 15 and Gate D blocked. |
| Human review approval on PR #42 | G-12-03 | Not evidenced; Gate D blocked. |
| Evidence comments and issue dispositions | G-12-07 / order 11 §7 | Owner/reviewer action pending; all issues open. |
| Hosted migration, RLS, policy, grant, function and Storage drift | H-12-02–H-12-08 | Blocking; Gates E–G not met. |
| Hosted staging branch | H-12-03 | None exists; formal decision still required. |
| Authenticated CLI dry-run/config diff | L-12-03 | Unknown / not reproduced; read-only MCP used instead. |
| Backup/recovery acceptance and §8.5 authorization | Gate record / §8 above | Owner evidence received but reviewer acceptance and exact fields incomplete. |
| F-3, F-8, F-9, invite/departments, unmounted routers, worker identity | Order 8/9 records | Still open. |
| Consent/grant full lifecycle | SPEC-04–SPEC-06 / order 9 | Still open. |
| Hosted application smoke, cross-tenant, Storage object and monitoring evidence | H-12-12 | Absent; Gate G blocked. |

---

## 10. Controlled guide §11.3 report

```text
Phase: Recommended execution order 12 / Formal Phase 0 acceptance review
Git branch: security/phase-0-order-12-acceptance-review
Commit SHA: 5a32da5e7cca77cff0b1c3da7ae0a1359510dcac
Supabase CLI version: 3.2.0
Local stack status: running at loopback; 6/6 migrations; 36/36 pgTAP; 0 WARN advisories; 22/22 local Storage checks; auxiliary services stopped
Remote project inspected: yes, read-only MCP
Remote project reference: iyueixtpmzznyffshqon
Files changed: this order 12 record; the order 12 status note and traceability-register update in the docs-side v2.0 baseline
Migration IDs: local 20261118135846, 20261118150000, 20261118160000, 20261120095915, 20261120110644, 20261122062921; hosted only 20261118135846
Storage config changes: NONE
Policies changed: NONE
Tests run: compileall; full backend pytest; supabase migration list; supabase test db; supabase db advisors; local Storage effective-access script; GitHub REST reads; read-only MCP catalog/advisors
Tests passed/failed/skipped: 1438 passed / 0 failed / 1 skipped; database 36/36; Storage 22/22; local advisors clean
Advisors: hosted security 7 lint types; performance 5 lint types; health 0
Drift found: yes — migrations, RLS force, policies, grants, functions, indexes, Storage buckets and Storage policies
Risks: local/CI success is not hosted proof; required check not enforced; no review approval; §8.5 authorization incomplete; hosted deployment unauthorized
Approval required: owner actions 1–6; then a fresh order 12 re-review before any acceptance decision
Production mutations performed: NONE
Next permitted action: owner completes branch protection, review approval, issue comments, §8.5 authorization and separately authorized hosted deployment/verification; then re-run order 12 against fresh evidence
```

---

## 11. Decision statement and cross-references

**Formal order 12 decision:** the review is recorded, but the exit condition **“All acceptance gates met” is NOT MET**. Phase 0 is **NOT ACCEPTED**. No SEC finding, GitHub issue, deployment, or controlled-release gate was closed or authorized by this review.

- [Phase 0 baseline — orders 12 and acceptance criteria](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [Order 11 SEC and GitHub issue reconciliation](PH0-WP-10-order-11-sec-and-issue-reconciliation-record.md)
- [Order 10 final acceptance evidence](PH0-WP-10-order-10-final-acceptance-evidence-record.md)
- [Backup, recovery and release gate](PH0-WP-10-backup-recovery-gate-record.md)
- [Controlled Supabase database and Storage release guide](../../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- [PR #42](https://github.com/jiko-medcore/MedAeterna/pull/42)

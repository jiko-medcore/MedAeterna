# PH0-WP-10 / Order 10 — Final Audit Evidence, CI, Branch Protection and Acceptance Review

**Plan order:** 10 in `PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md` (“Complete audit evidence, CI, branch protection and final acceptance review”)

**Work package:** PH0-WP-10 / GitHub #31, #38  
**Branch:** `security/phase-0-db-storage-release`  
**Evidence base commit (code under review):** local `e473df31a8881f67236a277c91ba01d38cbe2af8`  
**Review date:** 24 November 2026  
**Status:** **LOCAL/CI EVIDENCE COMPLETE — PR #42 MERGED — BRANCH PROTECTION OWNER ACTION REQUIRED — PRODUCTION MUTATIONS NONE — PHASE 0 NOT ACCEPTED**

**Owner decisions recorded in this review:**

1. Branch protection: the owner will apply the required status check in GitHub UI/API using their own credentials; no token was requested or used by the agent.
2. Production gate: order 10 is finalized as **evidence + STOP**. No hosted mutation, migration, Storage change, object operation, or SEC closure is authorized by this record.

**Post-merge reconciliation (24 November 2026):** PR #42 merged the release candidate into `main` at `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0`. `Backend verification` passed on PR head `59d69ce0e4e467ae0a7668df119db282ee1b7c52` (run `45353172296`) and on the merge commit (run `45354774540`). The test-execution portion of criterion 14 is therefore satisfied; the criterion is still **NOT MET as a merge gate** because the required status check is not enforced. The [order 11 reconciliation record](PH0-WP-10-order-11-sec-and-issue-reconciliation-record.md) is authoritative for post-merge SEC and GitHub issue dispositions. Phase 0 remains **NOT ACCEPTED**.

**Controlled procedure:** `backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md`, especially §§0.2–0.3, 2.2, 8.1–8.5, 9.4, 10, 11 and 12.

> This record consolidates local audit evidence, the CI workflow and its exact check name, the current GitHub ruleset state, read-only hosted evidence, and the 17 acceptance criteria from the v2.0 baseline. It does **not** accept Phase 0, close a SEC finding, deploy a migration, alter Storage, upload/download objects, or change production application code. No patient row data, object content, token, secret, connection string, or SQL dump was read or emitted.

---

## 1. Evidence discipline and controls followed

| Control | Evidence |
|---|---|
| Skills loaded | Official `supabase` and `supabase-postgres-best-practices` skills were loaded before any Supabase work. |
| Changelog checked | `https://supabase.com/changelog.md` was reviewed. The relevant breaking change remains CLI v3 local-by-default/hosted confirmation (2026-11-04), already addressed by the controlled guide. Supabase branch-merge permission change (2026-11-16) affects branch merges, not this read-only review. No change authorizes production mutation here. |
| CLI syntax discovered | `supabase --version` = **3.2.0**. `--help` was inspected for `db`, `test db`, `db advisors`, `migration list` and `config diff`. CLI v3 defaults to the local stack; `--remote` selects hosted. |
| Hosted access path | Read-only Supabase MCP for the confirmed production ref. SQL identity was `supabase_read_only_user` on PostgreSQL 17.6. No write MCP action, `--remote` CLI mutation, `db push`, `config push`, `apply_migration`, `migration repair`, or object operation was used. |
| Local vs hosted | Local results are explicitly labelled local. No local test, advisory, or documentation statement is treated as staging or production proof. |
| GitHub access | Public read-only REST API. No GitHub token was available or used. The protected-branch API returned `401 Requires authentication`; repository rulesets were publicly readable. |
| Stop condition | Controlled guide §§8.3, 8.4, 8.5 and 10.1 require STOP because production drift is unresolved, backup/PITR/recovery gates are incomplete, no staging branch exists, and no exact deployment authorization was supplied. |

Worktree note: `backend/supabase/snippets/` is untracked local Studio output. It is not evidence, is not part of this record, and was not committed.

---

## 2. Git and CI state

| Item | Evidence |
|---|---|
| Original local branch / HEAD | `security/phase-0-db-storage-release` / `e473df31a8881f67236a277c91ba01d38cbe2af8` (evidence base when order 10 was prepared; later merged through PR #42). |
| Local status at original review | Ahead of remote tracking by 9 commits; one untracked local Studio snippets directory. Patch hygiene `git diff --check --ignore-cr-at-eol` clean. |
| Remote release branch at original review | `0066602afac41662eb6c79f877049d0b6fb39ed9` — stale relative to the then-local HEAD. PR #42 later merged the updated branch. |
| `main` | `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0` after PR #42 merged (was `4a5941c…` when this review was prepared). |
| Open release PRs | None. PR #42 was merged; PR #41 was historically mis-oriented and is not a release merge. |
| Workflow file | `.github/workflows/backend-ci.yml` exists on both `origin/main` and the local release branch. YAML parses successfully. |
| Triggers | `pull_request` to `main`, `push` to `main`, `workflow_dispatch`. |
| Job / check name | Job id `backend-verification`; display name **`Backend verification`**. This is the exact required check name. |
| Workflow permissions | `contents: read`; dummy CI-only settings; no production Supabase/Resend credentials. |
| Workflow steps | Python 3.13, pip cache, declared requirements plus pinned `psycopg2-binary==2.9.11`, `python -m compileall -q app tests`, `python -m pytest -q` from `backend/`. |
| Known successful CI runs | `Backend verification` succeeded on prior `main` SHA `4a5941c…` (run `45045887370`), PR #42 head `59d69ce…` (run `45353172296`), and merge commit `ac28aa8…` (run `45354774540`). |
| Status of original gap | The original gap — no CI on the then-unpushed release commit — is closed by PR #42. Criterion 14 remains **NOT MET as a gate** because `Backend verification` is not enforced as a required status check and no human approval is recorded on PR #42. |

---

## 3. Local verification evidence (exact commands and results)

All Python commands ran from `backend/` with `.venv/Scripts/python.exe`. CI-equivalent environment values were the same placeholders used by the workflow (`ENV=test`, local `SUPABASE_URL`, placeholder publishable/secret keys, placeholder Resend/email settings). The local Supabase CLI target was `127.0.0.1:58562`; no `--remote` flag was passed.

| ID | Command / method | Result |
|---|---|---|
| E-10-01 | `python -m compileall -q app tests` with CI-equivalent environment | PASS |
| E-10-02 | `python -m pytest -q` with CI-equivalent environment | **1,438 passed, 1 skipped, 18 warnings in 12.28s** |
| E-10-03 | `supabase migration list` | 6/6 local migrations applied, in timestamp order |
| E-10-04 | `supabase test db` | **3 files, 36 tests, PASS** |
| E-10-05 | `supabase db advisors --type all --level warn` | **No issues found** locally |
| E-10-06 | `git diff --check --ignore-cr-at-eol` | Clean |
| E-10-07 | YAML parse of `.github/workflows/backend-ci.yml` | Valid; job name `Backend verification` |
| E-10-08 | GitHub REST read of workflow runs and check-runs | Originally: CI passed on old `main` SHA and no check run on the then-unpushed release SHA. Post-merge: CI passed on PR #42 head `59d69ce…` and merge commit `ac28aa8…`. |

The 1,438-test count matches the order 9 record and includes the 44 route-level authorization tests, the WP-01/WP-02 negative-authorization suites, audit-service tests, OpenAPI contract tests, database execution-policy tests, and storage/consent/practitioner-role regression suites. This is local evidence; it does not verify hosted RLS, Storage, or effective identity behavior.

---

## 4. Read-only hosted evidence (Supabase MCP)

Target: project ref `iyueixtpmzznyffshqon`; URL returned by `get_project_url`. All queries were `SELECT`-only. No patient data, object content, logs with payloads, or secrets were read.

| ID | Check | Result | Interpretation |
|---|---|---|---|
| H-10-01 | Identity | `current_database=postgres`, `current_user=supabase_read_only_user`, PG 17.6 | Read-only path confirmed. |
| H-10-02 | Hosted branches | `list_branches` = `[]` | No hosted staging/preview branch; staging verification cannot be claimed. |
| H-10-03 | Migration history | Only `20261118135846 / remote_schema` | Five reviewed local migrations remain pending remotely. |
| H-10-04 | Public tables / RLS | 26 tables, 26 RLS-enabled, **0 forced** | Local model has 34 forced-RLS tables; production drift remains blocking. |
| H-10-05 | Public policies | Policies on 5 tables: `patients` 4, `medical_records` 2, `profiles` 2, `user_roles` 2, `terminology_codes` 1 | Approved local policy set (16 policies over the reviewed inventory) is not deployed. |
| H-10-06 | Storage buckets | `organization-logos` public, 2 MiB, JPEG/PNG/WebP; `practitioner-photos` public with `file_size_limit=null` and `allowed_mime_types=null`; `patient-avatars` absent | SPEC-12 is not hosted-verified. |
| H-10-07 | `storage.objects` policies | 0 | Direct-client deny policy from SPEC-12 is absent in production. |
| H-10-08 | Synthetic audit rows | Exactly two pre-existing rows for the disclosed synthetic actor: `PRACTITIONER_ROLE_ASSIGNED` and `PRACTITIONER_ROLE_UPDATED`, both 2026-11-23 | Unchanged from order 8 §11; owner decided to leave them in place and document only. Order 10 added no row. |
| H-10-09 | Security advisories | 7 lint types: `rls_enabled_no_policy` INFO 21; `function_search_path_mutable` WARN 4; `pg_graphql_anon_table_exposed` WARN 25; `pg_graphql_authenticated_table_exposed` WARN 25; anon/authenticated definer-executable WARN 3 each; `auth_leaked_password_protection` WARN 1 | Confirms unresolved hosted policy/grant/function exposure. |
| H-10-10 | Performance advisories | 5 lint types: `unindexed_foreign_keys` INFO 19; `auth_rls_initplan` WARN 9; `unused_index` INFO 35; `multiple_permissive_policies` WARN 6; `duplicate_index` WARN 2 | Confirms legacy policy/index drift. |
| H-10-11 | Health advisories | 0 | No health finding claimed as security acceptance. |

No effective hosted anon/authenticated/service-role data-plane test and no hosted Storage upload/list/update/delete/signed-URL test was run. Those require an approved change set, synthetic identities, and authorization under controlled guide §§8–9.

---

## 5. Branch protection — exact owner action

Public GitHub evidence shows one active repository ruleset:

- ID: `11701421`
- Name: `Test`
- Target: `branch`, enforcement: `active`
- Conditions: `ref_name.include=[]`, `exclude=[]` (currently all branches)
- Existing rules: `deletion`, `non_fast_forward`, `pull_request`
- Existing PR parameters: 1 approving review, conversation resolution required, stale reviews not dismissed on push, no code-owner review, no last-push approval, all merge methods allowed
- **Missing rule:** `required_status_checks` for `Backend verification`

The owner elected to apply the change. In GitHub UI: **Settings → Rules → Rulesets → Test → Edit → Rules → Add rule → Require status checks to pass** → select **`Backend verification`** → optionally enable **Require branches to be up to date before merging** → save. Keep the existing deletion, force-push and PR rules. If the owner wants `main`-only scope, set the ruleset include pattern to `refs/heads/main`; do not change scope casually because the current ruleset covers all branches.

API alternative (owner-authenticated; current GitHub ruleset schema uses `PUT`, and the full rules array must be supplied):

```json
{
  "name": "Test",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": [], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": false,
        "required_reviewers": [],
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "require_extra_approval_for_unattributed_changes": true,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "required_status_checks": [
          { "context": "Backend verification" }
        ],
        "strict_required_status_checks_policy": true
      }
    }
  ]
}
```

Verification after the owner applies it: `GET /repos/jiko-medcore/MedAeterna/rules/branches/main` should include a `required_status_checks` rule with context `Backend verification`, and a test PR should be blocked until that check succeeds. Until this is observed, criterion 17 remains **NOT MET**.

---

## 6. Acceptance criteria review (17/17)

Statuses: **LOCAL** = evidenced locally only; **PARTIAL** = some evidence exists but a required part is open; **NOT MET** = acceptance evidence is absent or contradicted; **OWNER ACTION** = requires a repository/configuration change outside this agent’s authority.

| # | Acceptance criterion | Status | Evidence / residual |
|---:|---|---|---|
| 1 | No unresolved critical authorization or privilege-escalation finding remains | **NOT MET** | Order 8 F-3 anon data-plane, F-8 audit compensation, F-9 raw-SQL utility, invite/departments ordering, unmounted hardened routers, worker identity, and hosted drift remain open. |
| 2 | Every sensitive route has authentication and resource/action authorization | **LOCAL** | Order 9 maps and tests all 45 mounted sensitive routes; hosted effective behavior not verified. |
| 3 | One canonical patient-access dependency contract used by all callers | **LOCAL** | WP-01/order 9 local source and tests; no hosted runtime proof. |
| 4 | Organization context validated from resource or explicit operation context | **LOCAL** | Route/service-boundary tests in orders 8–9; hosted cross-org tests not run. |
| 5 | Role resolution deterministic, scoped, self-escalation resistant | **LOCAL** | SPEC-02/practitioner-role gating tests; production role policy/grants still drifted. |
| 6 | Patient-access grant and consent lifecycle implemented, attributable and enforced | **NOT MET** | Full SPEC-05 purpose/recipient/resource/expiry/revocation provenance and SPEC-06 canonical grant lifecycle remain open. |
| 7 | Patient, practitioner, org-admin and system-admin boundaries tested | **LOCAL** | Positive/negative tests exist locally; distinct hosted identities were not exercised. |
| 8 | All application relations inventoried and reconciled with migrations and hosted schema | **NOT MET** | Local reviewed candidate has 34 public tables; hosted has 26 and lacks the 8 clinical/access tables added locally. |
| 9 | RLS policies and grants reviewed table by table and verified under real role contexts | **NOT MET** | Local catalog/advisors pass; hosted has 0/26 forced RLS, legacy broad grants and 11 legacy policies. |
| 10 | SECURITY DEFINER functions have reviewed ownership, search_path, object qualification and EXECUTE rights | **LOCAL / NOT MET hosted** | Local functions hardened; hosted still has client-executable definer functions and mutable search paths. |
| 11 | Service-role call sites documented and guarded by application authorization | **PARTIAL** | Order 8 inventory exists, but F-3, F-8, F-9, worker identity and unmounted routers remain open. |
| 12 | Storage buckets explicitly classified and object-level access tested | **NOT MET** | Local 22/22 effective Storage checks pass; hosted bucket is missing, limits absent, and no deny policy exists. |
| 13 | Sensitive operations produce protected, attributable audit records | **PARTIAL / LOCAL** | Local audit tables forced with service-only grants; hosted audit/event tables retain broad client CRUD under legacy grants. Two synthetic rows remain by owner decision. |
| 14 | Positive and negative security regression tests pass in CI | **PARTIAL / NOT MET as a gate** | Full suite passed locally and `Backend verification` passed in CI on PR #42 head `59d69ce…` and merge commit `ac28aa8…`; not met as a gate because the required status check is not enforced and no review approval is recorded. |
| 15 | Staging verification complete; production configuration compared before release | **NOT MET** | No hosted staging branch exists. Production drift is documented but release comparison/verification gates are incomplete. |
| 16 | Every SEC finding has a documented disposition and supporting evidence | **PARTIAL** | Order 11 reconciled SEC-01–SEC-24 against PR #42 and fresh hosted evidence: 24 KEEP OPEN, 0 CLOSE; hosted evidence remains insufficient for application, database and Storage closures. |
| 17 | Branch protection requires backend verification check for merges to main | **OWNER ACTION / NOT MET** | Ruleset `Test` lacks `required_status_checks`; exact change supplied in §5. Protected-branch API unreadable without credentials. |

**Final acceptance decision: NOT ACCEPTED.** Zero SEC findings are closed by this record. Phase 0 must not be treated as accepted until criteria 1, 6, 8, 9, 10, 12, 14, 15 and 17 are satisfied and all critical/high findings have complete evidence and owner acceptance. For criterion 14, CI execution is now evidenced on PR #42; only required-check enforcement, human review and gate acceptance remain.

---

## 7. Residual gap register carried forward

| Gap | Source | Disposition |
|---|---|---|
| F-3 anon data-plane operations | Order 8 §4.3/§7 | Still open; caller-scoped migration or justified service-role gating remains SPEC-10 work. |
| F-8 post-write audit compensation | Order 8 §7 / order 9 §7 | Still open; no transactional audit guarantee claimed. |
| F-9 raw-SQL bootstrap utility | Order 8 §7 | Still open; exclude from release tooling or replace with reviewed migrations. |
| Consent/grant full lifecycle | Order 9 §7 | Still open; no policy guessed. |
| Invite/departments ordering and unmounted hardened routers | Order 8 §7 | Still open. |
| Worker identity/purpose evidence | Order 8 §5/§7 | Still open. |
| Hosted staging | H-10-02 | None exists; formal decision needed whether to create one. |
| Hosted RLS/grants/functions/Storage drift | H-10-03–H-10-10 | Blocking; reviewed migrations/config are not deployed. |
| Backup/PITR/restore/recovery owners and §8.5 authorization | PH0-WP-10 gate record | Incomplete; controlled guide STOP remains. |
| Required status check on `main` | §5 | Owner to apply; not yet verified. |
| CI as enforced merge gate | §2 / order 11 §2 | CI passed on PR #42 head and merge commit; required `Backend verification` status check still missing and no review approval evidenced. |

---

## 8. Controlled guide §11.3 report — historical order 10 snapshot

The snapshot below reflects the pre-merge order 10 review. Post-merge CI, SEC and issue reconciliations are in the order 11 record §9.

```text
Phase: Recommended execution order 10 / PH0-WP-10 final acceptance evidence
Git branch: security/phase-0-db-storage-release
Commit SHA: e473df31a8881f67236a277c91ba01d38cbe2af8 (original evidence base; later merged through PR #42)
Supabase CLI version: 3.2.0
Local stack status: reachable at 127.0.0.1:58562; 6/6 migrations; 36/36 pgTAP; 0 WARN advisories
Remote project inspected: yes, read-only MCP
Remote project reference: iyueixtpmzznyffshqon
Files changed: this evidence record and the order-10 note in the v2.0 baseline
Migration IDs: local 20261118135846, 20261118150000, 20261118160000, 20261120095915, 20261120110644, 20261122062921; hosted only 20261118135846
Storage config changes: NONE
Policies changed: NONE
Tests run: compileall; full backend pytest; supabase migration list; supabase test db; supabase db advisors; workflow YAML parse
Tests passed/failed/skipped: 1438 passed / 0 failed / 1 skipped; database 36/36; local advisors clean
Advisors: hosted security 7 lint types (6 WARN categories, 1 INFO), performance 5 lint types (3 WARN, 2 INFO), health 0
Drift found: yes — migrations, RLS force, policies, grants, functions, indexes, Storage buckets and Storage policies
Risks (at original review): local evidence is not hosted proof; release branch unpushed; required CI check not enforced; production change remains unauthorized
Approval required: branch protection owner action; backup/recovery gate; exact §8.5 deployment authorization; human review and SEC closure acceptance
Production mutations performed: NONE
Next permitted action (post-merge): PR #42 is merged and CI passed; owner applies the §5 ruleset change, records review approval, completes order 11 issue/SEC decisions, and separately completes controlled guide gates before any authorized deployment
```

---

## 9. Cross-references

- [Phase 0 baseline — order 10 and acceptance criteria](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [Backend CI workflow](../../.github/workflows/backend-ci.yml)
- [Order 9 route authorization record](PH0-WP-02-route-authorization-order-9-record.md)
- [Order 8 audit and privileged-path review](PH0-WP-08-WP-09-privileged-path-review-record.md)
- [SPEC-11/SPEC-12 hosted read-only preflight](SPEC-11-SPEC-12-hosted-read-only-preflight-record.md)
- [Backup, recovery and release gate](PH0-WP-10-backup-recovery-gate-record.md)
- [Order 11 SEC and GitHub issue reconciliation](PH0-WP-10-order-11-sec-and-issue-reconciliation-record.md)
- [Controlled Supabase database and Storage release guide](../../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)

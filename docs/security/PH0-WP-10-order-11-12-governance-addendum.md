# PH0-WP-10 Orders 11–12 — Governance Evidence Addendum

**Record date:** 25 November 2026  
**Repository:** `jiko-medcore/MedAeterna`  
**Baseline main commit:** `9aa5ba6a4965e19229e9a8c922a349e76be4d1d1` (merge of PR #43)  
**Related issue:** #38 — PH0-WP-04 Backend CI and main-branch protection  
**Status:** Governance evidence update only. Phase 0 remains **NOT ACCEPTED**; production release remains **STOP**.

> This addendum records new governance facts and GitHub evidence. It does not close any SEC finding, authorize a production change, or replace the full Order 11 / Order 12 assessment.

## 1. Repository documentation reconciliation

The documentation status summary uploaded on 24 November identifies the canonical records as:

- `docs/security/PH0-WP-10-order-11-sec-and-issue-reconciliation-record.md`
- `docs/security/PH0-WP-10-order-12-formal-phase-0-acceptance-review-record.md`

A read attempt against the repository's current `main` at `9aa5ba6a4965e19229e9a8c922a349e76be4d1d1` returned 404 for both paths. The summary itself also is not present at its expected `docs/security/PHASE-0-SECURITY-DOCUMENTATION-STATUS-SUMMARY.md` path on that commit. Therefore this addendum does not reconstruct or overwrite the missing source records. The canonical Order 11 and Order 12 files must be restored/added to the repository and this addendum incorporated into them.

## 2. Order 11 — SEC and issue reconciliation

### 2.1 PR #42 review correction

The only submitted review found for PR #42 is:

- Review ID: `6045194869`
- GitHub reviewer login: `SmogJ`
- Submitted: `2026-11-24T18:39:18Z`
- Reviewed head: `59d69ce0e4e467ae0a7668df119db282ee1b7c52`
- Review state: `APPROVED`
- Review text: “The code is good enough for the MVP and frontend connection, better will need to done for a proper product launch.”

PR #42 had already merged at `2026-11-24T08:17:04Z` (merge commit `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0`). The repository owner has clarified that `SmogJ` and `jiko-medcore` are the same person. Record the review as **retrospective owner approval / post-merge review**, not independent review and not pre-merge approval. There was no second human reviewer.

**Disposition:** Do not backdate the review or claim independent review. This retrospective review does not satisfy a governance requirement for an independent pre-merge reviewer.

### 2.2 Copilot review policy

GitHub Copilot code review may be requested as a supplementary automated review. It can identify defects and provide useful comments, but it is not an independent human reviewer and must not be described as one.

GitHub's current documentation says Copilot reviews are comments by default and do not count toward required approvals unless Copilot approvals are explicitly enabled in repository/organization/enterprise settings. Even where enabled, a Copilot approval is an automated control, not human accountability. The project should retain an accountable human owner for review and merge decisions and should not use Copilot to disguise a single-maintainer review limitation.

### 2.3 Finding and issue dispositions

No new environment-specific evidence in this governance update justifies closing a security finding. Preserve Order 11's prior disposition:

- SEC-01–SEC-24: **KEEP OPEN**.
- SEC findings closed: **0**.
- SEC findings risk-accepted: **0**.
- GitHub issues remain open until their individual acceptance criteria are met.

## 3. Order 12 — formal acceptance review correction

### 3.1 Governance evidence received

The repository owner reports the active ruleset configuration as follows:

| Setting | Owner-reported value |
|---|---|
| Bypass list | Empty |
| Target | Default branch (`main`) |
| Required status check | `Backend verification` |
| Administrator enforcement | Administrators are exempt from the requirements |

The connected GitHub repository tools used for this review did not expose ruleset-detail read access. These values are therefore recorded as **owner-confirmed**, not independently API-verified. The administrator exemption is a material exception: do not describe the ruleset as unbypassable or as enforcing the same requirements against administrators.

### 3.2 Negative merge demonstration — verified PR #44

The exact test artifact is [PR #44 — “test: deliberately fail Backend verification”](https://github.com/jiko-medcore/MedAeterna/pull/44).

Read-only GitHub evidence for PR #44:

- PR author: `jiko-medcore`.
- Head branch: `test/backend-verification-negative`.
- Test commit: `b214c8d4b7fe100a478ee6c89775fbb1a0395521`.
- Target: `main`, at base commit `9aa5ba6a4965e19229e9a8c922a349e76be4d1d1`.
- `Backend verification` check: **COMPLETED / FAILURE**.
- Actions job: [Backend verification — run 45556023177, job 139008151294](https://github.com/jiko-medcore/MedAeterna/actions/runs/45556023177/job/139008151294).
- GitHub pull-request state: **CLOSED**, `merged: false`, `merged_at: null`.
- GitHub's reported `mergeable_state`: **blocked**.

The failing required check and GitHub's `blocked` mergeability state, together with the PR's closed-but-unmerged state, provide repository evidence that the deliberately failing change did not merge into `main`. The PR's `merge_commit_sha` field is populated by GitHub even though `merged` is false; do not interpret that field as proof of a completed merge.

**Disposition:** Negative merge-gate demonstration is now **VERIFIED from GitHub PR/check evidence**, not merely owner-reported. Keep PR #44 closed and unmerged; do not merge it. This verifies the required-check gate for this test case, but does not remove the administrator-exemption caveat or prove all other branch/ruleset controls.

### 3.3 New CI evidence since PR #42

PR #43 — “Private patient avatars with authorized signed URLs and stable object paths” — merged to `main`:

- PR head: `0264e719d2d54f1aca7d9e88d58b4d29b4c94e06`
- Merge commit: `9aa5ba6a4965e19229e9a8c922a349e76be4d1d1`
- GitHub Actions run: `45549093195`
- Job: `Backend verification`
- Conclusion: **SUCCESS**
- The dependency-install, compile, and full pytest steps all completed successfully.

The PR's own record reports 52 focused tests passed and 1,468 passed / 1 skipped / 18 warnings for the full backend suite, plus compileall and `git diff --check`. These are local/CI results only. PR #43 explicitly did not perform a hosted migration, Storage config push, production deployment, or production verification.



### 3.3.1 PR #43 review independence correction

A follow-up inspection of PR #43 found one submitted review:

- Review ID: `PRR_kwDOQ1VHdc8AAAABaLsdng`
- Reviewer: `SmogJ`
- Submitted: `2026-11-25T04:56:06Z`
- Review state: `APPROVED`
- PR #43 merge time: `2026-11-25T04:57:41Z`

The PR author is `jiko-medcore`. The repository owner has clarified that `SmogJ` and `jiko-medcore` are the same person. This was technically submitted before merge, but it was **not an independent human review**. Record it as a same-owner pre-merge self-review across two GitHub identities, not as independent approval. The same-person governance limitation therefore also applies to PR #43.

### 3.4 Acceptance effect

This update improves the governance evidence but does not change the formal acceptance decision:

- A retrospective approval by the same human is not an independent pre-merge review.
- Ruleset settings are owner-confirmed, not independently read through the GitHub API in this review.
- PR #44 supplies independently inspectable GitHub evidence of a failed required check, blocked mergeability, and a closed-but-unmerged test PR.
- Hosted staging, production preflight, production deployment, and Gate G verification remain outstanding.

**Order 12 exit condition: NOT MET. Phase 0: NOT ACCEPTED. Controlled release: STOP.**

## 4. Issue #38 update

Issue #38 received a corresponding evidence comment on 25 November 2026. The issue remains **OPEN**. The comment records:

- the retrospective PR #42 approval and same-person clarification;
- the owner-confirmed ruleset settings and administrator exemption;
- verified negative merge-gate evidence from PR #44: the required `Backend verification` check failed, GitHub reported the PR as blocked, and the PR was closed without merging;
- successful `Backend verification` CI for PR #43 and its merge commit;
- continued non-closure of SEC findings and Phase 0.

## 5. Required follow-up

1. Restore the canonical Order 11 and Order 12 files to `docs/security/` and incorporate this addendum into their relevant sections.
2. Preserve PR #44 and its failed `Backend verification` check as the negative merge-gate evidence; do not merge the test PR.
3. Preserve the distinction between automated Copilot review, retrospective owner approval, independent human review, and pre-merge approval.
4. Keep all SEC findings and issues open until their own evidence-backed closure criteria are met.
5. Continue to treat §8.5 production authorization and Gate G as separate, outstanding controls.

---

**Source links**

- [PR #42](https://github.com/jiko-medcore/MedAeterna/pull/42)
- [PR #43](https://github.com/jiko-medcore/MedAeterna/pull/43)
- [Issue #38](https://github.com/jiko-medcore/MedAeterna/issues/38)
- [PR #43 merge commit](https://github.com/jiko-medcore/MedAeterna/commit/9aa5ba6a4965e19229e9a8c922a349e76be4d1d1)
- [PR #44 negative merge test](https://github.com/jiko-medcore/MedAeterna/pull/44)
- [PR #44 Backend verification job](https://github.com/jiko-medcore/MedAeterna/actions/runs/45556023177/job/139008151294)
- [GitHub documentation — Copilot code review](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-code-review)

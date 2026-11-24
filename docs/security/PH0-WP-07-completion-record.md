# PH0-WP-07 Completion Record — Complete Local Storage Classification and Object-Level Verification

**Work package:** PH0-WP-07 / Storage security and clinical-document readiness

**Plan order:** order 7 / PH0-WP-07 in `PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md` and `backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md`

**Branch:** `security/phase-0-db-storage-release`

**Execution base:** `eaa4f0d` (local HEAD before this work)

**Implementation commit:** `65f5156` (local, committed, not pushed)

**Review date:** 22 November 2026

**Status:** **Complete local Storage release candidate — NOT CLOSED, NOT ACCEPTED**

> This record documents local Storage classification and effective object-level access only. It does not claim staging or production deployment, hosted bucket/policy verification, SEC closure, or Phase 0 acceptance. No `--remote` CLI command, hosted mutation, production verification, or push was performed. The three read-only baseline/plan/release-guide files were not modified.

---

## 1. Scope completed

The local Storage model is now verified at three layers: declared inventory/config, applied Postgres catalog/pgTAP, and effective local Storage HTTP API behavior. All checks used synthetic PNG bytes and synthetic UUID identities; no patient data was used.

| Surface | Local outcome |
|---|---|
| `backend/app/core/storage_access_inventory.py` | Existing approved SPEC-12 model retained: three installed image buckets, explicit public flags, 2 MiB limit, `image/jpeg`/`image/png`/`image/webp`, owner-token path rule, and service-role execution mode. |
| `backend/supabase/config.toml` | Same three buckets declared locally with `public = true`, `2MiB` limits and the reviewed MIME allowlist. Global Storage limit remains `50MiB`; per-bucket limits are stricter. |
| `backend/supabase/migrations/20261120110644_spec12_storage_bucket_policy.sql` | Existing committed migration retained. Installs/reconciles the three buckets and the single explicit `FOR ALL ... USING (false) WITH CHECK (false)` policy for `anon` and `authenticated`. |
| `backend/supabase/tests/database/spec12_storage_bucket_policy.test.sql` | Existing `plan(8)` catalog suite retained and re-run after a clean reset. |
| `backend/scripts/verify_local_storage_effective_access.py` | **New** local-only effective Storage API verifier. Refuses non-loopback API URLs, uses a status snapshot from `supabase status -o json`, and exercises anon/authenticated/service-role behavior across upload, read, list, update, sign, upsert, MIME/size rejection, delete and cleanup. |
| `backend/tests/core/test_verify_local_storage_effective_access.py` | **New** unit tests for the verifier’s embedded-403 denial detection, listing parser and loopback-only status guard. |
| `patient-documents` | Still unimplemented and fail-closed. No private clinical bucket, object naming rule, signed-URL client flow or migration was invented. |
| `practitioner-photos` | Installed as a public image bucket per the approved SPEC-12 model; no upload route was added because none is approved. |

### Target distinction

The user-provided MCP URL `http://127.0.0.1:54321/mcp` belongs to a different, essentially empty local stack created from the repository root. It reported zero buckets and no `supabase_migrations` table. The project stack used by `backend/` is `http://127.0.0.1:58561` (API) and `127.0.0.1:58562` (DB), and contains the three SPEC-12 buckets and six applied migrations. All order 7 evidence below uses the backend stack CLI/MCP endpoint. The untracked root-level `supabase/` scaffolding was left untouched and was not committed.

---

## 2. Authorization and fail-closed decisions applied

| Decision | Applied behavior |
|---|---|
| Public/private classification | Only the three approved image buckets exist locally: `organization-logos`, `patient-avatars`, `practitioner-photos`. All are public for retrieval. No clinical bucket is public. |
| Patient avatars | Explicitly public under the already-approved SPEC-12 model. This record re-verifies that decision; it does not expand it to clinical documents. |
| Direct client object access | One policy, `Deny direct client object access`, applies `FOR ALL` to `anon` and `authenticated` on `storage.objects` with `USING (false)` and `WITH CHECK (false)`. This denies client INSERT/SELECT/UPDATE/DELETE at the RLS layer. |
| Public retrieval | Reading through `/storage/v1/object/public/...` succeeds because `storage.buckets.public = true`, not because of a client RLS grant. An authenticated bearer token does not add object access. |
| Trusted writes | Upload, upsert, list, signed-URL issuance and delete succeed with the local `service_role` key. Application routes must apply their own authorization before using that trusted path. |
| Object paths | The inventory requires the first non-empty path component to equal the owner/user/organization token and the extension to be derived from validated MIME type. Cross-tenant path rejection is covered by existing inventory tests. |
| Upload content | Bucket MIME/size limits and backend magic-byte validation are both retained. Unsupported MIME and oversized uploads were rejected in the effective API run. |
| Replacement/deletion | Non-upsert duplicate upload is rejected; service-role upsert replaces at the same deterministic path; service-role delete removes the object and leaves no object under the tested owner prefix. |
| Signed URLs | Client signed-URL issuance is denied. Service-role issuance succeeds for the public test bucket; no private-bucket or client-facing signed-URL feature was approved or implemented. |
| Role behavior | Anon and authenticated (owner/non-owner-equivalent) Storage writes are denied. Org-admin behavior remains an application-route responsibility, covered by existing branding service/route tests; no direct Storage admin role was invented. |
| Platform ACL residual | Broad platform-managed grants on `storage.objects` and `storage.buckets` remain for `anon`, `authenticated` and `service_role`; they are granted by `supabase_storage_admin` and cannot be revoked as `postgres`. Effective denial depends on the explicit RLS policy, not on those ACLs. |

No canonical purpose codes, recipient-kind storage, resource-scope storage, treatment/care-team source, legacy-row promotion, migration/cutover, private clinical object naming, or clinical signed-URL behavior was guessed. Those items remain fail-closed pending human decision.

---

## 3. Local catalog evidence

All catalog results below came from the backend local stack only, after the clean reset and before/after the effective API checks.

| Assertion | Local result |
|---|---|
| Supabase CLI | `3.2.0` |
| Local stack | API `http://127.0.0.1:58561`; DB `postgresql://postgres:postgres@127.0.0.1:58562/postgres`; CLI said `Target: local stack ... pass --remote for MedAeterna` |
| Installed buckets | **3** |
| `organization-logos` | `public=true`, `file_size_limit=2097152`, MIME `image/jpeg`, `image/png`, `image/webp` |
| `patient-avatars` | `public=true`, `file_size_limit=2097152`, MIME `image/jpeg`, `image/png`, `image/webp` |
| `practitioner-photos` | `public=true`, `file_size_limit=2097152`, MIME `image/jpeg`, `image/png`, `image/webp` |
| `patient-documents` | Absent |
| Storage policies | **1**: `storage.objects` / `Deny direct client object access` / `ALL` / `{anon,authenticated}` / `qual=false` / `with_check=false` |
| Other storage policies | **0** |
| RLS on `storage.objects` and `storage.buckets` | Enabled, asserted by pgTAP |
| Client storage grants | `anon` and `authenticated` each have platform-managed `SELECT`, `INSERT`, `UPDATE`, `DELETE` on `storage.objects` and `storage.buckets`, granted by `supabase_storage_admin`; RLS denies object access. |
| Service-role storage grants | `service_role` has platform-managed `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `REFERENCES`, `TRIGGER`, `TRUNCATE` on both tables and bypasses RLS. |
| Migration history | `20261118135846`, `20261118150000`, `20261118160000`, `20261120095915`, `20261120110644`, `20261122062921` |
| Post-reset catalog counts | 3 buckets, 1 storage policy, 6 migrations |

The catalog snapshot was read via the backend MCP endpoint and summarized above. No hosted project was contacted.

---

## 4. Verification evidence

All Python commands were run from `backend/` using `.venv/Scripts/python.exe`. Supabase CLI commands were run from `backend/` with `/home/linuxbrew/.linuxbrew/bin` on `PATH`, always against the local stack default and without `--remote`.

| Evidence ID | Check | Command | Result |
|---|---|---|---|
| E-WP07-01 | Current docs/changelog review | `curl -sS https://supabase.com/changelog.md` and Supabase Storage access-control docs | No Storage/RLS breaking change affecting this local implementation. Relevant notes: hosted TLS cipher deprecation (2026-10-12) and the 2025 restriction on SQL changes to `auth`/`storage`/`realtime` schemas. No policy guessing was based on these notes. |
| E-WP07-02 | CLI discovery | `supabase --version`, `supabase storage --help`, `supabase test db --help`, `supabase db advisors --help` | CLI `3.2.0`; all relevant commands are local by default with `--remote` only for hosted targets. |
| E-WP07-03 | MCP discovery and target check | `initialize` + `tools/list` on the user-provided endpoint, then `execute_sql` on both local endpoints | `execute_sql` exposed. Endpoint `54321` returned zero buckets; backend endpoint `58561` returned the three reviewed buckets. Backend endpoint used for evidence. |
| E-WP07-04 | Clean local reset | `supabase db reset --yes --no-seed` | Pass. Post-reset query reported 3 buckets, 1 Storage policy and 6 applied migrations. |
| E-WP07-05 | Local pgTAP suite | `supabase test db` | **PASS — 3 files, 36 tests**. `spec02` 5 ok, `spec11` 2 ok, `spec12` 8 ok. |
| E-WP07-06 | Focused Storage regression | `.venv/Scripts/python.exe -m pytest -q tests/core/test_storage_access_inventory.py tests/core/test_storage_upload_validation.py tests/core/test_verify_local_storage_effective_access.py tests/patients/test_avatar_upload.py tests/organizations/branding/test_storage.py` | **52 passed** |
| E-WP07-07 | Full backend regression | `.venv/Scripts/python.exe -m pytest -q` | **1,368 passed, 1 skipped, 18 warnings** |
| E-WP07-08 | Local advisories | `supabase db advisors --type all --level warn` | **No issues found**, 0 findings. INFO-level notices remain documented but non-blocking. |
| E-WP07-09 | Effective Storage API checks | `supabase status -o json > /tmp/opencode/storage_status_reset.json` then `.venv/Scripts/python.exe scripts/verify_local_storage_effective_access.py --status-json "$(wslpath -w /tmp/opencode/storage_status_reset.json)" --output-json "$(wslpath -w /tmp/opencode/order7_storage_results.json)"` | **22/22 checks passed** against API `http://127.0.0.1:58561`. Details below. |
| E-WP07-10 | Read-only catalog snapshot | MCP `execute_sql` against `http://127.0.0.1:58561/mcp` | Pass; summarized in section 3. |
| E-WP07-11 | Patch sanity | `git diff --check` | Clean |

### 4.1 Effective Storage object-level checks

All paths used a synthetic owner UUID `00000000-0000-4000-8000-000000000007`, a different synthetic authenticated UUID `00000000-0000-4000-8000-000000000017`, and a synthetic cross-tenant prefix `00000000-0000-4000-8000-000000000008`. Storage sometimes returns HTTP 400 with an embedded `statusCode: 403` for RLS denials; the verifier treats that as denial and records the raw status/body.

| Check | Result |
|---|---|
| Anonymous upload denied | **PASS** — HTTP 400, embedded 403, RLS violation |
| Authenticated upload denied | **PASS** — HTTP 400, embedded 403, RLS violation |
| Service-role upload succeeds | **PASS** — HTTP 200 |
| Public bucket read returns exact bytes | **PASS** — HTTP 200, byte-for-byte match |
| Public bucket object read succeeds with authenticated key | **PASS** — HTTP 200; this confirms public-bucket retrieval, not a client object grant |
| Anonymous object listing discloses no names | **PASS** — HTTP 200, zero entries |
| Authenticated object listing discloses no names | **PASS** — HTTP 200, zero entries |
| Service-role listing succeeds for trusted operations | **PASS** — HTTP 200, target listed under owner prefix |
| Service-role cross-tenant prefix listing is empty | **PASS** — HTTP 200, zero entries |
| Authenticated object update denied | **PASS** — HTTP 400, embedded 403 |
| Authenticated signed URL issuance denied | **PASS** — HTTP 400, embedded 404/no such key under RLS |
| Service-role signed URL issuance succeeds | **PASS** — HTTP 200, token present |
| Non-upsert duplicate upload rejected | **PASS** — HTTP 400/409 duplicate |
| Service-role upsert replaces object deterministically | **PASS** — HTTP 200 |
| Public read returns replacement bytes | **PASS** — HTTP 200, byte-for-byte match |
| Unsupported MIME rejected by bucket configuration | **PASS** — HTTP 400 |
| Oversized upload rejected by bucket limit | **PASS** — HTTP 400 |
| Planned private clinical bucket is not installed | **PASS** — HTTP 400/404 |
| Authenticated object delete denied | **PASS** — HTTP 400, embedded 403 |
| Service-role delete succeeds | **PASS** — HTTP 200 |
| Deleted public object is unavailable | **PASS** — HTTP 400/404 |
| Replacement and delete leave no orphan object under owner prefix | **PASS** — HTTP 200, zero entries |

These checks are effective local evidence for the tested paths and identities only. They do not establish hosted behavior or a complete production role matrix.

---

## 5. Evidence limits and residual risk

This work package does not close a SEC finding and does not constitute Phase 0 acceptance.

1. **No hosted verification.** No staging or production bucket, policy, object, advisory or role-based Storage check was performed.
2. **Different local stack at `54321`.** The user-provided MCP endpoint targets a separate root-level stack with no reviewed buckets. Evidence here is tied to the `backend/` stack (`58561`/`58562`). The root `supabase/` scaffolding remains untracked and untouched.
3. **Public image buckets.** Patient avatars, organization logos and practitioner photos are intentionally public under the approved SPEC-12 model. Public URLs remain public and unauthenticated.
4. **Clinical documents fail closed.** `patient-documents` is not installed. Private access rules, object naming, trusted grant/revoke provenance and clinical signed-URL behavior are still human decisions.
5. **Signed URLs.** Only service-role issuance for a public test bucket was verified. No client-facing signed-URL flow or private-bucket signing policy was approved.
6. **Platform ACL residual.** Broad `supabase_storage_admin` grants remain on Storage metadata tables. Effective client denial depends on the explicit RLS policy; the ACLs themselves were not altered.
7. **Partial role matrix.** Direct Storage API checks cover anon, authenticated and service-role identities. Distinct owner/non-owner/org-admin Storage identities were not modeled because client writes are denied regardless of role. Application-route authorization remains covered by existing Python tests, not by direct Storage policy grants.
8. **Practitioner photo upload.** No approved upload route exists for `practitioner-photos`; only the bucket catalog and ACL boundary were verified.
9. **No patient data.** Evidence uses synthetic UUIDs, synthetic object names and generated PNG bytes only.
10. **SEC/Phase 0 status.** No SEC finding is closed here, and no production acceptance claim is made.

---

## 6. Acceptance handoff

Before any production release:

- obtain human approval for the private clinical bucket model, object naming rules and any signed-URL flow;
- keep `patient-documents` unimplemented until that approval exists;
- review hosted Storage bucket/policy drift against the approved local migration;
- repeat the catalog, pgTAP, advisory and effective Storage checks in staging with explicit approval;
- obtain human approval before any production deployment;
- repeat the same evidence in production with distinct role identities;
- link the resulting evidence to both plans’ traceability registers and obtain reviewer acceptance.

**Current decision: NOT ACCEPTED.**

---

## 7. Cross-references

- [Phase 0 plan — PH0-WP-07 / order 7](PHASE-0-BACKEND-SECURITY-BASELINE-AND-REMEDIATION-PLAN-v2.0.md)
- [Backend plan — PH0-WP-07 / order 7](../backend/MedAeterna_Phase_0_Backend_Security_Baseline_and_Remediation_Plan_v2.0.md)
- [Controlled Supabase database and storage release guide](../backend/MedAeterna_Controlled_Supabase_Database_and_Storage_Release_Guide_v1.0.md)
- [SPEC-12 — storage bucket and object access](SPEC-12-storage-bucket-and-object-access.md)
- [PH0-WP-03 completion record](PH0-WP-03-completion-record.md)

---

## 8. Addendum — private patient-avatar storage cutover (local implementation only)

**Branch:** `security/private-patient-avatar-storage`

**Starting SHA:** `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0` (`origin/main`, PR #42 merge)

**Forward-only migration:** `backend/supabase/migrations/20261124192523_private_patient_avatar_storage.sql`

This addendum records a later owner-approved classification change and supersedes the all-public statements in sections 1–7. `organization-logos` remains public and unchanged. `patient-avatars` and `practitioner-photos` are now private in the reviewed inventory, local `config.toml`, the new migration, and the catalog test expectations. The 2 MiB limit and `image/jpeg`, `image/png`, `image/webp` allowlist are unchanged for all three buckets. No existing migration was edited, no broad authenticated Storage read/write policy was added, and the single deny-all client policy remains the only storage policy.

The database change adds nullable `patients.profile_image_path`, preserves `patients.profile_image_url`, backfills only exact owner-scoped legacy public-avatar paths, and documents that signed URLs must never be persisted. The upload route derives the object path from authenticated patient identity, validates MIME/signature/size, overwrites deterministically, persists only the stable path, returns a 60-second signed URL, and attempts compensating object removal after post-upload signing or database failure. Retrieval for `/patients/me`, `/patients/profile/me`, `/api/v1/user/summary`, and `/patients/mine` signs only avatars for patients already returned by the existing authorization checks. Outward field names remain `profile_image_url` and `avatarUrl`; `profile_image_path` is internal. Signing failures fail closed. Legacy organization-logo behavior is unchanged.

This addendum does **not** apply the migration to a hosted database, push Storage config, mutate production objects, close a SEC finding or issue, or accept Phase 0. Hosted drift and controlled-release gates remain open.

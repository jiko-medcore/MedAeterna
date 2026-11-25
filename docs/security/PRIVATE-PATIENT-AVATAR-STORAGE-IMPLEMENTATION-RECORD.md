# Private Patient Avatar Storage — Implementation Record

**Branch:** `security/private-patient-avatar-storage`

**Starting SHA:** `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0` (`origin/main`, PR #42 merge)

**Supabase CLI used to generate the migration:** `3.2.0`

**Status:** **Local implementation complete and committed — NOT DEPLOYED, NOT ACCEPTED**

> This record documents local source, configuration, migration, application, and test changes only. It does not claim that the migration was applied to a hosted database, that Storage config was pushed, that SEC findings or issues were closed, or that Phase 0 was accepted. Hosted drift and controlled-release gates remain open.

---

## 1. Baseline and worktree handling

- Confirmed repository root: `/mnt/c/Users/jeffrey/Documents/MedCore`.
- Confirmed `origin/main` at `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0`.
- SSH fetch failed because `ssh_askpass` and host-key verification are unavailable in this environment. `main` was verified and fetched through public HTTPS instead.
- Confirmed a clean worktree before editing.
- Preserved pre-existing user work from the prior branch in `stash@{0}`:
  - `backend/supabase/snippets/db and storage checks.sql`
  - `docs/security/PHASE-0-SECURITY-DOCUMENTATION-STATUS-SUMMARY.md`
- Created `security/private-patient-avatar-storage` from latest `origin/main`.

---

## 2. Approved classification implemented

| Bucket | Classification | Public read | Size limit | MIME allowlist | Upload status |
|---|---|---:|---:|---|---|
| `organization-logos` | `public_owned` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Existing scoped admin routes unchanged |
| `patient-avatars` | `private_owned` | No | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Patient self-service trusted upload |
| `practitioner-photos` | `private_owned` | No | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | Upload remains disabled |

No broad authenticated read or write policy was added. The single `Deny direct client object access` policy remains the only storage policy.

---

## 3. Files changed

### Storage classification and configuration

| File | Change |
|---|---|
| `backend/app/core/storage_access_inventory.py` | Changed `patient-avatars` and `practitioner-photos` to `BucketClass.PRIVATE_OWNED` and `public=False`; kept `organization-logos` public; kept exact 2 MiB and MIME values; updated notes for stable patient paths, signed reads, and disabled practitioner uploads. |
| `backend/supabase/config.toml` | Set `patient-avatars` and `practitioner-photos` to `public = false`; left all bucket size/MIME settings unchanged. |
| `backend/supabase/tests/database/spec12_storage_bucket_policy.test.sql` | Updated expected bucket flags, expanded the plan from 8 to 9 assertions, and added a check that the private cutover migration is recorded. |

### Database migration

| File | Change |
|---|---|
| `backend/supabase/migrations/20261124192523_private_patient_avatar_storage.sql` | New forward-only migration. Adds nullable `patients.profile_image_path`, adds stable-path comments, backfills only deterministic owner-scoped legacy public-avatar paths, preserves `patients.profile_image_url`, and reconciles the three reviewed bucket classifications without changing size/MIME limits. |

No existing migration was edited, renamed, deleted, repaired, or replayed manually.

### Application upload and retrieval

| File | Change |
|---|---|
| `backend/app/core/patient_avatar_access.py` | New centralized private-avatar helper. Defines the 60-second TTL, validates exact owner-scoped paths, parses legacy public URLs, issues signed URLs through the installed `storage3` SDK response keys (`signedURL` / `signedUrl`), projects API-safe patient rows, and fails closed on signing errors. |
| `backend/app/modules/patients/router.py` | Upload route now derives the path from authenticated patient identity, validates before Storage access, uploads with deterministic upsert, returns a signed URL, persists only the stable path, and compensates with sanitized logging if signing or DB persistence fails after upload. |
| `backend/app/modules/patients/service.py` | Selects `profile_image_path`, enriches `/patients/me`, `/patients/profile/me`, `/patients/mine`, and `get_or_create_patient` through the private-avatar projection, and replaces `update_profile_image` with `update_profile_image_path`, which never stores a signed URL. |

Existing patient-self checks, `authorize_patient_list_access`, `ensure_authorized_context`, active care-team filtering, and organization scoping were preserved.

### Tests

| File | Change |
|---|---|
| `backend/tests/core/test_storage_access_inventory.py` | Added explicit per-bucket public/classification expectations and a local `config.toml` parity test. |
| `backend/tests/core/test_storage_upload_validation.py` | Retained unchanged; still covers all three buckets with 2 MiB and MIME/signature validation. |
| `backend/tests/core/test_patient_avatar_access.py` | New tests for exact path validation, stable-path precedence, legacy URL parsing, unknown/cross-owner fail-closed behavior, SDK response-key handling, central TTL, signing failures, and internal-path hiding. |
| `backend/tests/patients/test_avatar_upload.py` | Updated from public URL behavior to signed URL behavior; added oversized-file, database-failure compensation, and signing-failure compensation tests. |
| `backend/tests/patients/test_private_avatar_retrieval.py` | New API-contract tests for all four retrieval routes, care-team scoping, legacy values, hidden `profile_image_path`, unchanged outward fields, and fail-closed signing failures. |

### Documentation

| File | Change |
|---|---|
| `docs/security/SPEC-12-storage-bucket-and-object-access.md` | Updated classification, decision, inventory, direct-access notes, private-avatar flow, file list, acceptance criteria, and a new implementation addendum. Historic evidence was explicitly labeled as superseded where appropriate. |
| `docs/security/PH0-WP-07-completion-record.md` | Added a clearly labeled addendum describing the private cutover and its local-only limits. |
| `docs/FRONTEND_API_CATALOG.md` | Documented that existing avatar fields now contain short-lived signed URLs and must not be cached as durable profile data. |
| `docs/security/PRIVATE-PATIENT-AVATAR-STORAGE-IMPLEMENTATION-RECORD.md` | This record. |

---

## 4. Data, upload, and retrieval behavior

### Database

- `patients.profile_image_path` is internal and nullable.
- `patients.profile_image_url` remains present for compatibility but is not authoritative.
- New uploads write `profile_image_path` and clear `profile_image_url`.
- Legacy public-avatar URLs are backfilled only when they decode to:
  - `<patient_id>/avatar.jpg`
  - `<patient_id>/avatar.png`
  - `<patient_id>/avatar.webp`

Unknown, cross-owner, nested, or unsupported legacy values remain null and produce no signed URL.

### Upload

1. Authenticate and require patient role.
2. Validate bucket, MIME, size, and signature.
3. Derive `<patient_id>/avatar.<ext>` from authenticated identity.
4. Upload through service role with deterministic `upsert`.
5. Issue a 60-second signed URL for the response only.
6. Persist the stable path, never the signed URL.
7. On post-upload failure, attempt object removal and emit sanitized logs.

### Retrieval

`GET /patients/me`, `GET /patients/profile/me`, `GET /api/v1/user/summary`, and `GET /patients/mine` now:

- keep their existing authorization checks;
- sign only avatars belonging to patients actually returned by those authorized paths;
- hide `profile_image_path`;
- preserve outward `profile_image_url` and `avatarUrl`;
- return ephemeral signed URLs or `null`;
- fail closed with HTTP 500 if a valid path cannot be signed.

Organization-logo upload, branding, storage paths, and public URL behavior were not changed.

---

## 5. Local verification

All verification used mocks or synthetic data. No hosted project was contacted and no production Storage object was created, read, modified, or deleted.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q tests/core/test_storage_access_inventory.py tests/core/test_storage_upload_validation.py tests/core/test_patient_avatar_access.py tests/patients/test_avatar_upload.py tests/patients/test_private_avatar_retrieval.py` | **52 passed, 12 warnings** |
| `.venv/Scripts/python.exe -m pytest -q` | **1468 passed, 1 skipped, 18 warnings** |
| `.venv/Scripts/python.exe -m compileall -q app tests` | **PASS** |
| `git diff --check` | **Clean** |

Not performed: `supabase db reset`, remote migration, `db push`, `config push`, hosted Storage operations, deployment, merge, issue/SEC closure, or Phase 0 acceptance.

---

## 6. Residual risks and handoff

- The new migration has not been applied to any hosted database.
- Updated pgTAP expectations have not been executed because no local reset was permitted.
- Hosted bucket drift remains open and must be reviewed before change approval.
- A human-reviewed `supabase config diff` is still required before config deployment.
- Frontend caches may retain expired signed URLs; a refresh-on-load follow-up is recommended.
- Cross-owner or unrecognized legacy avatar URLs intentionally produce `null`.
- Best-effort compensation can still leave an orphan object if Storage removal itself fails.
- No SEC finding or issue is closed by this work.
- **Phase 0 remains NOT ACCEPTED.**

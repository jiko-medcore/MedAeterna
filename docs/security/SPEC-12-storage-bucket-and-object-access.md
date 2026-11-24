# SPEC-12: Storage Bucket Classification and Object Access

**Status:** The reviewed model now classifies `organization-logos` as public and `patient-avatars` plus `practitioner-photos` as private. Source inventory, local config, a forward-only migration, and tests have been updated to match. The migration has not been applied to any hosted project in this work; hosted verification remains separate remediation work, and Phase 0 is still NOT ACCEPTED.

## Decision

Every Storage bucket must have one reviewed classification, an exact size/MIME limit, an owner-token path pattern, and one declared execution mode. A bucket that is absent from `STORAGE_BUCKET_INVENTORY` is denied by default: no configuration, no trusted upload path, and no object-level policy are created for it.

`organization-logos` is `public_owned` and remains the only bucket with public retrieval. `patient-avatars` and `practitioner-photos` are `private_owned`: no `storage.buckets.public` path exists for them, and authorized reads use short-lived signed URLs issued by the trusted backend. Direct client object access is denied by one explicit RLS policy. Every upload, replacement, and deletion goes through a trusted backend path using `ExecutionMode.SERVICE_ROLE` and the authorization evidence required by SPEC-10. No broad authenticated read or write policy was added.

Private clinical documents are not installed. `patient-documents` remains an explicit planned bucket and must be added to the inventory, migration, tests, and signed-URL implementation in the same change that creates it.

## Installed bucket inventory

| Bucket | Class | Public read | Size limit | Declared MIME types | Owner token / object path | Current write path |
|---|---|---:|---:|---|---|---|
| `organization-logos` | `public_owned` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | organization id; `<organization_id>/logo.<ext>` | Admin branding route uses service role with scoped organization-admin evidence. Legacy `/organizations/upload-logo` uses the same validated service-role helper after an explicit scoped organization-admin check. |
| `patient-avatars` | `private_owned` | No | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | patient user id; `<patient_id>/avatar.<ext>` | Patient self-service route uses service role after the authenticated user is verified as a patient. It stores the stable path in `patients.profile_image_path` and returns a short-lived signed URL only to authorized callers. |
| `practitioner-photos` | `private_owned` | No | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | practitioner id; `<practitioner_id>/photo.<ext>` | Upload remains disabled pending a separate approved trusted workflow. The bucket is installed with limits now. |

The application-level inventory is `backend/app/core/storage_access_inventory.py`. The same values are mirrored in `backend/supabase/config.toml` for local development and in the SPEC-12 migration for the catalog. The global Storage `file_size_limit` remains `50MiB`, but each reviewed bucket has the stricter 2 MiB value and the backend validator also enforces it.

## Object ownership and access rules

- The owner is the first non-empty path token. `object_owner_token()` and `object_path_is_valid()` enforce that first token and an allow-listed extension.
- Trusted writers must derive the owner token from authorized server-side context, never from a client-supplied object name. Organization writes require exact organization scope; avatar writes require patient self-service; practitioner writes will require practitioner self-service or another SPEC-03-approved rule.
- Object names are deterministic. Uploads use `upsert` so a replacement cannot create an unbounded set of objects for one owner.
- The stored extension is derived from the validated MIME type, not from the uploaded filename. Filenames never become object paths.
- Public retrieval is intentional only for `organization-logos`, which contains non-clinical branding images. Patient avatars are non-clinical but private by owner decision; no patient documents or clinical content may be placed in any installed bucket.

## Direct client access

The platform-owned ACL entries on `storage.objects` and `storage.buckets` grant broad CRUD to `anon` and `authenticated`. An application migration cannot revoke those entries because the grantor is `supabase_storage_admin` and `grantor must be current user`. They are therefore treated as platform-managed and are not relied on for authorization.

The application-controlled boundary is an explicit policy:

```sql
create policy "Deny direct client object access" on storage.objects
for all to anon, authenticated
using (false) with check (false);
```

This denies direct client object reads and writes while leaving the approved `bucket.public` retrieval path for `organization-logos` intact. `service_role` has `BYPASSRLS` and retains the platform-managed Storage CRUD grants; bypassing RLS is a capability, not caller authorization. Storage writes still require the trusted-path authorization and evidence described above.

Private buckets must never be exposed through `bucket.public`. `patient-avatars` reads use short-lived signed URLs issued only after the route's existing patient-self or care-team authorization succeeds, and the object path must still be patient-owned. Signed URLs are not persisted. When `patient-documents` is installed, reads must use the same authorized trusted-backend pattern after SPEC-03/04/05/06 checks.

## Upload validation

`backend/app/core/storage_upload_validation.py` is the shared validator for all reviewed image buckets:

1. The bucket must be in the inventory.
2. The declared MIME type must be one of the bucket's allow-listed types.
3. Content must be non-empty and no larger than the bucket limit.
4. Magic bytes must match the declared type: PNG `89 50 4E 47 0D 0A 1A 0A`, JPEG `FF D8 FF`, WebP `RIFF` plus `WEBP` at offset 8.
5. The returned trusted extension, not the upload filename, is used to build the object path.

Storage's configured MIME and size limits are the first layer; magic-byte inspection is the second layer because Storage does not inspect file bytes.

## Private patient-avatar flow

1. `POST /patients/profile/upload-avatar` authenticates the caller and requires the patient role. The object path is derived only from that authenticated patient id as `<patient_id>/avatar.<ext>`; the uploaded filename is never used.
2. The shared validator enforces the 2 MiB limit, allow-listed MIME type, and magic-byte signature. The trusted backend service-role client uploads with deterministic `upsert`.
3. After upload, the backend issues a 60-second signed URL for the caller's response. The signed URL is never written to the database. `patients.profile_image_path` stores the stable path; the legacy `patients.profile_image_url` column is preserved but cleared for new uploads.
4. If signing or the database update fails after the object was written, the backend attempts to remove the object and logs a sanitized failure without object paths, URLs, bytes, or exception details.
5. `GET /patients/me`, `GET /patients/profile/me`, `GET /api/v1/user/summary`, and `GET /patients/mine` sign only avatars belonging to patients already returned by their existing authorization checks. Care-team enumeration and organization scoping are unchanged.
6. `profile_image_path` is internal and is removed from API responses. Outward fields remain `profile_image_url` and dashboard `avatarUrl`, but their values are ephemeral signed URLs or `null`.
7. Legacy public-avatar URLs are accepted only when they decode to the exact owner-scoped `<patient_id>/avatar.<ext>` path. Unknown or cross-owner values produce `null`; if a valid path exists but signing fails, the API returns 500 rather than a legacy URL.

## Files

- Reference model: `backend/app/core/storage_access_inventory.py`
- Shared validator: `backend/app/core/storage_upload_validation.py`
- Private avatar signing/projection helper: `backend/app/core/patient_avatar_access.py`
- Branding compatibility constants: `backend/app/modules/organizations/branding/constants.py`
- Local bucket config: `backend/supabase/config.toml`
- Initial bucket migration: `backend/supabase/migrations/20261120110644_spec12_storage_bucket_policy.sql`
- Forward-only private cutover migration: `backend/supabase/migrations/20261124192523_private_patient_avatar_storage.sql`
- Python tests: `backend/tests/core/test_storage_access_inventory.py`, `backend/tests/core/test_storage_upload_validation.py`, `backend/tests/core/test_patient_avatar_access.py`, `backend/tests/patients/test_avatar_upload.py`, `backend/tests/patients/test_private_avatar_retrieval.py`, `backend/tests/organizations/branding/test_storage.py`, `backend/tests/organizations/test_router.py`
- Catalog tests: `backend/supabase/tests/database/spec12_storage_bucket_policy.test.sql`
- API catalog update: `docs/FRONTEND_API_CATALOG.md`

## Acceptance criteria

1. Every installed bucket has a reviewed classification, public flag, size limit, MIME allowlist, owner token, path pattern, and execution mode.
2. No unreviewed bucket is installed; `patient-documents` remains explicitly uncovered until its creation change updates the inventory.
3. The three installed buckets have exact `public`, `file_size_limit`, and `allowed_mime_types` values in the reviewed catalog model: only `organization-logos` is public.
4. Direct client object access is denied by a single reviewed policy; no broad authenticated read or write policy was added.
5. Uploads are rejected when the bucket is unknown, the declared MIME is unsupported, the file is empty or oversized, or the bytes do not match the declared type.
6. Stored object paths contain the authorized owner token and an extension derived from validated MIME; `patients.profile_image_path` is stable and signed URLs are never persisted.
7. Positive and negative route tests verify service-role writes, owner-scoped paths, forged-content rejection, patient self-service, scoped organization-admin enforcement, signed retrieval, legacy-value handling, and compensation on post-upload failure.
8. Focused Python tests, catalog assertions, effective Storage API checks, and the full backend regression suite pass with no patient data in output before any release approval.

## Addendum — private avatar cutover (local source implementation, 2026-11-24)

Branch `security/private-patient-avatar-storage` starts from `ac28aa82f24fcf0838d35edf2ea0e01822aaa2d0`. It adds one forward-only migration, `20261124192523_private_patient_avatar_storage.sql`, which adds `patients.profile_image_path`, backfills only deterministic owner-scoped legacy public-avatar URLs, preserves `patients.profile_image_url`, and flips `patient-avatars` and `practitioner-photos` to private while keeping all three buckets at 2 MiB with the same MIME allowlist. `organization-logos` remains public and unchanged in all application routes.

The application now signs patient avatars centrally with a 60-second TTL and projects the result into the existing `profile_image_url` / `avatarUrl` fields. The stable path is hidden from API responses. This is local implementation evidence only: no hosted migration, config push, Storage mutation, or production verification was performed, and Phase 0 remains NOT ACCEPTED.

## Historical verification evidence (local, 2026-11-20; superseded classification)

The evidence below was captured when all three installed buckets were public. It remains a record of that baseline and is superseded by the private classification above.

The migration was applied through the Supabase MCP `apply_migration` endpoint. `apply_migration` assigns its own version timestamp, so it is recorded in `supabase_migrations.schema_migrations` and the repository migration file as `20261120110644 / spec12_storage_bucket_policy` to reconcile local release history drift.

Live catalog checks against the applied database:

- 3 reviewed buckets exist with the exact public flag, 2 MiB limit, and MIME allowlist.
- No unreviewed bucket exists.
- Exactly 1 storage policy exists: `Deny direct client object access`, `FOR ALL TO anon, authenticated`, `USING (false) WITH CHECK (false)`.
- `storage.objects` and `storage.buckets` both still have RLS enabled.
- `service_role` retains the platform-managed CRUD grants on both storage tables and has `rolbypassrls = true`.
- The SPEC-12 migration is recorded exactly once.
- The 8 catalog assertions were extracted and executed directly through MCP because `supabase test db` cannot run locally without Docker/Podman: **8/8 passed**.

Effective-access checks against the real Storage API used only synthetic bytes:

- anonymous upload: denied;
- service-role upload: succeeded;
- public `GET` of the uploaded object: HTTP 200 and byte-for-byte match;
- temporary verification object: removed.

Python checks:

- focused storage/avatar/organization tests: **76 passed**;
- full backend suite: **1272 passed, 1 skipped**.

OpenAPI generation succeeded with **81 paths**; `/patients/profile/upload-avatar` and `/organizations/upload-logo` remain present. `supabase/config.toml` parses and contains the three reviewed bucket declarations. SPEC-11 live verification was re-run after a temporary grant probe was restored: **CHECKS PASSED**, with 26 tables, 18 policies, 4 trusted functions, and 5 migration records at that point; the SPEC-12 migration adds the sixth record.

No patient data was read or emitted. A temporary probe of the unrelated `terminology_codes` grant was restored, and the restored grant set was confirmed before final verification.

## Residual findings and deferred work

- SEC-22 is mitigated for installed image buckets: exact 2 MiB and MIME limits are configured in the catalog, mirrored in local config, and enforced before upload with byte-signature validation.
- SEC-24 local evidence covered direct-client denial, service-role upload, and public retrieval under the prior all-public baseline. No closure is claimed here; hosted deployment verification remains required.
- Public URLs remain intentionally readable only for `organization-logos`; patient-avatar URLs are now short-lived signed URLs and are not public bucket URLs.
- `practitioner-photos` is private with limits but still has no upload/removal route. A future route must use the shared validator, owner-scoped path, and trusted service-role path.
- Legacy `patients.profile_image_url` values that are not recognizable owner-scoped Storage paths produce a null outward URL. Backfill and hydration are deterministic and fail closed.
- `patient-documents` is not installed. It must be private, use signed URLs, and update the inventory/migration/tests in the same change.
- The legacy `/organizations/upload-logo` route resolves the organization from the user's first role assignment, so users with multiple organizations should use the explicit `/organizations/{organization_id}/branding/logo` route instead. The legacy route now enforces scoped organization-admin authority, but consolidating or deprecating it remains route-level cleanup.
- Replacement of a patient avatar uses the same deterministic path and overwrites the prior object. A dedicated delete route and stale-object lifecycle policy are not part of this SPEC.
- Supabase security advisor after the migration reported 28 findings: 2 `function_search_path_mutable` (WARN), 11 `pg_graphql_authenticated_table_exposed` (WARN), and 15 `rls_enabled_no_policy` (INFO). These are the accepted SPEC-11 findings plus deliberate storage policy-free service-only tables; none grants client object access.

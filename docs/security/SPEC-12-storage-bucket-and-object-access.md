# SPEC-12: Storage Bucket Classification and Object Access

**Status:** The intended model, least-privilege configuration, migration, and catalog tests are defined. The migration has been applied to the local Supabase database and the live catalog matches the model. Hosted/deployed verification remains separate remediation work, and Phase 0 is still NOT ACCEPTED.

## Decision

Every Storage bucket must have one reviewed classification, an exact size/MIME limit, an owner-token path pattern, and one declared execution mode. A bucket that is absent from `STORAGE_BUCKET_INVENTORY` is denied by default: no configuration, no trusted upload path, and no object-level policy are created for it.

All currently installed buckets are `public_owned`, non-clinical profile or branding images. Public retrieval is provided only by `storage.buckets.public`. Direct client object access is denied by an explicit RLS policy. Every upload, replacement, and deletion goes through a trusted backend path using `ExecutionMode.SERVICE_ROLE` and the authorization evidence required by SPEC-10.

Private clinical documents are not installed. `patient-documents` remains an explicit planned bucket and must be added to the inventory, migration, tests, and signed-URL implementation in the same change that creates it.

## Installed bucket inventory

| Bucket | Class | Public read | Size limit | Declared MIME types | Owner token / object path | Current write path |
|---|---|---:|---:|---|---|---|
| `organization-logos` | `public_owned` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | organization id; `<organization_id>/logo.<ext>` | Admin branding route uses service role with scoped organization-admin evidence. Legacy `/organizations/upload-logo` uses the same validated service-role helper after an explicit scoped organization-admin check. |
| `patient-avatars` | `public_owned` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | patient user id; `<patient_id>/avatar.<ext>` | Patient self-service route uses service role after the authenticated user is verified as a patient. |
| `practitioner-photos` | `public_owned` | Yes | 2 MiB | `image/jpeg`, `image/png`, `image/webp` | practitioner id; `<practitioner_id>/photo.<ext>` | No backend upload route exists. The bucket is installed with limits now; a future route must use the trusted path. |

The application-level inventory is `backend/app/core/storage_access_inventory.py`. The same values are mirrored in `backend/supabase/config.toml` for local development and in the SPEC-12 migration for the catalog. The global Storage `file_size_limit` remains `50MiB`, but each reviewed bucket has the stricter 2 MiB value and the backend validator also enforces it.

## Object ownership and access rules

- The owner is the first non-empty path token. `object_owner_token()` and `object_path_is_valid()` enforce that first token and an allow-listed extension.
- Trusted writers must derive the owner token from authorized server-side context, never from a client-supplied object name. Organization writes require exact organization scope; avatar writes require patient self-service; practitioner writes will require practitioner self-service or another SPEC-03-approved rule.
- Object names are deterministic. Uploads use `upsert` so a replacement cannot create an unbounded set of objects for one owner.
- The stored extension is derived from the validated MIME type, not from the uploaded filename. Filenames never become object paths.
- Public retrieval of these buckets is intentional because they contain non-clinical profile or branding images only. No patient documents or clinical content may be placed in a `public_owned` bucket.

## Direct client access

The platform-owned ACL entries on `storage.objects` and `storage.buckets` grant broad CRUD to `anon` and `authenticated`. An application migration cannot revoke those entries because the grantor is `supabase_storage_admin` and `grantor must be current user`. They are therefore treated as platform-managed and are not relied on for authorization.

The application-controlled boundary is an explicit policy:

```sql
create policy "Deny direct client object access" on storage.objects
for all to anon, authenticated
using (false) with check (false);
```

This denies direct client object reads and writes while leaving `bucket.public` retrieval intact. `service_role` has `BYPASSRLS` and retains the platform-managed Storage CRUD grants; bypassing RLS is a capability, not caller authorization. Storage writes still require the trusted-path authorization and evidence described above.

A private bucket must never be exposed through `bucket.public`. When `patient-documents` is installed, reads must use short-lived signed URLs issued by an authorized trusted backend path after SPEC-03/04/05/06 checks, and the object path must still be patient-owned.

## Upload validation

`backend/app/core/storage_upload_validation.py` is the shared validator for all reviewed image buckets:

1. The bucket must be in the inventory.
2. The declared MIME type must be one of the bucket's allow-listed types.
3. Content must be non-empty and no larger than the bucket limit.
4. Magic bytes must match the declared type: PNG `89 50 4E 47 0D 0A 1A 0A`, JPEG `FF D8 FF`, WebP `RIFF` plus `WEBP` at offset 8.
5. The returned trusted extension, not the upload filename, is used to build the object path.

Storage's configured MIME and size limits are the first layer; magic-byte inspection is the second layer because Storage does not inspect file bytes.

## Files

- Reference model: `backend/app/core/storage_access_inventory.py`
- Shared validator: `backend/app/core/storage_upload_validation.py`
- Branding compatibility constants: `backend/app/modules/organizations/branding/constants.py`
- Local bucket config: `backend/supabase/config.toml`
- Migration: `backend/supabase/migrations/20261120130000_spec12_storage_bucket_policy.sql`
- Python tests: `backend/tests/core/test_storage_access_inventory.py`, `backend/tests/core/test_storage_upload_validation.py`, `backend/tests/patients/test_avatar_upload.py`, `backend/tests/organizations/branding/test_storage.py`, `backend/tests/organizations/test_router.py`
- Catalog tests: `backend/supabase/tests/database/spec12_storage_bucket_policy.test.sql`
- API catalog update: `docs/FRONTEND_API_CATALOG.md`

## Acceptance criteria

1. Every installed bucket has a reviewed classification, public flag, size limit, MIME allowlist, owner token, path pattern, and execution mode.
2. No unreviewed bucket is installed; `patient-documents` remains explicitly uncovered until its creation change updates the inventory.
3. The three installed buckets have exact `public`, `file_size_limit`, and `allowed_mime_types` values in the live catalog.
4. Direct client object access is denied by a single reviewed policy; no other storage policy creates an alternate access path.
5. Uploads are rejected when the bucket is unknown, the declared MIME is unsupported, the file is empty or oversized, or the bytes do not match the declared type.
6. Stored object paths contain the authorized owner token and an extension derived from validated MIME.
7. Positive and negative route tests verify service-role writes, owner-scoped paths, forged-content rejection, patient self-service, and scoped organization-admin enforcement.
8. Focused Python tests, catalog assertions, effective Storage API checks, and the full backend regression suite pass with no patient data in output.

## Verification evidence (local, 2026-11-20)

The migration was applied through the Supabase MCP `apply_migration` endpoint. `apply_migration` assigns its own version timestamp, so it is recorded as `20261120110644 / spec12_storage_bucket_policy`; the repository filename remains `20261120130000_spec12_storage_bucket_policy.sql`.

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
- SEC-24 is closed locally by effective verification of direct-client denial, service-role upload, and public retrieval. Hosted deployment verification is still required before the finding can be closed across environments.
- Public URLs are intentionally readable by anyone who has them. Only non-clinical images may be stored in these buckets; this must be enforced by code review and future bucket changes.
- `practitioner-photos` has limits but no upload/removal route yet. A future route must use the shared validator, owner-scoped path, and trusted service-role path.
- `patient-documents` is not installed. It must be private, use signed URLs, and update the inventory/migration/tests in the same change.
- The legacy `/organizations/upload-logo` route resolves the organization from the user's first role assignment, so users with multiple organizations should use the explicit `/organizations/{organization_id}/branding/logo` route instead. The legacy route now enforces scoped organization-admin authority, but consolidating or deprecating it remains route-level cleanup.
- Replacement of a patient avatar uses the same deterministic path and overwrites the prior object. A dedicated delete route and stale-object lifecycle policy are not part of this SPEC.
- Supabase security advisor after the migration reported 28 findings: 2 `function_search_path_mutable` (WARN), 11 `pg_graphql_authenticated_table_exposed` (WARN), and 15 `rls_enabled_no_policy` (INFO). These are the accepted SPEC-11 findings plus deliberate storage policy-free service-only tables; none grants client object access.

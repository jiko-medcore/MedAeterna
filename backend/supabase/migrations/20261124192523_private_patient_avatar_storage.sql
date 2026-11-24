-- Private patient-avatar storage: forward-only cutover from public objects to
-- authorized, short-lived signed URLs issued by the trusted backend.
--
-- Stable object path contract:
--   patient-avatars: <patient_id>/avatar.<ext>
-- The owner token is the authenticated patient's user id. The extension is
-- derived from validated MIME bytes at upload time. Clients never supply an
-- object path, and signed URLs are never persisted.

-- 1. Store the stable private object path separately from the legacy display
-- URL column. The legacy column is preserved for API compatibility.
alter table public.patients
  add column if not exists profile_image_path text;

comment on column public.patients.profile_image_path is
  'Stable private Storage object path for patient-avatars (<patient_id>/avatar.<ext>). Derived from authenticated patient identity; never stores a signed URL.';

comment on column public.patients.profile_image_url is
  'Legacy display field preserved for API compatibility. Not authoritative for private avatars; outward values are short-lived signed URLs generated after authorization and are never persisted.';

-- 2. Backfill only legacy public patient-avatar URLs whose path is already
-- owner-scoped and deterministic. Unknown or cross-owned legacy values remain
-- null so the read path fails closed.
with legacy_candidates as (
  select
    id,
    split_part(
      split_part(
        regexp_replace(
          profile_image_url,
          '^.*/storage/v1/object/public/patient-avatars/',
          ''
        ),
        '?',
        1
      ),
      '#',
      1
    ) as object_path
  from public.patients
  where profile_image_path is null
    and profile_image_url like '%/storage/v1/object/public/patient-avatars/%'
)
update public.patients p
set profile_image_path = legacy_candidates.object_path
from legacy_candidates
where p.id = legacy_candidates.id
  and split_part(legacy_candidates.object_path, '/', 1) = p.id::text
  and legacy_candidates.object_path ~ '^[^/]+/avatar\.(jpg|png|webp)$';

-- 3. Reconcile the reviewed bucket classifications without changing the
-- approved 2 MiB limit or MIME allowlist. organization-logos stays public;
-- patient-avatars and practitioner-photos become private with no direct client
-- object access. The existing deny policy is intentionally unchanged.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types, updated_at)
values
  (
    'organization-logos',
    'organization-logos',
    true,
    2097152,
    ARRAY['image/jpeg', 'image/png', 'image/webp']::text[],
    now()
  ),
  (
    'patient-avatars',
    'patient-avatars',
    false,
    2097152,
    ARRAY['image/jpeg', 'image/png', 'image/webp']::text[],
    now()
  ),
  (
    'practitioner-photos',
    'practitioner-photos',
    false,
    2097152,
    ARRAY['image/jpeg', 'image/png', 'image/webp']::text[],
    now()
  )
on conflict (id) do update
set name = excluded.name,
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types,
    updated_at = now();

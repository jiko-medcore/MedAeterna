-- SPEC-12 catalog checks. Run with: supabase test db
BEGIN;

SELECT plan(8);

-- 1. Every reviewed bucket exists with the exact public/size/MIME configuration.
WITH spec12_expected_buckets (name, public, file_size_limit, allowed_mime_types) AS (
    VALUES
    ('organization-logos', true, 2097152, ARRAY['image/jpeg', 'image/png', 'image/webp']::text[]),
    ('patient-avatars', true, 2097152, ARRAY['image/jpeg', 'image/png', 'image/webp']::text[]),
    ('practitioner-photos', true, 2097152, ARRAY['image/jpeg', 'image/png', 'image/webp']::text[])
)
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM spec12_expected_buckets e
        LEFT JOIN storage.buckets b ON b.name = e.name
        WHERE b.id IS NULL
           OR b.public IS DISTINCT FROM e.public
           OR b.file_size_limit IS DISTINCT FROM e.file_size_limit
           OR b.allowed_mime_types IS DISTINCT FROM e.allowed_mime_types
    ),
    'reviewed buckets have exact public, size, and MIME configuration'
);

-- 2. No uninstalled or unregistered bucket is present.
WITH spec12_expected_buckets (name) AS (
    VALUES
    ('organization-logos'),
    ('patient-avatars'),
    ('practitioner-photos')
)
SELECT ok(
    NOT EXISTS (
        SELECT 1 FROM storage.buckets b
        LEFT JOIN spec12_expected_buckets e ON e.name = b.name
        WHERE e.name IS NULL
    ),
    'no unreviewed storage bucket exists'
);

-- 3. The reviewed client-deny policy exists exactly as modeled.
SELECT ok(
    EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'storage'
          AND tablename = 'objects'
          AND policyname = 'Deny direct client object access'
          AND cmd = 'ALL'
          AND roles::text[] = ARRAY['anon', 'authenticated']::text[]
          AND lower(btrim(coalesce(qual, ''))) = 'false'
          AND lower(btrim(coalesce(with_check, ''))) = 'false'
    ),
    'explicit deny policy exists for anon and authenticated'
);

-- 4. No other storage policy creates an alternate access path.
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'storage'
          AND tablename IN ('objects', 'buckets')
          AND policyname <> 'Deny direct client object access'
    ),
    'no unreviewed storage policy exists'
);

-- 5. Platform RLS remains enabled on the storage metadata tables.
SELECT ok(
    (SELECT relrowsecurity FROM pg_class WHERE oid = 'storage.objects'::regclass) IS TRUE
    AND (SELECT relrowsecurity FROM pg_class WHERE oid = 'storage.buckets'::regclass) IS TRUE,
    'RLS remains enabled on storage.objects and storage.buckets'
);

-- 6. Service role retains the platform-managed CRUD grants needed by Storage APIs.
WITH required_grant(table_name, privilege_type) AS (
    VALUES
        ('objects', 'SELECT'), ('objects', 'INSERT'), ('objects', 'UPDATE'), ('objects', 'DELETE'),
        ('buckets', 'SELECT'), ('buckets', 'INSERT'), ('buckets', 'UPDATE'), ('buckets', 'DELETE')
)
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM required_grant r
        WHERE NOT EXISTS (
            SELECT 1
            FROM information_schema.role_table_grants g
            WHERE g.table_schema = 'storage'
              AND g.table_name = r.table_name
              AND g.grantee = 'service_role'
              AND g.privilege_type = r.privilege_type
        )
    ),
    'service_role retains platform-managed storage CRUD grants'
);

-- 7. service_role can bypass RLS; application authorization remains the control.
SELECT ok(
    (SELECT rolbypassrls FROM pg_roles WHERE rolname = 'service_role') IS TRUE,
    'service_role bypasses RLS as required by the trusted execution model'
);

-- 8. The reviewed migration is recorded.
SELECT ok(
    EXISTS (
        SELECT 1 FROM supabase_migrations.schema_migrations
        WHERE name = 'spec12_storage_bucket_policy'
    ),
    'SPEC-12 migration is recorded'
);

SELECT finish();
ROLLBACK;

-- SPEC-11 catalog checks. Run with: supabase test db
BEGIN;

SELECT plan(10);

-- 1. Every reviewed relation exists with RLS enabled and forced.
WITH reviewed(table_name) AS (
    VALUES
        ('audit_logs'),
        ('care_teams'),
        ('clinicians_patients'),
        ('consent_records'),
        ('departments'),
        ('events'),
        ('events_dead_letter'),
        ('healthcare_services'),
        ('invitations'),
        ('lab_results'),
        ('medical_records'),
        ('organization_operating_hours'),
        ('organizations'),
        ('patient_care_team'),
        ('patients'),
        ('permissions'),
        ('practitioner_roles'),
        ('practitioners'),
        ('prescriptions'),
        ('profiles'),
        ('reminders'),
        ('role_assignment_audit'),
        ('role_permissions'),
        ('roles'),
        ('terminology_codes'),
        ('user_roles')
)
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM reviewed r
        LEFT JOIN pg_class c
            ON c.relname = r.table_name
            AND c.relnamespace = 'public'::regnamespace
            AND c.relkind = 'r'
        WHERE c.oid IS NULL OR NOT c.relrowsecurity OR NOT c.relforcerowsecurity
    ),
    'all reviewed public tables exist with RLS enabled and forced'
);

-- 2. Client roles hold no privilege that bypasses row filtering.
WITH reviewed(table_name) AS (
    VALUES
        ('audit_logs'),
        ('care_teams'),
        ('clinicians_patients'),
        ('consent_records'),
        ('departments'),
        ('events'),
        ('events_dead_letter'),
        ('healthcare_services'),
        ('invitations'),
        ('lab_results'),
        ('medical_records'),
        ('organization_operating_hours'),
        ('organizations'),
        ('patient_care_team'),
        ('patients'),
        ('permissions'),
        ('practitioner_roles'),
        ('practitioners'),
        ('prescriptions'),
        ('profiles'),
        ('reminders'),
        ('role_assignment_audit'),
        ('role_permissions'),
        ('roles'),
        ('terminology_codes'),
        ('user_roles')
)
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM information_schema.role_table_grants g
        JOIN reviewed r ON r.table_name = g.table_name
        WHERE g.table_schema = 'public'
          AND g.grantee IN ('anon', 'authenticated')
          AND g.privilege_type IN ('TRUNCATE', 'MAINTAIN', 'TRIGGER', 'REFERENCES', 'DELETE')
    ),
    'anon and authenticated have no write-bypass, destructive, or ownership privileges'
);

-- 3. Table grants match the inventory exactly for all three API roles.
WITH expected(table_name, grantee, privileges) AS (
    VALUES
    ('audit_logs', 'anon', ARRAY[]::text[]),
    ('audit_logs', 'authenticated', ARRAY[]::text[]),
    ('audit_logs', 'service_role', ARRAY['INSERT', 'SELECT']::text[]),
    ('care_teams', 'anon', ARRAY[]::text[]),
    ('care_teams', 'authenticated', ARRAY[]::text[]),
    ('care_teams', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('clinicians_patients', 'anon', ARRAY[]::text[]),
    ('clinicians_patients', 'authenticated', ARRAY[]::text[]),
    ('clinicians_patients', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('consent_records', 'anon', ARRAY[]::text[]),
    ('consent_records', 'authenticated', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('consent_records', 'service_role', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('departments', 'anon', ARRAY[]::text[]),
    ('departments', 'authenticated', ARRAY[]::text[]),
    ('departments', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('events', 'anon', ARRAY[]::text[]),
    ('events', 'authenticated', ARRAY[]::text[]),
    ('events', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('events_dead_letter', 'anon', ARRAY[]::text[]),
    ('events_dead_letter', 'authenticated', ARRAY[]::text[]),
    ('events_dead_letter', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('healthcare_services', 'anon', ARRAY[]::text[]),
    ('healthcare_services', 'authenticated', ARRAY[]::text[]),
    ('healthcare_services', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('invitations', 'anon', ARRAY[]::text[]),
    ('invitations', 'authenticated', ARRAY[]::text[]),
    ('invitations', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('lab_results', 'anon', ARRAY[]::text[]),
    ('lab_results', 'authenticated', ARRAY['SELECT']::text[]),
    ('lab_results', 'service_role', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('medical_records', 'anon', ARRAY[]::text[]),
    ('medical_records', 'authenticated', ARRAY['SELECT']::text[]),
    ('medical_records', 'service_role', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('organization_operating_hours', 'anon', ARRAY[]::text[]),
    ('organization_operating_hours', 'authenticated', ARRAY[]::text[]),
    ('organization_operating_hours', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('organizations', 'anon', ARRAY[]::text[]),
    ('organizations', 'authenticated', ARRAY[]::text[]),
    ('organizations', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('patient_care_team', 'anon', ARRAY[]::text[]),
    ('patient_care_team', 'authenticated', ARRAY[]::text[]),
    ('patient_care_team', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('patients', 'anon', ARRAY[]::text[]),
    ('patients', 'authenticated', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('patients', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('permissions', 'anon', ARRAY[]::text[]),
    ('permissions', 'authenticated', ARRAY[]::text[]),
    ('permissions', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('practitioner_roles', 'anon', ARRAY[]::text[]),
    ('practitioner_roles', 'authenticated', ARRAY['SELECT']::text[]),
    ('practitioner_roles', 'service_role', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('practitioners', 'anon', ARRAY[]::text[]),
    ('practitioners', 'authenticated', ARRAY['SELECT']::text[]),
    ('practitioners', 'service_role', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('prescriptions', 'anon', ARRAY[]::text[]),
    ('prescriptions', 'authenticated', ARRAY['SELECT']::text[]),
    ('prescriptions', 'service_role', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('profiles', 'anon', ARRAY[]::text[]),
    ('profiles', 'authenticated', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('profiles', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('reminders', 'anon', ARRAY[]::text[]),
    ('reminders', 'authenticated', ARRAY['SELECT']::text[]),
    ('reminders', 'service_role', ARRAY['INSERT', 'SELECT', 'UPDATE']::text[]),
    ('role_assignment_audit', 'anon', ARRAY[]::text[]),
    ('role_assignment_audit', 'authenticated', ARRAY[]::text[]),
    ('role_assignment_audit', 'service_role', ARRAY['INSERT', 'SELECT']::text[]),
    ('role_permissions', 'anon', ARRAY[]::text[]),
    ('role_permissions', 'authenticated', ARRAY[]::text[]),
    ('role_permissions', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('roles', 'anon', ARRAY[]::text[]),
    ('roles', 'authenticated', ARRAY[]::text[]),
    ('roles', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('terminology_codes', 'anon', ARRAY['SELECT']::text[]),
    ('terminology_codes', 'authenticated', ARRAY['SELECT']::text[]),
    ('terminology_codes', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[]),
    ('user_roles', 'anon', ARRAY[]::text[]),
    ('user_roles', 'authenticated', ARRAY['SELECT']::text[]),
    ('user_roles', 'service_role', ARRAY['DELETE', 'INSERT', 'SELECT', 'UPDATE']::text[])
),
actual AS (
    SELECT table_name, grantee,
           array_agg(privilege_type ORDER BY privilege_type)::text[] AS privileges
    FROM information_schema.role_table_grants
    WHERE table_schema = 'public'
      AND grantee IN ('anon', 'authenticated', 'service_role')
    GROUP BY table_name, grantee
),
mismatch AS (
    SELECT e.table_name, e.grantee, e.privileges AS expected, a.privileges AS actual
    FROM expected e
    LEFT JOIN actual a USING (table_name, grantee)
    WHERE coalesce(a.privileges, ARRAY[]::text[]) IS DISTINCT FROM e.privileges
    UNION ALL
    SELECT a.table_name, a.grantee, e.privileges, a.privileges
    FROM actual a
    LEFT JOIN expected e USING (table_name, grantee)
    WHERE e.table_name IS NULL
)
SELECT ok(
    NOT EXISTS (SELECT 1 FROM mismatch),
    'table grants match the SPEC-11 inventory exactly'
);

-- 4. Policies match the approved names, commands, roles, and expressions.
WITH expected(table_name, name, command, roles, predicate, check_expr) AS (
    VALUES
    ('consent_records', 'Patients read own consent', 'SELECT', ARRAY['authenticated']::text[], 'patient_id = (select auth.uid())', ''),
    ('consent_records', 'Patients insert own consent', 'INSERT', ARRAY['authenticated']::text[], '', 'patient_id = (select auth.uid())'),
    ('consent_records', 'Patients update own consent', 'UPDATE', ARRAY['authenticated']::text[], 'patient_id = (select auth.uid())', 'patient_id = (select auth.uid())'),
    ('lab_results', 'Patients read own lab results', 'SELECT', ARRAY['authenticated']::text[], 'patient_id = (select auth.uid())', ''),
    ('medical_records', 'Patients read own medical records', 'SELECT', ARRAY['authenticated']::text[], 'patient_id = (select auth.uid())', ''),
    ('patients', 'Patients read own record', 'SELECT', ARRAY['authenticated']::text[], 'id = (select auth.uid())', ''),
    ('patients', 'Patients insert own record', 'INSERT', ARRAY['authenticated']::text[], '', 'id = (select auth.uid())'),
    ('patients', 'Patients update own record', 'UPDATE', ARRAY['authenticated']::text[], 'id = (select auth.uid())', 'id = (select auth.uid())'),
    ('practitioner_roles', 'Practitioners read own roles', 'SELECT', ARRAY['authenticated']::text[], 'practitioner_id in (select p.id from public.practitioners p where p.profile_id = (select auth.uid()))', ''),
    ('practitioners', 'Practitioners read own profile', 'SELECT', ARRAY['authenticated']::text[], 'id = (select auth.uid()) or profile_id = (select auth.uid())', ''),
    ('prescriptions', 'Patients read own prescriptions', 'SELECT', ARRAY['authenticated']::text[], 'patient_id = (select auth.uid())', ''),
    ('profiles', 'Users read own profile', 'SELECT', ARRAY['authenticated']::text[], 'id = (select auth.uid())', ''),
    ('profiles', 'Users insert own profile', 'INSERT', ARRAY['authenticated']::text[], '', 'id = (select auth.uid())'),
    ('profiles', 'Users update own profile', 'UPDATE', ARRAY['authenticated']::text[], 'id = (select auth.uid())', 'id = (select auth.uid())'),
    ('reminders', 'Patients read own reminders', 'SELECT', ARRAY['authenticated']::text[], 'patient_id = (select auth.uid())', ''),
    ('terminology_codes', 'Read-only terminology', 'SELECT', ARRAY['anon', 'authenticated']::text[], 'true', ''),
    ('user_roles', 'Users read own roles', 'SELECT', ARRAY['authenticated']::text[], 'user_id = (select auth.uid())', ''),
    ('user_roles', 'Trusted service manages assignments', 'ALL', ARRAY['service_role']::text[], 'true', 'true')
),
actual AS (
    SELECT tablename AS table_name,
           policyname AS name,
           cmd AS command,
           roles::text[] AS roles,
           qual AS predicate,
           with_check AS check_expr
    FROM pg_policies
    WHERE schemaname = 'public'
),
norm_expected AS (
    SELECT table_name, name, command, roles,
           regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(predicate, '')), '\s+', ' ', 'g'), ' as uid', '', 'g'), 'public\.', '', 'g'), '[[:space:]]', '', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g') AS predicate,
           regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(check_expr, '')), '\s+', ' ', 'g'), ' as uid', '', 'g'), 'public\.', '', 'g'), '[[:space:]]', '', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g') AS check_expr
    FROM expected
),
norm_actual AS (
    SELECT table_name, name, command, roles,
           regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(predicate, '')), '\s+', ' ', 'g'), ' as uid', '', 'g'), 'public\.', '', 'g'), '[[:space:]]', '', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g') AS predicate,
           regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(check_expr, '')), '\s+', ' ', 'g'), ' as uid', '', 'g'), 'public\.', '', 'g'), '[[:space:]]', '', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g'), '\(([^()]*)\)', '\1', 'g') AS check_expr
    FROM actual
),
mismatch AS (
    SELECT e.table_name, e.name, e.command, e.roles, e.predicate, e.check_expr,
           a.command AS a_command, a.roles AS a_roles,
           a.predicate AS a_predicate, a.check_expr AS a_check_expr
    FROM norm_expected e
    LEFT JOIN norm_actual a USING (table_name, name)
    WHERE a.name IS NULL
       OR e.command <> a.command
       OR e.roles <> a.roles
       OR e.predicate <> a.predicate
       OR e.check_expr <> a.check_expr
    UNION ALL
    SELECT a.table_name, a.name, a.command, a.roles, a.predicate, a.check_expr,
           NULL, NULL, NULL, NULL
    FROM norm_actual a
    LEFT JOIN norm_expected e USING (table_name, name)
    WHERE e.name IS NULL
)
SELECT ok(
    NOT EXISTS (SELECT 1 FROM mismatch),
    'RLS policies match the approved inventory with no legacy duplicates'
);

-- 5. Service-only and append-only audit tables expose no policies.
WITH service_only(table_name) AS (
    VALUES
        ('audit_logs'),
        ('care_teams'),
        ('clinicians_patients'),
        ('departments'),
        ('events'),
        ('events_dead_letter'),
        ('healthcare_services'),
        ('invitations'),
        ('organization_operating_hours'),
        ('organizations'),
        ('patient_care_team'),
        ('permissions'),
        ('role_assignment_audit'),
        ('role_permissions'),
        ('roles')
)
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM pg_policies p
        JOIN service_only s ON s.table_name = p.tablename
        WHERE p.schemaname = 'public'
    ),
    'service-only and audit tables have no client-facing policy'
);

-- 6. Every auth.uid() occurrence is inside a wrapped (select auth.uid()) expression.
WITH expressions AS (
    SELECT tablename, policyname,
           regexp_replace(lower(coalesce(qual, '') || ' ' || coalesce(with_check, '')),
                          '\s+', ' ', 'g') AS e
    FROM pg_policies
    WHERE schemaname = 'public'
)
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM expressions
        WHERE e LIKE '%auth.uid()%'
          AND (
            (char_length(e) - char_length(replace(e, 'auth.uid()', ''))) / 10
            <>
            (char_length(e) - char_length(replace(e, 'select auth.uid()', ''))) / 17
          )
    ),
    'RLS predicates use (select auth.uid())'
);

-- 7. Append-only audit tables remain SELECT/INSERT only for service_role.
SELECT ok(
    has_table_privilege('service_role', 'public.audit_logs', 'SELECT')
    AND has_table_privilege('service_role', 'public.audit_logs', 'INSERT')
    AND NOT has_table_privilege('service_role', 'public.audit_logs', 'UPDATE')
    AND NOT has_table_privilege('service_role', 'public.audit_logs', 'DELETE')
    AND NOT has_table_privilege('service_role', 'public.audit_logs', 'TRUNCATE')
    AND has_table_privilege('service_role', 'public.role_assignment_audit', 'SELECT')
    AND has_table_privilege('service_role', 'public.role_assignment_audit', 'INSERT')
    AND NOT has_table_privilege('service_role', 'public.role_assignment_audit', 'UPDATE')
    AND NOT has_table_privilege('service_role', 'public.role_assignment_audit', 'DELETE')
    AND NOT has_table_privilege('service_role', 'public.role_assignment_audit', 'TRUNCATE'),
    'audit tables are append-only even for service_role'
);

-- 8. Role assignment writes still require the trusted function.
SELECT ok(
    NOT has_table_privilege('anon', 'public.user_roles', 'INSERT')
    AND NOT has_table_privilege('authenticated', 'public.user_roles', 'INSERT')
    AND NOT has_table_privilege('authenticated', 'public.user_roles', 'UPDATE')
    AND NOT has_table_privilege('authenticated', 'public.user_roles', 'DELETE')
    AND has_table_privilege('service_role', 'public.user_roles', 'INSERT'),
    'role assignment writes remain on the trusted service path'
);

-- 9. SECURITY DEFINER functions are pinned and service-role only.
WITH expected(signature, search_path) AS (
    VALUES
    ('can_manage_roles()', ARRAY['pg_catalog', 'public']::text[]),
    ('change_user_role_assignment(uuid, uuid, uuid, uuid, text, text, text)', ARRAY['pg_catalog', 'public']::text[]),
    ('get_user_permissions(uuid)', ARRAY['pg_catalog', 'public']::text[]),
    ('is_admin_user()', ARRAY['pg_catalog', 'public']::text[])
)
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM expected e
        JOIN pg_proc p
            ON p.oid = to_regprocedure('public.' || e.signature)
        WHERE NOT p.prosecdef
           OR p.proconfig IS DISTINCT FROM ARRAY[
                'search_path=' || array_to_string(e.search_path, ', ')
              ]::text[]
           OR NOT has_function_privilege('service_role', p.oid, 'EXECUTE')
           OR has_function_privilege('anon', p.oid, 'EXECUTE')
           OR has_function_privilege('authenticated', p.oid, 'EXECUTE')
    ),
    'SECURITY DEFINER functions have fixed search_path and service-role-only EXECUTE'
);

-- 10. Indexes that support scoped predicates and lookups exist.
WITH expected(indexname, table_name) AS (
    VALUES
        ('idx_patients_organization_id', 'patients'),
        ('idx_medical_records_patient_id', 'medical_records'),
        ('idx_lab_results_patient_id', 'lab_results'),
        ('idx_lab_results_clinician_id', 'lab_results'),
        ('idx_prescriptions_patient_id', 'prescriptions'),
        ('idx_reminders_patient_id', 'reminders'),
        ('idx_practitioners_profile_id', 'practitioners'),
        ('idx_terminology_codes_system_code', 'terminology_codes'),
        ('idx_audit_logs_actor_id', 'audit_logs'),
        ('idx_audit_logs_created_at', 'audit_logs'),
        ('idx_role_assignment_audit_user_id', 'role_assignment_audit'),
        ('idx_care_teams_clinician_id', 'care_teams'),
        ('idx_invitations_organization_id', 'invitations'),
        ('idx_roles_organization_id', 'roles'),
        ('idx_roles_is_active', 'roles'),
        ('idx_events_dead_letter_original_event_id', 'events_dead_letter'),
        ('idx_events_dead_letter_replayed', 'events_dead_letter'),
        ('idx_events_dead_letter_failed_at', 'events_dead_letter')
)
SELECT ok(
    NOT EXISTS (
        SELECT 1
        FROM expected e
        LEFT JOIN pg_indexes i
            ON i.indexname = e.indexname
            AND i.schemaname = 'public'
            AND i.tablename = e.table_name
        WHERE i.indexname IS NULL
    ),
    'all SPEC-11 supporting indexes exist'
);

SELECT * FROM finish();
ROLLBACK;

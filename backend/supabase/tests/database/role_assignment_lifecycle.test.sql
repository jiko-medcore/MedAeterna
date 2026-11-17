BEGIN;

SELECT plan(37);

-- Fixed fixture IDs keep the test deterministic. Everything rolls back below.
INSERT INTO auth.users (id, aud, role, email, raw_app_meta_data, raw_user_meta_data)
VALUES
    ('10000000-0000-4000-8000-000000000001', 'authenticated', 'authenticated', 'spec02-actor@example.test', '{"provider":"email","providers":["email"]}', '{}'),
    ('10000000-0000-4000-8000-000000000002', 'authenticated', 'authenticated', 'spec02-target@example.test', '{"provider":"email","providers":["email"]}', '{}'),
    ('10000000-0000-4000-8000-000000000003', 'authenticated', 'authenticated', 'spec02-admin-one@example.test', '{"provider":"email","providers":["email"]}', '{}'),
    ('10000000-0000-4000-8000-000000000004', 'authenticated', 'authenticated', 'spec02-admin-two@example.test', '{"provider":"email","providers":["email"]}', '{}')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.organizations (id, name)
VALUES ('20000000-0000-4000-8000-000000000001', 'SPEC-02 test organization')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.roles (id, name, role_type, organization_id, is_active)
VALUES
    ('30000000-0000-4000-8000-000000000001', 'practitioner', 'organization', '20000000-0000-4000-8000-000000000001', true),
    ('30000000-0000-4000-8000-000000000002', 'patient', 'system', NULL, true),
    ('30000000-0000-4000-8000-000000000003', 'super_admin', 'system', NULL, true),
    ('30000000-0000-4000-8000-000000000004', 'doctor', 'organization', '20000000-0000-4000-8000-000000000001', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.permissions (id, name, description)
VALUES ('40000000-0000-4000-8000-000000000001', 'spec02.test.permission', 'SPEC-02 lifecycle test fixture')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.role_permissions (role_id, permission_id)
VALUES ('30000000-0000-4000-8000-000000000001', '40000000-0000-4000-8000-000000000001')
ON CONFLICT DO NOTHING;

INSERT INTO public.user_roles (user_id, role_id, organization_id)
VALUES
    ('10000000-0000-4000-8000-000000000003', '30000000-0000-4000-8000-000000000003', NULL),
    ('10000000-0000-4000-8000-000000000004', '30000000-0000-4000-8000-000000000003', NULL)
ON CONFLICT DO NOTHING;

-- Grants and RLS policy structure: client roles must not write assignments.
SELECT ok(
    (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.user_roles'::regclass),
    'RLS remains enabled on user_roles'
);
SELECT ok(
    (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.role_assignment_audit'::regclass),
    'RLS is enabled on the assignment audit table'
);
SELECT ok(NOT has_table_privilege('anon', 'public.user_roles', 'INSERT'), 'anon cannot insert assignments');
SELECT ok(NOT has_table_privilege('anon', 'public.user_roles', 'UPDATE'), 'anon cannot update assignments');
SELECT ok(NOT has_table_privilege('anon', 'public.user_roles', 'DELETE'), 'anon cannot delete assignments');
SELECT ok(NOT has_table_privilege('authenticated', 'public.user_roles', 'INSERT'), 'authenticated cannot insert assignments');
SELECT ok(NOT has_table_privilege('authenticated', 'public.user_roles', 'UPDATE'), 'authenticated cannot update assignments');
SELECT ok(NOT has_table_privilege('authenticated', 'public.user_roles', 'DELETE'), 'authenticated cannot delete assignments');
SELECT ok(
    NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_roles'
          AND cmd IN ('INSERT', 'UPDATE', 'DELETE', 'ALL')
          AND roles && ARRAY['anon', 'authenticated', 'public']::name[]
    ),
    'no permissive client role-assignment write policy remains'
);
SELECT ok(NOT has_table_privilege('anon', 'public.role_assignment_audit', 'SELECT'), 'anon cannot read the audit table');
SELECT ok(NOT has_table_privilege('authenticated', 'public.role_assignment_audit', 'SELECT'), 'authenticated cannot read the audit table');
SELECT ok(has_table_privilege('service_role', 'public.role_assignment_audit', 'INSERT'), 'service_role can append audit events');
SELECT ok(NOT has_table_privilege('service_role', 'public.role_assignment_audit', 'UPDATE'), 'service_role cannot update audit events');
SELECT ok(NOT has_table_privilege('service_role', 'public.role_assignment_audit', 'DELETE'), 'service_role cannot delete audit events');
SELECT ok(
    NOT has_function_privilege('anon', 'public.change_user_role_assignment(uuid,uuid,uuid,uuid,text,text,text)', 'EXECUTE'),
    'anon cannot execute the trusted assignment function'
);
SELECT ok(
    NOT has_function_privilege('authenticated', 'public.change_user_role_assignment(uuid,uuid,uuid,uuid,text,text,text)', 'EXECUTE'),
    'authenticated cannot execute the trusted assignment function'
);
SELECT ok(
    has_function_privilege('service_role', 'public.change_user_role_assignment(uuid,uuid,uuid,uuid,text,text,text)', 'EXECUTE'),
    'service_role can execute the trusted assignment function'
);

-- The function gates on the request JWT role. These calls execute in the test
-- transaction and all fixture writes are rolled back at the end of this file.
SET LOCAL request.jwt.claim.role = 'service_role';

SELECT is(
    public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001',
        'user', 'assign', 'SPEC-02 test grant'
    ) ->> 'status',
    'active',
    'trusted grant creates an active scoped assignment'
);
SELECT ok(
    EXISTS (
        SELECT 1 FROM public.get_user_permissions('10000000-0000-4000-8000-000000000002')
        WHERE permission = 'spec02.test.permission'
    ),
    'active assignments contribute permissions'
);
SELECT is(
    (SELECT count(*)::integer FROM public.role_assignment_audit
     WHERE user_id = '10000000-0000-4000-8000-000000000002'
       AND role_id = '30000000-0000-4000-8000-000000000001'
       AND action = 'assigned'),
    1,
    'grant appends one audit event'
);

SELECT is(
    public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001',
        'user', 'revoke', 'SPEC-02 test revocation'
    ) ->> 'status',
    'revoked',
    'trusted revoke transitions the assignment to revoked'
);
SELECT ok(
    NOT EXISTS (
        SELECT 1 FROM public.get_user_permissions('10000000-0000-4000-8000-000000000002')
        WHERE permission = 'spec02.test.permission'
    ),
    'revoked assignments no longer grant permissions'
);
SELECT is(
    (SELECT reason FROM public.role_assignment_audit
     WHERE user_id = '10000000-0000-4000-8000-000000000002'
       AND role_id = '30000000-0000-4000-8000-000000000001'
       AND action = 'revoked'),
    'SPEC-02 test revocation',
    'revocation reason is recorded in the audit event'
);

SELECT is(
    public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001',
        'user', 'assign', 'SPEC-02 test regrant'
    ) ->> 'status',
    'active',
    'regrant reactivates the scoped assignment'
);
SELECT ok(
    EXISTS (
        SELECT 1 FROM public.get_user_permissions('10000000-0000-4000-8000-000000000002')
        WHERE permission = 'spec02.test.permission'
    ),
    'regranted assignment restores permissions'
);
SELECT is(
    (SELECT count(*)::integer FROM public.role_assignment_audit
     WHERE user_id = '10000000-0000-4000-8000-000000000002'
       AND role_id = '30000000-0000-4000-8000-000000000001'),
    3,
    'grant, revoke, and regrant each append an audit event'
);

SELECT throws_ok(
    $$SELECT public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001', 'user', 'assign', 'duplicate')$$,
    '23505', 'role assignment is already active',
    'duplicate active grant is rejected'
);
SELECT throws_ok(
    $$SELECT public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000001',
        '30000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001', 'user', 'assign', 'self grant')$$,
    '42501', 'self-assignment is forbidden',
    'self-assignment is rejected'
);
SELECT throws_ok(
    $$SELECT public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000002', NULL,
        '10000000-0000-4000-8000-000000000001', 'user', 'assign', 'patient')$$,
    '42501', 'patient roles are assigned only by onboarding',
    'user-driven patient assignment is rejected'
);
SELECT is(
    public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000002', NULL,
        NULL, 'system', 'assign', 'trusted test onboarding'
    ) ->> 'status',
    'active',
    'trusted onboarding may assign a global patient role'
);
SELECT throws_ok(
    $$SELECT public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000002', NULL,
        NULL, 'system', 'assign', 'duplicate global patient')$$,
    '23505', 'role assignment is already active',
    'NULL organization scope still prevents duplicate global grants'
);
SELECT throws_ok(
    $$SELECT public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000099',
        '10000000-0000-4000-8000-000000000001', 'user', 'assign', 'wrong scope')$$,
    '22023', 'invalid organization role scope',
    'organization role scope mismatch is rejected'
);
SELECT throws_ok(
    $$SELECT public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000004',
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001', 'user', 'assign', 'inactive role')$$,
    '23503', 'role is missing or inactive',
    'inactive role definitions cannot be assigned'
);

SET LOCAL request.jwt.claim.role = 'authenticated';
SELECT throws_ok(
    $$SELECT public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000002',
        '30000000-0000-4000-8000-000000000001',
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001', 'user', 'assign', 'untrusted call')$$,
    '42501', 'role assignment RPC is restricted to the trusted backend',
    'authenticated JWT cannot use the trusted function'
);
SET LOCAL request.jwt.claim.role = 'service_role';

SELECT is(
    public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000003',
        '30000000-0000-4000-8000-000000000003', NULL,
        '10000000-0000-4000-8000-000000000001', 'user', 'revoke', 'remove one admin'
    ) ->> 'status',
    'revoked',
    'one system administrator can be revoked while another remains active'
);
SELECT throws_ok(
    $$SELECT public.change_user_role_assignment(
        '10000000-0000-4000-8000-000000000004',
        '30000000-0000-4000-8000-000000000003', NULL,
        '10000000-0000-4000-8000-000000000001', 'user', 'revoke', 'remove final admin')$$,
    '23514', 'cannot revoke the final active system administrator',
    'the final active system administrator is protected'
);
SELECT is(
    (SELECT count(DISTINCT user_id)::integer FROM public.user_roles
     WHERE role_id = '30000000-0000-4000-8000-000000000003'
       AND organization_id IS NULL AND status = 'active'),
    1,
    'failed final-admin revocation leaves the remaining admin active'
);

SELECT * FROM finish();
ROLLBACK;

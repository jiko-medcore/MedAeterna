BEGIN;

SELECT plan(10);

SELECT ok(
    (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.user_roles'::regclass),
    'RLS remains enabled on user_roles'
);

SELECT ok(
    NOT has_table_privilege('anon', 'public.user_roles', 'INSERT')
    AND NOT has_table_privilege('anon', 'public.user_roles', 'SELECT')
    AND NOT has_table_privilege('anon', 'public.user_roles', 'UPDATE')
    AND NOT has_table_privilege('anon', 'public.user_roles', 'DELETE')
    AND NOT has_table_privilege('anon', 'public.user_roles', 'TRUNCATE'),
    'anon cannot modify or truncate role assignments'
);

SELECT ok(
    has_table_privilege('authenticated', 'public.user_roles', 'SELECT')
    AND NOT has_table_privilege('authenticated', 'public.user_roles', 'INSERT')
    AND NOT has_table_privilege('authenticated', 'public.user_roles', 'UPDATE')
    AND NOT has_table_privilege('authenticated', 'public.user_roles', 'DELETE')
    AND NOT has_table_privilege('authenticated', 'public.user_roles', 'TRUNCATE'),
    'authenticated cannot modify or truncate role assignments'
);

SELECT ok(
    has_table_privilege('service_role', 'public.user_roles', 'SELECT')
    AND has_table_privilege('service_role', 'public.user_roles', 'INSERT')
    AND has_table_privilege('service_role', 'public.user_roles', 'UPDATE')
    AND has_table_privilege('service_role', 'public.user_roles', 'DELETE'),
    'service_role retains the DML required by the trusted backend'
);

SELECT ok(
    NOT has_table_privilege('service_role', 'public.user_roles', 'TRUNCATE'),
    'service_role cannot truncate role assignments'
);

SELECT ok(
    NOT has_table_privilege('service_role', 'public.user_roles', 'REFERENCES')
    AND NOT has_table_privilege('service_role', 'public.user_roles', 'TRIGGER')
    AND NOT has_table_privilege('service_role', 'public.user_roles', 'MAINTAIN'),
    'service_role has no unnecessary table-level capabilities'
);

SELECT ok(
    (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.role_assignment_audit'::regclass),
    'RLS remains enabled on the role assignment audit table'
);

SELECT ok(
    NOT has_table_privilege('anon', 'public.role_assignment_audit', 'SELECT')
    AND NOT has_table_privilege('authenticated', 'public.role_assignment_audit', 'SELECT'),
    'client roles cannot read the role assignment audit table'
);

SELECT ok(
    has_table_privilege('service_role', 'public.role_assignment_audit', 'INSERT')
    AND NOT has_table_privilege('service_role', 'public.role_assignment_audit', 'UPDATE')
    AND NOT has_table_privilege('service_role', 'public.role_assignment_audit', 'DELETE')
    AND NOT has_table_privilege('service_role', 'public.role_assignment_audit', 'TRUNCATE'),
    'service_role can append audit events but cannot rewrite or truncate them'
);

SELECT ok(
    NOT has_function_privilege(
        'anon',
        'public.change_user_role_assignment(uuid,uuid,uuid,uuid,text,text,text)',
        'EXECUTE'
    )
    AND NOT has_function_privilege(
        'authenticated',
        'public.change_user_role_assignment(uuid,uuid,uuid,uuid,text,text,text)',
        'EXECUTE'
    )
    AND has_function_privilege(
        'service_role',
        'public.change_user_role_assignment(uuid,uuid,uuid,uuid,text,text,text)',
        'EXECUTE'
    ),
    'only service_role can execute the trusted role assignment function'
);

SELECT * FROM finish();
ROLLBACK;

-- SPEC-02: remove legacy privileges that can bypass row-level policies.
-- TRUNCATE and MAINTAIN are table-level capabilities and are not constrained
-- by row-level security.
REVOKE ALL ON TABLE public.user_roles
    FROM PUBLIC, anon, authenticated, service_role;

-- Preserve role visibility subject to the existing RLS policy.
GRANT SELECT ON TABLE public.user_roles TO anon, authenticated;

-- The backend's service-role client performs the authorized write workflow.
-- Grant only the DML needed by that trusted path.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE public.user_roles TO service_role;

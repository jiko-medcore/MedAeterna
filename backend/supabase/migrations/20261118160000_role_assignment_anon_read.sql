-- SPEC-02: anonymous clients have no reason to query role assignments.
-- Authenticated clients retain SELECT, constrained by the existing RLS policy.
REVOKE SELECT ON TABLE public.user_roles FROM anon;

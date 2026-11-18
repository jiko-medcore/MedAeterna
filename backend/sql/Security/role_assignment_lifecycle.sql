-- SPEC-02: role assignment lifecycle and trusted write path.
-- Apply this migration before deploying code that filters on user_roles.status.

ALTER TABLE public.user_roles
    ADD COLUMN IF NOT EXISTS id uuid,
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS assigned_by uuid REFERENCES auth.users(id),
    ADD COLUMN IF NOT EXISTS revoked_at timestamptz,
    ADD COLUMN IF NOT EXISTS revoked_by uuid REFERENCES auth.users(id),
    ADD COLUMN IF NOT EXISTS revocation_reason text;

UPDATE public.user_roles SET id = gen_random_uuid() WHERE id IS NULL;
ALTER TABLE public.user_roles ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE public.user_roles ALTER COLUMN id SET NOT NULL;
ALTER TABLE public.user_roles ALTER COLUMN organization_id DROP NOT NULL;

DO $$
DECLARE
    existing_pk text;
BEGIN
    SELECT conname INTO existing_pk
    FROM pg_constraint
    WHERE conrelid = 'public.user_roles'::regclass
      AND contype = 'p';

    IF existing_pk IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.user_roles DROP CONSTRAINT %I', existing_pk);
    END IF;

    ALTER TABLE public.user_roles ADD CONSTRAINT user_roles_pkey PRIMARY KEY (id);
END $$;

ALTER TABLE public.user_roles DROP CONSTRAINT IF EXISTS unique_user_role_org;
CREATE UNIQUE INDEX IF NOT EXISTS user_roles_assignment_identity_uq
    ON public.user_roles (user_id, role_id, organization_id) NULLS NOT DISTINCT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.user_roles'::regclass
          AND conname = 'user_roles_status_check'
    ) THEN
        ALTER TABLE public.user_roles
            ADD CONSTRAINT user_roles_status_check
            CHECK (status IN ('active', 'revoked'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.user_roles'::regclass
          AND conname = 'user_roles_revocation_state_check'
    ) THEN
        ALTER TABLE public.user_roles
            ADD CONSTRAINT user_roles_revocation_state_check
            CHECK (
                (status = 'active' AND revoked_at IS NULL AND revoked_by IS NULL)
                OR (status = 'revoked' AND revoked_at IS NOT NULL)
            );
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.role_assignment_audit (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    role_id uuid NOT NULL,
    organization_id uuid,
    action text NOT NULL CHECK (action IN ('assigned', 'revoked')),
    actor_id uuid,
    actor_type text NOT NULL CHECK (actor_type IN ('user', 'system')),
    reason text,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.role_assignment_audit ENABLE ROW LEVEL SECURITY;
-- Remove inherited/default table privileges as well as client grants. The
-- service role may append/read audit events but must not rewrite or erase them.
REVOKE ALL ON public.role_assignment_audit FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT ON public.role_assignment_audit TO service_role;

-- Remove every client-writable policy, including historically named permissive
-- policies. Keep SELECT policies (for example, users reading their own roles).
DO $$
DECLARE
    policy_row record;
BEGIN
    FOR policy_row IN
        SELECT policyname
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_roles'
          AND cmd IN ('INSERT', 'UPDATE', 'DELETE', 'ALL')
    LOOP
        EXECUTE format('DROP POLICY %I ON public.user_roles', policy_row.policyname);
    END LOOP;
END $$;

CREATE POLICY "Trusted service manages role assignments"
    ON public.user_roles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Clear every inherited/direct privilege first. Revoking only DML leaves
-- legacy service_role privileges such as TRUNCATE and MAINTAIN in place.
REVOKE ALL ON public.user_roles FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON public.user_roles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_roles TO service_role;

CREATE OR REPLACE FUNCTION public.change_user_role_assignment(
    p_user_id uuid,
    p_role_id uuid,
    p_organization_id uuid,
    p_actor_id uuid,
    p_actor_type text,
    p_action text,
    p_reason text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    role_row public.roles%ROWTYPE;
    assignment_row public.user_roles%ROWTYPE;
    event_action text;
    active_system_admins bigint;
BEGIN
    IF auth.role() <> 'service_role' THEN
        RAISE EXCEPTION 'role assignment RPC is restricted to the trusted backend'
            USING ERRCODE = '42501';
    END IF;
    IF p_actor_type NOT IN ('user', 'system') OR p_action NOT IN ('assign', 'revoke') THEN
        RAISE EXCEPTION 'invalid role change metadata' USING ERRCODE = '22023';
    END IF;

    SELECT * INTO role_row
    FROM public.roles
    WHERE id = p_role_id;
    IF NOT FOUND OR role_row.is_active IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'role is missing or inactive' USING ERRCODE = '23503';
    END IF;

    IF role_row.role_type = 'system' THEN
        IF role_row.organization_id IS NOT NULL OR p_organization_id IS NOT NULL
           OR role_row.name NOT IN ('patient', 'super_admin') THEN
            RAISE EXCEPTION 'invalid system role scope' USING ERRCODE = '22023';
        END IF;
    ELSIF role_row.role_type = 'organization' THEN
        IF p_organization_id IS NULL OR role_row.organization_id IS DISTINCT FROM p_organization_id THEN
            RAISE EXCEPTION 'invalid organization role scope' USING ERRCODE = '22023';
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid role type' USING ERRCODE = '22023';
    END IF;

    IF p_action = 'assign' THEN
        IF role_row.name = 'patient' AND p_actor_type <> 'system' THEN
            RAISE EXCEPTION 'patient roles are assigned only by onboarding' USING ERRCODE = '42501';
        END IF;
        IF p_actor_type = 'user' AND p_actor_id IS NOT DISTINCT FROM p_user_id THEN
            RAISE EXCEPTION 'self-assignment is forbidden' USING ERRCODE = '42501';
        END IF;

        INSERT INTO public.user_roles (
            user_id, role_id, organization_id, assigned_at, assigned_by,
            status, revoked_at, revoked_by, revocation_reason
        ) VALUES (
            p_user_id, p_role_id, p_organization_id, now(), p_actor_id,
            'active', NULL, NULL, NULL
        )
        ON CONFLICT (user_id, role_id, organization_id) DO UPDATE SET
            assigned_at = now(),
            assigned_by = EXCLUDED.assigned_by,
            status = 'active',
            revoked_at = NULL,
            revoked_by = NULL,
            revocation_reason = NULL
        WHERE public.user_roles.status = 'revoked'
        RETURNING * INTO assignment_row;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'role assignment is already active' USING ERRCODE = '23505';
        END IF;
        event_action := 'assigned';
    ELSE
        IF role_row.name = 'super_admin' AND role_row.role_type = 'system' THEN
            PERFORM pg_advisory_xact_lock(hashtextextended('medaeterna:super-admin-revocation', 0));
            SELECT count(DISTINCT ur.user_id)
            INTO active_system_admins
            FROM public.user_roles ur
            JOIN public.roles r ON r.id = ur.role_id
            WHERE r.name = 'super_admin'
              AND r.role_type = 'system'
              AND r.is_active IS TRUE
              AND ur.organization_id IS NULL
              AND ur.status = 'active';
            IF active_system_admins <= 1 THEN
                RAISE EXCEPTION 'cannot revoke the final active system administrator'
                    USING ERRCODE = '23514';
            END IF;
        END IF;

        UPDATE public.user_roles
        SET status = 'revoked',
            revoked_at = now(),
            revoked_by = p_actor_id,
            revocation_reason = NULLIF(btrim(p_reason), '')
        WHERE user_id = p_user_id
          AND role_id = p_role_id
          AND organization_id IS NOT DISTINCT FROM p_organization_id
          AND status = 'active'
        RETURNING * INTO assignment_row;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'active role assignment not found' USING ERRCODE = 'P0002';
        END IF;
        event_action := 'revoked';
    END IF;

    INSERT INTO public.role_assignment_audit (
        user_id, role_id, organization_id, action, actor_id, actor_type, reason
    ) VALUES (
        p_user_id, p_role_id, p_organization_id, event_action, p_actor_id,
        p_actor_type, NULLIF(btrim(p_reason), '')
    );

    RETURN jsonb_build_object(
        'id', assignment_row.id,
        'user_id', assignment_row.user_id,
        'role_id', assignment_row.role_id,
        'organization_id', assignment_row.organization_id,
        'status', assignment_row.status,
        'assigned_at', assignment_row.assigned_at,
        'assigned_by', assignment_row.assigned_by,
        'revoked_at', assignment_row.revoked_at,
        'revoked_by', assignment_row.revoked_by,
        'revocation_reason', assignment_row.revocation_reason
    );
END;
$$;

REVOKE ALL ON FUNCTION public.change_user_role_assignment(uuid, uuid, uuid, uuid, text, text, text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.change_user_role_assignment(uuid, uuid, uuid, uuid, text, text, text)
    TO service_role;

-- Permissions must not survive assignment or role-definition deactivation.
CREATE OR REPLACE FUNCTION public.get_user_permissions(uid uuid)
RETURNS TABLE(permission text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT p.name
    FROM public.user_roles ur
    JOIN public.roles r ON r.id = ur.role_id
    JOIN public.role_permissions rp ON rp.role_id = ur.role_id
    JOIN public.permissions p ON p.id = rp.permission_id
    WHERE ur.user_id = uid
      AND ur.status = 'active'
      AND r.is_active IS TRUE;
$$;

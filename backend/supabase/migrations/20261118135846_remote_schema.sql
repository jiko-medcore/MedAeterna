SET local check_function_bodies = off;

CREATE SEQUENCE "public"."patient_medical_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

CREATE TABLE "public"."audit_logs" (
  "id"            uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "actor_id"      uuid,
  "actor_type"    text,
  "action"        text                     NOT NULL,
  "resource_type" text                     NOT NULL,
  "resource_id"   text                     NOT NULL,
  "metadata"      jsonb                    DEFAULT '{}'::jsonb,
  "created_at"    timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT "audit_logs_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."audit_logs"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."care_teams" (
  "id"           uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "patient_id"   uuid                     NOT NULL,
  "clinician_id" uuid                     NOT NULL,
  "role"         text                     NOT NULL DEFAULT 'primary'::text,
  "assigned_at"  timestamp with time zone DEFAULT now(),
  CONSTRAINT "care_teams_patient_id_clinician_id_key" UNIQUE (patient_id, clinician_id),
  CONSTRAINT "care_teams_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."care_teams"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."clinicians_patients" (
  "clinician_id" uuid                     NOT NULL,
  "patient_id"   uuid                     NOT NULL,
  "role"         text                     NOT NULL,
  "active"       boolean                  DEFAULT true,
  "assigned_at"  timestamp with time zone DEFAULT now(),
  "assigned_by"  uuid,
  CONSTRAINT "clinicians_patients_pkey" PRIMARY KEY (clinician_id, patient_id),
  CONSTRAINT "clinicians_patients_role_check" CHECK ((role = ANY (ARRAY['primary'::text, 'consulting'::text, 'emergency'::text])))
);

ALTER TABLE "public"."clinicians_patients"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."consent_records" (
  "id"               uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "patient_id"       uuid                     NOT NULL,
  "organization_id"  uuid,
  "practitioner_id"  uuid,
  "granted_by"       uuid,
  "consent_type"     text,
  "access_level"     text,
  "purpose_of_use"   text,
  "legal_basis"      text,
  "status"           text                     DEFAULT 'active'::text,
  "emergency_access" boolean                  DEFAULT false,
  "otp_verified"     boolean                  DEFAULT false,
  "granted_at"       timestamp with time zone DEFAULT now(),
  "effective_from"   timestamp with time zone,
  "expires_at"       timestamp with time zone,
  "revoked_at"       timestamp with time zone,
  "revoked_reason"   text,
  "metadata"         jsonb,
  "fhir_resource"    jsonb,
  "created_at"       timestamp with time zone DEFAULT now(),
  "updated_at"       timestamp with time zone DEFAULT now(),
  CONSTRAINT "consent_records_access_level_check" CHECK ((access_level = ANY (ARRAY['read'::text, 'write'::text, 'full'::text]))),
  CONSTRAINT "consent_records_consent_type_check"
    CHECK ((consent_type = ANY (ARRAY['treatment'::text, 'emergency'::text, 'research'::text, 'telemedicine'::text, 'data_sharing'::text]))),
  CONSTRAINT "consent_records_pkey" PRIMARY KEY (id),
  CONSTRAINT "consent_records_status_check" CHECK ((status = ANY (ARRAY['draft'::text, 'active'::text, 'revoked'::text, 'expired'::text, 'rejected'::text])))
);

ALTER TABLE "public"."consent_records"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."departments" (
  "id"                   uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "organization_id"      uuid                     NOT NULL,
  "parent_department_id" uuid,
  "name"                 text                     NOT NULL,
  "code"                 text,
  "description"          text,
  "active"               boolean                  NOT NULL DEFAULT true,
  "created_by"           uuid,
  "updated_by"           uuid,
  "created_at"           timestamp with time zone NOT NULL DEFAULT now(),
  "updated_at"           timestamp with time zone NOT NULL DEFAULT now(),
  "deleted_at"           timestamp with time zone,
  CONSTRAINT "departments_pkey" PRIMARY KEY (id),
  CONSTRAINT "unique_department_name_per_organization" UNIQUE (organization_id, name)
);

ALTER TABLE "public"."departments"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."events_dead_letter" (
  "id"                uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "original_event_id" uuid                     NOT NULL,
  "aggregate_type"    text                     NOT NULL,
  "aggregate_id"      text                     NOT NULL,
  "event_type"        text                     NOT NULL,
  "payload"           jsonb,
  "retry_count"       integer                  NOT NULL,
  "failure_reason"    text                     NOT NULL,
  "replayed"          boolean                  NOT NULL DEFAULT false,
  "replayed_at"       timestamp with time zone NOT NULL,
  "replayed_by"       uuid,
  "failed_at"         timestamp with time zone DEFAULT now(),
  CONSTRAINT "events_dead_letter_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."events_dead_letter"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."events" (
  "id"              uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "aggregate_type"  text                     NOT NULL,
  "aggregate_id"    uuid                     NOT NULL,
  "event_type"      text                     NOT NULL,
  "payload"         jsonb                    DEFAULT '{}'::jsonb,
  "status"          text                     DEFAULT 'pending'::text,
  "created_at"      timestamp with time zone DEFAULT now(),
  "processed_at"    timestamp with time zone,
  "failure_reason"  text,
  "retry_count"     integer                  DEFAULT 0,
  "last_attempt_at" timestamp with time zone,
  "locked_at"       timestamp with time zone,
  "next_retry_at"   timestamp with time zone,
  "last_error"      text,
  CONSTRAINT "events_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."events"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."healthcare_services" (
  "id"                       uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "organization_id"          uuid                     NOT NULL,
  "department_id"            uuid,
  "name"                     text                     NOT NULL,
  "description"              text,
  "active"                   boolean                  NOT NULL DEFAULT true,
  "category"                 text,
  "type"                     text,
  "specialty"                text,
  "appointment_required"     boolean                  NOT NULL DEFAULT true,
  "referral_required"        boolean                  NOT NULL DEFAULT false,
  "online_booking_available" boolean                  NOT NULL DEFAULT false,
  "phone"                    text,
  "email"                    text,
  "website"                  text,
  "service_code"             text,
  "display_order"            integer                  DEFAULT 0,
  "deleted_at"               timestamp with time zone,
  "created_by"               uuid,
  "updated_by"               uuid,
  "created_at"               timestamp with time zone NOT NULL DEFAULT now(),
  "updated_at"               timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT "healthcare_services_name_org_unique" UNIQUE (organization_id, name),
  CONSTRAINT "healthcare_services_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."healthcare_services"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."invitations" (
  "id"              uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "email"           text                     NOT NULL,
  "organization_id" uuid,
  "role_name"       text                     NOT NULL,
  "invited_by"      uuid,
  "token"           text                     NOT NULL,
  "status"          text                     DEFAULT 'pending'::text,
  "expires_at"      timestamp with time zone,
  "created_at"      timestamp with time zone DEFAULT now(),
  CONSTRAINT "invitations_pkey" PRIMARY KEY (id),
  CONSTRAINT "invitations_status_check" CHECK ((status = ANY (ARRAY['pending'::text, 'accepted'::text, 'expired'::text]))),
  CONSTRAINT "invitations_token_key" UNIQUE (token)
);

ALTER TABLE "public"."invitations"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."lab_results" (
  "id"           uuid                        NOT NULL DEFAULT gen_random_uuid(),
  "patient_id"   uuid,
  "clinician_id" uuid,
  "test_name"    text,
  "status"       text,
  "result_data"  jsonb,
  "file_url"     text,
  "performed_at" timestamp without time zone,
  "created_at"   timestamp without time zone DEFAULT now(),
  CONSTRAINT "lab_results_pkey" PRIMARY KEY (id),
  CONSTRAINT "lab_results_status_check" CHECK ((status = ANY (ARRAY['pending'::text, 'completed'::text, 'reviewed'::text])))
);

ALTER TABLE "public"."lab_results"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."medical_records" (
  "id"            uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "patient_id"    uuid,
  "clinician_id"  uuid,
  "record_type"   text                     NOT NULL,
  "recorded_at"   timestamp with time zone DEFAULT timezone('utc'::text, now()),
  "clinical_data" jsonb                    NOT NULL,
  "created_at"    timestamp with time zone DEFAULT timezone('utc'::text, now()),
  "updated_by"    uuid,
  "updated_at"    timestamp with time zone DEFAULT timezone('utc'::text, now()),
  CONSTRAINT "medical_records_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."medical_records"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."organization_operating_hours" (
  "id"              uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "organization_id" uuid                     NOT NULL,
  "day_of_week"     smallint                 NOT NULL,
  "slot_index"      smallint                 NOT NULL DEFAULT 0,
  "opens_at"        time without time zone,
  "closes_at"       time without time zone,
  "is_closed"       boolean                  NOT NULL DEFAULT false,
  "created_by"      uuid,
  "updated_by"      uuid,
  "deleted_at"      timestamp with time zone,
  "created_at"      timestamp with time zone NOT NULL DEFAULT now(),
  "updated_at"      timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT "operating_hours_slot_unique" UNIQUE (organization_id, day_of_week, slot_index),
  CONSTRAINT "operating_hours_time_shape" CHECK (((is_closed AND (opens_at IS NULL) AND (closes_at IS NULL)) OR ((NOT is_closed) AND (opens_at IS NOT NULL) AND (closes_at IS
    NOT NULL) AND (opens_at < closes_at)))),
  CONSTRAINT "organization_operating_hours_day_of_week_check" CHECK (((day_of_week >= 0) AND (day_of_week <= 6))),
  CONSTRAINT "organization_operating_hours_pkey" PRIMARY KEY (id),
  CONSTRAINT "organization_operating_hours_slot_index_check" CHECK ((slot_index >= 0))
);

ALTER TABLE "public"."organization_operating_hours"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."organizations" (
  "id"                         uuid                        NOT NULL DEFAULT gen_random_uuid(),
  "name"                       text                        NOT NULL,
  "type"                       text,
  "phone"                      text,
  "email"                      text,
  "address"                    text,
  "active"                     boolean                     DEFAULT true,
  "created_at"                 timestamp without time zone DEFAULT now(),
  "state"                      text,
  "country"                    text,
  "logo_url"                   text,
  "onboarding_status"          text                        DEFAULT 'pending'::text,
  "onboarding_email_sent"      boolean                     DEFAULT false,
  "onboarding_email_sent_at"   timestamp with time zone,
  "onboarding_completed"       boolean                     DEFAULT false,
  "onboarding_completed_at"    timestamp with time zone,
  "onboarding_retry_count"     integer                     DEFAULT 0,
  "onboarding_last_attempt_at" timestamp with time zone,
  "onboarding_last_error"      text,
  "onboarding_failure_reason"  text,
  "website"                    text,
  "city"                       text,
  "postal_code"                text,
  "description"                text,
  "timezone"                   text                        DEFAULT 'Africa/Lagos'::text,
  "updated_at"                 timestamp with time zone    DEFAULT now(),
  "logo_path"                  text,
  "primary_color"              character varying(7),
  "secondary_color"            character varying(7),
  CONSTRAINT "chk_timezone_length" CHECK (((timezone IS NULL) OR (length(timezone) <= 100))),
  CONSTRAINT "chk_website_length" CHECK (((website IS NULL) OR (length(website) <= 255))),
  CONSTRAINT "organizations_pkey" PRIMARY KEY (id),
  CONSTRAINT "organizations_primary_color_hex" CHECK (((primary_color IS NULL) OR ((primary_color)::text ~ '^#[0-9A-Fa-f]{6}$'::text))),
  CONSTRAINT "organizations_secondary_color_hex" CHECK (((secondary_color IS NULL) OR ((secondary_color)::text ~ '^#[0-9A-Fa-f]{6}$'::text)))
);

ALTER TABLE "public"."organizations"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."patient_care_team" (
  "id"              uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "patient_id"      uuid                     NOT NULL,
  "practitioner_id" uuid                     NOT NULL,
  "organization_id" uuid                     NOT NULL,
  "role"            text,
  "status"          text                     DEFAULT 'active'::text,
  "start_date"      timestamp with time zone DEFAULT now(),
  "end_date"        timestamp with time zone,
  "assigned_by"     uuid,
  "notes"           text,
  "metadata"        jsonb,
  "fhir_resource"   jsonb,
  "created_at"      timestamp with time zone DEFAULT now(),
  CONSTRAINT "patient_care_team_patient_id_practitioner_id_organization_i_key" UNIQUE (patient_id, practitioner_id, organization_id),
  CONSTRAINT "patient_care_team_pkey" PRIMARY KEY (id),
  CONSTRAINT "patient_care_team_role_check" CHECK ((role = ANY (ARRAY['primary'::text, 'consulting'::text, 'specialist'::text, 'emergency'::text, 'observer'::text]))),
  CONSTRAINT "patient_care_team_status_check" CHECK ((status = ANY (ARRAY['active'::text, 'inactive'::text, 'suspended'::text])))
);

ALTER TABLE "public"."patient_care_team"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."patients" (
  "id"                         uuid                        NOT NULL,
  "first_name"                 text,
  "last_name"                  text,
  "middle_name"                text,
  "date_of_birth"              date,
  "gender"                     text,
  "blood_group"                text,
  "marital_status"             text,
  "phone"                      text,
  "email"                      text,
  "address"                    text,
  "emergency_contact_name"     text,
  "emergency_contact_phone"    text,
  "organization_id"            uuid,
  "active"                     boolean                     DEFAULT true,
  "created_at"                 timestamp without time zone DEFAULT now(),
  "fhir_metadata"              jsonb                       DEFAULT '{}'::jsonb,
  "profile_image_url"          text,
  "identifier_system"          text                        DEFAULT 'https://api.medcore.africa/fhir/identifier/patient'::text,
  "identifier_use"             text                        DEFAULT 'official'::text,
  "onboarding_completed"       boolean                     DEFAULT false,
  "onboarding_completed_at"    timestamp without time zone,
  "onboarding_email_sent"      boolean                     DEFAULT false,
  "onboarding_email_sent_at"   timestamp with time zone,
  "onboarding_retry_count"     integer                     DEFAULT 0,
  "onboarding_status"          text                        DEFAULT 'pending'::text,
  "onboarding_failure_reason"  text,
  "onboarding_last_error"      text,
  "onboarding_last_attempt_at" timestamp with time zone,
  CONSTRAINT "patients_gender_check" CHECK ((gender = ANY (ARRAY['male'::text, 'female'::text, 'other'::text, 'unknown'::text]))),
  CONSTRAINT "patients_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."patients"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."permissions" (
  "id"          uuid NOT NULL DEFAULT gen_random_uuid(),
  "name"        text NOT NULL,
  "description" text,
  CONSTRAINT "permissions_name_key" UNIQUE (name),
  CONSTRAINT "permissions_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."permissions"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."practitioner_roles" (
  "id"              uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "practitioner_id" uuid                     NOT NULL,
  "organization_id" uuid                     NOT NULL,
  "role_code"       text                     NOT NULL,
  "specialty_code"  text,
  "department"      text,
  "location_id"     uuid,
  "active"          boolean                  DEFAULT true,
  "start_date"      timestamp with time zone,
  "end_date"        timestamp with time zone,
  "availability"    jsonb,
  "permissions"     jsonb,
  "fhir_resource"   jsonb,
  "created_at"      timestamp with time zone DEFAULT now(),
  CONSTRAINT "practitioner_roles_pkey" PRIMARY KEY (id),
  CONSTRAINT "practitioner_roles_practitioner_id_organization_id_role_cod_key" UNIQUE (practitioner_id, organization_id, role_code)
);

ALTER TABLE "public"."practitioner_roles"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."practitioners" (
  "id"                        uuid                     NOT NULL,
  "profile_id"                uuid,
  "practitioner_identifier"   text,
  "first_name"                text,
  "last_name"                 text,
  "middle_name"               text,
  "gender"                    text,
  "birth_date"                date,
  "phone"                     text,
  "email"                     text,
  "active"                    boolean                  DEFAULT true,
  "qualifications"            jsonb                    DEFAULT '[]'::jsonb,
  "specialties"               jsonb                    DEFAULT '[]'::jsonb,
  "languages"                 jsonb                    DEFAULT '[]'::jsonb,
  "identifiers"               jsonb                    DEFAULT '[]'::jsonb,
  "telecom"                   jsonb                    DEFAULT '[]'::jsonb,
  "addresses"                 jsonb                    DEFAULT '[]'::jsonb,
  "photo"                     jsonb,
  "communication_preferences" jsonb,
  "fhir_resource"             jsonb,
  "created_at"                timestamp with time zone DEFAULT now(),
  "updated_at"                timestamp with time zone DEFAULT now(),
  CONSTRAINT "practitioners_gender_check" CHECK ((gender = ANY (ARRAY['male'::text, 'female'::text, 'other'::text, 'unknown'::text]))),
  CONSTRAINT "practitioners_pkey" PRIMARY KEY (id),
  CONSTRAINT "practitioners_practitioner_identifier_key" UNIQUE (practitioner_identifier)
);

ALTER TABLE "public"."practitioners"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."prescriptions" (
  "id"           uuid                        NOT NULL DEFAULT gen_random_uuid(),
  "patient_id"   uuid                        NOT NULL,
  "drug_name"    text,
  "category"     text,
  "dosage"       text,
  "instructions" text,
  "start_date"   date,
  "end_date"     date,
  "status"       text,
  "created_at"   timestamp without time zone DEFAULT now(),
  CONSTRAINT "prescriptions_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."prescriptions"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."profiles" (
  "id"         uuid                     NOT NULL,
  "email"      text,
  "full_name"  text,
  "created_at" timestamp with time zone DEFAULT timezone('utc'::text, now()),
  CONSTRAINT "profiles_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."profiles"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."reminders" (
  "id"            uuid                        NOT NULL DEFAULT gen_random_uuid(),
  "patient_id"    uuid,
  "created_by"    uuid,
  "title"         text,
  "description"   text,
  "reminder_date" timestamp without time zone,
  "status"        text,
  "created_at"    timestamp without time zone DEFAULT now(),
  CONSTRAINT "reminders_pkey" PRIMARY KEY (id),
  CONSTRAINT "reminders_status_check" CHECK ((status = ANY (ARRAY['pending'::text, 'done'::text, 'missed'::text])))
);

ALTER TABLE "public"."reminders"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."role_assignment_audit" (
  "id"              uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "user_id"         uuid                     NOT NULL,
  "role_id"         uuid                     NOT NULL,
  "organization_id" uuid,
  "action"          text                     NOT NULL,
  "actor_id"        uuid,
  "actor_type"      text                     NOT NULL,
  "reason"          text,
  "occurred_at"     timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT "role_assignment_audit_action_check" CHECK ((action = ANY (ARRAY['assigned'::text, 'revoked'::text]))),
  CONSTRAINT "role_assignment_audit_actor_type_check" CHECK ((actor_type = ANY (ARRAY['user'::text, 'system'::text]))),
  CONSTRAINT "role_assignment_audit_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."role_assignment_audit"
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "public"."role_assignment_audit" FROM "anon", "authenticated";

CREATE TABLE "public"."role_permissions" (
  "role_id"       uuid NOT NULL,
  "permission_id" uuid NOT NULL,
  CONSTRAINT "role_permissions_pkey" PRIMARY KEY (role_id, permission_id)
);

ALTER TABLE "public"."role_permissions"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."roles" (
  "id"              uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "name"            text                     NOT NULL,
  "description"     text,
  "organization_id" uuid,
  "role_type"       text                     DEFAULT 'organization'::text,
  "is_active"       boolean                  DEFAULT true,
  "created_at"      timestamp with time zone DEFAULT now(),
  "updated_at"      timestamp with time zone DEFAULT now(),
  CONSTRAINT "roles_name_org_unique" UNIQUE (name, organization_id),
  CONSTRAINT "roles_pkey" PRIMARY KEY (id),
  CONSTRAINT "roles_role_type_check" CHECK ((role_type = ANY (ARRAY['system'::text, 'organization'::text])))
);

ALTER TABLE "public"."roles"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."terminology_codes" (
  "id"      uuid NOT NULL DEFAULT gen_random_uuid(),
  "system"  text NOT NULL,
  "code"    text NOT NULL,
  "display" text NOT NULL,
  CONSTRAINT "terminology_codes_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."terminology_codes"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."user_roles" (
  "user_id"           uuid                     NOT NULL,
  "role_id"           uuid                     NOT NULL,
  "assigned_at"       timestamp with time zone DEFAULT now(),
  "organization_id"   uuid,
  "id"                uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "status"            text                     NOT NULL DEFAULT 'active'::text,
  "assigned_by"       uuid,
  "revoked_at"        timestamp with time zone,
  "revoked_by"        uuid,
  "revocation_reason" text,
  CONSTRAINT "user_roles_pkey" PRIMARY KEY (id),
  CONSTRAINT "user_roles_revocation_state_check"
    CHECK ((((status = 'active'::text) AND (revoked_at IS NULL) AND (revoked_by IS NULL)) OR ((status = 'revoked'::text) AND (revoked_at IS NOT NULL)))),
  CONSTRAINT "user_roles_status_check" CHECK ((status = ANY (ARRAY['active'::text, 'revoked'::text])))
);

ALTER TABLE "public"."user_roles"
  ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.can_manage_roles()
  RETURNS boolean
  LANGUAGE sql
  SECURITY DEFINER
  AS $function$
    select exists (
        select 1
        from user_roles ur
        join roles r on ur.role_id = r.id
        where ur.user_id = auth.uid()
        and (
            r.name = 'org_admin'
            or r.role_type = 'system'
        )
    );
$function$;

CREATE OR REPLACE FUNCTION public.change_user_role_assignment (
  p_user_id         uuid,
  p_role_id         uuid,
  p_organization_id uuid,
  p_actor_id        uuid,
  p_actor_type      text,
  p_action          text,
  p_reason          text DEFAULT NULL::text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'pg_catalog', 'public'
  AS $function$
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
$function$;

REVOKE ALL ON FUNCTION "public"."change_user_role_assignment"(uuid, uuid, uuid, uuid, text, text, text) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.generate_patient_medical_id()
  RETURNS text
  LANGUAGE plpgsql
  AS $function$
DECLARE
    seq BIGINT;
BEGIN
    seq := nextval('patient_medical_id_seq');

    RETURN 'MC-NG-P-' || LPAD(seq::TEXT, 10, '0');
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_user_permissions (
  uid uuid
)
  RETURNS TABLE (
    permission text
  )
  LANGUAGE sql
  SECURITY DEFINER
  SET search_path TO 'pg_catalog', 'public'
  AS $function$
    SELECT p.name
    FROM public.user_roles ur
    JOIN public.roles r ON r.id = ur.role_id
    JOIN public.role_permissions rp ON rp.role_id = ur.role_id
    JOIN public.permissions p ON p.id = rp.permission_id
    WHERE ur.user_id = uid
      AND ur.status = 'active'
      AND r.is_active IS TRUE;
$function$;

CREATE OR REPLACE FUNCTION public.is_admin_user()
  RETURNS boolean
  LANGUAGE sql
  SECURITY DEFINER
  AS $function$
    select exists (
        select 1
        from user_roles ur
        join roles r on ur.role_id = r.id
        where ur.user_id = auth.uid()
        and r.name = 'admin'
    );
$function$;

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  AS $function$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$function$;

ALTER TABLE "public"."clinicians_patients"
  ADD CONSTRAINT "clinicians_patients_assigned_by_fkey" FOREIGN KEY (assigned_by) REFERENCES auth.users(id);

ALTER TABLE "public"."clinicians_patients"
  ADD CONSTRAINT "clinicians_patients_clinician_id_fkey" FOREIGN KEY (clinician_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE "public"."departments"
  ADD CONSTRAINT "departments_created_by_fkey" FOREIGN KEY (created_by) REFERENCES auth.users(id);

ALTER TABLE "public"."departments"
  ADD CONSTRAINT "departments_parent_department_id_fkey" FOREIGN KEY (parent_department_id) REFERENCES public.departments(id) ON DELETE SET NULL;

ALTER TABLE "public"."departments"
  ADD CONSTRAINT "departments_updated_by_fkey" FOREIGN KEY (updated_by) REFERENCES auth.users(id);

ALTER TABLE "public"."healthcare_services"
  ADD CONSTRAINT "healthcare_services_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL;

ALTER TABLE "public"."invitations"
  ADD CONSTRAINT "invitations_invited_by_fkey" FOREIGN KEY (invited_by) REFERENCES auth.users(id);

ALTER TABLE "public"."medical_records"
  ADD CONSTRAINT "medical_records_clinician_id_fkey" FOREIGN KEY (clinician_id) REFERENCES auth.users(id);

ALTER TABLE "public"."medical_records"
  ADD CONSTRAINT "medical_records_updated_by_fkey" FOREIGN KEY (updated_by) REFERENCES auth.users(id);

ALTER TABLE "public"."consent_records"
  ADD CONSTRAINT "consent_records_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE "public"."departments"
  ADD CONSTRAINT "departments_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE "public"."healthcare_services"
  ADD CONSTRAINT "healthcare_services_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE "public"."invitations"
  ADD CONSTRAINT "invitations_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE "public"."organization_operating_hours"
  ADD CONSTRAINT "organization_operating_hours_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE "public"."patient_care_team"
  ADD CONSTRAINT "patient_care_team_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE "public"."patients"
  ADD CONSTRAINT "patients_id_fkey" FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE "public"."patients"
  ADD CONSTRAINT "patients_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id);

ALTER TABLE "public"."care_teams"
  ADD CONSTRAINT "care_teams_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES public.patients(id) ON DELETE CASCADE;

ALTER TABLE "public"."clinicians_patients"
  ADD CONSTRAINT "clinicians_patients_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES public.patients(id) ON DELETE CASCADE;

ALTER TABLE "public"."lab_results"
  ADD CONSTRAINT "lab_results_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES public.patients(id);

ALTER TABLE "public"."medical_records"
  ADD CONSTRAINT "medical_records_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES public.patients(id) ON DELETE CASCADE;

ALTER TABLE "public"."practitioner_roles"
  ADD CONSTRAINT "practitioner_roles_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE "public"."practitioners"
  ADD CONSTRAINT "practitioners_id_fkey" FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE "public"."consent_records"
  ADD CONSTRAINT "consent_records_practitioner_id_fkey" FOREIGN KEY (practitioner_id) REFERENCES public.practitioners(id) ON DELETE SET NULL;

ALTER TABLE "public"."patient_care_team"
  ADD CONSTRAINT "patient_care_team_practitioner_id_fkey" FOREIGN KEY (practitioner_id) REFERENCES public.practitioners(id) ON DELETE CASCADE;

ALTER TABLE "public"."practitioner_roles"
  ADD CONSTRAINT "practitioner_roles_practitioner_id_fkey" FOREIGN KEY (practitioner_id) REFERENCES public.practitioners(id) ON DELETE CASCADE;

ALTER TABLE "public"."profiles"
  ADD CONSTRAINT "profiles_id_fkey" FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE "public"."consent_records"
  ADD CONSTRAINT "consent_records_granted_by_fkey" FOREIGN KEY (granted_by) REFERENCES public.profiles(id);

ALTER TABLE "public"."consent_records"
  ADD CONSTRAINT "consent_records_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES public.profiles(id) ON DELETE CASCADE;

ALTER TABLE "public"."patient_care_team"
  ADD CONSTRAINT "patient_care_team_assigned_by_fkey" FOREIGN KEY (assigned_by) REFERENCES public.profiles(id);

ALTER TABLE "public"."patient_care_team"
  ADD CONSTRAINT "patient_care_team_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES public.profiles(id) ON DELETE CASCADE;

ALTER TABLE "public"."practitioners"
  ADD CONSTRAINT "practitioners_profile_id_fkey" FOREIGN KEY (profile_id) REFERENCES public.profiles(id);

ALTER TABLE "public"."reminders"
  ADD CONSTRAINT "reminders_created_by_fkey" FOREIGN KEY (created_by) REFERENCES auth.users(id);

ALTER TABLE "public"."reminders"
  ADD CONSTRAINT "reminders_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES public.patients(id);

ALTER TABLE "public"."role_permissions"
  ADD CONSTRAINT "role_permissions_permission_id_fkey" FOREIGN KEY (permission_id) REFERENCES public.permissions(id) ON DELETE CASCADE;

ALTER TABLE "public"."roles"
  ADD CONSTRAINT "roles_organization_id_fkey" FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;

ALTER TABLE "public"."role_permissions"
  ADD CONSTRAINT "role_permissions_role_id_fkey" FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;

ALTER TABLE "public"."user_roles"
  ADD CONSTRAINT "user_roles_assigned_by_fkey" FOREIGN KEY (assigned_by) REFERENCES auth.users(id);

ALTER TABLE "public"."user_roles"
  ADD CONSTRAINT "user_roles_revoked_by_fkey" FOREIGN KEY (revoked_by) REFERENCES auth.users(id);

ALTER TABLE "public"."user_roles"
  ADD CONSTRAINT "user_roles_role_id_fkey" FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;

ALTER TABLE "public"."user_roles"
  ADD CONSTRAINT "user_roles_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX idx_care_team_org ON public.patient_care_team USING btree (organization_id);

CREATE INDEX idx_care_team_patient ON public.patient_care_team USING btree (patient_id);

CREATE INDEX idx_care_team_practitioner ON public.patient_care_team USING btree (practitioner_id);

CREATE INDEX idx_clinicians_patients_clinician ON public.clinicians_patients USING btree (clinician_id);

CREATE INDEX idx_clinicians_patients_patient ON public.clinicians_patients USING btree (patient_id);

CREATE INDEX idx_consent_fhir ON public.consent_records USING gin (fhir_resource);

CREATE INDEX idx_consent_org ON public.consent_records USING btree (organization_id);

CREATE INDEX idx_consent_patient ON public.consent_records USING btree (patient_id);

CREATE INDEX idx_consent_practitioner ON public.consent_records USING btree (practitioner_id);

CREATE INDEX idx_consent_status ON public.consent_records USING btree (status);

CREATE INDEX idx_departments_active ON public.departments USING btree (active);

CREATE INDEX idx_departments_deleted ON public.departments USING btree (deleted_at);

CREATE INDEX idx_departments_org ON public.departments USING btree (organization_id);

CREATE INDEX idx_departments_parent ON public.departments USING btree (parent_department_id);

CREATE INDEX idx_events_aggregate ON public.events USING btree (aggregate_type, aggregate_id);

CREATE INDEX idx_events_status ON public.events USING btree (status);

CREATE INDEX idx_events_type ON public.events USING btree (event_type);

CREATE INDEX idx_healthcare_services_active ON public.healthcare_services USING btree (active);

CREATE INDEX idx_healthcare_services_category ON public.healthcare_services USING btree (category);

CREATE INDEX idx_healthcare_services_department ON public.healthcare_services USING btree (department_id);

CREATE INDEX idx_healthcare_services_organization ON public.healthcare_services USING btree (organization_id);

CREATE INDEX idx_healthcare_services_specialty ON public.healthcare_services USING btree (specialty);

CREATE INDEX idx_practitioner_fhir ON public.practitioners USING gin (fhir_resource);

CREATE INDEX idx_practitioner_roles_org ON public.practitioner_roles USING btree (organization_id);

CREATE INDEX idx_practitioner_roles_practitioner ON public.practitioner_roles USING btree (practitioner_id);

CREATE INDEX idx_practitioners_active ON public.practitioners USING btree (active);

CREATE INDEX idx_role_permissions_permission ON public.role_permissions USING btree (permission_id);

CREATE INDEX idx_role_permissions_role ON public.role_permissions USING btree (role_id);

CREATE INDEX idx_terminology_search ON public.terminology_codes USING btree (system, display);

CREATE INDEX idx_user_roles_org ON public.user_roles USING btree (organization_id);

CREATE INDEX idx_user_roles_user ON public.user_roles USING btree (user_id);

CREATE INDEX organization_operating_hours_lookup_idx ON public.organization_operating_hours USING btree (organization_id, day_of_week, slot_index)
  WHERE (deleted_at IS NULL);

CREATE INDEX terminology_codes_code_idx ON public.terminology_codes USING btree (code);

CREATE INDEX terminology_codes_system_idx1 ON public.terminology_codes USING btree (system);

CREATE INDEX terminology_codes_system_idx ON public.terminology_codes USING btree (system);

CREATE UNIQUE INDEX user_roles_assignment_identity_uq ON public.user_roles USING btree (user_id, role_id, organization_id) NULLS NOT DISTINCT;

CREATE TRIGGER organizations_updated_at
  BEFORE UPDATE ON public.organizations
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_roles_updated_at
  BEFORE UPDATE ON public.roles
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE POLICY "Clinicians insert records" ON "public"."medical_records"
  FOR INSERT
  TO PUBLIC
  WITH CHECK ((auth.uid() = clinician_id));

CREATE POLICY "Patients read own records" ON "public"."medical_records"
  FOR SELECT
  TO PUBLIC
  USING ((auth.uid() = patient_id));

CREATE POLICY "Patients can insert own data" ON "public"."patients"
  FOR INSERT
  TO PUBLIC
  WITH CHECK ((auth.uid() = id));

CREATE POLICY "Patients can read own data" ON "public"."patients"
  FOR SELECT
  TO PUBLIC
  USING ((auth.uid() = id));

CREATE POLICY "Patients can read own record" ON "public"."patients"
  FOR SELECT
  TO PUBLIC
  USING ((auth.uid() = id));

CREATE POLICY "Patients can update own data" ON "public"."patients"
  FOR UPDATE
  TO PUBLIC
  USING ((auth.uid() = id));

CREATE POLICY "Users can insert own profile" ON "public"."profiles"
  FOR INSERT
  TO PUBLIC
  WITH CHECK ((auth.uid() = id));

CREATE POLICY "Users can read own profile" ON "public"."profiles"
  FOR SELECT
  TO PUBLIC
  USING ((auth.uid() = id));

CREATE POLICY "Read-only terminology" ON "public"."terminology_codes"
  FOR SELECT
  TO PUBLIC
  USING (true);

CREATE POLICY "Trusted service manages role assignments" ON "public"."user_roles"
  FOR ALL
  TO "service_role"
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Users read own roles" ON "public"."user_roles"
  FOR SELECT
  TO PUBLIC
  USING ((auth.uid() = user_id));

GRANT EXECUTE ON FUNCTION "public"."can_manage_roles"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."can_manage_roles"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."can_manage_roles"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."can_manage_roles"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."change_user_role_assignment"(uuid, uuid, uuid, uuid, text, text, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."change_user_role_assignment"(uuid, uuid, uuid, uuid, text, text, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."change_user_role_assignment"(uuid, uuid, uuid, uuid, text, text, text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."generate_patient_medical_id"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."generate_patient_medical_id"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."generate_patient_medical_id"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."generate_patient_medical_id"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."get_user_permissions"(uuid) TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."get_user_permissions"(uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."get_user_permissions"(uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."get_user_permissions"(uuid) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."is_admin_user"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."is_admin_user"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."is_admin_user"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."is_admin_user"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."update_updated_at_column"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."update_updated_at_column"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."update_updated_at_column"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."update_updated_at_column"() TO "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."patient_medical_id_seq" TO "anon", "authenticated";

REVOKE ALL ON SEQUENCE "public"."patient_medical_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."patient_medical_id_seq" TO "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."patient_medical_id_seq" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."audit_logs" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."audit_logs" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."audit_logs" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."audit_logs" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."care_teams" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."care_teams" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."care_teams" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."care_teams" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."clinicians_patients" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."clinicians_patients" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."clinicians_patients" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."clinicians_patients" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."consent_records" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."consent_records" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."consent_records" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."consent_records" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."departments" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."departments" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."departments" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."departments" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."events" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events_dead_letter" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."events_dead_letter" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events_dead_letter" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events_dead_letter" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."healthcare_services" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."healthcare_services" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."healthcare_services" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."healthcare_services" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."invitations" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."invitations" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."invitations" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."invitations" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."lab_results" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."lab_results" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."lab_results" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."lab_results" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."medical_records" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."medical_records" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."medical_records" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."medical_records" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."organization_operating_hours" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."organization_operating_hours" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."organization_operating_hours" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."organization_operating_hours" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."organizations" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."organizations" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."organizations" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."organizations" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."patient_care_team" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."patient_care_team" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."patient_care_team" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."patient_care_team" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."patients" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."patients" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."patients" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."patients" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."permissions" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."permissions" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."permissions" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."permissions" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."practitioner_roles" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."practitioner_roles" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."practitioner_roles" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."practitioner_roles" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."practitioners" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."practitioners" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."practitioners" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."practitioners" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."prescriptions" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."prescriptions" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."prescriptions" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."prescriptions" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."profiles" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."profiles" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."profiles" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."profiles" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."reminders" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."reminders" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."reminders" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."reminders" TO "service_role";

REVOKE ALL ON TABLE "public"."role_assignment_audit" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."role_assignment_audit" TO "postgres";

REVOKE ALL ON TABLE "public"."role_assignment_audit" FROM "service_role";

GRANT INSERT, SELECT ON TABLE "public"."role_assignment_audit" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."role_permissions" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."role_permissions" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."role_permissions" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."role_permissions" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."roles" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."roles" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."roles" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."roles" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."terminology_codes" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."terminology_codes" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."terminology_codes" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."terminology_codes" TO "service_role";

REVOKE ALL ON TABLE "public"."user_roles" FROM "anon";

GRANT MAINTAIN, SELECT ON TABLE "public"."user_roles" TO "anon";

REVOKE ALL ON TABLE "public"."user_roles" FROM "authenticated";

GRANT MAINTAIN, SELECT ON TABLE "public"."user_roles" TO "authenticated";

REVOKE ALL ON TABLE "public"."user_roles" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."user_roles" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."user_roles" TO "service_role";

ALTER TABLE "public"."patients"
  ADD COLUMN "medical_id" text NOT NULL DEFAULT public.generate_patient_medical_id();

ALTER TABLE "public"."patients"
  ADD CONSTRAINT "patients_medical_id_key" UNIQUE (medical_id);

CREATE UNIQUE INDEX idx_patients_medical_id ON public.patients USING btree (medical_id);


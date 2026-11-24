-- PH0-WP-03 local database release candidate (local-only).
--
-- The committed SPEC-11 and SPEC-12 migration files are comment-only no-ops.
-- Their previously applied active statements are replayed here so a clean local
-- reset reproduces the reviewed catalog. This migration then reconciles the
-- application-referenced clinical relations, canonical patient grants, consent
-- lifecycle constraints, sequence/function privileges, default privileges and
-- Data API exposure. No hosted target or production state is referenced.
--
-- Rollback note: this is an additive local migration. Do not down by dropping
-- tables or deleting audit history; disable the client grants and policies
-- introduced here only after an approved replacement migration exists.

-- Replay of the active SPEC-11 statements.
-- SPEC-11: table-by-table RLS, least-privilege grants, and trusted functions.
-- Generated from app/core/table_access_inventory.py. Reviewed tables only;
-- an unregistered table receives no grant and no policy by this migration.

-- 1. Enable and force RLS on every reviewed public table.
alter table public.audit_logs enable row level security;
alter table public.audit_logs force row level security;
alter table public.care_teams enable row level security;
alter table public.care_teams force row level security;
alter table public.clinicians_patients enable row level security;
alter table public.clinicians_patients force row level security;
alter table public.consent_records enable row level security;
alter table public.consent_records force row level security;
alter table public.departments enable row level security;
alter table public.departments force row level security;
alter table public.events enable row level security;
alter table public.events force row level security;
alter table public.events_dead_letter enable row level security;
alter table public.events_dead_letter force row level security;
alter table public.healthcare_services enable row level security;
alter table public.healthcare_services force row level security;
alter table public.invitations enable row level security;
alter table public.invitations force row level security;
alter table public.lab_results enable row level security;
alter table public.lab_results force row level security;
alter table public.medical_records enable row level security;
alter table public.medical_records force row level security;
alter table public.organization_operating_hours enable row level security;
alter table public.organization_operating_hours force row level security;
alter table public.organizations enable row level security;
alter table public.organizations force row level security;
alter table public.patient_care_team enable row level security;
alter table public.patient_care_team force row level security;
alter table public.patients enable row level security;
alter table public.patients force row level security;
alter table public.permissions enable row level security;
alter table public.permissions force row level security;
alter table public.practitioner_roles enable row level security;
alter table public.practitioner_roles force row level security;
alter table public.practitioners enable row level security;
alter table public.practitioners force row level security;
alter table public.prescriptions enable row level security;
alter table public.prescriptions force row level security;
alter table public.profiles enable row level security;
alter table public.profiles force row level security;
alter table public.reminders enable row level security;
alter table public.reminders force row level security;
alter table public.role_assignment_audit enable row level security;
alter table public.role_assignment_audit force row level security;
alter table public.role_permissions enable row level security;
alter table public.role_permissions force row level security;
alter table public.roles enable row level security;
alter table public.roles force row level security;
alter table public.terminology_codes enable row level security;
alter table public.terminology_codes force row level security;
alter table public.user_roles enable row level security;
alter table public.user_roles force row level security;

-- 2. Remove legacy policies. Grants are revoked below, so stale policies
-- cannot survive as a misleading allow path in the catalog.
drop policy if exists "Clinicians insert records" on public.medical_records;
drop policy if exists "Patients read own records" on public.medical_records;
drop policy if exists "Patients can insert own data" on public.patients;
drop policy if exists "Patients can read own data" on public.patients;
drop policy if exists "Patients can read own record" on public.patients;
drop policy if exists "Patients can update own data" on public.patients;
drop policy if exists "Users can insert own profile" on public.profiles;
drop policy if exists "Users can read own profile" on public.profiles;
drop policy if exists "Read-only terminology" on public.terminology_codes;
drop policy if exists "Trusted service manages role assignments" on public.user_roles;
drop policy if exists "Users read own roles" on public.user_roles;

-- 3. Create only the approved policies from the SPEC-11 inventory.
drop policy if exists "Patients read own consent" on public.consent_records;
create policy "Patients read own consent" on public.consent_records for SELECT to authenticated using (patient_id = (select auth.uid()));
drop policy if exists "Patients insert own consent" on public.consent_records;
create policy "Patients insert own consent" on public.consent_records for INSERT to authenticated with check (patient_id = (select auth.uid()));
drop policy if exists "Patients update own consent" on public.consent_records;
create policy "Patients update own consent" on public.consent_records for UPDATE to authenticated using (patient_id = (select auth.uid())) with check (patient_id = (select auth.uid()));
drop policy if exists "Patients read own lab results" on public.lab_results;
create policy "Patients read own lab results" on public.lab_results for SELECT to authenticated using (patient_id = (select auth.uid()));
drop policy if exists "Patients read own medical records" on public.medical_records;
create policy "Patients read own medical records" on public.medical_records for SELECT to authenticated using (patient_id = (select auth.uid()));
drop policy if exists "Patients read own record" on public.patients;
create policy "Patients read own record" on public.patients for SELECT to authenticated using (id = (select auth.uid()));
drop policy if exists "Patients insert own record" on public.patients;
create policy "Patients insert own record" on public.patients for INSERT to authenticated with check (id = (select auth.uid()));
drop policy if exists "Patients update own record" on public.patients;
create policy "Patients update own record" on public.patients for UPDATE to authenticated using (id = (select auth.uid())) with check (id = (select auth.uid()));
drop policy if exists "Practitioners read own roles" on public.practitioner_roles;
create policy "Practitioners read own roles" on public.practitioner_roles for SELECT to authenticated using (practitioner_id in (select p.id from public.practitioners p where p.profile_id = (select auth.uid())));
drop policy if exists "Practitioners read own profile" on public.practitioners;
create policy "Practitioners read own profile" on public.practitioners for SELECT to authenticated using (id = (select auth.uid()) or profile_id = (select auth.uid()));
drop policy if exists "Patients read own prescriptions" on public.prescriptions;
create policy "Patients read own prescriptions" on public.prescriptions for SELECT to authenticated using (patient_id = (select auth.uid()));
drop policy if exists "Users read own profile" on public.profiles;
create policy "Users read own profile" on public.profiles for SELECT to authenticated using (id = (select auth.uid()));
drop policy if exists "Users insert own profile" on public.profiles;
create policy "Users insert own profile" on public.profiles for INSERT to authenticated with check (id = (select auth.uid()));
drop policy if exists "Users update own profile" on public.profiles;
create policy "Users update own profile" on public.profiles for UPDATE to authenticated using (id = (select auth.uid())) with check (id = (select auth.uid()));
drop policy if exists "Patients read own reminders" on public.reminders;
create policy "Patients read own reminders" on public.reminders for SELECT to authenticated using (patient_id = (select auth.uid()));
drop policy if exists "Read-only terminology" on public.terminology_codes;
create policy "Read-only terminology" on public.terminology_codes for SELECT to anon, authenticated using (true);
drop policy if exists "Users read own roles" on public.user_roles;
create policy "Users read own roles" on public.user_roles for SELECT to authenticated using (user_id = (select auth.uid()));
drop policy if exists "Trusted service manages assignments" on public.user_roles;
create policy "Trusted service manages assignments" on public.user_roles for ALL to service_role using (true) with check (true);

-- 4. Revoke every table privilege from client and service roles first.
revoke all on table public.audit_logs from anon, authenticated, service_role;
revoke all on table public.care_teams from anon, authenticated, service_role;
revoke all on table public.clinicians_patients from anon, authenticated, service_role;
revoke all on table public.consent_records from anon, authenticated, service_role;
revoke all on table public.departments from anon, authenticated, service_role;
revoke all on table public.events from anon, authenticated, service_role;
revoke all on table public.events_dead_letter from anon, authenticated, service_role;
revoke all on table public.healthcare_services from anon, authenticated, service_role;
revoke all on table public.invitations from anon, authenticated, service_role;
revoke all on table public.lab_results from anon, authenticated, service_role;
revoke all on table public.medical_records from anon, authenticated, service_role;
revoke all on table public.organization_operating_hours from anon, authenticated, service_role;
revoke all on table public.organizations from anon, authenticated, service_role;
revoke all on table public.patient_care_team from anon, authenticated, service_role;
revoke all on table public.patients from anon, authenticated, service_role;
revoke all on table public.permissions from anon, authenticated, service_role;
revoke all on table public.practitioner_roles from anon, authenticated, service_role;
revoke all on table public.practitioners from anon, authenticated, service_role;
revoke all on table public.prescriptions from anon, authenticated, service_role;
revoke all on table public.profiles from anon, authenticated, service_role;
revoke all on table public.reminders from anon, authenticated, service_role;
revoke all on table public.role_assignment_audit from anon, authenticated, service_role;
revoke all on table public.role_permissions from anon, authenticated, service_role;
revoke all on table public.roles from anon, authenticated, service_role;
revoke all on table public.terminology_codes from anon, authenticated, service_role;
revoke all on table public.user_roles from anon, authenticated, service_role;

-- 5. Grant only the commands in the inventory.
-- anon
grant SELECT on table public.terminology_codes to anon;

-- authenticated
grant INSERT, SELECT, UPDATE on table public.consent_records to authenticated;
grant SELECT on table public.lab_results to authenticated;
grant SELECT on table public.medical_records to authenticated;
grant INSERT, SELECT, UPDATE on table public.patients to authenticated;
grant SELECT on table public.practitioner_roles to authenticated;
grant SELECT on table public.practitioners to authenticated;
grant SELECT on table public.prescriptions to authenticated;
grant INSERT, SELECT, UPDATE on table public.profiles to authenticated;
grant SELECT on table public.reminders to authenticated;
grant SELECT on table public.terminology_codes to authenticated;
grant SELECT on table public.user_roles to authenticated;

-- service_role
grant INSERT, SELECT on table public.audit_logs to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.care_teams to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.clinicians_patients to service_role;
grant INSERT, SELECT, UPDATE on table public.consent_records to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.departments to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.events to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.events_dead_letter to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.healthcare_services to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.invitations to service_role;
grant INSERT, SELECT, UPDATE on table public.lab_results to service_role;
grant INSERT, SELECT, UPDATE on table public.medical_records to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.organization_operating_hours to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.organizations to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.patient_care_team to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.patients to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.permissions to service_role;
grant INSERT, SELECT, UPDATE on table public.practitioner_roles to service_role;
grant INSERT, SELECT, UPDATE on table public.practitioners to service_role;
grant INSERT, SELECT, UPDATE on table public.prescriptions to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.profiles to service_role;
grant INSERT, SELECT, UPDATE on table public.reminders to service_role;
grant INSERT, SELECT on table public.role_assignment_audit to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.role_permissions to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.roles to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.terminology_codes to service_role;
grant DELETE, INSERT, SELECT, UPDATE on table public.user_roles to service_role;

-- 6. Add indexes that support the approved RLS predicates and scoped lookups.
create index if not exists idx_patients_organization_id on public.patients (organization_id);
create index if not exists idx_medical_records_patient_id on public.medical_records (patient_id);
create index if not exists idx_lab_results_patient_id on public.lab_results (patient_id);
create index if not exists idx_lab_results_clinician_id on public.lab_results (clinician_id);
create index if not exists idx_prescriptions_patient_id on public.prescriptions (patient_id);
create index if not exists idx_reminders_patient_id on public.reminders (patient_id);
create index if not exists idx_practitioners_profile_id on public.practitioners (profile_id);
create index if not exists idx_terminology_codes_system_code on public.terminology_codes (system, code);
create index if not exists idx_audit_logs_actor_id on public.audit_logs (actor_id);
create index if not exists idx_audit_logs_created_at on public.audit_logs (created_at);
create index if not exists idx_role_assignment_audit_user_id on public.role_assignment_audit (user_id);
create index if not exists idx_care_teams_clinician_id on public.care_teams (clinician_id);
create index if not exists idx_invitations_organization_id on public.invitations (organization_id);
create index if not exists idx_roles_organization_id on public.roles (organization_id);
create index if not exists idx_roles_is_active on public.roles (is_active);
create index if not exists idx_events_dead_letter_original_event_id on public.events_dead_letter (original_event_id);
create index if not exists idx_events_dead_letter_replayed on public.events_dead_letter (replayed);
create index if not exists idx_events_dead_letter_failed_at on public.events_dead_letter (failed_at);

-- 7. Harden SECURITY DEFINER functions.
revoke all on function public.can_manage_roles() from public, anon, authenticated, service_role;
grant execute on function public.can_manage_roles() to service_role;
alter function public.can_manage_roles() set search_path = pg_catalog, public;
revoke all on function public.change_user_role_assignment(uuid, uuid, uuid, uuid, text, text, text) from public, anon, authenticated, service_role;
grant execute on function public.change_user_role_assignment(uuid, uuid, uuid, uuid, text, text, text) to service_role;
alter function public.change_user_role_assignment(uuid, uuid, uuid, uuid, text, text, text) set search_path = pg_catalog, public;
revoke all on function public.get_user_permissions(uuid) from public, anon, authenticated, service_role;
grant execute on function public.get_user_permissions(uuid) to service_role;
alter function public.get_user_permissions(uuid) set search_path = pg_catalog, public;
revoke all on function public.is_admin_user() from public, anon, authenticated, service_role;
grant execute on function public.is_admin_user() to service_role;
alter function public.is_admin_user() set search_path = pg_catalog, public;

-- Replay of the active SPEC-12 statements.
-- SPEC-12: bucket classification, size/MIME limits, and deny-by-default object access.
-- Generated from app/core/storage_access_inventory.py.
-- Public retrieval uses bucket.public; direct client object access is
-- explicitly denied by RLS because the platform owns the storage ACLs.

-- 1. Install or reconcile every reviewed bucket.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types, updated_at)
values
    ('organization-logos', 'organization-logos', true, 2097152, ARRAY['image/jpeg', 'image/png', 'image/webp']::text[], now()),
    ('patient-avatars', 'patient-avatars', true, 2097152, ARRAY['image/jpeg', 'image/png', 'image/webp']::text[], now()),
    ('practitioner-photos', 'practitioner-photos', true, 2097152, ARRAY['image/jpeg', 'image/png', 'image/webp']::text[], now())
on conflict (id) do update
set name = excluded.name,
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types,
    updated_at = now();

-- 2. Explicitly deny direct client object access. The platform owns the
-- storage table ACLs, so RLS is the application-controlled boundary.
drop policy if exists "Deny direct client object access" on storage.objects;
create policy "Deny direct client object access" on storage.objects
for ALL to anon, authenticated
using (false) with check (false);

-- 3. Service-role writes bypass RLS and public reads use bucket.public.
-- Private objects will use signed URLs issued by the trusted backend.

-- ---------------------------------------------------------------------------
-- PH0-WP-03 additions: complete local catalog, canonical grants and fail-closed
-- consent invariants. Local-only; no hosted target is referenced.
-- ---------------------------------------------------------------------------

-- A. Data API exposure must be explicit. Existing exposed objects retain their
-- reviewed grants; future public objects receive no automatic API grants.
alter default privileges for role postgres in schema public
  revoke all on tables from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke all on sequences from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke all on functions from public, anon, authenticated, service_role;

-- B. Sequence: the medical-id generator is the only trusted caller.
revoke all on all sequences in schema public from public, anon, authenticated, service_role;
grant select, update, usage on sequence public.patient_medical_id_seq to service_role;

-- C. Harden every remaining public function. All use an explicit search path
-- and schema-qualified object references. SECURITY DEFINER capabilities are
-- service-role-only; the invoker medical-id generator remains callable by
-- authenticated clients only because patients.medical_id uses it as a default.
create or replace function public.can_manage_roles()
returns boolean
language sql
security definer
set search_path = pg_catalog, public
as $function$
    select exists (
        select 1
        from public.user_roles ur
        join public.roles r on ur.role_id = r.id
        where ur.user_id = (select auth.uid())
          and (
              r.name = 'org_admin'
              or r.role_type = 'system'
          )
    );
$function$;

create or replace function public.is_admin_user()
returns boolean
language sql
security definer
set search_path = pg_catalog, public
as $function$
    select exists (
        select 1
        from public.user_roles ur
        join public.roles r on ur.role_id = r.id
        where ur.user_id = (select auth.uid())
          and r.name = 'admin'
    );
$function$;

create or replace function public.generate_patient_medical_id()
returns text
language plpgsql
security invoker
set search_path = pg_catalog, public
as $function$
declare
    seq bigint;
begin
    seq := nextval('public.patient_medical_id_seq'::regclass);
    return 'MC-NG-P-' || lpad(seq::text, 10, '0');
end;
$function$;

create or replace function public.update_updated_at_column()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog, public
as $function$
begin
    new.updated_at := pg_catalog.now();
    return new;
end;
$function$;

revoke all on function public.can_manage_roles() from public, anon, authenticated, service_role;
grant execute on function public.can_manage_roles() to service_role;
revoke all on function public.is_admin_user() from public, anon, authenticated, service_role;
grant execute on function public.is_admin_user() to service_role;
revoke all on function public.generate_patient_medical_id() from public, anon, authenticated, service_role;
grant execute on function public.generate_patient_medical_id() to authenticated, service_role;
revoke all on function public.update_updated_at_column() from public, anon, authenticated, service_role;
grant execute on function public.update_updated_at_column() to service_role;

-- D. Clinical relations used by application code. They are service-only until
-- an approved patient self-read policy is defined; no client grant/policy.
create table if not exists public.appointments (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null,
    organization_id uuid not null,
    practitioner_id uuid,
    appointment_type text not null check (btrim(appointment_type) <> ''),
    status text not null default 'booked' check (btrim(status) <> ''),
    start_time timestamptz not null,
    end_time timestamptz not null,
    reason text,
    location text,
    notes text,
    metadata jsonb not null default '{}'::jsonb,
    created_by uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint appointments_time_order_check check (end_time > start_time)
);

create table if not exists public.encounters (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null,
    organization_id uuid not null,
    practitioner_id uuid,
    encounter_class text not null check (btrim(encounter_class) <> ''),
    status text not null default 'planned' check (btrim(status) <> ''),
    reason text,
    appointment_id uuid,
    start_time timestamptz,
    end_time timestamptz,
    location text,
    notes text,
    metadata jsonb not null default '{}'::jsonb,
    created_by uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint encounters_time_order_check check (
        start_time is null or end_time is null or end_time >= start_time
    )
);

create table if not exists public.observations (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null,
    encounter_id uuid not null,
    organization_id uuid not null,
    practitioner_id uuid,
    category text not null check (btrim(category) <> ''),
    code text not null check (btrim(code) <> ''),
    display text,
    value text,
    unit text,
    interpretation text,
    status text not null default 'final' check (btrim(status) <> ''),
    effective_at timestamptz,
    issued_at timestamptz,
    notes text,
    metadata jsonb not null default '{}'::jsonb,
    created_by uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.conditions (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null,
    encounter_id uuid not null,
    organization_id uuid not null,
    practitioner_id uuid,
    code text not null check (btrim(code) <> ''),
    display text,
    clinical_status text not null check (btrim(clinical_status) <> ''),
    verification_status text not null check (btrim(verification_status) <> ''),
    category text,
    severity text,
    onset_date timestamptz,
    abatement_date timestamptz,
    recorded_date timestamptz,
    notes text,
    metadata jsonb not null default '{}'::jsonb,
    created_by uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.medication_requests (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null,
    encounter_id uuid not null,
    organization_id uuid not null,
    practitioner_id uuid,
    medication_code text,
    medication_name text not null check (btrim(medication_name) <> ''),
    status text not null default 'active' check (btrim(status) <> ''),
    intent text not null default 'order' check (btrim(intent) <> ''),
    dosage_instruction text not null check (btrim(dosage_instruction) <> ''),
    route text,
    frequency text,
    quantity text,
    duration text,
    dispense_request text,
    substitution_allowed boolean not null default true,
    authored_on timestamptz,
    notes text,
    metadata jsonb not null default '{}'::jsonb,
    created_by uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.care_team_participants (
    id uuid primary key default gen_random_uuid(),
    care_team_id uuid not null,
    practitioner_id uuid not null,
    role_code text not null check (btrim(role_code) <> ''),
    responsibility text,
    start_date timestamptz,
    end_date timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    active boolean not null default true,
    created_by uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint care_team_participants_time_order_check check (
        end_date is null or start_date is null or end_date >= start_date
    )
);

-- Referential integrity for the application-visible clinical relations. These
-- constraints do not select a canonical treatment/care-team source.
alter table public.appointments
  add constraint appointments_patient_id_fkey foreign key (patient_id) references public.patients(id),
  add constraint appointments_organization_id_fkey foreign key (organization_id) references public.organizations(id),
  add constraint appointments_practitioner_id_fkey foreign key (practitioner_id) references public.practitioners(id);
alter table public.encounters
  add constraint encounters_patient_id_fkey foreign key (patient_id) references public.patients(id),
  add constraint encounters_organization_id_fkey foreign key (organization_id) references public.organizations(id),
  add constraint encounters_practitioner_id_fkey foreign key (practitioner_id) references public.practitioners(id),
  add constraint encounters_appointment_id_fkey foreign key (appointment_id) references public.appointments(id);
alter table public.observations
  add constraint observations_patient_id_fkey foreign key (patient_id) references public.patients(id),
  add constraint observations_encounter_id_fkey foreign key (encounter_id) references public.encounters(id),
  add constraint observations_organization_id_fkey foreign key (organization_id) references public.organizations(id),
  add constraint observations_practitioner_id_fkey foreign key (practitioner_id) references public.practitioners(id);
alter table public.conditions
  add constraint conditions_patient_id_fkey foreign key (patient_id) references public.patients(id),
  add constraint conditions_encounter_id_fkey foreign key (encounter_id) references public.encounters(id),
  add constraint conditions_organization_id_fkey foreign key (organization_id) references public.organizations(id),
  add constraint conditions_practitioner_id_fkey foreign key (practitioner_id) references public.practitioners(id);
alter table public.medication_requests
  add constraint medication_requests_patient_id_fkey foreign key (patient_id) references public.patients(id),
  add constraint medication_requests_encounter_id_fkey foreign key (encounter_id) references public.encounters(id),
  add constraint medication_requests_organization_id_fkey foreign key (organization_id) references public.organizations(id),
  add constraint medication_requests_practitioner_id_fkey foreign key (practitioner_id) references public.practitioners(id);
alter table public.care_team_participants
  add constraint care_team_participants_care_team_id_fkey foreign key (care_team_id) references public.care_teams(id),
  add constraint care_team_participants_practitioner_id_fkey foreign key (practitioner_id) references public.practitioners(id);

-- Additive columns required by current care-team application queries. They are
-- nullable and do not declare a canonical active-treatment source.
alter table public.care_teams
  add column if not exists organization_id uuid,
  add column if not exists name text,
  add column if not exists status text default 'active'::text,
  add column if not exists category text,
  add column if not exists reason text,
  add column if not exists managing_organization_id uuid,
  add column if not exists notes text,
  add column if not exists created_at timestamptz default now(),
  add column if not exists updated_at timestamptz default now();
alter table public.care_teams
  add constraint care_teams_organization_id_fkey foreign key (organization_id) references public.organizations(id);

create index if not exists idx_care_teams_organization_id on public.care_teams (organization_id);

alter table public.appointments enable row level security;
alter table public.appointments force row level security;
alter table public.encounters enable row level security;
alter table public.encounters force row level security;
alter table public.observations enable row level security;
alter table public.observations force row level security;
alter table public.conditions enable row level security;
alter table public.conditions force row level security;
alter table public.medication_requests enable row level security;
alter table public.medication_requests force row level security;
alter table public.care_team_participants enable row level security;
alter table public.care_team_participants force row level security;

revoke all on table public.appointments from public, anon, authenticated, service_role;
revoke all on table public.encounters from public, anon, authenticated, service_role;
revoke all on table public.observations from public, anon, authenticated, service_role;
revoke all on table public.conditions from public, anon, authenticated, service_role;
revoke all on table public.medication_requests from public, anon, authenticated, service_role;
revoke all on table public.care_team_participants from public, anon, authenticated, service_role;
grant select, insert, update on public.appointments to service_role;
grant select, insert, update on public.encounters to service_role;
grant select, insert, update on public.observations to service_role;
grant select, insert, update on public.conditions to service_role;
grant select, insert, update on public.medication_requests to service_role;
grant select, insert, update on public.care_team_participants to service_role;

create index if not exists idx_appointments_patient_id on public.appointments (patient_id);
create index if not exists idx_appointments_practitioner_id on public.appointments (practitioner_id);
create index if not exists idx_appointments_organization_id on public.appointments (organization_id);
create index if not exists idx_appointments_start_time on public.appointments (start_time);
create index if not exists idx_encounters_patient_id on public.encounters (patient_id);
create index if not exists idx_encounters_organization_id on public.encounters (organization_id);
create index if not exists idx_encounters_practitioner_id on public.encounters (practitioner_id);
create index if not exists idx_encounters_appointment_id on public.encounters (appointment_id);
create index if not exists idx_observations_patient_id on public.observations (patient_id);
create index if not exists idx_observations_encounter_id on public.observations (encounter_id);
create index if not exists idx_observations_organization_id on public.observations (organization_id);
create index if not exists idx_conditions_patient_id on public.conditions (patient_id);
create index if not exists idx_conditions_encounter_id on public.conditions (encounter_id);
create index if not exists idx_conditions_organization_id on public.conditions (organization_id);
create index if not exists idx_medication_requests_patient_id on public.medication_requests (patient_id);
create index if not exists idx_medication_requests_encounter_id on public.medication_requests (encounter_id);
create index if not exists idx_medication_requests_organization_id on public.medication_requests (organization_id);
create index if not exists idx_care_team_participants_care_team_id on public.care_team_participants (care_team_id);
create index if not exists idx_care_team_participants_practitioner_id on public.care_team_participants (practitioner_id);

drop trigger if exists appointments_updated_at on public.appointments;
create trigger appointments_updated_at before update on public.appointments
  for each row execute function public.update_updated_at_column();
drop trigger if exists encounters_updated_at on public.encounters;
create trigger encounters_updated_at before update on public.encounters
  for each row execute function public.update_updated_at_column();
drop trigger if exists observations_updated_at on public.observations;
create trigger observations_updated_at before update on public.observations
  for each row execute function public.update_updated_at_column();
drop trigger if exists conditions_updated_at on public.conditions;
create trigger conditions_updated_at before update on public.conditions
  for each row execute function public.update_updated_at_column();
drop trigger if exists medication_requests_updated_at on public.medication_requests;
create trigger medication_requests_updated_at before update on public.medication_requests
  for each row execute function public.update_updated_at_column();
drop trigger if exists care_team_participants_updated_at on public.care_team_participants;
create trigger care_team_participants_updated_at before update on public.care_team_participants
  for each row execute function public.update_updated_at_column();

-- E. Canonical explicit patient grants (SPEC-06) and append-only audit.
create table if not exists public.patient_access_grants (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null references public.patients(id),
    practitioner_id uuid not null references public.practitioners(id),
    organization_id uuid not null references public.organizations(id),
    access_type text not null default 'patient_granted'
      constraint patient_access_grants_access_type_check check (access_type = 'patient_granted'),
    access_level text not null default 'read'
      constraint patient_access_grants_access_level_check check (access_level = 'read'),
    resource_families text[] not null
      constraint patient_access_grants_resource_families_check check (
          cardinality(resource_families) > 0
          and resource_families <@ array[
              'clinical_history', 'encounter', 'observation', 'condition',
              'prescription', 'lab_result', 'clinical_document'
          ]::text[]
      ),
    status text not null
      constraint patient_access_grants_status_check check (
          status in ('pending', 'approved', 'revoked', 'expired')
      ),
    requested_by uuid not null,
    requested_at timestamptz not null default now(),
    granted_by uuid,
    granted_at timestamptz,
    effective_from timestamptz not null,
    expires_at timestamptz not null,
    revoked_by uuid,
    revoked_at timestamptz,
    revocation_reason text,
    expired_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint patient_access_grants_grant_event_pair_check check (
        (granted_by is null) = (granted_at is null)
    ),
    constraint patient_access_grants_revoke_event_pair_check check (
        (revoked_by is null) = (revoked_at is null)
    ),
    constraint patient_access_grants_grant_after_request_check check (
        granted_at is null or granted_at >= requested_at
    ),
    constraint patient_access_grants_period_check check (
        expires_at > greatest(effective_from, coalesce(granted_at, requested_at))
    ),
    constraint patient_access_grants_revoke_after_grant_check check (
        revoked_at is null or revoked_at >= coalesce(granted_at, requested_at)
    ),
    constraint patient_access_grants_status_event_check check (
        (status = 'pending' and granted_by is null and revoked_at is null and expired_at is null)
        or (status = 'approved' and granted_by is not null and revoked_at is null and expired_at is null)
        or (status = 'revoked' and revoked_at is not null and expired_at is null)
        or (status = 'expired' and expired_at is not null and revoked_at is null)
    ),
    constraint patient_access_grants_expiry_event_check check (
        expired_at is null or expired_at >= expires_at
    )
);

create table if not exists public.patient_access_grant_audit (
    id uuid primary key default gen_random_uuid(),
    grant_id uuid not null references public.patient_access_grants(id),
    action text not null
      constraint patient_access_grant_audit_action_check check (
          action in ('requested', 'approved', 'revoked', 'expired')
      ),
    actor_id uuid,
    occurred_at timestamptz not null default now(),
    reason text,
    metadata jsonb not null default '{}'::jsonb
);

create or replace function public.validate_patient_access_grant_record()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
begin
    if exists (
        select 1
        from unnest(new.resource_families) as family(value)
        group by family.value
        having count(*) > 1
    ) then
        raise exception 'resource_families must not contain duplicates'
            using errcode = '23514';
    end if;
    return new;
end;
$function$;

create or replace function public.record_patient_access_grant_audit()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    v_action text;
    v_actor uuid;
    v_occurred_at timestamptz;
begin
    if tg_op = 'INSERT' then
        if new.status = 'pending' then
            v_action := 'requested';
            v_actor := new.requested_by;
            v_occurred_at := new.requested_at;
        elsif new.status = 'approved' then
            v_action := 'approved';
            v_actor := new.granted_by;
            v_occurred_at := new.granted_at;
        end if;
    elsif tg_op = 'UPDATE' and new.status is distinct from old.status then
        if new.status = 'approved' then
            v_action := 'approved';
            v_actor := new.granted_by;
            v_occurred_at := new.granted_at;
        elsif new.status = 'revoked' then
            v_action := 'revoked';
            v_actor := new.revoked_by;
            v_occurred_at := new.revoked_at;
            insert into public.patient_access_grant_audit
                (grant_id, action, actor_id, occurred_at, reason)
            values
                (new.id, v_action, v_actor, v_occurred_at, new.revocation_reason);
            return new;
        elsif new.status = 'expired' then
            v_action := 'expired';
            v_actor := null;
            v_occurred_at := new.expired_at;
        end if;
    end if;

    if v_action is not null then
        insert into public.patient_access_grant_audit
            (grant_id, action, actor_id, occurred_at)
        values
            (new.id, v_action, v_actor, v_occurred_at);
    end if;
    return new;
end;
$function$;

revoke all on function public.validate_patient_access_grant_record() from public, anon, authenticated, service_role;
grant execute on function public.validate_patient_access_grant_record() to service_role;
revoke all on function public.record_patient_access_grant_audit() from public, anon, authenticated, service_role;
grant execute on function public.record_patient_access_grant_audit() to service_role;

alter table public.patient_access_grants enable row level security;
alter table public.patient_access_grants force row level security;
alter table public.patient_access_grant_audit enable row level security;
alter table public.patient_access_grant_audit force row level security;

revoke all on table public.patient_access_grants from public, anon, authenticated, service_role;
revoke all on table public.patient_access_grant_audit from public, anon, authenticated, service_role;
grant select, insert, update on public.patient_access_grants to service_role;
grant select, insert on public.patient_access_grant_audit to service_role;

create unique index if not exists patient_access_grants_one_open_per_scope
  on public.patient_access_grants (patient_id, practitioner_id, organization_id)
  where status in ('pending', 'approved');
create index if not exists idx_patient_access_grants_patient_id
  on public.patient_access_grants (patient_id);
create index if not exists idx_patient_access_grants_practitioner_id
  on public.patient_access_grants (practitioner_id);
create index if not exists idx_patient_access_grants_organization_id
  on public.patient_access_grants (organization_id);
create index if not exists idx_patient_access_grant_audit_grant_id
  on public.patient_access_grant_audit (grant_id);
create index if not exists idx_patient_access_grant_audit_occurred_at
  on public.patient_access_grant_audit (occurred_at);

drop trigger if exists patient_access_grants_validate_record on public.patient_access_grants;
create trigger patient_access_grants_validate_record before insert or update
  on public.patient_access_grants for each row
  execute function public.validate_patient_access_grant_record();
drop trigger if exists patient_access_grants_updated_at on public.patient_access_grants;
create trigger patient_access_grants_updated_at before update
  on public.patient_access_grants for each row
  execute function public.update_updated_at_column();
drop trigger if exists patient_access_grants_audit on public.patient_access_grants;
create trigger patient_access_grants_audit after insert or update
  on public.patient_access_grants for each row
  execute function public.record_patient_access_grant_audit();

-- F. Consent lifecycle hardening. Direct client writes are revoked; the
-- trusted backend path supplies grantor/revoker provenance. Unapproved
-- purpose codes, recipient kinds, resource-scope storage and legacy promotion
-- are deliberately not guessed.
drop policy if exists "Patients insert own consent" on public.consent_records;
drop policy if exists "Patients update own consent" on public.consent_records;
revoke insert, update on public.consent_records from authenticated;

-- Trusted revocation actor. Recipient kind, resource scope and canonical
-- purpose codes remain deliberately unimplemented pending human decision.
alter table public.consent_records
  add column if not exists revoked_by uuid;

alter table public.consent_records
  drop constraint if exists consent_records_finite_expiry_check;
alter table public.consent_records
  add constraint consent_records_finite_expiry_check check (
      status = 'draft'
      or (
          expires_at is not null
          and (granted_at is null or expires_at > granted_at)
          and (effective_from is null or expires_at > effective_from)
      )
  );

alter table public.consent_records
  drop constraint if exists consent_records_approval_provenance_check;
alter table public.consent_records
  add constraint consent_records_approval_provenance_check check (
      status in ('draft', 'rejected')
      or (granted_by is not null and granted_at is not null)
  );

alter table public.consent_records
  drop constraint if exists consent_records_revocation_provenance_check;
alter table public.consent_records
  add constraint consent_records_revocation_provenance_check check (
      (status = 'revoked' and revoked_by is not null and revoked_at is not null)
      or (status <> 'revoked' and revoked_at is null)
  );

alter table public.consent_records
  drop constraint if exists consent_records_emergency_consent_prohibited_check;
alter table public.consent_records
  add constraint consent_records_emergency_consent_prohibited_check check (
      emergency_access is distinct from true
      and consent_type is distinct from 'emergency'
  );

create or replace function public.enforce_consent_record_immutability()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
begin
    if tg_op = 'UPDATE' and old.status <> 'draft' then
        if new.patient_id is distinct from old.patient_id
           or new.organization_id is distinct from old.organization_id
           or new.practitioner_id is distinct from old.practitioner_id
           or new.granted_by is distinct from old.granted_by
           or new.granted_at is distinct from old.granted_at
           or new.consent_type is distinct from old.consent_type
           or new.access_level is distinct from old.access_level
           or new.purpose_of_use is distinct from old.purpose_of_use
           or new.legal_basis is distinct from old.legal_basis
           or new.effective_from is distinct from old.effective_from
           or new.expires_at is distinct from old.expires_at
           or new.metadata is distinct from old.metadata
           or new.fhir_resource is distinct from old.fhir_resource then
            raise exception 'approved consent scope and lifecycle fields are immutable'
                using errcode = '23514';
        end if;
    end if;
    return new;
end;
$function$;

revoke all on function public.enforce_consent_record_immutability()
  from public, anon, authenticated, service_role;
grant execute on function public.enforce_consent_record_immutability() to service_role;

drop trigger if exists consent_records_immutable_fields on public.consent_records;
create trigger consent_records_immutable_fields before update
  on public.consent_records for each row
  execute function public.enforce_consent_record_immutability();

-- G. Remove pre-existing duplicate indexes found by local db advisors. The
-- unique constraint and the original system index remain authoritative.
drop index if exists public.idx_patients_medical_id;
drop index if exists public.terminology_codes_system_idx1;

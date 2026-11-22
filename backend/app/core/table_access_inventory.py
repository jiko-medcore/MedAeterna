"""SPEC-11 reference inventory for table-level RLS and SQL grants.

This is a declarative model of the *intended* database access boundary. It does
not connect to Postgres, execute grants, create policies, or prove that the
deployed database matches this model. Migration and catalog tests must compare
the live database against these expectations.

Client roles never receive table-level capabilities that bypass row filtering.
`service_role` bypasses RLS by design, so every service-role operation still
requires the execution-mode evidence described in SPEC-10.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping

from app.core.database_execution_policy import ExecutionMode


class TableClass(StrEnum):
    CALLER_RLS = "caller_rls"
    PUBLIC_REFERENCE = "public_reference"
    SERVICE_ONLY = "service_only"
    APPEND_ONLY_AUDIT = "append_only_audit"


@dataclass(frozen=True)
class PolicyRule:
    """One intended RLS policy, written as it should appear in the migration."""

    name: str
    command: str
    role: str
    predicate: str
    check: str | None = None


@dataclass(frozen=True)
class TableAccessRule:
    table: str
    classification: TableClass
    client_grants: Mapping[str, frozenset[str]]
    service_grants: frozenset[str]
    policies: tuple[PolicyRule, ...] = ()
    required_indexes: tuple[str, ...] = ()
    note: str = ""
    rls_forced: bool = True


@dataclass(frozen=True)
class FunctionAccessRule:
    """Expected hardening for a SECURITY DEFINER function in ``public``."""

    signature: str
    required_search_path: tuple[str, ...]
    allowed_execute_roles: frozenset[str]
    note: str = ""


FORBIDDEN_CLIENT_PRIVILEGES = frozenset(
    {"TRUNCATE", "MAINTAIN", "TRIGGER", "REFERENCES"}
)
ALLOWED_COMMANDS = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})
ALLOWED_POLICY_ROLES = frozenset({"anon", "authenticated", "service_role"})


def _rule(
    table: str,
    classification: TableClass,
    *,
    authenticated: Iterable[str] = (),
    anon: Iterable[str] = (),
    service: Iterable[str] = (),
    policies: Iterable[PolicyRule] = (),
    indexes: Iterable[str] = (),
    note: str = "",
) -> TableAccessRule:
    return TableAccessRule(
        table=table,
        classification=classification,
        client_grants={
            "anon": frozenset(anon),
            "authenticated": frozenset(authenticated),
        },
        service_grants=frozenset(service),
        policies=tuple(policies),
        required_indexes=tuple(indexes),
        note=note,
    )


def _own(name: str, command: str, column: str) -> PolicyRule:
    expression = f"{column} = (select auth.uid())"
    # INSERT policies have only WITH CHECK; SELECT policies have only USING;
    # UPDATE policies have both. Mirror how Postgres stores them so catalog
    # comparisons are exact rather than relying on fallbacks.
    return PolicyRule(
        name=name,
        command=command,
        role="authenticated",
        predicate="" if command == "INSERT" else expression,
        check=expression if command in {"INSERT", "UPDATE"} else None,
    )


# Reviewed public relations. The first 26 were observed in the local Supabase
# catalog on 2026-11-20; the remaining entries are installed by the PH0-WP-03
# local release-candidate migration. Every entry must have an explicit class,
# explicit grants, and explicit policy intent. Absence means deny by default.
DATABASE_ACCESS_INVENTORY: dict[str, TableAccessRule] = {
    "profiles": _rule(
        "profiles",
        TableClass.CALLER_RLS,
        authenticated={"SELECT", "INSERT", "UPDATE"},
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        policies=(
            _own("Users read own profile", "SELECT", "id"),
            _own("Users insert own profile", "INSERT", "id"),
            _own("Users update own profile", "UPDATE", "id"),
        ),
        indexes=("profiles(id)",),
    ),
    "patients": _rule(
        "patients",
        TableClass.CALLER_RLS,
        authenticated={"SELECT", "INSERT", "UPDATE"},
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        policies=(
            _own("Patients read own record", "SELECT", "id"),
            _own("Patients insert own record", "INSERT", "id"),
            _own("Patients update own record", "UPDATE", "id"),
        ),
        indexes=("patients(id)", "patients(organization_id)"),
        note="Consolidate the two legacy duplicate SELECT policies into one.",
    ),
    "medical_records": _rule(
        "medical_records",
        TableClass.CALLER_RLS,
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE"},
        policies=(_own("Patients read own medical records", "SELECT", "patient_id"),),
        indexes=("medical_records(patient_id)",),
        note="Practitioner writes use service role with SPEC-03/04/05 evidence.",
    ),
    "lab_results": _rule(
        "lab_results",
        TableClass.CALLER_RLS,
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE"},
        policies=(_own("Patients read own lab results", "SELECT", "patient_id"),),
        indexes=("lab_results(patient_id)", "lab_results(clinician_id)"),
    ),
    "prescriptions": _rule(
        "prescriptions",
        TableClass.CALLER_RLS,
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE"},
        policies=(_own("Patients read own prescriptions", "SELECT", "patient_id"),),
        indexes=("prescriptions(patient_id)",),
    ),
    "reminders": _rule(
        "reminders",
        TableClass.CALLER_RLS,
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE"},
        policies=(_own("Patients read own reminders", "SELECT", "patient_id"),),
        indexes=("reminders(patient_id)",),
    ),
    "consent_records": _rule(
        "consent_records",
        TableClass.CALLER_RLS,
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE"},
        policies=(_own("Patients read own consent", "SELECT", "patient_id"),),
        indexes=(
            "consent_records(patient_id)",
            "consent_records(organization_id)",
            "consent_records(practitioner_id)",
            "consent_records(status)",
        ),
        note=(
            "Direct client writes are revoked; the trusted backend supplies "
            "grantor/revoker provenance. Finite expiry, emergency prohibition "
            "and immutable scope constraints are enforced by migration."
        ),
    ),
    "practitioners": _rule(
        "practitioners",
        TableClass.CALLER_RLS,
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE"},
        policies=(
            PolicyRule(
                name="Practitioners read own profile",
                command="SELECT",
                role="authenticated",
                predicate=(
                    "id = (select auth.uid()) or profile_id = (select auth.uid())"
                ),
            ),
        ),
        indexes=("practitioners(id)", "practitioners(profile_id)"),
    ),
    "practitioner_roles": _rule(
        "practitioner_roles",
        TableClass.CALLER_RLS,
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE"},
        policies=(
            PolicyRule(
                name="Practitioners read own roles",
                command="SELECT",
                role="authenticated",
                predicate=(
                    "practitioner_id in (select p.id from public.practitioners p "
                    "where p.profile_id = (select auth.uid()))"
                ),
            ),
        ),
        indexes=(
            "practitioner_roles(practitioner_id)",
            "practitioners(profile_id)",
        ),
    ),
    "user_roles": _rule(
        "user_roles",
        TableClass.CALLER_RLS,
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        policies=(
            _own("Users read own roles", "SELECT", "user_id"),
            PolicyRule(
                name="Trusted service manages assignments",
                command="ALL",
                role="service_role",
                predicate="true",
                check="true",
            ),
        ),
        indexes=("user_roles(user_id)", "user_roles(organization_id)"),
        note="Writes must go through public.change_user_role_assignment (SPEC-02).",
    ),
    "terminology_codes": _rule(
        "terminology_codes",
        TableClass.PUBLIC_REFERENCE,
        anon={"SELECT"},
        authenticated={"SELECT"},
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        policies=(
            PolicyRule(
                name="Read-only terminology",
                command="SELECT",
                role="anon, authenticated",
                predicate="true",
            ),
        ),
        indexes=("terminology_codes(system, code)",),
    ),
    "audit_logs": _rule(
        "audit_logs",
        TableClass.APPEND_ONLY_AUDIT,
        service={"SELECT", "INSERT"},
        indexes=("audit_logs(actor_id)", "audit_logs(created_at)"),
        note="No client privileges; no UPDATE/DELETE/TRUNCATE for any role.",
    ),
    "role_assignment_audit": _rule(
        "role_assignment_audit",
        TableClass.APPEND_ONLY_AUDIT,
        service={"SELECT", "INSERT"},
        indexes=("role_assignment_audit(user_id)",),
        note="Already restricted by SPEC-02 migration; preserved here.",
    ),
    "care_teams": _rule(
        "care_teams",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=(
            "care_teams(patient_id, clinician_id)",
            "care_teams(clinician_id)",
            "care_teams(organization_id)",
        ),
    ),
    "clinicians_patients": _rule(
        "clinicians_patients",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("clinicians_patients(patient_id)", "clinicians_patients(clinician_id)"),
    ),
    "patient_care_team": _rule(
        "patient_care_team",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=(
            "patient_care_team(patient_id)",
            "patient_care_team(practitioner_id)",
            "patient_care_team(organization_id)",
        ),
    ),
    "organizations": _rule(
        "organizations",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("organizations(id)",),
    ),
    "departments": _rule(
        "departments",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("departments(organization_id)", "departments(deleted_at)"),
    ),
    "healthcare_services": _rule(
        "healthcare_services",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("healthcare_services(organization_id)",),
    ),
    "organization_operating_hours": _rule(
        "organization_operating_hours",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("organization_operating_hours(organization_id)",),
    ),
    "invitations": _rule(
        "invitations",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("invitations(organization_id)", "invitations(token)"),
        note="Invitation tokens are secrets; no direct client access.",
    ),
    "roles": _rule(
        "roles",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("roles(organization_id)", "roles(is_active)"),
    ),
    "permissions": _rule(
        "permissions",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("permissions(name)",),
    ),
    "role_permissions": _rule(
        "role_permissions",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("role_permissions(role_id)", "role_permissions(permission_id)"),
    ),
    "events": _rule(
        "events",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=("events(status)", "events(aggregate_type, aggregate_id)"),
        note="Event payloads may contain patient data (SPEC-09).",
    ),
    "events_dead_letter": _rule(
        "events_dead_letter",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE", "DELETE"},
        indexes=(
            "events_dead_letter(original_event_id)",
            "events_dead_letter(replayed)",
            "events_dead_letter(failed_at)",
        ),
    ),
    "appointments": _rule(
        "appointments",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE"},
        indexes=(
            "appointments(patient_id)",
            "appointments(practitioner_id)",
            "appointments(organization_id)",
            "appointments(start_time)",
        ),
        note="Application-referenced clinical relation; no client grant or policy.",
    ),
    "encounters": _rule(
        "encounters",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE"},
        indexes=(
            "encounters(patient_id)",
            "encounters(organization_id)",
            "encounters(practitioner_id)",
            "encounters(appointment_id)",
        ),
        note="Application-referenced clinical relation; no client grant or policy.",
    ),
    "observations": _rule(
        "observations",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE"},
        indexes=(
            "observations(patient_id)",
            "observations(encounter_id)",
            "observations(organization_id)",
        ),
        note="Application-referenced clinical relation; no client grant or policy.",
    ),
    "conditions": _rule(
        "conditions",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE"},
        indexes=(
            "conditions(patient_id)",
            "conditions(encounter_id)",
            "conditions(organization_id)",
        ),
        note="Application-referenced clinical relation; no client grant or policy.",
    ),
    "medication_requests": _rule(
        "medication_requests",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE"},
        indexes=(
            "medication_requests(patient_id)",
            "medication_requests(encounter_id)",
            "medication_requests(organization_id)",
        ),
        note="Application-referenced clinical relation; no client grant or policy.",
    ),
    "care_team_participants": _rule(
        "care_team_participants",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE"},
        indexes=(
            "care_team_participants(care_team_id)",
            "care_team_participants(practitioner_id)",
        ),
        note="Application-referenced care-team relation; no client grant or policy.",
    ),
    "patient_access_grants": _rule(
        "patient_access_grants",
        TableClass.SERVICE_ONLY,
        service={"SELECT", "INSERT", "UPDATE"},
        indexes=(
            "patient_access_grants(patient_id, practitioner_id, organization_id)",
            "patient_access_grants(patient_id)",
            "patient_access_grants(practitioner_id)",
            "patient_access_grants(organization_id)",
        ),
        note="SPEC-06 canonical patient-approved grants; no client access or legacy promotion.",
    ),
    "patient_access_grant_audit": _rule(
        "patient_access_grant_audit",
        TableClass.APPEND_ONLY_AUDIT,
        service={"SELECT", "INSERT"},
        indexes=(
            "patient_access_grant_audit(grant_id)",
            "patient_access_grant_audit(occurred_at)",
        ),
        note="Append-only request/approval/revocation/expiry trail; no client access.",
    ),
}

# Still absent from the local catalog. Implemented relations were promoted into
# DATABASE_ACCESS_INVENTORY by the PH0-WP-03 migration; an unregistered relation
# remains denied by default.
PLANNED_TABLES: dict[str, str] = {
    "patient_admin_data": "SPEC-07: view with security_invoker = true in a private schema, service_role only",
}

# SECURITY DEFINER functions are privileged database capabilities. They must
# have a fixed search_path and must not be callable by anon/authenticated.
FUNCTION_ACCESS_INVENTORY: dict[str, FunctionAccessRule] = {
    "can_manage_roles()": FunctionAccessRule(
        signature="can_manage_roles()",
        required_search_path=("pg_catalog", "public"),
        allowed_execute_roles=frozenset({"service_role"}),
        note="Legacy helper; retained only for trusted backend compatibility.",
    ),
    "change_user_role_assignment(p_user_id uuid, p_role_id uuid, p_organization_id uuid, p_actor_id uuid, p_actor_type text, p_action text, p_reason text)": FunctionAccessRule(
        signature=(
            "change_user_role_assignment(p_user_id uuid, p_role_id uuid, "
            "p_organization_id uuid, p_actor_id uuid, p_actor_type text, "
            "p_action text, p_reason text)"
        ),
        required_search_path=("pg_catalog", "public"),
        allowed_execute_roles=frozenset({"service_role"}),
        note="SPEC-02 trusted role assignment RPC; already hardened.",
    ),
    "get_user_permissions(uid uuid)": FunctionAccessRule(
        signature="get_user_permissions(uid uuid)",
        required_search_path=("pg_catalog", "public"),
        allowed_execute_roles=frozenset({"service_role"}),
        note="Accepts an arbitrary user ID; must never be client-callable.",
    ),
    "is_admin_user()": FunctionAccessRule(
        signature="is_admin_user()",
        required_search_path=("pg_catalog", "public"),
        allowed_execute_roles=frozenset({"service_role"}),
        note="Uses unmapped legacy role name 'admin'; retained only for service role.",
    ),
    "validate_patient_access_grant_record()": FunctionAccessRule(
        signature="validate_patient_access_grant_record()",
        required_search_path=("pg_catalog", "public"),
        allowed_execute_roles=frozenset({"service_role"}),
        note="SPEC-06 canonical grant scope validator; service-role-only capability.",
    ),
    "record_patient_access_grant_audit()": FunctionAccessRule(
        signature="record_patient_access_grant_audit()",
        required_search_path=("pg_catalog", "public"),
        allowed_execute_roles=frozenset({"service_role"}),
        note="SPEC-06 append-only lifecycle audit trigger; service-role-only capability.",
    ),
    "enforce_consent_record_immutability()": FunctionAccessRule(
        signature="enforce_consent_record_immutability()",
        required_search_path=("pg_catalog", "public"),
        allowed_execute_roles=frozenset({"service_role"}),
        note="SPEC-05 approved consent scope and lifecycle fields are immutable.",
    ),
}


def table_is_covered(table: str) -> bool:
    """Return whether a table has an approved rule (planned tables do not)."""
    return table in DATABASE_ACCESS_INVENTORY


def expected_policy_names(table: str) -> tuple[str, ...]:
    """Return the policy names that should exist on a table."""
    rule = DATABASE_ACCESS_INVENTORY.get(table)
    return tuple(policy.name for policy in rule.policies) if rule else ()


def all_policy_names() -> frozenset[str]:
    """Return every approved policy name, for duplicate detection."""
    return frozenset(
        policy.name
        for rule in DATABASE_ACCESS_INVENTORY.values()
        for policy in rule.policies
    )


def expected_grants(table: str, role: str) -> frozenset[str]:
    """Return the commands a role should hold on a known table."""
    rule = DATABASE_ACCESS_INVENTORY.get(table)
    if rule is None:
        return frozenset()
    if role == "service_role":
        return rule.service_grants
    return rule.client_grants.get(role, frozenset())


def required_execution_mode(table: str) -> ExecutionMode:
    """Return the SPEC-10 mode implied by a table's access class."""
    rule = DATABASE_ACCESS_INVENTORY.get(table)
    if rule is None:
        return ExecutionMode.SERVICE_ROLE
    if rule.classification in {TableClass.CALLER_RLS, TableClass.PUBLIC_REFERENCE}:
        return ExecutionMode.CALLER_RLS
    return ExecutionMode.SERVICE_ROLE


def coverage_gaps(observed_tables: Iterable[str]) -> tuple[str, ...]:
    """List deployed public tables that have no reviewed access rule."""
    return tuple(sorted(set(observed_tables) - set(DATABASE_ACCESS_INVENTORY)))


def unexpected_inventory_tables(observed_tables: Iterable[str]) -> tuple[str, ...]:
    """List inventory rows whose tables are not present in the catalog snapshot."""
    return tuple(sorted(set(DATABASE_ACCESS_INVENTORY) - set(observed_tables)))


def grant_violations(table: str, role: str, observed: Iterable[str]) -> tuple[str, ...]:
    """List observed privileges that must not be granted on this table/role."""
    expected = expected_grants(table, role)
    extra = set(observed) - expected
    forbidden = extra & FORBIDDEN_CLIENT_PRIVILEGES
    unknown = extra - ALLOWED_COMMANDS - FORBIDDEN_CLIENT_PRIVILEGES
    return tuple(sorted(forbidden | unknown | (extra - expected)))


def missing_grants(table: str, role: str, observed: Iterable[str]) -> tuple[str, ...]:
    """List required privileges that are absent from the observed grant set."""
    return tuple(sorted(expected_grants(table, role) - set(observed)))


def policy_hygiene_violations(policy: PolicyRule) -> tuple[str, ...]:
    """Check that a policy follows the fail-closed, indexed-predicate rules."""
    violations: list[str] = []
    if policy.role not in ALLOWED_POLICY_ROLES and policy.role != "anon, authenticated":
        violations.append("policy target role is not explicitly allowlisted")
    if policy.command not in ALLOWED_COMMANDS | {"ALL"}:
        violations.append("unsupported policy command")
    expression = f"{policy.predicate} {policy.check or ''}"
    if "auth.role(" in expression:
        violations.append("deprecated auth.role() check")
    if "auth.uid()" in expression and "(select auth.uid())" not in expression:
        violations.append("auth.uid() must be wrapped in SELECT")
    if policy.role == "service_role" and policy.name != "Trusted service manages assignments":
        violations.append("service_role policy is not an approved trusted path")
    return tuple(violations)


def function_violations(
    signature: str,
    *,
    security_definer: bool,
    search_path: tuple[str, ...] | list[str] | None,
    execute_roles: Iterable[str],
) -> tuple[str, ...]:
    """Check a SECURITY DEFINER function against the trusted-function model."""
    rule = FUNCTION_ACCESS_INVENTORY.get(signature)
    if rule is None:
        return ("function is not in the trusted-function inventory",)
    violations: list[str] = []
    if not security_definer:
        violations.append("function is not SECURITY DEFINER")
    if tuple(search_path or ()) != rule.required_search_path:
        violations.append("fixed search_path is missing or incorrect")
    observed_roles = set(execute_roles)
    if observed_roles - rule.allowed_execute_roles:
        violations.append("function is executable by an unapproved role")
    if rule.allowed_execute_roles - observed_roles:
        violations.append("approved execute grant is missing")
    return tuple(violations)

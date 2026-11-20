import pytest

from app.core.database_execution_policy import ExecutionMode
from app.core.table_access_inventory import (
    ALLOWED_COMMANDS,
    DATABASE_ACCESS_INVENTORY,
    FORBIDDEN_CLIENT_PRIVILEGES,
    FUNCTION_ACCESS_INVENTORY,
    PLANNED_TABLES,
    TableClass,
    all_policy_names,
    coverage_gaps,
    expected_grants,
    expected_policy_names,
    function_violations,
    grant_violations,
    missing_grants,
    policy_hygiene_violations,
    required_execution_mode,
    table_is_covered,
    unexpected_inventory_tables,
)

EXPECTED_TABLES = {
    "audit_logs",
    "care_teams",
    "clinicians_patients",
    "consent_records",
    "departments",
    "events",
    "events_dead_letter",
    "healthcare_services",
    "invitations",
    "lab_results",
    "medical_records",
    "organization_operating_hours",
    "organizations",
    "patient_care_team",
    "patients",
    "permissions",
    "practitioner_roles",
    "practitioners",
    "prescriptions",
    "profiles",
    "reminders",
    "role_assignment_audit",
    "role_permissions",
    "roles",
    "terminology_codes",
    "user_roles",
}

ALL_POLICIES = [
    (table, policy)
    for table, rule in DATABASE_ACCESS_INVENTORY.items()
    for policy in rule.policies
]


def test_inventory_covers_every_reviewed_public_table():
    assert set(DATABASE_ACCESS_INVENTORY) == EXPECTED_TABLES


def test_planned_tables_are_explicitly_not_covered():
    assert PLANNED_TABLES
    for table in PLANNED_TABLES:
        assert table_is_covered(table) is False
        assert expected_grants(table, "service_role") == frozenset()
        assert expected_policy_names(table) == ()


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_every_table_has_an_explicit_class_and_service_grants(table):
    rule = DATABASE_ACCESS_INVENTORY[table]
    assert isinstance(rule.classification, TableClass)
    assert rule.service_grants
    assert rule.service_grants <= ALLOWED_COMMANDS
    assert rule.rls_forced is True


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_client_roles_have_no_privilege_that_bypasses_row_filtering(role):
    for table in EXPECTED_TABLES:
        grants = expected_grants(table, role)
        assert grants <= ALLOWED_COMMANDS
        assert grants.isdisjoint(FORBIDDEN_CLIENT_PRIVILEGES)


def test_service_role_has_no_dangerous_table_privileges():
    for table in EXPECTED_TABLES:
        grants = expected_grants(table, "service_role")
        assert grants <= ALLOWED_COMMANDS
        assert grants.isdisjoint(FORBIDDEN_CLIENT_PRIVILEGES)


def test_authenticated_role_never_has_delete_on_a_reviewed_table():
    for table in EXPECTED_TABLES:
        assert "DELETE" not in expected_grants(table, "authenticated")


def test_anon_only_reads_public_reference_data():
    anon_tables = {
        table
        for table in EXPECTED_TABLES
        if expected_grants(table, "anon")
    }
    assert anon_tables == {"terminology_codes"}
    assert expected_grants("terminology_codes", "anon") == frozenset({"SELECT"})


@pytest.mark.parametrize("table", ["audit_logs", "role_assignment_audit"])
def test_audit_tables_are_append_only_for_the_service_role(table):
    rule = DATABASE_ACCESS_INVENTORY[table]
    assert rule.classification is TableClass.APPEND_ONLY_AUDIT
    assert rule.service_grants == frozenset({"SELECT", "INSERT"})
    assert rule.policies == ()
    for role in ("anon", "authenticated"):
        assert rule.client_grants[role] == frozenset()


@pytest.mark.parametrize("table,policy", ALL_POLICIES)
def test_policy_definitions_follow_fail_closed_hygiene_rules(table, policy):
    assert policy_hygiene_violations(policy) == ()
    assert table in EXPECTED_TABLES


def test_policy_names_are_unique():
    names = [policy.name for _, policy in ALL_POLICIES]
    assert len(names) == len(set(names))
    assert set(names) == all_policy_names()


@pytest.mark.parametrize(
    "table",
    [
        name
        for name, rule in DATABASE_ACCESS_INVENTORY.items()
        if rule.classification in {TableClass.SERVICE_ONLY, TableClass.APPEND_ONLY_AUDIT}
    ],
)
def test_service_only_tables_have_no_policies(table):
    assert expected_policy_names(table) == ()


@pytest.mark.parametrize(
    "table",
    [
        name
        for name, rule in DATABASE_ACCESS_INVENTORY.items()
        if rule.classification in {TableClass.CALLER_RLS, TableClass.PUBLIC_REFERENCE}
    ],
)
def test_client_accessible_tables_have_at_least_one_policy(table):
    assert expected_policy_names(table)


def test_no_legacy_clinical_write_policy_survives():
    medical_policies = expected_policy_names("medical_records")
    assert medical_policies == ("Patients read own medical records",)
    assert "Clinicians insert records" not in {p.name for _, p in ALL_POLICIES}


@pytest.mark.parametrize(
    "classification,expected_mode",
    [
        (TableClass.CALLER_RLS, ExecutionMode.CALLER_RLS),
        (TableClass.PUBLIC_REFERENCE, ExecutionMode.CALLER_RLS),
        (TableClass.SERVICE_ONLY, ExecutionMode.SERVICE_ROLE),
        (TableClass.APPEND_ONLY_AUDIT, ExecutionMode.SERVICE_ROLE),
    ],
)
def test_table_class_maps_to_a_required_execution_mode(classification, expected_mode):
    table = next(
        name
        for name, rule in DATABASE_ACCESS_INVENTORY.items()
        if rule.classification is classification
    )
    assert required_execution_mode(table) is expected_mode


def test_unknown_table_fails_closed_to_service_role_and_no_grants():
    assert required_execution_mode("not_in_inventory") is ExecutionMode.SERVICE_ROLE
    assert expected_grants("not_in_inventory", "service_role") == frozenset()


def test_coverage_helpers_report_only_unreviewed_relations():
    assert coverage_gaps(sorted(EXPECTED_TABLES)) == ()
    assert coverage_gaps(["patients", "shadow_table"]) == ("shadow_table",)
    assert unexpected_inventory_tables(sorted(EXPECTED_TABLES)) == ()
    assert unexpected_inventory_tables(["patients"]) == tuple(
        sorted(EXPECTED_TABLES - {"patients"})
    )


def test_grant_violations_detects_unexpected_and_missing_privileges():
    assert grant_violations("patients", "authenticated", ["SELECT", "INSERT", "UPDATE"]) == ()
    assert grant_violations("patients", "authenticated", ["TRUNCATE"]) == ("TRUNCATE",)
    assert grant_violations("patients", "authenticated", ["SELECT", "DELETE"]) == ("DELETE",)
    assert missing_grants("patients", "authenticated", ["SELECT"]) == ("INSERT", "UPDATE")


@pytest.mark.parametrize("signature", sorted(FUNCTION_ACCESS_INVENTORY))
def test_security_definer_functions_are_hardened(signature):
    assert function_violations(
        signature,
        security_definer=True,
        search_path=["pg_catalog", "public"],
        execute_roles=["service_role"],
    ) == ()


def test_function_guard_rejects_client_callable_or_unpinned_definer():
    signature = "get_user_permissions(uid uuid)"
    assert function_violations(
        signature,
        security_definer=True,
        search_path=["pg_catalog", "public"],
        execute_roles=["service_role", "authenticated"],
    ) == ("function is executable by an unapproved role",)
    assert function_violations(
        signature,
        security_definer=True,
        search_path=None,
        execute_roles=["service_role"],
    ) == ("fixed search_path is missing or incorrect",)
    assert function_violations(
        "unknown_function()",
        security_definer=True,
        search_path=["public"],
        execute_roles=["anon"],
    ) == ("function is not in the trusted-function inventory",)

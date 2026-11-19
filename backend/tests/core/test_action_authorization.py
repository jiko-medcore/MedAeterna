from app.core.action_authorization import (
    ACTION_MATRIX,
    ACTIONS,
    ROLE_CATEGORIES,
    evaluate_action,
)
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
)


def assignment(category, organization_id=None):
    return {"category": category, "organization_id": organization_id}


def test_matrix_covers_every_resource_action_and_known_role_category():
    assert ACTION_MATRIX
    assert all(set(rules) == set(ACTIONS) for rules in ACTION_MATRIX.values())
    assert all(
        set(role_rules).issubset(ROLE_CATEGORIES)
        for resource_rules in ACTION_MATRIX.values()
        for role_rules in resource_rules.values()
    )


def test_every_declared_rule_allows_only_when_all_gates_are_verified():
    for resource, resource_rules in ACTION_MATRIX.items():
        for action, role_rules in resource_rules.items():
            for category, rule in role_rules.items():
                actor_id = "actor-1"
                subject_user_id = (
                    actor_id if "subject_is_actor" in rule.conditions else "subject-2"
                )
                change_kind = "grant" if "no_self_grant" in rule.conditions else None
                target_role_category = None
                if "role_delegation_policy" in rule.conditions:
                    target_role_category = (
                        PRACTITIONER
                        if category == ORGANIZATION_ADMINISTRATOR
                        else ORGANIZATION_ADMINISTRATOR
                    )
                scoped = category in {
                    PRACTITIONER,
                    ORGANIZATION_ADMINISTRATOR,
                }
                result = evaluate_action(
                    actor_roles=[
                        assignment(category, "org-1" if scoped else None)
                    ],
                    resource=resource,
                    action=action,
                    actor_id=actor_id,
                    subject_user_id=subject_user_id,
                    organization_id="org-1" if scoped else None,
                    change_kind=change_kind,
                    target_role_category=target_role_category,
                    verified_conditions=set(rule.conditions),
                )
                assert result.allowed, (resource, action, category, result)


def test_every_empty_matrix_cell_is_denied():
    for resource, resource_rules in ACTION_MATRIX.items():
        for action, role_rules in resource_rules.items():
            for category in ROLE_CATEGORIES - set(role_rules):
                scoped = category in {
                    PRACTITIONER,
                    ORGANIZATION_ADMINISTRATOR,
                }
                result = evaluate_action(
                    actor_roles=[
                        assignment(category, "org-1" if scoped else None)
                    ],
                    resource=resource,
                    action=action,
                    actor_id="actor-1",
                    subject_user_id="subject-2",
                    organization_id="org-1" if scoped else None,
                    verified_conditions={
                        condition
                        for role_rule in role_rules.values()
                        for condition in role_rule.conditions
                    },
                )
                assert result.decision == "deny", (resource, action, category, result)


def test_unknown_resource_action_and_unmapped_role_deny():
    result = evaluate_action(
        actor_roles=[assignment("unmapped")],
        resource="unknown",
        action="erase",
    )
    assert result.decision == "deny"
    assert not result.allowed

    result = evaluate_action(
        actor_roles=[assignment("unmapped")],
        resource="clinical_record",
        action="read",
    )
    assert result.decision == "deny"


def test_patient_can_read_and_update_only_their_own_profile_fields():
    own_read = evaluate_action(
        actor_roles=[assignment(PATIENT)],
        resource="patient_profile",
        action="read",
        actor_id="user-1",
        subject_user_id="user-1",
    )
    assert own_read.allowed

    other_read = evaluate_action(
        actor_roles=[assignment(PATIENT)],
        resource="patient_profile",
        action="read",
        actor_id="user-1",
        subject_user_id="user-2",
    )
    assert other_read.decision == "deny"

    incomplete_update = evaluate_action(
        actor_roles=[assignment(PATIENT)],
        resource="patient_profile",
        action="update",
        actor_id="user-1",
        subject_user_id="user-1",
    )
    assert incomplete_update.decision == "conditional"
    assert incomplete_update.missing_conditions == ("permitted_fields",)

    own_update = evaluate_action(
        actor_roles=[assignment(PATIENT)],
        resource="patient_profile",
        action="update",
        actor_id="user-1",
        subject_user_id="user-1",
        verified_conditions={"permitted_fields"},
    )
    assert own_update.allowed


def test_patient_clinical_access_is_self_only_and_resource_scoped():
    result = evaluate_action(
        actor_roles=[assignment(PATIENT)],
        resource="clinical_record",
        action="read",
        actor_id="patient-1",
        subject_user_id="patient-1",
    )
    assert result.decision == "conditional"
    assert result.missing_conditions == ("permitted_resource_scope",)

    permitted = evaluate_action(
        actor_roles=[assignment(PATIENT)],
        resource="clinical_record",
        action="read",
        actor_id="patient-1",
        subject_user_id="patient-1",
        verified_conditions={"permitted_resource_scope"},
    )
    assert permitted.allowed

    cannot_create = evaluate_action(
        actor_roles=[assignment(PATIENT)],
        resource="clinical_record",
        action="create",
        actor_id="patient-1",
        subject_user_id="patient-1",
        verified_conditions={"permitted_resource_scope", "clinical_workflow"},
    )
    assert cannot_create.decision == "deny"


def test_practitioner_clinical_access_requires_org_relationship_and_workflow():
    roles = [assignment(PRACTITIONER, "org-1")]
    missing = evaluate_action(
        actor_roles=roles,
        resource="clinical_record",
        action="update",
        organization_id="org-1",
    )
    assert missing.decision == "conditional"
    assert set(missing.missing_conditions) == {
        "clinical_workflow",
        "consent_if_required",
        "patient_relationship",
    }

    allowed = evaluate_action(
        actor_roles=roles,
        resource="clinical_record",
        action="update",
        organization_id="org-1",
        verified_conditions={
            "clinical_workflow",
            "consent_if_required",
            "patient_relationship",
        },
    )
    assert allowed.allowed

    wrong_org = evaluate_action(
        actor_roles=roles,
        resource="clinical_record",
        action="read",
        organization_id="org-2",
        verified_conditions={
            "patient_relationship",
            "consent_if_required",
            "clinical_workflow",
        },
    )
    assert wrong_org.decision == "deny"


def test_clinical_record_delete_denies_even_if_other_conditions_are_met():
    result = evaluate_action(
        actor_roles=[assignment(PRACTITIONER, "org-1")],
        resource="clinical_record",
        action="delete",
        organization_id="org-1",
        verified_conditions={
            "patient_relationship",
            "consent_if_required",
            "clinical_workflow",
        },
    )
    assert result.decision == "deny"


def test_org_admin_configuration_access_is_organization_scoped():
    roles = [assignment(ORGANIZATION_ADMINISTRATOR, "org-1")]
    missing_audit = evaluate_action(
        actor_roles=roles,
        resource="organization_configuration",
        action="update",
        organization_id="org-1",
    )
    assert missing_audit.decision == "conditional"
    assert missing_audit.missing_conditions == ("audit_recorded",)

    allowed = evaluate_action(
        actor_roles=roles,
        resource="organization_configuration",
        action="update",
        organization_id="org-1",
        verified_conditions={"audit_recorded"},
    )
    assert allowed.allowed

    cross_tenant = evaluate_action(
        actor_roles=roles,
        resource="organization_configuration",
        action="update",
        organization_id="org-2",
        verified_conditions={"audit_recorded"},
    )
    assert cross_tenant.decision == "deny"


def test_org_admin_role_delegation_cannot_self_grant_but_can_self_revoke():
    roles = [assignment(ORGANIZATION_ADMINISTRATOR, "org-1")]
    conditions = {"role_delegation_policy", "audit_recorded"}
    self_grant = evaluate_action(
        actor_roles=roles,
        resource="role_assignment",
        action="administer",
        actor_id="user-1",
        subject_user_id="user-1",
        organization_id="org-1",
        change_kind="grant",
        target_role_category=PRACTITIONER,
        verified_conditions=conditions,
    )
    assert self_grant.decision == "deny"

    self_revoke = evaluate_action(
        actor_roles=roles,
        resource="role_assignment",
        action="administer",
        actor_id="user-1",
        subject_user_id="user-1",
        organization_id="org-1",
        change_kind="revoke",
        target_role_category=PRACTITIONER,
        verified_conditions=conditions,
    )
    assert self_revoke.allowed

    missing_identity = evaluate_action(
        actor_roles=roles,
        resource="role_assignment",
        action="administer",
        organization_id="org-1",
        change_kind="grant",
        target_role_category=PRACTITIONER,
        verified_conditions=conditions | {"no_self_grant"},
    )
    assert missing_identity.decision == "conditional"
    assert "no_self_grant" in missing_identity.missing_conditions


def test_role_delegation_cannot_cross_the_spec02_target_role_boundary():
    org_admin = evaluate_action(
        actor_roles=[assignment(ORGANIZATION_ADMINISTRATOR, "org-1")],
        resource="role_assignment",
        action="administer",
        actor_id="admin-1",
        subject_user_id="user-2",
        organization_id="org-1",
        change_kind="grant",
        target_role_category=ORGANIZATION_ADMINISTRATOR,
        verified_conditions={"role_delegation_policy", "audit_recorded"},
    )
    assert org_admin.decision == "deny"

    system_admin_patient = evaluate_action(
        actor_roles=[assignment(SYSTEM_ADMINISTRATOR)],
        resource="role_assignment",
        action="administer",
        actor_id="admin-1",
        subject_user_id="user-2",
        change_kind="grant",
        target_role_category=PATIENT,
        verified_conditions={"role_delegation_policy", "audit_recorded"},
    )
    assert system_admin_patient.decision == "deny"

    incomplete = evaluate_action(
        actor_roles=[assignment(SYSTEM_ADMINISTRATOR)],
        resource="role_assignment",
        action="administer",
        actor_id="admin-1",
        subject_user_id="user-2",
        change_kind="grant",
        verified_conditions={"audit_recorded"},
    )
    assert incomplete.decision == "conditional"
    assert "role_delegation_policy" in incomplete.missing_conditions


def test_system_admin_does_not_get_patient_clinical_access_from_platform_role():
    result = evaluate_action(
        actor_roles=[assignment(SYSTEM_ADMINISTRATOR)],
        resource="clinical_record",
        action="read",
        actor_id="admin-1",
        subject_user_id="patient-1",
        verified_conditions={"explicit_admin_purpose", "patient_relationship"},
    )
    assert result.decision == "deny"


def test_system_event_retry_requires_explicit_purpose_authority_and_audit():
    roles = [assignment(SYSTEM_ADMINISTRATOR)]
    missing = evaluate_action(
        actor_roles=roles,
        resource="operational_event",
        action="retry",
    )
    assert missing.decision == "conditional"
    assert set(missing.missing_conditions) == {
        "audit_recorded",
        "event_retry_authority",
        "explicit_admin_purpose",
        "event_payload_redacted",
        "patient_data_redacted",
    }

    allowed = evaluate_action(
        actor_roles=roles,
        resource="operational_event",
        action="retry",
        verified_conditions={
            "audit_recorded",
            "event_retry_authority",
            "explicit_admin_purpose",
            "event_payload_redacted",
            "patient_data_redacted",
        },
    )
    assert allowed.allowed


def test_system_admin_event_and_audit_views_require_patient_data_redaction():
    roles = [assignment(SYSTEM_ADMINISTRATOR)]
    cases = [
        ("operational_event", "read", {"explicit_admin_purpose", "event_visibility_approved", "event_payload_redacted", "audit_recorded"}),
        ("operational_event", "retry", {"explicit_admin_purpose", "event_retry_authority", "event_payload_redacted", "audit_recorded"}),
        ("audit_record", "read", {"explicit_admin_purpose", "audit_visibility_approved", "event_payload_redacted", "audit_recorded"}),
    ]

    for resource, action, remaining_conditions in cases:
        missing_redaction = evaluate_action(
            actor_roles=roles,
            resource=resource,
            action=action,
            verified_conditions=remaining_conditions,
        )
        assert missing_redaction.decision == "conditional"
        assert missing_redaction.missing_conditions == ("patient_data_redacted",)

        visible = evaluate_action(
            actor_roles=roles,
            resource=resource,
            action=action,
            verified_conditions=remaining_conditions | {"patient_data_redacted"},
        )
        assert visible.allowed

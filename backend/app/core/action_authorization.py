"""SPEC-03 action-level policy registry.

This evaluates the role/action portion of authorization. Callers must provide
verified relationship, workflow, and purpose conditions; request payloads are
not proof. Route and RLS enforcement remain separate implementation work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
)


ACTIONS = ("read", "create", "update", "delete", "administer", "retry")
ROLE_CATEGORIES = frozenset(
    {PATIENT, PRACTITIONER, ORGANIZATION_ADMINISTRATOR, SYSTEM_ADMINISTRATOR}
)
RESOURCE_FAMILIES = (
    "patient_profile",
    "patient_admin_data",
    "practitioner_profile",
    "clinical_record",
    "appointment",
    "reminder",
    "consent_preference",
    "care_team",
    "organization_configuration",
    "organization_membership",
    "role_assignment",
    "operational_event",
    "audit_record",
    "platform_configuration",
)


@dataclass(frozen=True)
class ActionRule:
    """A base permission and trusted checks required before allowing it."""

    conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionDecision:
    """Fail-closed result for one role/resource/action request."""

    decision: str
    reason: str
    missing_conditions: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


def _empty_matrix() -> dict[str, dict[str, dict[str, ActionRule]]]:
    return {
        resource: {action: {} for action in ACTIONS}
        for resource in RESOURCE_FAMILIES
    }


def _build_action_matrix() -> dict[str, dict[str, dict[str, ActionRule]]]:
    matrix = _empty_matrix()

    def add(resource: str, action: str, category: str, *conditions: str) -> None:
        matrix[resource][action][category] = ActionRule(tuple(conditions))

    add("patient_profile", "read", PATIENT, "subject_is_actor")
    add("patient_profile", "update", PATIENT, "subject_is_actor", "permitted_fields")
    add(
        "patient_admin_data",
        "read",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "patient_admin_link_verified",
        "explicit_admin_purpose",
        "minimum_patient_fields",
        "audit_recorded",
    )
    add("practitioner_profile", "read", PRACTITIONER, "subject_is_actor")

    add(
        "clinical_record",
        "read",
        PATIENT,
        "subject_is_actor",
        "permitted_resource_scope",
    )
    for action in ("read", "create", "update"):
        add(
            "clinical_record",
            action,
            PRACTITIONER,
            "organization_scope",
            "patient_relationship",
            "consent_if_required",
            "clinical_workflow",
        )

    add("appointment", "read", PATIENT, "subject_is_actor")
    add(
        "appointment",
        "read",
        PRACTITIONER,
        "organization_scope",
        "appointment_assigned_to_actor",
    )
    for action in ("create", "update"):
        add(
            "appointment",
            action,
            PRACTITIONER,
            "organization_scope",
            "patient_relationship",
            "authorized_appointment_workflow",
        )

    add("reminder", "read", PATIENT, "subject_is_actor")

    add("consent_preference", "read", PATIENT, "subject_is_actor")
    for action in ("create", "update", "administer"):
        add(
            "consent_preference",
            action,
            PATIENT,
            "subject_is_actor",
            "audit_recorded",
        )
    add(
        "consent_preference",
        "read",
        PRACTITIONER,
        "organization_scope",
        "patient_relationship",
        "consent_scope_verified",
    )

    add(
        "care_team",
        "read",
        PRACTITIONER,
        "organization_scope",
        "patient_relationship",
        "care_team_membership",
    )
    add(
        "care_team",
        "read",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "patient_relationship",
        "organization_care_authority",
    )
    for action in ("create", "update", "administer"):
        add(
            "care_team",
            action,
            ORGANIZATION_ADMINISTRATOR,
            "organization_scope",
            "patient_relationship",
            "organization_care_authority",
            "audit_recorded",
        )

    add(
        "organization_configuration",
        "read",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
    )
    for action in ("create", "update", "administer"):
        add(
            "organization_configuration",
            action,
            ORGANIZATION_ADMINISTRATOR,
            "organization_scope",
            "audit_recorded",
        )
    add(
        "organization_configuration",
        "delete",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "soft_deactivation",
        "audit_recorded",
    )

    add(
        "organization_membership",
        "read",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "minimal_member_data",
    )
    add(
        "organization_membership",
        "create",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "inviter_authority",
        "audit_recorded",
    )

    add(
        "role_assignment",
        "read",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "minimal_member_data",
    )
    add("role_assignment", "read", SYSTEM_ADMINISTRATOR, "audit_recorded")
    add(
        "role_assignment",
        "administer",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "role_delegation_policy",
        "no_self_grant",
        "audit_recorded",
    )
    add(
        "role_assignment",
        "administer",
        SYSTEM_ADMINISTRATOR,
        "role_delegation_policy",
        "no_self_grant",
        "audit_recorded",
    )

    add(
        "operational_event",
        "read",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "event_visibility_approved",
    )
    add(
        "operational_event",
        "read",
        SYSTEM_ADMINISTRATOR,
        "explicit_admin_purpose",
        "event_visibility_approved",
        "patient_data_redacted",
        "audit_recorded",
    )
    add(
        "operational_event",
        "retry",
        SYSTEM_ADMINISTRATOR,
        "explicit_admin_purpose",
        "event_retry_authority",
        "patient_data_redacted",
        "audit_recorded",
    )

    add(
        "audit_record",
        "read",
        ORGANIZATION_ADMINISTRATOR,
        "organization_scope",
        "audit_visibility_approved",
    )
    add(
        "audit_record",
        "read",
        SYSTEM_ADMINISTRATOR,
        "explicit_admin_purpose",
        "audit_visibility_approved",
        "patient_data_redacted",
        "audit_recorded",
    )

    add(
        "platform_configuration",
        "read",
        SYSTEM_ADMINISTRATOR,
        "explicit_admin_purpose",
    )
    for action in ("create", "update", "administer"):
        add(
            "platform_configuration",
            action,
            SYSTEM_ADMINISTRATOR,
            "explicit_admin_purpose",
            "audit_recorded",
        )

    return matrix


# Empty role maps are explicit denials. Unknown resources/actions also deny.
ACTION_MATRIX = _build_action_matrix()

_IDENTITY_AND_SCOPE_CONDITIONS = frozenset(
    {"subject_is_actor", "organization_scope", "no_self_grant"}
)


def _automatic_condition(
    condition: str,
    *,
    actor_id: str | None,
    subject_user_id: str | None,
    change_kind: str | None,
    category: str,
    assignment_organization_id: str | None,
    organization_id: str | None,
    target_role_category: str | None,
) -> bool | None:
    if condition == "subject_is_actor":
        if actor_id is None or subject_user_id is None:
            return None
        return str(actor_id) == str(subject_user_id)
    if condition == "organization_scope":
        return (
            category in {PRACTITIONER, ORGANIZATION_ADMINISTRATOR}
            and organization_id is not None
            and assignment_organization_id is not None
            and str(assignment_organization_id) == str(organization_id)
        )
    if condition == "no_self_grant":
        if change_kind == "revoke":
            return True
        if change_kind != "grant":
            return None
        if actor_id is None or subject_user_id is None:
            return None
        return str(actor_id) != str(subject_user_id)
    if condition == "role_delegation_policy":
        if target_role_category is None:
            return None
        allowed_targets = {
            ORGANIZATION_ADMINISTRATOR: {PRACTITIONER},
            SYSTEM_ADMINISTRATOR: {
                ORGANIZATION_ADMINISTRATOR,
                SYSTEM_ADMINISTRATOR,
            },
        }
        if target_role_category not in allowed_targets.get(category, set()):
            return False
        return None
    return None


def evaluate_action(
    *,
    actor_roles: Iterable[dict],
    resource: str,
    action: str,
    actor_id: str | None = None,
    subject_user_id: str | None = None,
    organization_id: str | None = None,
    change_kind: str | None = None,
    target_role_category: str | None = None,
    verified_conditions: Iterable[str] = (),
) -> ActionDecision:
    """Evaluate a SPEC-03 rule; external conditions must come from trusted code."""
    resource_key = resource.strip().casefold() if isinstance(resource, str) else ""
    action_key = action.strip().casefold() if isinstance(action, str) else ""
    role_rules = ACTION_MATRIX.get(resource_key, {}).get(action_key)
    if not role_rules:
        return ActionDecision("deny", "no explicit action rule")

    checked = set(verified_conditions)
    pending_conditions: set[str] = set()
    had_matching_rule = False

    for assignment in actor_roles:
        category = assignment.get("category")
        rule = role_rules.get(category)
        if category not in ROLE_CATEGORIES or rule is None:
            continue

        assignment_org = assignment.get("organization_id")
        if category in {PRACTITIONER, ORGANIZATION_ADMINISTRATOR}:
            if organization_id is None or assignment_org is None:
                continue
            if str(assignment_org) != str(organization_id):
                continue
        elif assignment_org is not None:
            continue

        had_matching_rule = True
        missing: list[str] = []
        failed = False
        for condition in rule.conditions:
            result = _automatic_condition(
                condition,
                actor_id=actor_id,
                subject_user_id=subject_user_id,
                change_kind=change_kind,
                category=category,
                assignment_organization_id=assignment_org,
                organization_id=organization_id,
                target_role_category=target_role_category,
            )
            if (
                result is None
                and condition in checked
                and condition not in _IDENTITY_AND_SCOPE_CONDITIONS
                and not (
                    condition == "role_delegation_policy"
                    and target_role_category is None
                )
            ):
                result = True
            if result is False:
                failed = True
                break
            if result is None:
                missing.append(condition)

        if failed:
            continue
        if not missing:
            return ActionDecision("allow", "explicit role/action rule satisfied")
        pending_conditions.update(missing)

    if pending_conditions:
        return ActionDecision(
            "conditional",
            "required authorization conditions are not verified",
            tuple(sorted(pending_conditions)),
        )
    if not had_matching_rule:
        return ActionDecision("deny", "no matching scoped role rule")
    return ActionDecision("deny", "a required identity or scope condition failed")

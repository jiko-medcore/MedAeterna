"""SPEC-08 explicit prohibition on system-admin patient-data access."""

from __future__ import annotations

from collections.abc import Iterable

from app.core.action_authorization import ActionDecision
from app.core.role_catalogue import SYSTEM_ADMINISTRATOR


PATIENT_DATA_RESOURCES = frozenset(
    {
        "patient_profile",
        "patient_admin_data",
        "patients",
        "patient",
        "clinical_record",
        "medical_history",
        "encounter",
        "observation",
        "condition",
        "medication",
        "medication_request",
        "prescription",
        "lab_result",
        "laboratory_result",
        "clinical_document",
        "fhir_bundle",
        "patient_summary",
        "patient_timeline",
        "appointment",
        "reminder",
        "consent_preference",
        "consent",
        "consent_record",
        "consent_records",
        "care_team",
        "patient_access",
        "patient_access_grants",
        "patient_document",
        "patient_audit_record",
        "patient_relationship",
    }
)


def evaluate_system_admin_patient_data_access(
    *,
    actor_roles: Iterable[dict],
    resource: str,
    action: str,
    break_glass_requested: bool = False,
) -> ActionDecision:
    """Deny system administrators access to patient data, including break-glass.

    This guard is for patient-related resource paths. Operational metadata has
    separate SPEC-03/SPEC-09 policy and must be redacted before system-admin
    visibility. Trusted role resolution is still the caller's responsibility.
    """
    is_system_admin = any(
        assignment.get("category") == SYSTEM_ADMINISTRATOR
        and assignment.get("organization_id") is None
        for assignment in actor_roles
    )
    if not is_system_admin:
        return ActionDecision("deny", "system-administrator assignment is required")

    resource_key = resource.strip().casefold() if isinstance(resource, str) else ""
    action_key = action.strip().casefold() if isinstance(action, str) else ""
    if resource_key not in PATIENT_DATA_RESOURCES:
        return ActionDecision("deny", "resource is outside the patient-data boundary")

    if break_glass_requested:
        return ActionDecision(
            "deny",
            "SPEC-08 does not authorize a system-administrator break-glass path",
        )
    return ActionDecision(
        "deny",
        f"system-administrator {action_key or 'unknown'} access to patient data is prohibited",
    )

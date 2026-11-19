"""SPEC-07 minimum-necessary organization-administrator patient data policy.

This reference policy does not fetch patient data or establish its own trusted
facts. Callers must resolve role assignments and patient-to-organization links
through server-side code before providing those conditions.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.core.action_authorization import ActionDecision, evaluate_action


ADMIN_PATIENT_PURPOSE_FIELDS = {
    "registration_identity": frozenset({"patient_reference", "patient_name"}),
    "appointment_coordination": frozenset(
        {"patient_reference", "patient_name", "contact_phone", "contact_email"}
    ),
    "billing_administration": frozenset(
        {
            "patient_reference",
            "patient_name",
            "contact_phone",
            "contact_email",
            "billing_reference",
            "billing_status",
        }
    ),
}


def evaluate_organization_admin_patient_access(
    *,
    actor_roles: Iterable[dict],
    organization_id: str | None,
    subject_patient_id: str | None,
    purpose: str,
    requested_fields: Iterable[str],
    patient_admin_link_verified: bool = False,
    audit_recorded: bool = False,
    bulk_access: bool = False,
) -> ActionDecision:
    """Evaluate one organization-admin read against SPEC-07.

    ``purpose`` must be selected by the server-side workflow (or strictly
    validated against that workflow), never accepted as authorization evidence
    merely because a client supplied a string. ``requested_fields`` must be
    the actual response projection, not a client-controlled projection.
    """
    if bulk_access:
        return ActionDecision("deny", "bulk patient-data access is not permitted")
    if not isinstance(subject_patient_id, str) or not subject_patient_id.strip():
        return ActionDecision("deny", "a verified patient subject is required")
    if not isinstance(purpose, str):
        return ActionDecision("deny", "administrative purpose is not approved")

    allowed_fields = ADMIN_PATIENT_PURPOSE_FIELDS.get(purpose)
    if allowed_fields is None:
        return ActionDecision("deny", "administrative purpose is not approved")

    try:
        fields = set(requested_fields)
    except TypeError:
        return ActionDecision("deny", "requested fields are invalid")
    if any(not isinstance(field, str) for field in fields):
        return ActionDecision("deny", "requested fields are invalid")
    if not fields or not fields.issubset(allowed_fields):
        return ActionDecision(
            "deny",
            "requested fields exceed the minimum data approved for this purpose",
        )

    verified_conditions = {"explicit_admin_purpose", "minimum_patient_fields"}
    if patient_admin_link_verified:
        verified_conditions.add("patient_admin_link_verified")
    if audit_recorded:
        verified_conditions.add("audit_recorded")

    return evaluate_action(
        actor_roles=actor_roles,
        resource="patient_admin_data",
        action="read",
        organization_id=organization_id,
        verified_conditions=verified_conditions,
    )

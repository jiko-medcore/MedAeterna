"""PH0-WP-02 clinical resource authorization contracts.

These helpers bind a verified identity (``get_current_user``) to a concrete
stored clinical resource before any service-layer query runs. They combine:

* SPEC-04 relationship evidence (patient ownership / active treatment
  relationship / organization care authority), and
* SPEC-03 role/action evaluation via :func:`evaluate_action`.

Request payload values are never treated as relationship evidence. Resource
patient, organization, encounter and practitioner context is loaded through a
trusted backend lookup first. Service functions must additionally accept the
returned ``authorized_context`` and validate it with
:func:`ensure_authorized_context`, so a direct service call cannot silently
bypass the route decision.

Limitations: hosted RLS/grant enforcement, purpose-specific consent evaluation
(SPEC-19), and complete workflow/audit coverage remain separate work packages.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from fastapi import Depends, HTTPException, Request, status

from app.core import security
from app.core.action_authorization import ACTIONS, evaluate_action
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    has_scoped_category,
)

CLINICAL_RECORD = "clinical_record"
APPOINTMENT = "appointment"
CARE_TEAM = "care_team"
PATIENT_LIST = "patient_list"
RESOURCES = frozenset({CLINICAL_RECORD, APPOINTMENT, CARE_TEAM})

# Columns are intentionally minimal: only context needed for authorization.
TABLE_POLICY: dict[str, dict[str, Any]] = {
    "medication_requests": {
        "columns": "id, patient_id, organization_id, encounter_id",
        "resource": CLINICAL_RECORD,
    },
    "encounters": {
        "columns": "id, patient_id, organization_id, practitioner_id, appointment_id, status",
        "resource": CLINICAL_RECORD,
    },
    "observations": {
        "columns": "id, patient_id, organization_id, encounter_id",
        "resource": CLINICAL_RECORD,
    },
    "conditions": {
        "columns": "id, patient_id, organization_id, encounter_id",
        "resource": CLINICAL_RECORD,
    },
    "appointments": {
        "columns": "id, patient_id, organization_id, practitioner_id, status",
        "resource": APPOINTMENT,
    },
    "care_teams": {
        "columns": "id, patient_id, organization_id",
        "resource": CARE_TEAM,
    },
    # Legacy clinical-history rows do not carry organization_id; organization
    # scope is resolved from the persisted patient row by the authorization path.
    "medical_records": {
        "columns": "id, patient_id, clinician_id, record_type",
        "resource": CLINICAL_RECORD,
        "relationship_resource_family": "clinical_history",
    },
    # Lab results have patient and clinician references but no organization or
    # order/specimen foreign key in the current schema. Read scope is patient-bound.
    "lab_results": {
        "columns": "id, patient_id, clinician_id",
        "resource": CLINICAL_RECORD,
        "relationship_resource_family": "lab_result",
    },
}


def _deny(detail: str, status_code: int = status.HTTP_403_FORBIDDEN) -> None:
    raise HTTPException(status_code=status_code, detail=detail)


def practitioner_actor_id(current_user: dict[str, Any]) -> str:
    """Resolve the authenticated user's practitioner identity or fail closed."""
    user_id = str(current_user.get("id") or "")
    roles = current_user.get("roles") or []
    if not user_id or not any(r.get("category") == PRACTITIONER for r in roles):
        _deny("Practitioner access required")
    practitioner_id = security.resolve_practitioner_id(user_id)
    if not practitioner_id:
        _deny("Practitioner profile required")
    return practitioner_id


def practitioner_organization_ids(current_user: dict[str, Any]) -> tuple[str, ...]:
    """Return organization scopes from the authenticated practitioner role context."""
    org_ids = {
        str(role["organization_id"])
        for role in (current_user.get("roles") or [])
        if role.get("category") == PRACTITIONER and role.get("organization_id")
    }
    return tuple(sorted(org_ids))


def resolve_practitioner_organization_id(
    current_user: dict[str, Any],
    requested_organization_id: str | None = None,
) -> str:
    """Resolve one practitioner organization, allowing only an in-scope selection."""
    org_ids = practitioner_organization_ids(current_user)
    if requested_organization_id is not None:
        requested = str(requested_organization_id)
        if requested not in org_ids:
            _deny("Organization is outside the practitioner active role scope")
        return requested
    if len(org_ids) != 1:
        _deny("An unambiguous practitioner organization is required")
    return org_ids[0]


def practitioner_organization_id(current_user: dict[str, Any]) -> str:
    """Resolve one unambiguous practitioner organization or fail closed."""
    return resolve_practitioner_organization_id(current_user)


def authorize_patient_list_access(current_user: dict[str, Any]) -> dict[str, Any]:
    """Authorize a practitioner's organization-scoped patient list operation.

    This is a closed internal list context, not a new broad data-access policy:
    the actor profile and organization are resolved from trusted role state,
    and the service still restricts results to active care-team rows in that
    exact organization.
    """
    actor_id = practitioner_actor_id(current_user)
    organization_id = practitioner_organization_id(current_user)
    return {
        **current_user,
        "authorized_action": "read",
        "authorized_resource": PATIENT_LIST,
        "authorized_user_id": str(current_user.get("id") or ""),
        "authorized_practitioner_id": actor_id,
        "authorized_organization_id": organization_id,
    }


def bind_clinical_actor(payload: Any, context: dict[str, Any]) -> Any:
    """Bind a clinical create payload to the authorized practitioner actor.

    Client-supplied practitioner IDs are relationship claims, not identity
    evidence. A forged or mismatched value is denied; an omitted value is filled
    from the already-authorized context. The returned payload is a copy so the
    original request model is not mutated.
    """
    actor_id = str(context.get("authorized_practitioner_id") or "")
    if not actor_id:
        _deny("Practitioner access required")
    if not hasattr(payload, "practitioner_id"):
        _deny("Practitioner context required", status.HTTP_400_BAD_REQUEST)
    supplied = getattr(payload, "practitioner_id")
    if supplied is not None and str(supplied) != actor_id:
        _deny("Practitioner must match the authenticated actor")
    if hasattr(payload, "model_copy"):
        return payload.model_copy(update={"practitioner_id": actor_id})
    bound = dict(payload) if isinstance(payload, dict) else payload
    if isinstance(bound, dict):
        bound["practitioner_id"] = actor_id
        return bound
    setattr(bound, "practitioner_id", actor_id)
    return bound


def _assert_same(value: Any, expected: Any, detail: str) -> None:
    if value is None or expected is None or str(value) != str(expected):
        _deny(detail)


def authorize_clinical_access(
    current_user: dict[str, Any],
    *,
    resource: str,
    action: str,
    patient_id: str,
    organization_id: str | None = None,
    verified_conditions: Iterable[str] = (),
    allow_organization_admin: bool = False,
    organization_care_authority: bool = False,
    relationship_resource_family: str = "clinical_history",
) -> dict[str, Any]:
    """Authorize one role/action against a verified patient-scoped resource.

    ``verified_conditions`` must only contain conditions established by trusted
    server-side checks (for example encounter linkage or a field allowlist).
    Identity/scope conditions from SPEC-03 are computed here and cannot be
    supplied by a caller.
    """
    if resource not in RESOURCES:
        _deny("Unknown clinical resource", status.HTTP_400_BAD_REQUEST)
    if action not in ACTIONS:
        _deny("Unknown clinical action", status.HTTP_400_BAD_REQUEST)

    user_id = str(current_user.get("id") or "")
    if not user_id:
        _deny("Authentication required", status.HTTP_401_UNAUTHORIZED)
    if not patient_id:
        _deny("Patient context required", status.HTTP_400_BAD_REQUEST)

    roles = list(current_user.get("roles") or [])
    checked = set(verified_conditions)
    is_self = has_scoped_category(roles, PATIENT) and user_id == str(patient_id)
    is_org_admin = has_scoped_category(
        roles, ORGANIZATION_ADMINISTRATOR, organization_id
    )
    is_practitioner = any(r.get("category") == PRACTITIONER for r in roles)

    context: dict[str, Any]
    if is_self:
        context = security.authorize_patient_access(
            current_user,
            str(patient_id),
            organization_id=organization_id,
            allow_practitioner=False,
            resource_family=relationship_resource_family,
            action=action,
        )
        checked.update({"subject_is_actor", "permitted_resource_scope"})
    elif is_org_admin and allow_organization_admin and organization_id:
        # Organization-admin care authority is limited to the exact organization
        # and to patients belonging to it. It never implies clinical-care access.
        patient = security.fetch_resource(
            "patients", "id, organization_id", id=str(patient_id)
        )
        if not patient:
            _deny("Patient not found", status.HTTP_404_NOT_FOUND)
        patient_org = str(patient.get("organization_id") or "") or None
        if patient_org and str(patient_org) != str(organization_id):
            _deny("Patient not found", status.HTTP_404_NOT_FOUND)
        if not organization_care_authority:
            _deny("Organization care authority required")
        checked.update({"patient_relationship", "organization_care_authority"})
        context = {
            **current_user,
            "authorized_patient_id": str(patient_id),
            "authorized_organization_id": str(organization_id),
        }
    elif is_practitioner:
        context = security.authorize_patient_access(
            current_user,
            str(patient_id),
            organization_id=organization_id,
            resource_family="clinical_history",
            action=action,
        )
        # Treatment relationship is verified above. Consent is a separate SPEC-05
        # gate and is deliberately not asserted until trusted consent policy
        # evaluation is wired into this authorization context.
        checked.add("patient_relationship")
    else:
        _deny("Access denied")

    # Organization scope may come from the stored patient/resource even when a
    # route did not accept an explicit organization parameter.
    effective_org = organization_id or context.get("authorized_organization_id")
    decision = evaluate_action(
        actor_roles=roles,
        resource=resource,
        action=action,
        actor_id=user_id,
        subject_user_id=str(patient_id),
        organization_id=str(effective_org) if effective_org else None,
        verified_conditions=checked,
    )
    if not decision.allowed:
        missing = (
            f" (missing: {', '.join(decision.missing_conditions)})"
            if decision.missing_conditions
            else ""
        )
        _deny(f"Action denied: {decision.reason}{missing}")

    return {
        **context,
        "authorized_action": action,
        "authorized_resource": resource,
        "authorized_patient_id": str(patient_id),
        "authorized_organization_id": str(effective_org) if effective_org else None,
        "authorized_user_id": user_id,
    }


def authorize_patient_scoped_access(
    current_user: dict[str, Any],
    *,
    resource: str,
    action: str,
    patient_id: str,
    organization_id: str | None = None,
    verified_conditions: Iterable[str] = (),
    allow_organization_admin: bool = False,
    organization_care_authority: bool = False,
) -> dict[str, Any]:
    """Authorize a patient-id-scoped operation (list/create/read endpoints)."""
    checked = set(verified_conditions)
    if resource == CARE_TEAM and action == "read":
        roles = current_user.get("roles") or []
        if any(r.get("category") == PRACTITIONER for r in roles) and not has_scoped_category(
            roles, ORGANIZATION_ADMINISTRATOR, organization_id
        ):
            practitioner_id = practitioner_actor_id(current_user)
            if not security.active_care_team_access(
                str(patient_id), practitioner_id, organization_id
            ):
                _deny("Care team membership required")
            checked.add("care_team_membership")
    if resource in {CLINICAL_RECORD, APPOINTMENT} and action == "read":
        # Reads are constrained to the verified patient id by the caller's query.
        checked.add("clinical_workflow")

    context = authorize_clinical_access(
        current_user,
        resource=resource,
        action=action,
        patient_id=str(patient_id),
        organization_id=organization_id,
        verified_conditions=checked,
        allow_organization_admin=allow_organization_admin,
        organization_care_authority=organization_care_authority,
    )
    return context


def authorize_table_access(
    current_user: dict[str, Any],
    table: str,
    resource_id: str,
    action: str,
    *,
    verified_conditions: Iterable[str] = (),
    relationship_resource_family: str | None = None,
) -> dict[str, Any]:
    """Load a stored resource and authorize an action against its own context."""
    policy = TABLE_POLICY.get(table)
    if not policy:
        _deny("Unknown clinical resource", status.HTTP_400_BAD_REQUEST)
    if not resource_id:
        _deny("Resource context required", status.HTTP_400_BAD_REQUEST)

    row = security.fetch_resource(table, policy["columns"], id=str(resource_id))
    if not row:
        _deny(f"{table.rstrip('s').replace('_', ' ').title()} not found", status.HTTP_404_NOT_FOUND)
    patient_id = row.get("patient_id")
    if not patient_id:
        _deny("Resource has no patient context")
    organization_id = str(row.get("organization_id") or "") or None
    resource = str(policy["resource"])
    checked = set(verified_conditions)

    roles = current_user.get("roles") or []
    if resource == APPOINTMENT and any(r.get("category") == PRACTITIONER for r in roles):
        practitioner_id = practitioner_actor_id(current_user)
        _assert_same(
            row.get("practitioner_id"),
            practitioner_id,
            "Appointment is not assigned to this practitioner",
        )
        checked.add("appointment_assigned_to_actor")

    if resource == CARE_TEAM:
        is_org_admin = has_scoped_category(
        roles, ORGANIZATION_ADMINISTRATOR, organization_id
    )
        if is_org_admin:
            if not organization_id:
                _deny("Organization context required", status.HTTP_400_BAD_REQUEST)
            checked.update({"organization_care_authority", "audit_recorded"})
        else:
            practitioner_id = practitioner_actor_id(current_user)
            if not security.active_care_team_access(
                str(patient_id), practitioner_id, organization_id
            ):
                _deny("Care team membership required")
            checked.add("care_team_membership")

    if resource == CLINICAL_RECORD and action == "read":
        # The resource was loaded by id and bound to its stored patient below.
        checked.add("clinical_workflow")

    context = authorize_clinical_access(
        current_user,
        resource=resource,
        action=action,
        patient_id=str(patient_id),
        organization_id=organization_id,
        verified_conditions=checked,
        allow_organization_admin=resource == CARE_TEAM,
        organization_care_authority="organization_care_authority" in checked,
        relationship_resource_family=(
            relationship_resource_family
            or policy.get("relationship_resource_family", "clinical_history")
        ),
    )
    return {
        **context,
        "authorized_resource_id": str(resource_id),
        "resource_row": row,
    }


def authorize_practitioner_schedule_access(
    current_user: dict[str, Any],
    *,
    practitioner_id: str,
    organization_id: str | None,
) -> dict[str, Any]:
    """Authorize a practitioner's own appointment list (no patient target)."""
    actor_practitioner_id = practitioner_actor_id(current_user)
    _assert_same(
        actor_practitioner_id,
        practitioner_id,
        "Practitioners may only view their own schedule",
    )
    if not organization_id:
        _deny("Organization context required", status.HTTP_400_BAD_REQUEST)
    decision = evaluate_action(
        actor_roles=current_user.get("roles") or [],
        resource=APPOINTMENT,
        action="read",
        actor_id=str(current_user.get("id") or ""),
        organization_id=str(organization_id),
        verified_conditions={"appointment_assigned_to_actor"},
    )
    if not decision.allowed:
        _deny(f"Action denied: {decision.reason}")
    return {
        **current_user,
        "authorized_action": "read",
        "authorized_resource": APPOINTMENT,
        "authorized_organization_id": str(organization_id),
        "authorized_user_id": str(current_user.get("id") or ""),
        "authorized_practitioner_id": str(actor_practitioner_id),
    }


def ensure_authorized_context(
    context: dict[str, Any] | None,
    *,
    resource: str,
    action: str,
    patient_id: str | None = None,
    organization_id: str | None = None,
    resource_id: str | None = None,
) -> None:
    """Fail a direct service call unless it carries a matching route decision."""
    if not isinstance(context, dict) or not context:
        _deny("Authorized context required")
    if context.get("authorized_resource") != resource or context.get("authorized_action") != action:
        _deny("Action not authorized")
    # The service boundary requires an explicit actor binding from authorization.
    # The ordinary authenticated-user id is not an authorization-context substitute.
    if not context.get("authorized_user_id"):
        _deny("Authorized actor context required", status.HTTP_401_UNAUTHORIZED)
    if patient_id is not None and str(context.get("authorized_patient_id") or "") != str(patient_id):
        _deny("Patient scope mismatch")
    if organization_id is not None and str(context.get("authorized_organization_id") or "") != str(organization_id):
        _deny("Organization scope mismatch")
    if resource_id is not None and str(context.get("authorized_resource_id") or "") != str(resource_id):
        _deny("Resource scope mismatch")


def require_patient_clinical(
    resource: str,
    action: str,
    *,
    allow_organization_admin: bool = False,
    organization_care_authority: bool = False,
) -> Callable:
    """Dependency for patient-id-scoped reads."""

    def dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(security.get_current_user),
    ) -> dict[str, Any]:
        patient_id = request.path_params.get("patient_id") or request.query_params.get("patient_id")
        organization_id = (
            request.path_params.get("organization_id")
            or request.query_params.get("organization_id")
        )
        if not patient_id:
            _deny("Patient context required", status.HTTP_400_BAD_REQUEST)
        return authorize_patient_scoped_access(
            current_user,
            resource=resource,
            action=action,
            patient_id=str(patient_id),
            organization_id=str(organization_id) if organization_id else None,
            allow_organization_admin=allow_organization_admin,
            organization_care_authority=organization_care_authority,
        )

    return dependency


def require_encounter_clinical(resource: str, action: str) -> Callable:
    """Dependency that resolves patient/org from a stored encounter first."""

    def dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(security.get_current_user),
    ) -> dict[str, Any]:
        encounter_id = request.path_params.get("encounter_id") or request.query_params.get("encounter_id")
        if not encounter_id:
            _deny("Encounter context required", status.HTTP_400_BAD_REQUEST)
        encounter = security.fetch_resource(
            "encounters", "id, patient_id, organization_id", id=str(encounter_id)
        )
        if not encounter:
            _deny("Encounter not found", status.HTTP_404_NOT_FOUND)
        context = authorize_patient_scoped_access(
            current_user,
            resource=resource,
            action=action,
            patient_id=str(encounter["patient_id"]),
            organization_id=(
                str(encounter.get("organization_id") or "") or None
            ),
            verified_conditions={"encounter_resolved"},
        )
        return {**context, "authorized_resource_id": str(encounter["id"])}

    return dependency


def require_table_clinical(
    table: str,
    id_param: str,
    action: str,
    *,
    verified_conditions: Iterable[str] = (),
) -> Callable:
    """Dependency for resource-id-scoped reads and constrained updates."""

    def dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(security.get_current_user),
    ) -> dict[str, Any]:
        resource_id = request.path_params.get(id_param) or request.query_params.get(id_param)
        return authorize_table_access(
            current_user,
            table,
            str(resource_id or ""),
            action,
            verified_conditions=verified_conditions,
        )

    return dependency


def audit_clinical_write(context: dict[str, Any], *, action: str, resource_type: str, resource_id: str) -> None:
    """Record an attributable audit event for a sensitive care-team write."""
    from app.core.audit.service import log_audit_event

    log_audit_event(
        actor_id=str(context.get("authorized_user_id") or context.get("id") or ""),
        actor_type="user",
        action=f"{resource_type}.{action}",
        resource_type=resource_type,
        resource_id=str(resource_id),
        metadata={
            "patient_id": context.get("authorized_patient_id"),
            "organization_id": context.get("authorized_organization_id"),
        },
    )

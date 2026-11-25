from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
    has_scoped_category,
    normalize_role_assignment,
)
from app.core.supabase_admin import supabase_admin
from app.core.patient_relationship_policy import RelationshipEvidence, evaluate_patient_relationship

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class AuthorizationError(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


def _deny(detail: str = "Access denied", status_code: int = status.HTTP_403_FORBIDDEN) -> None:
    raise AuthorizationError(status_code=status_code, detail=detail)


def _require_authenticated(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return credentials.credentials


def _is_invalid_access_token_error(exc: Exception) -> bool:
    """Return True only for Supabase Auth errors that identify bad user credentials.

    Auth infrastructure failures (5xx, rate limits, transport failures, and
    unexpected client errors) must not be misreported as invalid credentials.
    The SDK exposes stable error codes; class names are retained as a
    compatibility fallback for locally raised auth errors.
    """
    code = str(getattr(exc, "code", "") or "").casefold()
    error_name = type(exc).__name__
    invalid_codes = {
        "bad_jwt",
        "invalid_credentials",
        "session_expired",
        "session_not_found",
        "user_not_found",
    }
    invalid_error_names = {
        "AuthInvalidJwtError",
        "AuthInvalidCredentialsError",
        "AuthSessionMissingError",
        "UserDoesNotExistError",
    }
    raw_status = (
        getattr(exc, "status_code", None)
        or getattr(exc, "status", None)
        or getattr(exc, "http_status", None)
    )
    try:
        error_status = int(raw_status) if raw_status is not None else None
    except (TypeError, ValueError):
        error_status = None
    if error_status is None or not 400 <= error_status < 500:
        return False
    return code in invalid_codes or error_name in invalid_error_names


def _load_active_role_context(user_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Load and normalize active role assignments using the trusted backend client."""
    role_rows = (
        supabase_admin.table("user_roles")
        .select("organization_id, role_id, status")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .execute()
    ).data or []

    if not role_rows:
        _deny("User has no assigned roles")

    role_ids = sorted({str(row["role_id"]) for row in role_rows if row.get("role_id")})
    if not role_ids:
        _deny("User has no assigned roles")

    role_lookup_rows = (
        supabase_admin.table("roles")
        .select("id, name, role_type, organization_id, is_active")
        .in_("id", role_ids)
        .execute()
    ).data or []
    role_lookup = {str(role["id"]): role for role in role_lookup_rows if role.get("id")}

    roles: list[dict[str, Any]] = []
    organization_ids: set[str] = set()

    for assignment in role_rows:
        role_info = role_lookup.get(str(assignment.get("role_id") or ""))
        if not role_info:
            # A dangling role reference is not authority. Other valid assignments
            # may still establish the user's recognized authorization context.
            continue

        normalized = normalize_role_assignment(
            role_name=role_info.get("name") or "",
            role_type=role_info.get("role_type"),
            organization_id=assignment.get("organization_id"),
            role_organization_id=role_info.get("organization_id"),
            role_is_active=role_info.get("is_active"),
        )
        roles.append(normalized)

        if (
            normalized["category"] in {PRACTITIONER, ORGANIZATION_ADMINISTRATOR}
            and assignment.get("organization_id")
        ):
            organization_ids.add(str(assignment["organization_id"]))

    recognized_categories = {
        PATIENT,
        PRACTITIONER,
        ORGANIZATION_ADMINISTRATOR,
        SYSTEM_ADMINISTRATOR,
    }
    if not any(role.get("category") in recognized_categories for role in roles):
        _deny("User has no recognized active role assignments")

    return roles, sorted(organization_ids)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    """Validate a bearer token and resolve trusted identity/role context.

    Supabase Auth establishes the user identity. The trusted service-role client
    then resolves active role assignments and active role definitions. Auth
    verification and role-resolution failures are intentionally distinguished:
    invalid user credentials return 401, while an unavailable trust dependency
    returns 503 and never produces a partially authorized user context.
    """
    from app.core.supabase_client import supabase

    token = _require_authenticated(credentials)

    try:
        response = supabase.auth.get_user(token)
        user = getattr(response, "user", None)
    except Exception as exc:
        if _is_invalid_access_token_error(exc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from exc
        logger.error(
            "Supabase Auth verification unavailable (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        ) from exc

    user_id = getattr(user, "id", None) if user else None
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )

    try:
        roles, organization_ids = _load_active_role_context(str(user_id))
    except AuthorizationError:
        raise
    except Exception as exc:
        logger.error(
            "Trusted role resolution unavailable (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization context temporarily unavailable",
        ) from exc

    legacy_role = (
        roles[0]["name"]
        if len(roles) == 1 and roles[0].get("category") != "unmapped"
        else None
    )

    return {
        "id": str(user_id),
        "email": getattr(user, "email", None),
        "role": legacy_role,
        "roles": roles,
        "organization_ids": organization_ids,
        "is_patient": has_scoped_category(roles, PATIENT),
        "is_practitioner": has_scoped_category(roles, PRACTITIONER)
        or any(role.get("category") == PRACTITIONER for role in roles),
        "is_admin": has_scoped_category(roles, SYSTEM_ADMINISTRATOR),
        "is_org_admin": any(
            role.get("category") == ORGANIZATION_ADMINISTRATOR for role in roles
        ),
        "is_super_admin": has_scoped_category(roles, SYSTEM_ADMINISTRATOR),
    }


def require_role(required_role: str) -> Callable:
    """Require a recognized active global system role assignment."""

    def checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        required_name = (required_role or "").strip().casefold()
        has_system_role = any(
            (role.get("name") or "").strip().casefold() == required_name
            and role.get("role_type") == "system"
            and role.get("organization_id") is None
            and role.get("category") != "unmapped"
            for role in current_user.get("roles", [])
        )
        if not has_system_role:
            _deny("Insufficient permissions")
        return current_user

    return checker


def require_system_admin() -> Callable:
    def checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not has_scoped_category(current_user.get("roles", []), SYSTEM_ADMINISTRATOR):
            _deny("System administrator access required")
        return current_user

    return checker


def _extract_org_id(request: Request, org_id_param: str | None = None) -> str | None:
    candidates = []
    if org_id_param:
        candidates.append(org_id_param)
    candidates.extend(["org_id", "organization_id"])
    for name in candidates:
        value = request.path_params.get(name)
        if value:
            return str(value)
        value = request.query_params.get(name)
        if value:
            return str(value)
    return None


def get_user_permissions(
    user_id: str,
    *,
    organization_id: str | None = None,
) -> set[str]:
    """Return permission names for a user via trusted backend lookup.

    When organization_id is provided, permissions are restricted to active
    assignments in that organization. Without organization context this returns
    permissions from all active assignments and must not be used as proof of
    access to a specific organization-scoped resource.
    """
    query = (
        supabase_admin.table("user_roles")
        .select(
            "organization_id, status, roles!inner(is_active, role_permissions!inner(permissions!inner(name)))"
        )
        .eq("user_id", str(user_id))
        .eq("status", "active")
    )
    if organization_id is not None:
        query = query.eq("organization_id", str(organization_id))

    result = query.execute().data or []
    permissions: set[str] = set()
    for row in result:
        role = row.get("roles") or {}
        if role.get("is_active") is not True:
            continue
        if organization_id is not None and str(row.get("organization_id") or "") != str(organization_id):
            continue
        for rp in role.get("role_permissions") or []:
            perm = (rp or {}).get("permissions") or {}
            name = perm.get("name")
            if name:
                permissions.add(str(name))
    return permissions


def _resolve_resource_derived_org_id(request: Request) -> str | None:
    """Best-effort resource-derived organization context for permission checks.

    Uses only trusted server-side resource lookups. Returns None when context
    cannot be derived safely from request path/query parameters.
    """
    path = request.url.path.rstrip("/")

    # Patient-scoped resources.
    patient_id = request.path_params.get("patient_id") or request.query_params.get("patient_id")
    if patient_id:
        patient = _fetch_patient(str(patient_id))
        if not patient:
            raise AuthorizationError(status.HTTP_404_NOT_FOUND, "Patient not found")
        return str(patient.get("organization_id") or "") or None

    # Encounter-scoped resources.
    encounter_id = request.path_params.get("encounter_id") or request.query_params.get("encounter_id")
    if encounter_id:
        encounter = _get_encounter(str(encounter_id))
        if not encounter:
            raise AuthorizationError(status.HTTP_404_NOT_FOUND, "Encounter not found")
        return str(encounter.get("organization_id") or "") or None

    # Appointment-scoped resources.
    appointment_id = request.path_params.get("appointment_id") or request.query_params.get("appointment_id")
    if appointment_id:
        appointment = _get_appointment(str(appointment_id))
        if not appointment:
            raise AuthorizationError(status.HTTP_404_NOT_FOUND, "Appointment not found")
        return str(appointment.get("organization_id") or "") or None

    # Organization-self routes derive scope from verified membership when unambiguous.
    if path in {"/organizations/me", "/organizations/update", "/organizations/upload-logo"}:
        # Caller-provided membership claims are not sufficient; resolve from trusted assignments.
        return None

    return None


def _resolve_permission_org_context(
    *,
    request: Request,
    current_user: dict[str, Any],
    permission_name: str,
    org_id_param: str | None,
) -> str:
    org_id = _extract_org_id(request, org_id_param)
    if org_id:
        return str(org_id)

    # Resource-derived context (patient/encounter/etc.) when available.
    derived = _resolve_resource_derived_org_id(request)
    if derived:
        return str(derived)

    # Organization-self routes may derive scope from caller's verified organization membership.
    # Fail closed for ambiguous multi-organization contexts.
    path = request.url.path.rstrip("/")
    if path in {"/organizations/me", "/organizations/update", "/organizations/upload-logo"}:
        user_id = str(current_user.get("id") or "")
        if not user_id:
            raise AuthorizationError(status.HTTP_401_UNAUTHORIZED, "Authentication required")
        # Use trusted active role assignments in DB as source of org membership.
        membership_rows = (
            supabase_admin.table("user_roles")
            .select("organization_id, status, roles!inner(name, role_type, organization_id, is_active)")
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        ).data or []
        org_ids: set[str] = set()
        for row in membership_rows:
            role = row.get("roles") or {}
            assignment = normalize_role_assignment(
                role_name=role.get("name") or "",
                role_type=role.get("role_type"),
                organization_id=row.get("organization_id"),
                role_organization_id=role.get("organization_id"),
                role_is_active=role.get("is_active") is True,
            )
            if assignment.get("category") == ORGANIZATION_ADMINISTRATOR and row.get("organization_id"):
                org_ids.add(str(row["organization_id"]))
        if len(org_ids) == 1:
            return next(iter(org_ids))
        if len(org_ids) > 1:
            raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Organization context required")
        raise AuthorizationError(status.HTTP_403_FORBIDDEN, "Organization access denied")

    raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Organization context required")


def authorize_permission(
    current_user: dict[str, Any],
    permission_name: str,
    organization_id: str,
) -> dict[str, Any]:
    """Programmatic permission check with explicit organization context."""
    user_id = str(current_user.get("id") or "")
    if not user_id:
        _deny("Authentication required", status.HTTP_401_UNAUTHORIZED)
    if not organization_id:
        raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Organization context required")
    permissions = get_user_permissions(user_id, organization_id=str(organization_id))
    if permission_name not in permissions:
        _deny("Permission denied")
    enriched = dict(current_user)
    enriched["authorized_organization_id"] = str(organization_id)
    return enriched


def require_permission(permission_name: str, org_id_param: str = "org_id") -> Callable:
    """Require an organization-scoped permission with explicit/fail-closed context.

    Organization context must be explicit in request params or safely derivable
    from a trusted resource (e.g. patient/encounter path param). For operations
    where context is only available in request body, callers must perform an
    explicit programmatic check after resolving the target resource.
    """

    def checker(
        request: Request,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        org_id = _resolve_permission_org_context(
            request=request,
            current_user=current_user,
            permission_name=permission_name,
            org_id_param=org_id_param,
        )
        return authorize_permission(current_user, permission_name, org_id)

    return checker


def _fetch_single(table: str, columns: str, **filters: Any) -> dict[str, Any] | None:
    query = supabase_admin.table(table).select(columns)
    for key, value in filters.items():
        if value is None:
            query = query.is_(key, "null")
        else:
            query = query.eq(key, value)
    result = query.limit(1).execute()
    data = result.data or []
    return data[0] if data else None


def _fetch_patient(patient_id: str) -> dict[str, Any] | None:
    return _fetch_single("patients", "id, organization_id", id=str(patient_id))


def _resolve_practitioner_id(user_id: str) -> str | None:
    """Resolve exactly one practitioner profile linked to the authenticated user."""
    if not user_id:
        return None
    rows = (
        supabase_admin.table("practitioners")
        .select("id, profile_id")
        .eq("profile_id", str(user_id))
        .limit(2)
        .execute()
    ).data or []
    if len(rows) != 1:
        return None
    row = rows[0]
    if str(row.get("profile_id") or "") != str(user_id) or not row.get("id"):
        return None
    return str(row["id"])


def _parse_relationship_time(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _load_active_treatment_evidence(
    patient_id: str, practitioner_id: str, organization_id: str, *, now: datetime
) -> list[RelationshipEvidence]:
    """Load trusted patient_care_team evidence; malformed rows never authorize."""
    rows = (
        supabase_admin.table("patient_care_team")
        .select("id, patient_id, practitioner_id, organization_id, status, start_date, end_date")
        .eq("patient_id", str(patient_id))
        .eq("practitioner_id", str(practitioner_id))
        .eq("organization_id", str(organization_id))
        .eq("status", "active")
        .execute()
    ).data or []
    evidence: list[RelationshipEvidence] = []
    for row in rows:
        if (
            str(row.get("patient_id") or "") != str(patient_id)
            or str(row.get("practitioner_id") or "") != str(practitioner_id)
            or str(row.get("organization_id") or "") != str(organization_id)
            or row.get("status") != "active"
        ):
            continue
        start_value, end_value = row.get("start_date"), row.get("end_date")
        effective_from = _parse_relationship_time(start_value) if start_value is not None else None
        effective_until = _parse_relationship_time(end_value) if end_value is not None else None
        if start_value is not None and effective_from is None:
            continue
        if end_value is not None and effective_until is None:
            continue
        evidence.append(RelationshipEvidence(
            kind="active_treatment", status="active",
            patient_id=str(patient_id), practitioner_id=str(practitioner_id),
            organization_id=str(organization_id), effective_from=effective_from,
            effective_until=effective_until, source_verified=bool(row.get("id")),
        ))
    return evidence


def _active_care_team_access(patient_id: str, practitioner_id: str, organization_id: str | None) -> bool:
    """Compatibility boolean backed only by current authoritative assignments."""
    if not organization_id:
        return False
    now = datetime.now(timezone.utc)
    return evaluate_patient_relationship(
        actor_user_id="internal-verification", actor_category=PRACTITIONER,
        actor_practitioner_id=str(practitioner_id),
        linked_practitioner_user_id="internal-verification",
        patient_id=str(patient_id), organization_id=str(organization_id),
        resource_family="clinical_history", action="read",
        evidence=_load_active_treatment_evidence(
            str(patient_id), str(practitioner_id), str(organization_id), now=now
        ), now=now,
    ).allowed


def authorize_patient_access(
    current_user: dict[str, Any],
    patient_id: str,
    *,
    organization_id: str | None = None,
    allow_patient_self: bool = True,
    allow_practitioner: bool = True,
    require_organization_context: bool = False,
    resource_family: str = "clinical_history",
    action: str = "read",
) -> dict[str, Any]:
    """Resolve trusted patient relationship evidence and delegate to SPEC-04."""
    if not patient_id:
        raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Patient context required")
    patient = _fetch_patient(str(patient_id))
    if not patient:
        raise AuthorizationError(status.HTTP_404_NOT_FOUND, "Patient not found")
    patient_org_id = str(patient.get("organization_id") or "") or None
    resolved_org_id = str(organization_id) if organization_id else patient_org_id
    if require_organization_context and not resolved_org_id:
        raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Organization context required")
    if organization_id and patient_org_id and str(organization_id) != patient_org_id:
        raise AuthorizationError(status.HTTP_404_NOT_FOUND, "Patient not found")

    user_id = str(current_user.get("id") or "")
    roles = current_user.get("roles") or []
    patient_actor = allow_patient_self and has_scoped_category(roles, PATIENT) and user_id == str(patient_id)
    practitioner_actor = allow_practitioner and any(r.get("category") == PRACTITIONER for r in roles)

    if patient_actor:
        decision = evaluate_patient_relationship(
            actor_user_id=user_id, actor_category=PATIENT, actor_patient_id=user_id,
            patient_id=str(patient_id), organization_id=resolved_org_id,
            resource_family=resource_family, action=action, evidence=(),
            now=datetime.now(timezone.utc),
        )
        if decision.allowed:
            return {**current_user, "authorized_patient_id": str(patient_id),
                    "authorized_organization_id": resolved_org_id}
        _deny("Patient access denied")

    if has_scoped_category(roles, SYSTEM_ADMINISTRATOR) and not has_scoped_category(roles, PATIENT):
        _deny("Patient access denied")

    if practitioner_actor and resolved_org_id:
        practitioner_id = _resolve_practitioner_id(user_id)
        if practitioner_id:
            now = datetime.now(timezone.utc)
            evidence = _load_active_treatment_evidence(
                str(patient_id), practitioner_id, str(resolved_org_id), now=now
            )
            decision = evaluate_patient_relationship(
                actor_user_id=user_id, actor_category=PRACTITIONER,
                actor_practitioner_id=practitioner_id, linked_practitioner_user_id=user_id,
                patient_id=str(patient_id), organization_id=str(resolved_org_id),
                resource_family=resource_family, action=action, evidence=evidence, now=now,
            )
            if decision.allowed:
                return {**current_user, "authorized_patient_id": str(patient_id),
                        "authorized_organization_id": str(resolved_org_id),
                        "authorized_practitioner_id": practitioner_id}
    _deny("Patient access denied")
    raise AssertionError("unreachable")


def require_patient_access(
    patient_id: str | None = None,
    current_user: dict[str, Any] | None = None,
    *,
    organization_id: str | None = None,
):
    """Canonical patient-access dependency/service.

    - Dependency usage: ``Depends(require_patient_access())`` with path/query
      params ``patient_id`` and optional ``organization_id``.
    - Programmatic usage: ``require_patient_access(patient_id, current_user)``
      or ``require_patient_access(patient_id, current_user, organization_id=...)``.
    """

    if current_user is not None and patient_id is not None:
        return authorize_patient_access(
            current_user,
            str(patient_id),
            organization_id=str(organization_id) if organization_id else None,
        )

    async def dependency(
        request: Request,
        user: dict[str, Any] = Depends(get_current_user),
        patient_id_param: str | None = None,
        organization_id_param: str | None = None,
    ) -> dict[str, Any]:
        pid = (
            patient_id
            or patient_id_param
            or request.path_params.get("patient_id")
            or request.query_params.get("patient_id")
        )
        oid = (
            organization_id
            or organization_id_param
            or request.path_params.get("organization_id")
            or request.path_params.get("org_id")
            or request.query_params.get("organization_id")
        )
        if not pid:
            raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Patient context required")
        return authorize_patient_access(
            user,
            str(pid),
            organization_id=str(oid) if oid else None,
        )

    return dependency


def require_patient_access_for_resource(
    *,
    patient_id_param: str = "patient_id",
    organization_id_param: str | None = None,
    require_org: bool = False,
) -> Callable:
    def dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        patient_id = request.path_params.get(patient_id_param) or request.query_params.get(patient_id_param)
        organization_id = None
        if organization_id_param:
            organization_id = request.path_params.get(organization_id_param) or request.query_params.get(organization_id_param)
        organization_id = organization_id or request.path_params.get("organization_id") or request.query_params.get("organization_id")
        if not patient_id:
            raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Patient context required")
        if require_org and not organization_id:
            # Derive from patient if possible; helper will fail closed as needed.
            pass
        return authorize_patient_access(
            current_user,
            str(patient_id),
            organization_id=str(organization_id) if organization_id else None,
            require_organization_context=require_org,
        )

    return dependency


def _get_encounter(encounter_id: str) -> dict[str, Any] | None:
    return _fetch_single("encounters", "id, patient_id, organization_id, practitioner_id", id=str(encounter_id))


def _get_appointment(appointment_id: str) -> dict[str, Any] | None:
    return _fetch_single(
        "appointments",
        "id, patient_id, organization_id, practitioner_id",
        id=str(appointment_id),
    )


def authorize_encounter_access(
    current_user: dict[str, Any],
    encounter_id: str,
    *,
    organization_id: str | None = None,
) -> dict[str, Any]:
    encounter = _get_encounter(encounter_id)
    if not encounter:
        raise AuthorizationError(status.HTTP_404_NOT_FOUND, "Encounter not found")
    if organization_id and encounter.get("organization_id") and str(organization_id) != str(encounter["organization_id"]):
        raise AuthorizationError(status.HTTP_404_NOT_FOUND, "Encounter not found")
    return authorize_patient_access(
        current_user,
        str(encounter["patient_id"]),
        organization_id=str(encounter.get("organization_id") or organization_id or "") or None,
    )


def require_encounter_access(encounter_id_param: str = "encounter_id") -> Callable:
    def dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        encounter_id = request.path_params.get(encounter_id_param)
        if not encounter_id:
            raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Encounter context required")
        return authorize_encounter_access(current_user, str(encounter_id))

    return dependency


def require_practitioner(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if not any(r.get("category") == PRACTITIONER for r in current_user.get("roles", [])):
        _deny("Practitioner access required")
    practitioner_id = _resolve_practitioner_id(str(current_user["id"]))
    if not practitioner_id:
        _deny("Practitioner profile required")
    practitioner = _fetch_single("practitioners", "*", id=practitioner_id)
    if not practitioner:
        _deny("Practitioner profile required")
    enriched = dict(practitioner)
    enriched["user_id"] = str(current_user["id"])
    enriched["auth_context"] = current_user
    return enriched


def require_org_role(
    required_role: str | list[str] | None = None,
    *,
    organization_id: str | None = None,
    allowed_roles: list[str] | None = None,
    organization_id_param: str = "organization_id",
):
    """Organization-scoped practitioner role dependency (canonical).

    Supports legacy call style ``require_org_role(organization_id, allowed_roles)``
    by detecting a UUID-like first argument used as organization id in older code.
    """
    # Legacy compatibility: require_org_role(organization_id, [roles...])
    if (
        isinstance(required_role, str)
        and allowed_roles is None
        and organization_id is None
        and required_role.count("-") >= 4
    ):
        legacy_org_id = required_role
        legacy_allowed = None
        # cannot see second positional here except via signature change; handled by callers migrated below
        # keep simple: treat as org id when called positionally in old style
        def legacy_dependency(
            request: Request,
            practitioner: dict[str, Any] = Depends(require_practitioner),
        ) -> dict[str, Any]:
            org_id = legacy_org_id or request.path_params.get(organization_id_param) or request.path_params.get("org_id")
            if not org_id:
                raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Organization context required")
            query = (
                supabase_admin.table("practitioner_roles")
                .select("*")
                .eq("practitioner_id", str(practitioner["id"]))
                .eq("organization_id", str(org_id))
                .eq("active", True)
            )
            response = query.execute()
            if not (response.data or []):
                _deny("Organization access denied")
            return (response.data or [practitioner])[0]
        return legacy_dependency

    roles_filter: list[str] | None
    if isinstance(required_role, list):
        roles_filter = required_role
    elif isinstance(required_role, str) and required_role:
        roles_filter = [required_role]
    else:
        roles_filter = allowed_roles

    def dependency(
        request: Request,
        practitioner: dict[str, Any] = Depends(require_practitioner),
    ) -> dict[str, Any]:
        org_id = (
            organization_id
            or request.path_params.get(organization_id_param)
            or request.path_params.get("org_id")
            or request.query_params.get("organization_id")
        )
        if not org_id:
            raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Organization context required")

        query = (
            supabase_admin.table("practitioner_roles")
            .select("*")
            .eq("practitioner_id", str(practitioner["id"]))
            .eq("organization_id", str(org_id))
            .eq("active", True)
        )
        if roles_filter:
            query = query.in_("role_code", roles_filter)
        response = query.execute()
        if not (response.data or []):
            _deny("Organization access denied")
        return (response.data or [practitioner])[0]

    return dependency


def require_patient_access_manual(patient_id: str, user_id: str) -> bool:
    """Compatibility wrapper for legacy manual checks.

    Resolves the user context by id and authorizes against the target patient.
    Prefer ``authorize_patient_access`` with an authenticated user object.
    """
    if not patient_id or not user_id:
        raise AuthorizationError(status.HTTP_400_BAD_REQUEST, "Patient context required")
    # Build a minimal trusted context from active role assignments.
    role_rows = (
        supabase_admin.table("user_roles")
        .select("organization_id, role_id, status")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .execute()
    ).data or []
    role_ids = [r["role_id"] for r in role_rows if r.get("role_id")]
    role_lookup_rows = (
        supabase_admin.table("roles")
        .select("id, name, role_type, organization_id, is_active")
        .in_("id", role_ids)
        .execute()
    ).data or [] if role_ids else []
    role_lookup = {r["id"]: r for r in role_lookup_rows}
    roles = []
    for assignment in role_rows:
        info = role_lookup.get(assignment.get("role_id"))
        if not info:
            continue
        roles.append(
            normalize_role_assignment(
                role_name=info["name"],
                role_type=info.get("role_type"),
                organization_id=assignment.get("organization_id"),
                role_organization_id=info.get("organization_id"),
                role_is_active=info.get("is_active"),
            )
        )
    if not roles:
        _deny("User has no assigned roles")
    user = {"id": str(user_id), "roles": roles}
    authorize_patient_access(user, str(patient_id))
    return True


# --- Trusted resource/relationship helpers used by clinical authorization ---
# These are thin public aliases for the private lookups above. They keep the
# service-role fetch in one module so callers do not duplicate query logic.

def fetch_resource(table: str, columns: str, **filters: Any) -> dict[str, Any] | None:
    """Fetch one resource row for authorization context (never for display)."""
    return _fetch_single(table, columns, **filters)


def resolve_practitioner_id(user_id: str) -> str | None:
    """Resolve an authenticated user to a verified practitioner identity."""
    return _resolve_practitioner_id(str(user_id))


def active_care_team_access(
    patient_id: str, practitioner_id: str, organization_id: str | None
) -> bool:
    """Check an active, organization-bound care-team treatment relationship."""
    return _active_care_team_access(str(patient_id), str(practitioner_id), organization_id)


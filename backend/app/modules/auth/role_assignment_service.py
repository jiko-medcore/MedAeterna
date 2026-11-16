"""Trusted role-assignment writes for SPEC-02."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.role_assignment_policy import authorize_role_change
from app.core.supabase_admin import supabase_admin


def _find_role(role_name: str, organization_id: str | None) -> dict[str, Any]:
    query = (
        supabase_admin.table("roles")
        .select("id, name, role_type, organization_id, is_active")
        .eq("name", role_name.strip())
    )
    if organization_id is None:
        query = query.is_("organization_id", "null")
    else:
        query = query.eq("organization_id", str(organization_id))

    result = query.maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Role not found")
    return result.data


def _validate_target_user(target_user_id: str) -> None:
    try:
        result = supabase_admin.auth.admin.get_user_by_id(str(target_user_id))
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Target user not found") from exc
    if not getattr(result, "user", None):
        raise HTTPException(status_code=404, detail="Target user not found")


def _change_assignment(
    *,
    actor_id: str | None,
    actor_type: str,
    target_user_id: str,
    role_name: str,
    organization_id: str | None,
    actor_roles: list[dict[str, Any]],
    action: str,
    reason: str | None = None,
) -> dict[str, Any]:
    role = _find_role(role_name, organization_id)
    authorize_role_change(
        actor_id=str(actor_id or ""),
        actor_roles=actor_roles,
        target_user_id=str(target_user_id),
        role_name=role["name"],
        role_type=role.get("role_type"),
        organization_id=str(organization_id) if organization_id is not None else None,
        role_organization_id=(
            str(role["organization_id"])
            if role.get("organization_id") is not None
            else None
        ),
        role_is_active=role.get("is_active") is True,
        action=action,
        actor_type=actor_type,
    )

    if actor_type == "user":
        _validate_target_user(str(target_user_id))

    response = supabase_admin.rpc(
        "change_user_role_assignment",
        {
            "p_user_id": str(target_user_id),
            "p_role_id": str(role["id"]),
            "p_organization_id": (
                str(organization_id) if organization_id is not None else None
            ),
            "p_actor_id": str(actor_id) if actor_id is not None else None,
            "p_actor_type": actor_type,
            "p_action": action,
            "p_reason": (reason or "").strip() or None,
        },
    ).execute()
    result = response.data
    if isinstance(result, list):
        result = result[0] if result else None
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role assignment change did not return a result",
        )
    return result


def assign_organization_role(
    *,
    actor_id: str,
    actor_roles: list[dict[str, Any]],
    target_user_id: str,
    role_name: str,
    organization_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    return _change_assignment(
        actor_id=actor_id,
        actor_type="user",
        target_user_id=target_user_id,
        role_name=role_name,
        organization_id=organization_id,
        actor_roles=actor_roles,
        action="assign",
        reason=reason or "Organization role granted by authorized administrator",
    )


def revoke_organization_role(
    *,
    actor_id: str,
    actor_roles: list[dict[str, Any]],
    target_user_id: str,
    role_name: str,
    organization_id: str,
    reason: str,
) -> dict[str, Any]:
    return _change_assignment(
        actor_id=actor_id,
        actor_type="user",
        target_user_id=target_user_id,
        role_name=role_name,
        organization_id=organization_id,
        actor_roles=actor_roles,
        action="revoke",
        reason=reason,
    )


def assign_system_managed_role(
    *,
    actor_id: str,
    actor_roles: list[dict[str, Any]],
    target_user_id: str,
    role_name: str,
    organization_id: str | None,
    reason: str | None = None,
) -> dict[str, Any]:
    return _change_assignment(
        actor_id=actor_id,
        actor_type="user",
        target_user_id=target_user_id,
        role_name=role_name,
        organization_id=organization_id,
        actor_roles=actor_roles,
        action="assign",
        reason=reason or "Role granted through system-administration path",
    )


def revoke_system_managed_role(
    *,
    actor_id: str,
    actor_roles: list[dict[str, Any]],
    target_user_id: str,
    role_name: str,
    organization_id: str | None,
    reason: str,
) -> dict[str, Any]:
    return _change_assignment(
        actor_id=actor_id,
        actor_type="user",
        target_user_id=target_user_id,
        role_name=role_name,
        organization_id=organization_id,
        actor_roles=actor_roles,
        action="revoke",
        reason=reason,
    )


def assign_onboarding_role(
    *,
    target_user_id: str,
    role_name: str,
    organization_id: str | None,
    actor_id: str | None,
    reason: str,
) -> dict[str, Any]:
    """Only trusted signup/invitation/organization bootstrap code may call this."""
    if role_name not in {"patient", "org_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role is not assignable through onboarding",
        )
    return _change_assignment(
        actor_id=actor_id,
        actor_type="system",
        target_user_id=target_user_id,
        role_name=role_name,
        organization_id=organization_id,
        actor_roles=[],
        action="assign",
        reason=reason,
    )

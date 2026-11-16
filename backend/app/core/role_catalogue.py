"""Canonical role names and scope rules for authorization context.

This is the SPEC-01 catalogue only. It classifies role assignments; it does not
grant resource/action permissions, which remain subject to the authorization
matrix and resource relationship checks.
"""

from __future__ import annotations

from typing import Any


PATIENT = "patient"
PRACTITIONER = "practitioner"
ORGANIZATION_ADMINISTRATOR = "organization_administrator"
SYSTEM_ADMINISTRATOR = "system_administrator"
UNMAPPED = "unmapped"

_SYSTEM_ROLES = {
    "patient": PATIENT,
    "super_admin": SYSTEM_ADMINISTRATOR,
}

_ORGANIZATION_ROLES = {
    "practitioner": PRACTITIONER,
    "doctor": PRACTITIONER,
    "clinician": PRACTITIONER,
    "nurse": PRACTITIONER,
    "laboratory scientist": PRACTITIONER,
    "lab-tech": PRACTITIONER,
    "org_admin": ORGANIZATION_ADMINISTRATOR,
}


def classify_role_assignment(
    role_name: str,
    role_type: str | None,
    organization_id: str | None,
    role_organization_id: str | None = None,
    role_is_active: bool | None = None,
) -> str:
    """Return the canonical category only when the assignment has valid scope."""
    if role_is_active is not True:
        return UNMAPPED

    name = role_name.strip().casefold()
    scope = (role_type or "").strip().casefold()

    if scope == "system" and organization_id is None and role_organization_id is None:
        return _SYSTEM_ROLES.get(name, UNMAPPED)
    if (
        scope == "organization"
        and organization_id is not None
        and str(role_organization_id) == str(organization_id)
    ):
        return _ORGANIZATION_ROLES.get(name, UNMAPPED)
    return UNMAPPED


def normalize_role_assignment(
    role_name: str,
    role_type: str | None,
    organization_id: str | None,
    role_organization_id: str | None = None,
    role_is_active: bool | None = None,
) -> dict[str, Any]:
    """Build a stable authorization-context representation for one assignment."""
    return {
        "name": role_name,
        "role_type": role_type,
        "organization_id": organization_id,
        "category": classify_role_assignment(
            role_name,
            role_type,
            organization_id,
            role_organization_id,
            role_is_active,
        ),
    }


def has_scoped_category(
    assignments: list[dict[str, Any]],
    category: str,
    organization_id: str | None = None,
) -> bool:
    """Check a category in its permitted scope; org roles require exact scope."""
    for assignment in assignments:
        if assignment.get("category") != category:
            continue
        if category in {PATIENT, SYSTEM_ADMINISTRATOR}:
            if assignment.get("organization_id") is None:
                return True
        elif organization_id is not None and str(assignment.get("organization_id")) == str(organization_id):
            return True
    return False

from datetime import (
    datetime, 
    timezone
)
from app.core.audit.actions import AuditActions
from app.core.audit.service import log_audit_event
from app.core.role_assignment_policy import authorize_organization_admin
from app.modules.organizations.profile.schemas import (
    OrganizationProfileUpdate,
    OrganizationProfileResponse,
    OrganizationAddress,
    OrganizationTelecom,
)
from app.modules.organizations.profile.queries import (
    get_organization_profile,
    update_organization_profile,
)
from app.modules.organizations.exceptions import (
    OrganizationNotFoundError,
    OrganizationProfileUpdateError,
)



# ---------------------------------
# Flat Profile Update Service
# ---------------------------------
def _flatten_profile_update(
    profile: OrganizationProfileUpdate,
) -> dict:
    """
    Convert the FHIR-inspired schema into
    relational database columns.
    """

    updates = profile.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    telecom = updates.pop("telecom", None)
    address = updates.pop("address", None)

    if telecom:
        updates.update({
            "phone": telecom.get("phone"),
            "email": telecom.get("email"),
            "website": telecom.get("website"),
        })

    if address:
        updates.update({
            "address": address.get("line"),
            "city": address.get("city"),
            "state": address.get("state"),
            "postal_code": address.get("postal_code"),
            "country": address.get("country"),
        })

    return updates


# ---------------------------------
# Build Profile Service
# ---------------------------------
def _build_profile_response(
    organization: dict,
) -> OrganizationProfileResponse:

    return OrganizationProfileResponse(
        id=str(organization["id"]),
        active=organization["active"],
        name=organization["name"],
        type=organization["type"],

        telecom=OrganizationTelecom(
            phone=organization.get("phone"),
            email=organization.get("email"),
            website=organization.get("website"),
        ),

        address=OrganizationAddress(
            line=organization.get("address"),
            city=organization.get("city"),
            state=organization.get("state"),
            postal_code=organization.get("postal_code"),
            country=organization.get("country"),
        ),

        description=organization.get("description"),
        logo_url=organization.get("logo_url"),
        timezone=organization.get("timezone"),
        setup_completed=organization.get(
            "setup_completed",
            False,
        ),
    )


# ---------------------------------
# Get Organization Profile Service
# ---------------------------------
def get_profile(
    organization_id: str,
) -> OrganizationProfileResponse:

    organization = get_organization_profile(
        organization_id
    )

    if organization is None:
        raise OrganizationNotFoundError(
            "Organization not found."
        )

    return _build_profile_response(
        organization
    )


# ------------------------------------
# Update Organization Profile Service
# ------------------------------------
def update_profile(
    organization_id: str,
    payload: OrganizationProfileUpdate,
    actor_id: str,
    actor_roles: list[dict],
) -> OrganizationProfileResponse:

    # Authorize before any privileged lookup or write.
    authorize_organization_admin(
        actor_roles=actor_roles,
        organization_id=organization_id,
    )

    organization = get_organization_profile(
        organization_id
    )

    if organization is None:
        raise OrganizationNotFoundError(
            "Organization not found."
        )

    updates = _flatten_profile_update(
        payload
    )

    updates["updated_at"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    # Fail closed: record the privileged write before it happens.
    log_audit_event(
        actor_id=actor_id,
        actor_type="user",
        action=AuditActions.ORGANIZATION_PROFILE_UPDATED,
        resource_type="organization",
        resource_id=organization_id,
        metadata={
            "organization_id": organization_id,
            "updated_fields": sorted(updates.keys()),
        },
    )

    updated = update_organization_profile(
        organization_id,
        updates,
    )

    if updated is None:
        raise OrganizationProfileUpdateError(
            "Unable to update organization."
        )

    return _build_profile_response(updated)
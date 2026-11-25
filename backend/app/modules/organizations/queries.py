from app.core.supabase_admin import supabase_admin
from app.modules.organizations.exceptions import OrganizationNotFoundError


def get_organization(organization_id: str) -> dict:
    """Retrieve an organization after the caller's scope has been authorized.

    Callers handling authenticated organization routes must use an organization
    dependency before invoking this privileged service-role lookup.
    """
    response = (
        supabase_admin
        .table("organizations")
        .select("*")
        .eq("id", str(organization_id))
        .maybe_single()
        .execute()
    )

    if not response or not response.data:
        raise OrganizationNotFoundError(
            f"Organization {organization_id} not found."
        )

    return response.data

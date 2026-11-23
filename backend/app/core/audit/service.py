from app.core.supabase_admin import supabase_admin


# ----- Audit Logging Service -----
def log_audit_event(
    *,
    actor_id: str | None,
    actor_type: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict | None = None,
    organization_id: str | None = None,
):
    audit_metadata = dict(metadata or {})
    if organization_id is not None:
        audit_metadata["organization_id"] = str(organization_id)

    (
        supabase_admin
        .table("audit_logs")
        .insert({
            "actor_id": actor_id,
            "actor_type": actor_type,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": audit_metadata,
        })
        .execute()
    )

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.action_authorization import evaluate_action
from app.core.audit.service import log_audit_event
from app.core.role_catalogue import SYSTEM_ADMINISTRATOR
from app.core.security import get_current_user
from app.core.supabase_admin import supabase_admin


router = APIRouter(prefix="/admin/audit", tags=["Audit"])


@router.get("/{resource_type}/{resource_id}")
def get_audit(
    resource_type: str,
    resource_id: str,
    purpose: str = Query(..., description="Approved audit-visibility purpose"),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    if not any(r.get("category") == SYSTEM_ADMINISTRATOR for r in (current_user.get("roles") or [])):
        raise HTTPException(status_code=403, detail="Access denied")
    if purpose not in {"security_incident", "platform_health"}:
        raise HTTPException(status_code=400, detail="An approved purpose is required")

    decision = evaluate_action(
        actor_roles=current_user.get("roles") or [],
        resource="audit_record",
        action="read",
        verified_conditions={
            "explicit_admin_purpose",
            "audit_visibility_approved",
            "event_payload_redacted",
            "patient_data_redacted",
            "audit_recorded",
        },
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    # Audit the access itself; fail closed if it cannot be recorded.
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action="AUDIT_LOG_READ",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={"purpose": purpose},
        )
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")

    rows = (
        supabase_admin.table("audit_logs")
        .select("id, actor_id, actor_type, action, resource_type, resource_id, created_at")
        .eq("resource_type", resource_type)
        .eq("resource_id", resource_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    # Do not return metadata/payload fields; expose a safe projection only.
    return [
        {
            "id": r.get("id"),
            "actor_id": r.get("actor_id"),
            "actor_type": r.get("actor_type"),
            "action": r.get("action"),
            "resource_type": r.get("resource_type"),
            "resource_id": r.get("resource_id"),
            "created_at": r.get("created_at"),
        }
        for r in rows
    ]

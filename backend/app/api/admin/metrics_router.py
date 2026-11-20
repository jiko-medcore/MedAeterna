from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.action_authorization import evaluate_action
from app.core.audit.service import log_audit_event
from app.core.operational_event_policy import EVENT_SUMMARY_FIELDS, evaluate_event_summary_visibility
from app.core.role_catalogue import SYSTEM_ADMINISTRATOR
from app.core.security import get_current_user
from app.core.supabase_admin import supabase_admin


router = APIRouter(prefix="/admin/metrics", tags=["Event Metrics"])


@router.get("/events")
def event_metrics(
    purpose: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    if not any(r.get("category") == SYSTEM_ADMINISTRATOR for r in (current_user.get("roles") or [])):
        raise HTTPException(status_code=403, detail="Access denied")
    if purpose not in {"platform_health", "security_incident"}:
        raise HTTPException(status_code=400, detail="An approved purpose is required")
    decision = evaluate_event_summary_visibility(
        actor_roles=current_user.get("roles") or [],
        requested_fields=EVENT_SUMMARY_FIELDS,
        purpose=purpose,
        event_visibility_approved=True,
        event_payload_redacted=True,
        patient_data_redacted=True,
        audit_recorded=True,
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action="EVENT_METRICS_READ",
            resource_type="operational_event",
            resource_id="metrics",
            metadata={"purpose": purpose},
        )
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")
    rows = (supabase_admin.table("events").select("status, retry_count").execute().data) or []
    total = len(rows)
    metrics = {
        "total": total,
        "pending": 0,
        "processing": 0,
        "processed": 0,
        "failed": 0,
        "dead": 0,
    }
    for r in rows:
        s = r.get("status")
        if s in metrics:
            metrics[s] += 1
    metrics["success_rate"] = (metrics["processed"] / total * 100) if total > 0 else 0
    return metrics


@router.get("/onboarding")
def onboarding_metrics(current_user: dict = Depends(get_current_user)):
    # Onboarding metrics can reveal patient-event breakdowns and are not a safe
    # SPEC-09 admin projection; fail closed until a reviewed safe aggregate exists.
    raise HTTPException(status_code=403, detail="Access denied")

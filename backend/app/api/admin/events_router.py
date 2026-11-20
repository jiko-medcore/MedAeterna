from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.action_authorization import ActionDecision
from app.core.audit.actions import AuditActions
from app.core.audit.service import log_audit_event
from app.core.events.registry import EVENT_HANDLERS
from app.core.events.replay import replay_dead_event
from app.core.operational_event_policy import (
    EVENT_METADATA_FIELDS,
    EVENT_SUMMARY_FIELDS,
    PATIENT_EVENT_METADATA_FIELDS,
    evaluate_event_retry,
    evaluate_event_summary_visibility,
    evaluate_event_visibility,
)
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, SYSTEM_ADMINISTRATOR
from app.core.security import get_current_user
from app.core.supabase_admin import supabase_admin


router = APIRouter(prefix="/admin/events", tags=["Event Monitoring"])


def _is_system_admin(user: dict) -> bool:
    return any(r.get("category") == SYSTEM_ADMINISTRATOR for r in (user.get("roles") or []))


def _org_admin_org_ids(user: dict) -> list[str]:
    ids = []
    for role in user.get("roles") or []:
        if role.get("category") == ORGANIZATION_ADMINISTRATOR and role.get("organization_id"):
            ids.append(str(role["organization_id"]))
    return sorted(set(ids))


def _deny(detail: str = "Access denied", status_code: int = 403) -> None:
    raise HTTPException(status_code=status_code, detail=detail)


def _require_decision(decision: ActionDecision) -> None:
    if not decision.allowed:
        raise HTTPException(status_code=403, detail="Access denied")


def _normalize_error_code(value) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _project_event_row(row: dict, *, actor_is_system: bool, purpose: str) -> dict | None:
    event_type = str(row.get("event_type") or "")
    aggregate_type = str(row.get("aggregate_type") or "")
    status = str(row.get("status") or "")
    requested = EVENT_METADATA_FIELDS if actor_is_system else EVENT_METADATA_FIELDS
    # For system-admin patient/aggregate-patient events, omit event_type and identifiers.
    if actor_is_system and (aggregate_type == "patient" or event_type.startswith("patient.") or event_type.startswith("onboarding.")):
        requested = PATIENT_EVENT_METADATA_FIELDS
    decision = evaluate_event_visibility(
        actor_roles=[{"category": SYSTEM_ADMINISTRATOR, "organization_id": None}] if actor_is_system else [],
        event_type=event_type,
        aggregate_type=aggregate_type,
        status=status,
        requested_fields=requested,
        purpose=purpose,
        event_payload_redacted=True,
        patient_data_redacted=True,
        event_visibility_approved=True,
        audit_recorded=True,
    )
    # For org admin this helper is not used; org admin visibility requires trusted org resolution we cannot provide here.
    if not decision.allowed:
        return None
    allowed = set(requested)
    projected = {"event_reference": str(row.get("id") or "")}
    if "event_type" in allowed:
        projected["event_type"] = event_type
    if "status" in allowed:
        projected["status"] = status
    if "created_at" in allowed:
        projected["created_at"] = row.get("created_at")
    if "processed_at" in allowed:
        projected["processed_at"] = row.get("processed_at")
    if "retry_count" in allowed:
        projected["retry_count"] = row.get("retry_count", 0)
    if "normalized_error_code" in allowed:
        code = _normalize_error_code(row.get("normalized_error_code"))
        if code:
            projected["normalized_error_code"] = code
    return projected


def _require_system_admin_purpose(purpose: str | None) -> str:
    if not purpose or purpose not in {"platform_health", "security_incident", "event_recovery"}:
        raise HTTPException(status_code=400, detail="An approved purpose is required")
    return purpose


@router.get("/stats")
def stats(
    purpose: str = Query(..., description="Approved system-admin purpose"),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_system_admin_purpose(purpose)
    if purpose == "event_recovery":
        purpose = "platform_health"
    decision = evaluate_event_summary_visibility(
        actor_roles=current_user.get("roles") or [],
        requested_fields=EVENT_SUMMARY_FIELDS,
        purpose=purpose,
        event_visibility_approved=True,
        event_payload_redacted=True,
        patient_data_redacted=True,
        audit_recorded=True,
    )
    _require_decision(decision)
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action="EVENT_SUMMARY_READ",
            resource_type="operational_event",
            resource_id="summary",
            metadata={"purpose": purpose},
        )
    except Exception:
        _deny("Audit required", 403)
    rows = (supabase_admin.table("events").select("status").execute().data) or []
    total = len(rows)
    stats_map = {"total": total, "pending": 0, "processing": 0, "processed": 0, "failed": 0, "dead": 0}
    for r in rows:
        s = r.get("status")
        if s in stats_map:
            stats_map[s] += 1
    stats_map["success_rate"] = (stats_map["processed"] / total * 100) if total > 0 else 0
    return stats_map


@router.get("/failed")
def failed(
    purpose: str = Query(...),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_system_admin_purpose(purpose)
    if purpose == "event_recovery":
        purpose = "platform_health"
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action="EVENT_LIST_READ",
            resource_type="operational_event",
            resource_id="failed",
            metadata={"purpose": purpose},
        )
    except Exception:
        _deny("Audit required", 403)
    rows = (
        supabase_admin.table("events")
        .select("id, aggregate_type, event_type, status, created_at, processed_at, retry_count, normalized_error_code")
        .eq("status", "failed")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    projected = []
    for row in rows:
        p = _project_event_row(row, actor_is_system=True, purpose=purpose)
        if p:
            projected.append(p)
    return projected


@router.get("/dead")
def dead(
    purpose: str = Query(...),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_system_admin_purpose(purpose)
    if purpose == "event_recovery":
        purpose = "platform_health"
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action="EVENT_LIST_READ",
            resource_type="operational_event",
            resource_id="dead_letter",
            metadata={"purpose": purpose},
        )
    except Exception:
        _deny("Audit required", 403)
    rows = (
        supabase_admin.table("events_dead_letter")
        .select("id, aggregate_type, event_type, retry_count, failed_at, normalized_error_code")
        .order("failed_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    out = []
    for row in rows:
        event_type = str(row.get("event_type") or "")
        aggregate_type = str(row.get("aggregate_type") or "")
        requested = PATIENT_EVENT_METADATA_FIELDS if (aggregate_type == "patient" or event_type.startswith("patient.") or event_type.startswith("onboarding.")) else EVENT_METADATA_FIELDS
        decision = evaluate_event_visibility(
            actor_roles=current_user.get("roles") or [],
            event_type=event_type,
            aggregate_type=aggregate_type,
            status="dead",
            requested_fields=requested,
            purpose=purpose,
            event_payload_redacted=True,
            patient_data_redacted=True,
            event_visibility_approved=True,
            audit_recorded=True,
        )
        if not decision.allowed:
            continue
        item = {"event_reference": str(row.get("id") or ""), "status": "dead", "retry_count": row.get("retry_count", 0)}
        if "event_type" in requested:
            item["event_type"] = event_type
        if "created_at" in requested:
            item["created_at"] = row.get("failed_at")
        code = _normalize_error_code(row.get("normalized_error_code"))
        if code and "normalized_error_code" in requested:
            item["normalized_error_code"] = code
        out.append(item)
    return out


@router.get("/dead/{dead_event_id}")
def dead_event_detail(
    dead_event_id: str,
    purpose: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_system_admin_purpose(purpose)
    if purpose == "event_recovery":
        purpose = "platform_health"
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action="EVENT_READ",
            resource_type="operational_event",
            resource_id="dead_letter",
            metadata={"purpose": purpose},
        )
    except Exception:
        _deny("Audit required", 403)
    row = (
        supabase_admin.table("events_dead_letter")
        .select("id, aggregate_type, event_type, retry_count, failed_at, normalized_error_code")
        .eq("id", dead_event_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not row:
        raise HTTPException(status_code=404, detail="Dead letter event not found")
    item = row[0]
    event_type = str(item.get("event_type") or "")
    aggregate_type = str(item.get("aggregate_type") or "")
    requested = PATIENT_EVENT_METADATA_FIELDS if (aggregate_type == "patient" or event_type.startswith("patient.") or event_type.startswith("onboarding.")) else EVENT_METADATA_FIELDS
    decision = evaluate_event_visibility(
        actor_roles=current_user.get("roles") or [],
        event_type=event_type,
        aggregate_type=aggregate_type,
        status="dead",
        requested_fields=requested,
        purpose=purpose,
        event_payload_redacted=True,
        patient_data_redacted=True,
        event_visibility_approved=True,
        audit_recorded=True,
    )
    _require_decision(decision)
    projected = {"event_reference": str(item.get("id") or ""), "status": "dead", "retry_count": item.get("retry_count", 0)}
    if "event_type" in requested:
        projected["event_type"] = event_type
    if "created_at" in requested:
        projected["created_at"] = item.get("failed_at")
    code = _normalize_error_code(item.get("normalized_error_code"))
    if code and "normalized_error_code" in requested:
        projected["normalized_error_code"] = code
    return projected


@router.post("/dead/{dead_event_id}/replay")
def replay_dead(
    dead_event_id: str,
    reason: str = Query(..., min_length=1, max_length=500),
    purpose: str = Query("event_recovery"),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    if purpose not in {"event_recovery", "security_incident"}:
        raise HTTPException(status_code=400, detail="An approved retry purpose is required")
    # Fetch minimal state for policy evaluation without exposing payload.
    row = (
        supabase_admin.table("events_dead_letter")
        .select("id, aggregate_type, event_type, retry_count, replayed")
        .eq("id", dead_event_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not row:
        raise HTTPException(status_code=404, detail="Dead letter event not found")
    item = row[0]
    decision = evaluate_event_retry(
        actor_roles=current_user.get("roles") or [],
        event_reference=str(item.get("id") or ""),
        event_type=str(item.get("event_type") or ""),
        status="dead",
        purpose=purpose,
        reason=reason,
        retry_count=int(item.get("retry_count") or 0),
        handler_registered=str(item.get("event_type") or "") in EVENT_HANDLERS,
        handler_retry_safe=str(item.get("event_type") or "") in EVENT_HANDLERS,
        patient_data_redacted=True,
        event_payload_redacted=True,
        audit_recorded=True,
        already_replayed=bool(item.get("replayed")),
    )
    _require_decision(decision)
    # Audit before state-changing retry; fail closed if audit cannot be recorded.
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action=AuditActions.EVENT_REPLAYED,
            resource_type="event_dead_letter",
            resource_id=str(item.get("id") or ""),
            metadata={"purpose": purpose, "reason": reason[:500]},
        )
    except Exception:
        _deny("Audit required", 403)
    try:
        result = replay_dead_event(dead_event_id=dead_event_id, actor_id=current_user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Replay not permitted") from exc
    return {"status": "queued", "event_reference": str(result.get("new_event_id") or "")}


@router.get("")
def list_events(
    purpose: str = Query(...),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_system_admin_purpose(purpose)
    if purpose == "event_recovery":
        purpose = "platform_health"
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action="EVENT_LIST_READ",
            resource_type="operational_event",
            resource_id="list",
            metadata={"purpose": purpose, "status": status},
        )
    except Exception:
        _deny("Audit required", 403)
    query = (
        supabase_admin.table("events")
        .select("id, aggregate_type, event_type, status, created_at, processed_at, retry_count, normalized_error_code")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("status", status)
    rows = query.execute().data or []
    projected = []
    for row in rows:
        p = _project_event_row(row, actor_is_system=True, purpose=purpose)
        if p:
            projected.append(p)
    return projected


@router.get("/{event_id}")
def event_detail(
    event_id: str,
    purpose: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_system_admin_purpose(purpose)
    if purpose == "event_recovery":
        purpose = "platform_health"
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action="EVENT_READ",
            resource_type="operational_event",
            resource_id="detail",
            metadata={"purpose": purpose},
        )
    except Exception:
        _deny("Audit required", 403)
    row = (
        supabase_admin.table("events")
        .select("id, aggregate_type, event_type, status, created_at, processed_at, retry_count, normalized_error_code")
        .eq("id", event_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    projected = _project_event_row(row[0], actor_is_system=True, purpose=purpose)
    if projected is None:
        _deny()
    return projected

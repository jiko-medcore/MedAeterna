import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.action_authorization import ActionDecision
from app.core.audit.actions import AuditActions
from app.core.audit.service import log_audit_event
from app.core.events.registry import EVENT_HANDLERS
from app.core.events.replay import replay_dead_event
from app.core.operational_event_policy import (
    EVENT_METADATA_FIELDS,
    EVENT_SUMMARY_FIELDS,
    NORMALIZED_ERROR_CODES,
    PATIENT_EVENT_METADATA_FIELDS,
    evaluate_event_retry,
    evaluate_event_summary_visibility,
    evaluate_event_visibility,
    is_manual_retry_safe,
    normalize_event_error_text,
)
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, SYSTEM_ADMINISTRATOR
from app.core.security import get_current_user
from app.core.supabase_admin import supabase_admin


router = APIRouter(prefix="/admin/events", tags=["Event Monitoring"])

# The local event schema has no normalized_error_code column. Select only
# approved metadata plus raw failure text for server-side normalization; raw
# text is never returned to the operator and never stored in audit metadata.
EVENT_METADATA_SELECT = (
    "id, aggregate_type, event_type, status, created_at, processed_at, "
    "retry_count, failure_reason, last_error"
)
DEAD_LETTER_METADATA_SELECT = (
    "id, aggregate_type, event_type, retry_count, failed_at, failure_reason"
)
READ_PURPOSES = frozenset({"platform_health", "security_incident"})
RETRY_PURPOSES = frozenset({"event_recovery", "security_incident"})


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


def _normalize_error_code(row: dict) -> str | None:
    """Return only a fixed code; never return raw failure text."""
    stored = row.get("normalized_error_code")
    if isinstance(stored, str) and stored in NORMALIZED_ERROR_CODES:
        return stored
    return normalize_event_error_text(row.get("failure_reason") or row.get("last_error"))


def _is_patient_event(event_type: str, aggregate_type: str) -> bool:
    return (
        aggregate_type == "patient"
        or event_type.startswith("patient.")
        or event_type.startswith("onboarding.")
    )


def _project_event_row(row: dict, *, actor_is_system: bool, purpose: str) -> dict | None:
    """Apply the same role, purpose, redaction and field rules to every row."""
    event_type = str(row.get("event_type") or "")
    aggregate_type = str(row.get("aggregate_type") or "")
    status = str(row.get("status") or "")
    requested = (
        PATIENT_EVENT_METADATA_FIELDS
        if _is_patient_event(event_type, aggregate_type)
        else EVENT_METADATA_FIELDS
    )
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
    # Org-admin visibility needs a trusted event-to-organization resolver;
    # until one exists this helper deliberately remains system-admin-only.
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
    code = _normalize_error_code(row)
    if "normalized_error_code" in allowed and code:
        projected["normalized_error_code"] = code
    return projected


def _project_dead_event_row(row: dict, *, purpose: str, roles: list[dict]) -> dict | None:
    event_type = str(row.get("event_type") or "")
    aggregate_type = str(row.get("aggregate_type") or "")
    requested = (
        PATIENT_EVENT_METADATA_FIELDS
        if _is_patient_event(event_type, aggregate_type)
        else EVENT_METADATA_FIELDS
    )
    decision = evaluate_event_visibility(
        actor_roles=roles,
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
        return None
    allowed = set(requested)
    projected = {
        "event_reference": str(row.get("id") or ""),
        "status": "dead",
        "retry_count": row.get("retry_count", 0),
    }
    if "event_type" in allowed:
        projected["event_type"] = event_type
    if "created_at" in allowed:
        projected["created_at"] = row.get("failed_at")
    code = _normalize_error_code(row)
    if "normalized_error_code" in allowed and code:
        projected["normalized_error_code"] = code
    return projected


def _require_read_purpose(purpose: str | None) -> str:
    if not purpose or purpose not in READ_PURPOSES:
        raise HTTPException(status_code=400, detail="An approved read purpose is required")
    return purpose


def _require_retry_purpose(purpose: str | None) -> str:
    if not purpose or purpose not in RETRY_PURPOSES:
        raise HTTPException(status_code=400, detail="An approved retry purpose is required")
    return purpose


def _contains_contact_data(reason: str) -> bool:
    """Reject obvious patient contact data in a free-text retry reason."""
    return bool(re.search(r"@|\+?\d(?:[\s().-]?\d){9,}", reason))


@router.get("/stats")
def stats(
    purpose: str = Query(..., description="Approved system-admin purpose"),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_read_purpose(purpose)
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
    purpose = _require_read_purpose(purpose)
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
        .select(EVENT_METADATA_SELECT)
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
    purpose = _require_read_purpose(purpose)
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
        .select(DEAD_LETTER_METADATA_SELECT)
        .order("failed_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    out = []
    for row in rows:
        projected = _project_dead_event_row(
            row, purpose=purpose, roles=current_user.get("roles") or []
        )
        if projected:
            out.append(projected)
    return out


@router.get("/dead/{dead_event_id}")
def dead_event_detail(
    dead_event_id: str,
    purpose: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_read_purpose(purpose)
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
        .select(DEAD_LETTER_METADATA_SELECT)
        .eq("id", dead_event_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not row:
        raise HTTPException(status_code=404, detail="Dead letter event not found")
    projected = _project_dead_event_row(
        row[0], purpose=purpose, roles=current_user.get("roles") or []
    )
    if projected is None:
        _deny()
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
    purpose = _require_retry_purpose(purpose)
    if _contains_contact_data(reason):
        raise HTTPException(status_code=400, detail="Retry reason must not contain contact data")
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
        handler_retry_safe=is_manual_retry_safe(
            str(item.get("event_type") or ""), EVENT_HANDLERS
        ),
        patient_data_redacted=True,
        event_payload_redacted=True,
        audit_recorded=True,
        already_replayed=bool(item.get("replayed")),
    )
    _require_decision(decision)
    base_audit = {
        "purpose": purpose,
        "reason": reason[:500],
        "event_type": str(item.get("event_type") or ""),
        "state_before": "dead",
        "attempt_count": int(item.get("retry_count") or 0) + 1,
    }
    # Record authorization before the state-changing retry; fail closed if the
    # attempt cannot be audited. A final record captures the actual outcome.
    try:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action=AuditActions.EVENT_REPLAY_ATTEMPTED,
            resource_type="event_dead_letter",
            resource_id=str(item.get("id") or ""),
            metadata={
                **base_audit,
                "state_after": "pending_if_claim_succeeds",
                "outcome": "authorized_cas_claim_attempted",
            },
        )
    except Exception:
        _deny("Audit required", 403)

    try:
        result = replay_dead_event(dead_event_id=dead_event_id, actor_id=current_user["id"])
    except ValueError as exc:
        log_audit_event(
            actor_id=current_user.get("id"),
            actor_type="system_admin",
            action=AuditActions.EVENT_REPLAY_DENIED,
            resource_type="event_dead_letter",
            resource_id=str(item.get("id") or ""),
            metadata={**base_audit, "state_after": "dead", "outcome": "cas_claim_failed"},
        )
        raise HTTPException(status_code=409, detail="Replay not permitted") from exc

    new_event_reference = str(result.get("new_event_id") or "")
    log_audit_event(
        actor_id=current_user.get("id"),
        actor_type="system_admin",
        action=AuditActions.EVENT_REPLAYED,
        resource_type="event_dead_letter",
        resource_id=str(item.get("id") or ""),
        metadata={
            **base_audit,
            "state_after": "pending",
            "outcome": "queued",
            "new_event_reference": new_event_reference,
        },
    )
    return {"status": "queued", "event_reference": new_event_reference}


@router.get("")
def list_events(
    purpose: str = Query(...),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    if not _is_system_admin(current_user):
        _deny()
    purpose = _require_read_purpose(purpose)
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
        .select(EVENT_METADATA_SELECT)
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
    purpose = _require_read_purpose(purpose)
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
        .select(EVENT_METADATA_SELECT)
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

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import authorize_patient_access, get_current_user, require_practitioner
from app.core.supabase_admin import supabase_admin
from app.modules.care_team.schemas import (
    CareTeamAssign,
    CareTeamCreate,
    CareTeamParticipantAdd,
    CareTeamParticipantUpdate,
)
from app.modules.care_team.service import (
    add_care_team_participant,
    assign_care_team,
    create_care_team,
    get_patient_care_teams,
    update_care_team_participant,
)


router = APIRouter(prefix="/care-teams", tags=["Care Teams"])


@router.post("/")
def create_team(
    payload: CareTeamCreate,
    current_user: dict = Depends(get_current_user),
    _practitioner: dict = Depends(require_practitioner),
):
    authorize_patient_access(
        current_user,
        str(payload.patient_id),
        organization_id=str(payload.organization_id) if payload.organization_id else None,
    )
    return create_care_team(payload)


@router.post("/{care_team_id}/participants")
def add_participant(
    care_team_id: str,
    payload: CareTeamParticipantAdd,
    current_user: dict = Depends(get_current_user),
    _practitioner: dict = Depends(require_practitioner),
):
    team_rows = (
        supabase_admin.table("care_teams")
        .select("id, patient_id, organization_id")
        .eq("id", care_team_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not team_rows:
        raise HTTPException(status_code=404, detail="Care team not found")
    team = team_rows[0]
    authorize_patient_access(
        current_user,
        str(team["patient_id"]),
        organization_id=str(team.get("organization_id") or "") or None,
    )
    return add_care_team_participant(care_team_id, payload)


@router.get("/patient/{patient_id}")
def patient_care_teams(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(current_user, str(patient_id))
    return get_patient_care_teams(patient_id)


@router.patch("/participants/{participant_id}")
def update_participant(
    participant_id: str,
    payload: CareTeamParticipantUpdate,
    current_user: dict = Depends(get_current_user),
    _practitioner: dict = Depends(require_practitioner),
):
    rows = (
        supabase_admin.table("care_team_participants")
        .select("id, care_team_id, care_teams(patient_id, organization_id)")
        .eq("id", participant_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Care team participant not found")
    team = rows[0].get("care_teams") or {}
    patient_id = team.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=403, detail="Access denied")
    authorize_patient_access(
        current_user,
        str(patient_id),
        organization_id=str(team.get("organization_id") or "") or None,
    )
    return update_care_team_participant(participant_id, payload)


@router.post("/assign")
def assign_team_member(
    payload: CareTeamAssign,
    current_user: dict = Depends(get_current_user),
    practitioner: dict = Depends(require_practitioner),
):
    authorize_patient_access(
        current_user,
        str(payload.patient_id),
        organization_id=str(payload.organization_id) if payload.organization_id else None,
    )
    return assign_care_team(
        str(practitioner.get("id") or current_user["id"]),
        payload,
        current_user["id"],
    )

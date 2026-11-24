from fastapi import APIRouter, Depends, HTTPException

from app.core import security
from app.core.clinical_authorization import (
    CARE_TEAM,
    authorize_clinical_access,
    require_patient_clinical,
)
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


def _require_org_practitioner(practitioner_id: str, organization_id: str) -> None:
    """A target must hold an active practitioner role in the exact organization."""
    row = security.fetch_resource(
        "practitioner_roles",
        "id, practitioner_id, organization_id, active",
        practitioner_id=str(practitioner_id),
        organization_id=str(organization_id),
        active=True,
    )
    if not row:
        raise HTTPException(
            status_code=403,
            detail="Practitioner is not active in this organization",
        )


@router.post("/")
def create_team(
    payload: CareTeamCreate,
    current_user: dict = Depends(security.get_current_user),
):
    context = authorize_clinical_access(
        current_user,
        resource=CARE_TEAM,
        action="create",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
        verified_conditions={"audit_recorded"},
        allow_organization_admin=True,
        organization_care_authority=True,
    )
    return create_care_team(payload, authorized_context=context)


@router.post("/{care_team_id}/participants")
def add_participant(
    care_team_id: str,
    payload: CareTeamParticipantAdd,
    current_user: dict = Depends(security.get_current_user),
):
    team = security.fetch_resource(
        "care_teams", "id, patient_id, organization_id", id=str(care_team_id)
    )
    if not team:
        raise HTTPException(status_code=404, detail="Care team not found")

    context = authorize_clinical_access(
        current_user,
        resource=CARE_TEAM,
        action="update",
        patient_id=str(team["patient_id"]),
        organization_id=str(team.get("organization_id") or "") or None,
        verified_conditions={"audit_recorded"},
        allow_organization_admin=True,
        organization_care_authority=True,
    )
    organization_id = str(context.get("authorized_organization_id") or "")
    _require_org_practitioner(payload.practitioner_id, organization_id)
    return add_care_team_participant(
        care_team_id, payload, authorized_context=context
    )


@router.get("/patient/{patient_id}")
def patient_care_teams(
    patient_id: str,
    context: dict = Depends(
        require_patient_clinical(
            CARE_TEAM,
            "read",
            allow_organization_admin=True,
            organization_care_authority=True,
        )
    ),
):
    return get_patient_care_teams(patient_id, authorized_context=context)


@router.patch("/participants/{participant_id}")
def update_participant(
    participant_id: str,
    payload: CareTeamParticipantUpdate,
    current_user: dict = Depends(security.get_current_user),
):
    row = security.fetch_resource(
        "care_team_participants",
        "id, care_team_id, care_teams(patient_id, organization_id)",
        id=str(participant_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Care team participant not found")
    team = row.get("care_teams") or {}
    patient_id = team.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    context = authorize_clinical_access(
        current_user,
        resource=CARE_TEAM,
        action="update",
        patient_id=str(patient_id),
        organization_id=str(team.get("organization_id") or "") or None,
        verified_conditions={"audit_recorded"},
        allow_organization_admin=True,
        organization_care_authority=True,
    )
    return update_care_team_participant(
        participant_id, payload, authorized_context=context
    )


@router.post("/assign")
def assign_team_member(
    payload: CareTeamAssign,
    current_user: dict = Depends(security.get_current_user),
):
    context = authorize_clinical_access(
        current_user,
        resource=CARE_TEAM,
        action="administer",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
        verified_conditions={"audit_recorded"},
        allow_organization_admin=True,
        organization_care_authority=True,
    )
    target_practitioner_id = str(
        payload.practitioner_id
        or security.resolve_practitioner_id(str(current_user["id"]))
        or ""
    )
    if not target_practitioner_id:
        raise HTTPException(
            status_code=400, detail="Practitioner context required"
        )
    # No self-assignment to arbitrary patients, even by an org administrator.
    actor_practitioner_id = security.resolve_practitioner_id(str(current_user["id"]))
    if actor_practitioner_id and str(actor_practitioner_id) == target_practitioner_id:
        raise HTTPException(status_code=403, detail="Self-assignment is not permitted")
    _require_org_practitioner(target_practitioner_id, str(payload.organization_id))

    return assign_care_team(
        target_practitioner_id,
        payload,
        current_user["id"],
        authorized_context=context,
    )

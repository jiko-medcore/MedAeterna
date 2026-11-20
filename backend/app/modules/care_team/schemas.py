from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


# ----- Care Team Creation Model -----
class CareTeamCreate(BaseModel):
    patient_id: str
    organization_id: str
    name: Optional[str] = None
    status: str = "active"
    category: Optional[str] = None
    reason: Optional[str] = None
    managing_organization_id: Optional[str] = None
    notes: Optional[str] = None


# ----- Add Care Team Patiticipants Model -----
class CareTeamParticipantAdd(BaseModel):
    practitioner_id: str
    role_code: str
    responsibility: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


# ----- Update Care Team Pariticipants -----
class CareTeamParticipantUpdate(BaseModel):
    responsibility: Optional[str] = None
    active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


# ----- Care Team Assignment Model -----
class CareTeamAssign(BaseModel):
    patient_id: str
    organization_id: str
    practitioner_id: Optional[str] = None
    role: str
    notes: Optional[str] = None 
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
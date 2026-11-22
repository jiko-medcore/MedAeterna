from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, field_validator


class ConsentGrant(BaseModel):
    organization_id: str
    practitioner_id: Optional[str] = None
    consent_type: str
    access_level: str
    purpose_of_use: Optional[str] = None
    legal_basis: Optional[str] = None
    emergency_access: Literal[False] = False
    effective_from: Optional[datetime] = None
    expires_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("effective_from", "expires_at")
    @classmethod
    def require_timezone_aware_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("consent timestamps must include a timezone")
        return value


class ConsentRevoke(BaseModel):
    consent_id: str
    revoked_reason: Optional[str] = None

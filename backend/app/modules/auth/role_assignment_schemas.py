from uuid import UUID

from pydantic import BaseModel, Field


class RoleAssignmentChange(BaseModel):
    user_id: UUID
    role_name: str = Field(min_length=1, max_length=80)
    organization_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=500)


class RoleAssignmentRevocation(BaseModel):
    user_id: UUID
    role_name: str = Field(min_length=1, max_length=80)
    organization_id: UUID | None = None
    reason: str = Field(min_length=3, max_length=500)

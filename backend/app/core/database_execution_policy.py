"""Authorization gates for trusted Supabase/Postgres execution modes.

This is a reference policy. It does not execute queries or replace route-level
authorization; callers must provide evidence established by trusted backend
code for the exact target resource and action.
"""

from dataclasses import dataclass
from enum import StrEnum


class ExecutionMode(StrEnum):
    CALLER_RLS = "caller_rls"
    SERVICE_ROLE = "service_role"
    BACKGROUND_WORKER = "background_worker"


@dataclass(frozen=True)
class ExecutionEvidence:
    mode: ExecutionMode
    caller_verified: bool = False
    caller_jwt_propagated: bool = False
    application_authorized: bool = False
    target_scope_verified: bool = False
    action_authorized: bool = False
    worker_identity_verified: bool = False
    job_purpose_allowlisted: bool = False


def execution_allowed(evidence: ExecutionEvidence) -> bool:
    """Return whether trusted evidence satisfies the selected access mode."""
    if evidence.mode is ExecutionMode.CALLER_RLS:
        return (
            evidence.caller_verified
            and evidence.caller_jwt_propagated
        )

    if evidence.mode is ExecutionMode.SERVICE_ROLE:
        return (
            evidence.caller_verified
            and evidence.application_authorized
            and evidence.target_scope_verified
            and evidence.action_authorized
        )

    if evidence.mode is ExecutionMode.BACKGROUND_WORKER:
        return (
            evidence.worker_identity_verified
            and evidence.job_purpose_allowlisted
            and evidence.target_scope_verified
            and evidence.action_authorized
        )

    return False

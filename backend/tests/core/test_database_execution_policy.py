import pytest

from app.core.database_execution_policy import (
    ExecutionEvidence,
    ExecutionMode,
    execution_allowed,
)
from app.core.supabase_client import create_caller_scoped_client


@pytest.mark.parametrize(
    "evidence",
    [
        ExecutionEvidence(ExecutionMode.CALLER_RLS),
        ExecutionEvidence(ExecutionMode.CALLER_RLS, caller_verified=True),
        ExecutionEvidence(ExecutionMode.CALLER_RLS, caller_jwt_propagated=True),
    ],
)
def test_caller_rls_requires_verified_and_propagated_identity(evidence):
    assert execution_allowed(evidence) is False


def test_caller_rls_allows_verified_identity_propagated_to_query():
    evidence = ExecutionEvidence(
        ExecutionMode.CALLER_RLS,
        caller_verified=True,
        caller_jwt_propagated=True,
    )
    assert execution_allowed(evidence) is True


@pytest.mark.parametrize(
    "missing",
    ["caller_verified", "application_authorized", "target_scope_verified", "action_authorized"],
)
def test_service_role_requires_each_authorization_boundary(missing):
    evidence_values = {
        "caller_verified": True,
        "application_authorized": True,
        "target_scope_verified": True,
        "action_authorized": True,
    }
    evidence_values[missing] = False
    evidence = ExecutionEvidence(ExecutionMode.SERVICE_ROLE, **evidence_values)
    assert execution_allowed(evidence) is False


def test_service_role_is_allowed_only_after_explicit_target_and_action_authorization():
    evidence = ExecutionEvidence(
        ExecutionMode.SERVICE_ROLE,
        caller_verified=True,
        application_authorized=True,
        target_scope_verified=True,
        action_authorized=True,
    )
    assert execution_allowed(evidence) is True


def test_service_role_does_not_substitute_for_caller_rls_context():
    evidence = ExecutionEvidence(
        ExecutionMode.CALLER_RLS,
        caller_verified=True,
        application_authorized=True,
        target_scope_verified=True,
        action_authorized=True,
    )
    assert execution_allowed(evidence) is False


@pytest.mark.parametrize(
    "missing",
    ["worker_identity_verified", "job_purpose_allowlisted", "target_scope_verified", "action_authorized"],
)
def test_worker_requires_identity_allowlisted_purpose_and_scoped_action(missing):
    evidence_values = {
        "worker_identity_verified": True,
        "job_purpose_allowlisted": True,
        "target_scope_verified": True,
        "action_authorized": True,
    }
    evidence_values[missing] = False
    evidence = ExecutionEvidence(ExecutionMode.BACKGROUND_WORKER, **evidence_values)
    assert execution_allowed(evidence) is False


def test_worker_can_run_allowlisted_scoped_job_without_human_caller():
    evidence = ExecutionEvidence(
        ExecutionMode.BACKGROUND_WORKER,
        worker_identity_verified=True,
        job_purpose_allowlisted=True,
        target_scope_verified=True,
        action_authorized=True,
    )
    assert execution_allowed(evidence) is True


def test_caller_scoped_client_propagates_jwt_without_shared_session():
    token = "verified-test-jwt"
    client = create_caller_scoped_client(token)
    try:
        assert client.options.headers["Authorization"] == f"Bearer {token}"
        assert client.postgrest.headers["Authorization"] == f"Bearer {token}"
        assert client.postgrest.headers["apiKey"]
        assert client.options.auto_refresh_token is False
        assert client.options.persist_session is False
    finally:
        client.postgrest.aclose()


def test_caller_scoped_client_rejects_missing_token():
    with pytest.raises(ValueError, match="verified caller access token"):
        create_caller_scoped_client("")

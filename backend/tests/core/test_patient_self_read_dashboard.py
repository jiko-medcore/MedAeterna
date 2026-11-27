from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import clinical_authorization
from app.core.role_catalogue import PATIENT, PRACTITIONER
from app.modules.dashboard import router as dashboard_router
from app.modules.dashboard import service as dashboard_service
from app.modules.prescriptions import service as prescription_service
from app.modules.reminders import service as reminder_service

PATIENT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def patient_user():
    return {
        "id": PATIENT_ID,
        "email": "patient@example.test",
        "roles": [{"category": PATIENT, "organization_id": None}],
        "is_patient": True,
    }


def valid_context(resource: str = "clinical_record", **overrides):
    context = {
        **patient_user(),
        "authorized_action": "read",
        "authorized_resource": resource,
        "authorized_user_id": PATIENT_ID,
        "authorized_patient_id": PATIENT_ID,
        "authorized_organization_id": None,
    }
    context.update(overrides)
    return context


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.columns = None
        self.filters = {}

    def select(self, columns):
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def gte(self, column, value):
        self.filters[column] = (">=", value)
        return self

    def execute(self):
        self.client.calls.append(
            {"table": self.table, "columns": self.columns, "filters": dict(self.filters)}
        )
        return SimpleNamespace(data=[])


class FakeClient:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return FakeQuery(self, name)


@pytest.mark.parametrize("resource", ["clinical_record", "reminder"])
def test_authorize_patient_self_read_builds_resource_specific_context(
    monkeypatch, resource
):
    user = patient_user()
    relationship_calls = []

    def fake_patient_access(_user, patient_id, **kwargs):
        relationship_calls.append((patient_id, kwargs))
        return {
            "authorized_patient_id": patient_id,
            "authorized_organization_id": None,
        }

    monkeypatch.setattr(
        clinical_authorization.security,
        "authorize_patient_access",
        fake_patient_access,
    )

    context = clinical_authorization.authorize_patient_self_read(
        user,
        resource=resource,
        patient_id=PATIENT_ID,
    )

    assert context["authorized_resource"] == resource
    assert context["authorized_action"] == "read"
    assert context["authorized_user_id"] == PATIENT_ID
    assert context["authorized_patient_id"] == PATIENT_ID
    if resource == "clinical_record":
        assert relationship_calls == [
            (
                PATIENT_ID,
                {
                    "allow_practitioner": False,
                    "resource_family": "clinical_history",
                    "action": "read",
                },
            )
        ]
    else:
        # Reminder authorization is a SPEC-03 self-read rule, not a SPEC-04
        # clinical relationship resource.
        assert relationship_calls == []


def test_authorize_patient_self_read_rejects_practitioner():
    practitioner = {
        "id": PATIENT_ID,
        "roles": [{"category": PRACTITIONER, "organization_id": "org-1"}],
    }
    with pytest.raises(HTTPException) as exc:
        clinical_authorization.authorize_patient_self_read(
            practitioner,
            resource="reminder",
            patient_id=PATIENT_ID,
        )
    assert exc.value.status_code == 403


def test_authorize_patient_self_read_rejects_other_patient():
    user = patient_user()
    with pytest.raises(HTTPException) as exc:
        clinical_authorization.authorize_patient_self_read(
            user,
            resource="clinical_record",
            patient_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
    assert exc.value.status_code == 403


def test_authorize_patient_self_read_rejects_unsupported_resource():
    with pytest.raises(HTTPException) as exc:
        clinical_authorization.authorize_patient_self_read(
            patient_user(),
            resource="appointment",
            patient_id=PATIENT_ID,
        )
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "context,resource,patient_id",
    [
        (None, "clinical_record", PATIENT_ID),
        (valid_context("reminder"), "clinical_record", PATIENT_ID),
        (valid_context("clinical_record", authorized_action="create"), "clinical_record", PATIENT_ID),
        (valid_context("clinical_record", authorized_patient_id="other"), "clinical_record", PATIENT_ID),
        (valid_context("clinical_record", authorized_user_id="other"), "clinical_record", PATIENT_ID),
        (
            valid_context(
                "clinical_record",
                roles=[{"category": PRACTITIONER, "organization_id": "org-1"}],
            ),
            "clinical_record",
            PATIENT_ID,
        ),
    ],
)
def test_patient_self_read_context_rejects_invalid_context(context, resource, patient_id):
    with pytest.raises(HTTPException) as exc:
        clinical_authorization.ensure_patient_self_read_context(
            context,
            resource=resource,
            patient_id=patient_id,
        )
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "service,resource,table",
    [
        (prescription_service.get_active_prescriptions, "clinical_record", "prescriptions"),
        (reminder_service.get_upcoming_reminders, "reminder", "reminders"),
    ],
)
@pytest.mark.parametrize(
    "context",
    [
        None,
        valid_context("wrong-resource"),
        valid_context(authorized_action="update"),
        valid_context(authorized_user_id="different-actor"),
        valid_context(authorized_patient_id="different-patient"),
        valid_context(
            roles=[{"category": PRACTITIONER, "organization_id": "org-1"}]
        ),
    ],
)
def test_legacy_self_read_services_reject_invalid_context_before_query(
    monkeypatch, service, resource, table, context
):
    fake = FakeClient()
    if table == "prescriptions":
        monkeypatch.setattr(prescription_service, "supabase", fake)
    else:
        monkeypatch.setattr(reminder_service, "supabase", fake)

    with pytest.raises(HTTPException) as exc:
        service(PATIENT_ID, authorized_context=context)

    assert exc.value.status_code == 403
    assert fake.calls == []


@pytest.mark.parametrize(
    "service,resource,table",
    [
        (prescription_service.get_active_prescriptions, "clinical_record", "prescriptions"),
        (reminder_service.get_upcoming_reminders, "reminder", "reminders"),
    ],
)
def test_legacy_self_read_services_query_only_after_valid_context(
    monkeypatch, service, resource, table
):
    fake = FakeClient()
    if table == "prescriptions":
        monkeypatch.setattr(prescription_service, "supabase", fake)
    else:
        monkeypatch.setattr(reminder_service, "supabase", fake)

    assert service(
        PATIENT_ID,
        authorized_context=valid_context(resource),
    ) == []
    assert len(fake.calls) == 1
    assert fake.calls[0]["table"] == table
    assert fake.calls[0]["filters"]["patient_id"] == PATIENT_ID


def test_dashboard_service_validates_both_contexts_before_patient_lookup(mocker):
    patient_lookup = mocker.patch.object(dashboard_service, "get_or_create_patient")
    with pytest.raises(HTTPException):
        dashboard_service.build_user_summary(
            patient_user(),
            prescriptions_authorized_context=valid_context("clinical_record"),
            reminders_authorized_context=None,
        )
    patient_lookup.assert_not_called()


def test_dashboard_service_passes_distinct_contexts_to_legacy_services(mocker):
    patient = {"first_name": "Test", "last_name": "Patient"}
    mocker.patch.object(
        dashboard_service, "get_or_create_patient", return_value={"patient": patient}
    )
    prescriptions = mocker.patch.object(
        dashboard_service, "get_active_prescriptions", return_value=[]
    )
    reminders = mocker.patch.object(
        dashboard_service, "get_upcoming_reminders", return_value=[]
    )
    prescriptions_context = valid_context("clinical_record")
    reminders_context = valid_context("reminder")

    result = dashboard_service.build_user_summary(
        patient_user(),
        prescriptions_authorized_context=prescriptions_context,
        reminders_authorized_context=reminders_context,
    )

    assert result["user"]["fullName"] == "Test Patient"
    prescriptions.assert_called_once_with(
        PATIENT_ID, authorized_context=prescriptions_context
    )
    reminders.assert_called_once_with(
        PATIENT_ID, authorized_context=reminders_context
    )


def test_dashboard_route_authorizes_both_resources_before_building_summary(
    authenticated_client, current_user, mocker
):
    current_user.update(patient_user())
    current_user["roles"] = [{"category": PATIENT, "organization_id": None}]
    authorize = mocker.patch.object(
        dashboard_router,
        "authorize_patient_self_read",
        side_effect=lambda user, *, resource, patient_id: valid_context(resource),
    )
    build = mocker.patch.object(
        dashboard_router, "build_user_summary", return_value={"summary": "ok"}
    )

    response = authenticated_client.get("/api/v1/user/summary")

    assert response.status_code == 200
    assert [call.kwargs["resource"] for call in authorize.call_args_list] == [
        "clinical_record",
        "reminder",
    ]
    build.assert_called_once_with(
        current_user,
        prescriptions_authorized_context=valid_context("clinical_record"),
        reminders_authorized_context=valid_context("reminder"),
    )


def test_dashboard_route_does_not_build_summary_when_second_authorization_fails(
    authenticated_client, current_user, mocker
):
    current_user.update(patient_user())
    current_user["roles"] = [{"category": PATIENT, "organization_id": None}]

    def authorize(_user, *, resource, patient_id):
        if resource == "reminder":
            raise HTTPException(status_code=403, detail="Denied")
        return valid_context(resource)

    authorize_mock = mocker.patch.object(
        dashboard_router, "authorize_patient_self_read", side_effect=authorize
    )
    build = mocker.patch.object(
        dashboard_router, "build_user_summary", return_value={"summary": "ok"}
    )

    response = authenticated_client.get("/api/v1/user/summary")

    assert response.status_code == 403
    assert authorize_mock.call_count == 2
    build.assert_not_called()


@pytest.mark.parametrize(
    "roles",
    [
        [{"category": PRACTITIONER, "organization_id": "org-1"}],
        [{"category": "organization_administrator", "organization_id": "org-1"}],
        [],
    ],
)
def test_dashboard_route_denies_non_patient_roles_before_summary(
    authenticated_client, current_user, mocker, roles
):
    current_user["roles"] = roles
    current_user["is_patient"] = False
    build = mocker.patch.object(
        dashboard_router, "build_user_summary", return_value={"summary": "ok"}
    )

    response = authenticated_client.get("/api/v1/user/summary")

    assert response.status_code == 403
    build.assert_not_called()

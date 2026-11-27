from types import SimpleNamespace

import pytest

from app.core import patient_avatar_access as access
from app.core.patient_avatar_access import PATIENT_AVATAR_URL_TTL_SECONDS
from app.modules.dashboard import service as dashboard_service
from app.modules.patients import router as patients_router
from app.modules.patients import service as patients_service

SIGNED_URL = "https://storage.test/object/sign/patient-avatars/avatar.png?token=x"


class Query:
    """Minimal chainable PostgREST query used only by local tests."""

    def __init__(self, rows):
        self.rows = rows

    def select(self, columns=None):
        return self

    def eq(self, key, value):
        return self

    def in_(self, key, values):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


def _mock_storage(mocker, signed_url=SIGNED_URL):
    admin = mocker.patch.object(access, "supabase_admin")
    bucket = admin.storage.from_.return_value
    bucket.create_signed_url.return_value = {"signedURL": signed_url}
    return admin, bucket


def _mock_select(mocker, rows):
    admin = mocker.patch.object(patients_service, "supabase")
    admin.table.return_value = Query(rows)
    return admin


def test_patients_me_returns_signed_url_and_hides_stored_path(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    path = f"{patient_id}/avatar.png"
    _, bucket = _mock_storage(mocker)
    _mock_select(
        mocker,
        [
            {
                "id": patient_id,
                "first_name": "Test",
                "profile_image_path": path,
                "profile_image_url": "https://stale.test/public.png",
            }
        ],
    )

    response = authenticated_client.get("/patients/me")

    assert response.status_code == 200
    body = response.json()
    assert body["profile_image_url"] == SIGNED_URL
    assert "profile_image_path" not in body
    bucket.create_signed_url.assert_called_once_with(path, PATIENT_AVATAR_URL_TTL_SECONDS)


def test_patient_profile_me_returns_signed_url_and_hides_stored_path(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    path = f"{patient_id}/avatar.webp"
    _, bucket = _mock_storage(mocker)
    _mock_select(
        mocker,
        [
            {
                "id": patient_id,
                "first_name": "Test",
                "profile_image_path": path,
                "profile_image_url": "https://stale.test/public.png",
            }
        ],
    )

    response = authenticated_client.get("/patients/profile/me")

    assert response.status_code == 200
    body = response.json()
    assert body["profile_image_url"] == SIGNED_URL
    assert "profile_image_path" not in body
    bucket.create_signed_url.assert_called_once_with(path, PATIENT_AVATAR_URL_TTL_SECONDS)


def test_user_summary_returns_signed_avatar_url_under_existing_field(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    path = f"{patient_id}/avatar.jpg"
    _, bucket = _mock_storage(mocker)
    _mock_select(
        mocker,
        [
            {
                "id": patient_id,
                "first_name": "Test",
                "last_name": "Patient",
                "profile_image_path": path,
                "profile_image_url": "https://stale.test/public.png",
            }
        ],
    )
    mocker.patch.object(dashboard_service, "get_active_prescriptions", return_value=[])
    mocker.patch.object(dashboard_service, "get_upcoming_reminders", return_value=[])
    from app.modules.dashboard import router as dashboard_router
    mocker.patch.object(
        dashboard_router,
        "authorize_patient_self_read",
        side_effect=lambda user, *, resource, patient_id: {
            **user,
            "authorized_action": "read",
            "authorized_resource": resource,
            "authorized_user_id": patient_id,
            "authorized_patient_id": patient_id,
        },
    )

    response = authenticated_client.get("/api/v1/user/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["avatarUrl"] == SIGNED_URL
    assert "profile_image_path" not in body
    assert "profile_image_path" not in body["user"]
    bucket.create_signed_url.assert_called_once_with(path, PATIENT_AVATAR_URL_TTL_SECONDS)


def test_patients_mine_signs_only_authorized_returned_patients(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = False
    context = {
        **current_user,
        "authorized_action": "read",
        "authorized_resource": patients_service.PATIENT_LIST,
        "authorized_user_id": str(current_user["id"]),
        "authorized_practitioner_id": "practitioner-1",
        "authorized_organization_id": "org-1",
    }
    mocker.patch.object(
        patients_router, "authorize_patient_list_access", return_value=context
    )

    authorized_id = "authorized-patient"
    unauthorized_id = "other-patient"
    paths = {
        authorized_id: f"{authorized_id}/avatar.png",
        unauthorized_id: f"{unauthorized_id}/avatar.png",
    }
    rows = [
        {
            "id": authorized_id,
            "profile_image_path": paths[authorized_id],
            "profile_image_url": None,
        }
    ]

    care_team_query = Query([{"patient_id": authorized_id}])
    patient_query = Query(rows)
    admin = mocker.patch.object(patients_service, "supabase_admin")
    admin.table.side_effect = [care_team_query, patient_query]
    _, bucket = _mock_storage(mocker)

    response = authenticated_client.get("/patients/mine")

    assert response.status_code == 200
    body = response.json()
    assert [row["profile_image_url"] for row in body] == [SIGNED_URL]
    assert all("profile_image_path" not in row for row in body)
    bucket.create_signed_url.assert_called_once_with(
        paths[authorized_id], PATIENT_AVATAR_URL_TTL_SECONDS
    )
    assert unauthorized_id not in {row["id"] for row in body}


@pytest.mark.parametrize(
    "route",
    ["/patients/me", "/patients/profile/me"],
)
def test_patient_read_fails_closed_when_signing_fails(
    authenticated_client, current_user, mocker, route
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    _, bucket = _mock_storage(mocker, signed_url="")
    bucket.create_signed_url.return_value = {}
    _mock_select(
        mocker,
        [
            {
                "id": patient_id,
                "profile_image_path": f"{patient_id}/avatar.png",
                "profile_image_url": "https://stale.test/public.png",
            }
        ],
    )

    response = authenticated_client.get(route)

    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to issue profile image URL"


def test_legacy_public_url_is_signed_without_legacy_path_column(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    path = f"{patient_id}/avatar.png"
    legacy_url = (
        "https://project.supabase.co/storage/v1/object/public/patient-avatars/"
        + path
    )
    _, bucket = _mock_storage(mocker)
    _mock_select(
        mocker,
        [
            {
                "id": patient_id,
                "profile_image_path": None,
                "profile_image_url": legacy_url,
            }
        ],
    )

    response = authenticated_client.get("/patients/profile/me")

    assert response.status_code == 200
    assert response.json()["profile_image_url"] == SIGNED_URL
    bucket.create_signed_url.assert_called_once_with(path, PATIENT_AVATAR_URL_TTL_SECONDS)


def test_unknown_legacy_value_is_not_returned_as_avatar_url(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    _, bucket = _mock_storage(mocker)
    _mock_select(
        mocker,
        [
            {
                "id": patient_id,
                "profile_image_path": None,
                "profile_image_url": "https://external.test/legacy-avatar.png",
            }
        ],
    )

    response = authenticated_client.get("/patients/profile/me")

    assert response.status_code == 200
    assert response.json()["profile_image_url"] is None
    bucket.create_signed_url.assert_not_called()

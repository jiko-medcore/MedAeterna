from unittest.mock import ANY, Mock

from app.core import patient_avatar_access as patient_avatar_access_module
from app.core.patient_avatar_access import PATIENT_AVATAR_URL_TTL_SECONDS

PNG = b"\x89PNG\r\n\x1a\n" + b"avatar-content"
SIGNED_URL = "https://storage.test/object/sign/patient-avatars/avatar.png?token=x"


def _mock_admin(mocker, signed_url=SIGNED_URL):
    bucket = Mock()
    bucket.create_signed_url.return_value = {"signedURL": signed_url}
    admin = mocker.patch("app.modules.patients.router.supabase_admin")
    admin.storage.from_.return_value = bucket
    mocker.patch.object(patient_avatar_access_module, "supabase_admin", admin)
    return bucket, admin


def test_patient_avatar_upload_uses_service_role_owner_path_and_signed_url(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    file_path = f"{patient_id}/avatar.png"
    bucket, admin = _mock_admin(mocker)
    update_image = mocker.patch("app.modules.patients.router.update_profile_image_path")

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={"file": ("ignored.png", PNG, "image/png")},
    )

    assert response.status_code == 200
    assert admin.storage.from_.call_count == 2
    assert all(
        call.args == ("patient-avatars",)
        for call in admin.storage.from_.call_args_list
    )
    bucket.upload.assert_called_once_with(
        path=file_path,
        file=PNG,
        file_options={"content-type": "image/png", "upsert": "true"},
    )
    bucket.create_signed_url.assert_called_once_with(
        file_path, PATIENT_AVATAR_URL_TTL_SECONDS
    )
    bucket.get_public_url.assert_not_called()
    update_image.assert_called_once_with(
        patient_id, file_path, authorized_context=ANY
    )
    assert response.json() == {
        "message": "Profile image uploaded successfully",
        "profile_image_url": SIGNED_URL,
    }


def test_patient_avatar_upload_rejects_forged_image_before_storage_call(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    bucket, admin = _mock_admin(mocker)

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={"file": ("avatar.png", b"not-a-png", "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "content does not match its declared type"
    bucket.upload.assert_not_called()
    bucket.create_signed_url.assert_not_called()


def test_patient_avatar_upload_rejects_oversized_file(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    bucket, admin = _mock_admin(mocker)

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={
            "file": (
                "avatar.png",
                PNG + b"x" * (2 * 1024 * 1024),
                "image/png",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid file size"
    bucket.upload.assert_not_called()


def test_non_patient_cannot_upload_avatar(authenticated_client, mocker):
    bucket, admin = _mock_admin(mocker)

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={"file": ("avatar.png", PNG, "image/png")},
    )

    assert response.status_code == 403
    bucket.upload.assert_not_called()
    bucket.create_signed_url.assert_not_called()


def test_avatar_upload_compensates_object_when_database_update_fails(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    file_path = f"{patient_id}/avatar.png"
    bucket, admin = _mock_admin(mocker)
    mocker.patch(
        "app.modules.patients.router.update_profile_image_path",
        side_effect=RuntimeError("db unavailable"),
    )

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={"file": ("avatar.png", PNG, "image/png")},
    )

    assert response.status_code == 500
    bucket.remove.assert_called_once_with([file_path])


def test_avatar_upload_compensates_object_when_signing_fails(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    current_user["roles"] = [{"category": "patient", "organization_id": None}]
    patient_id = str(current_user["id"])
    file_path = f"{patient_id}/avatar.png"
    bucket, admin = _mock_admin(mocker, signed_url="")
    update_image = mocker.patch("app.modules.patients.router.update_profile_image_path")

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={"file": ("avatar.png", PNG, "image/png")},
    )

    assert response.status_code == 500
    bucket.remove.assert_called_once_with([file_path])
    update_image.assert_not_called()

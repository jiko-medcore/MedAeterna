from unittest.mock import Mock

PNG = b"\x89PNG\r\n\x1a\n" + b"avatar-content"


def test_patient_avatar_upload_uses_service_role_and_owner_scoped_path(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True

    bucket = Mock()
    bucket.get_public_url.return_value = (
        f"https://storage.test/patient-avatars/{current_user['id']}/avatar.png"
    )
    admin = mocker.patch("app.modules.patients.router.supabase_admin")
    admin.storage.from_.return_value = bucket
    update_image = mocker.patch("app.modules.patients.router.update_profile_image")

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={"file": ("avatar.png", PNG, "image/png")},
    )

    assert response.status_code == 200
    admin.storage.from_.assert_called_once_with("patient-avatars")
    bucket.upload.assert_called_once_with(
        path=f"{current_user['id']}/avatar.png",
        file=PNG,
        file_options={"content-type": "image/png", "upsert": "true"},
    )
    update_image.assert_called_once_with(
        current_user["id"], bucket.get_public_url.return_value
    )
    assert response.json() == {
        "message": "Profile image uploaded successfully",
        "profile_image_url": bucket.get_public_url.return_value,
    }


def test_patient_avatar_upload_rejects_forged_image_before_storage_call(
    authenticated_client, current_user, mocker
):
    current_user["is_patient"] = True
    admin = mocker.patch("app.modules.patients.router.supabase_admin")

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={"file": ("avatar.png", b"not-a-png", "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "content does not match its declared type"
    admin.storage.from_.assert_not_called()


def test_non_patient_cannot_upload_avatar(authenticated_client, mocker):
    admin = mocker.patch("app.modules.patients.router.supabase_admin")

    response = authenticated_client.post(
        "/patients/profile/upload-avatar",
        files={"file": ("avatar.png", PNG, "image/png")},
    )

    assert response.status_code == 403
    admin.storage.from_.assert_not_called()

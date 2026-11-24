import pytest
from fastapi import HTTPException

from app.core import patient_avatar_access as access
from app.core.patient_avatar_access import (
    PATIENT_AVATAR_URL_TTL_SECONDS,
    PatientAvatarSigningError,
    create_signed_patient_avatar_url,
    is_patient_avatar_object_path,
    patient_avatar_object_path,
    with_private_avatar_url,
    with_private_avatar_urls,
)

PATIENT_ID = "user-1"
PATH = f"{PATIENT_ID}/avatar.png"
SIGNED_URL = "https://storage.test/object/sign/patient-avatars/user-1/avatar.png?token=x"


def _mock_bucket(mocker, signed_url=SIGNED_URL):
    admin = mocker.patch.object(access, "supabase_admin")
    bucket = admin.storage.from_.return_value
    bucket.create_signed_url.return_value = {"signedURL": signed_url}
    return admin, bucket


def test_object_path_is_exact_and_owner_scoped():
    assert is_patient_avatar_object_path(PATH, PATIENT_ID) is True
    assert is_patient_avatar_object_path(f"{PATIENT_ID}/avatar.webp", PATIENT_ID) is True
    assert is_patient_avatar_object_path(f"{PATIENT_ID}/avatar.exe", PATIENT_ID) is False
    assert is_patient_avatar_object_path("other/avatar.png", PATIENT_ID) is False
    assert is_patient_avatar_object_path(f"{PATIENT_ID}/nested/avatar.png", PATIENT_ID) is False
    assert is_patient_avatar_object_path(None, PATIENT_ID) is False


def test_stable_path_takes_precedence_over_legacy_value():
    assert (
        patient_avatar_object_path(
            patient_id=PATIENT_ID,
            stored_path=PATH,
            legacy_url="https://example.test/stale.png",
        )
        == PATH
    )


@pytest.mark.parametrize(
    "legacy_url",
    [
        f"https://project.supabase.co/storage/v1/object/public/patient-avatars/{PATH}",
        f"https://project.supabase.co/storage/v1/object/public/patient-avatars/{PATH}?download=1",
        PATH,
    ],
)
def test_legacy_public_url_is_converted_to_trusted_path(legacy_url):
    assert patient_avatar_object_path(patient_id=PATIENT_ID, legacy_url=legacy_url) == PATH


@pytest.mark.parametrize(
    "legacy_url",
    [
        "https://example.test/avatar.png",
        f"https://project.supabase.co/storage/v1/object/public/patient-avatars/other/avatar.png",
        f"https://project.supabase.co/storage/v1/object/public/patient-avatars/{PATIENT_ID}/avatar.exe",
        f"https://project.supabase.co/storage/v1/object/public/patient-avatars/{PATIENT_ID}/nested/avatar.png",
        None,
    ],
)
def test_untrusted_legacy_values_fail_closed(legacy_url):
    assert patient_avatar_object_path(patient_id=PATIENT_ID, legacy_url=legacy_url) is None


def test_create_signed_url_uses_central_ttl_and_sdk_response_key(mocker):
    admin, bucket = _mock_bucket(mocker)

    assert (
        create_signed_patient_avatar_url(patient_id=PATIENT_ID, object_path=PATH)
        == SIGNED_URL
    )
    admin.storage.from_.assert_called_once_with("patient-avatars")
    bucket.create_signed_url.assert_called_once_with(PATH, PATIENT_AVATAR_URL_TTL_SECONDS)


def test_create_signed_url_accepts_alternate_sdk_key(mocker):
    _, bucket = _mock_bucket(mocker, signed_url=SIGNED_URL)
    bucket.create_signed_url.return_value = {"signedUrl": SIGNED_URL}

    assert (
        create_signed_patient_avatar_url(patient_id=PATIENT_ID, object_path=PATH)
        == SIGNED_URL
    )


def test_create_signed_url_rejects_missing_or_invalid_response(mocker):
    _, bucket = _mock_bucket(mocker)
    bucket.create_signed_url.return_value = {}

    with pytest.raises(PatientAvatarSigningError):
        create_signed_patient_avatar_url(patient_id=PATIENT_ID, object_path=PATH)

    bucket.create_signed_url.side_effect = RuntimeError("storage unavailable")
    with pytest.raises(PatientAvatarSigningError):
        create_signed_patient_avatar_url(patient_id=PATIENT_ID, object_path=PATH)


def test_create_signed_url_rejects_unvalidated_path(mocker):
    admin = mocker.patch.object(access, "supabase_admin")

    with pytest.raises(PatientAvatarSigningError):
        create_signed_patient_avatar_url(
            patient_id=PATIENT_ID, object_path="other/avatar.png"
        )
    admin.storage.from_.assert_not_called()


def test_private_avatar_projection_hides_path_and_signs_stored_path(mocker):
    _mock_bucket(mocker)
    row = {
        "id": PATIENT_ID,
        "profile_image_path": PATH,
        "profile_image_url": "https://stale.test/public.png",
        "first_name": "Test",
    }

    result = with_private_avatar_url(row)

    assert result["profile_image_url"] == SIGNED_URL
    assert "profile_image_path" not in result
    assert result["first_name"] == "Test"


def test_private_avatar_projection_without_trusted_path_is_null(mocker):
    admin = mocker.patch.object(access, "supabase_admin")

    result = with_private_avatar_url(
        {
            "id": PATIENT_ID,
            "profile_image_path": None,
            "profile_image_url": "https://external.test/not-a-storage-object.png",
        }
    )

    assert result["profile_image_url"] is None
    admin.storage.from_.assert_not_called()


def test_private_avatar_projection_fails_closed_when_signing_fails(mocker):
    _, bucket = _mock_bucket(mocker)
    bucket.create_signed_url.return_value = {}

    with pytest.raises(HTTPException) as exc:
        with_private_avatar_url({"id": PATIENT_ID, "profile_image_path": PATH})

    assert exc.value.status_code == 500
    assert exc.value.detail == "Unable to issue profile image URL"


def test_private_avatar_collection_applies_same_projection(mocker):
    _mock_bucket(mocker)
    rows = [
        {"id": PATIENT_ID, "profile_image_path": PATH},
        {"id": "user-2", "profile_image_path": None, "profile_image_url": None},
    ]

    result = with_private_avatar_urls(rows)

    assert [row["profile_image_url"] for row in result] == [SIGNED_URL, None]
    assert all("profile_image_path" not in row for row in result)

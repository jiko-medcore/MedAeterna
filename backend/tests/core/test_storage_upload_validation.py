import pytest

from app.core.storage_upload_validation import (
    StorageUploadValidationError,
    content_type_matches_signature,
    validate_image_upload,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"payload"
JPEG = b"\xff\xd8\xff" + b"payload"
WEBP = b"RIFF" + b"1234" + b"WEBP" + b"payload"


@pytest.mark.parametrize(
    ("content_type", "content"),
    [("image/png", PNG), ("image/jpeg", JPEG), ("image/webp", WEBP)],
)
def test_supported_image_signatures_are_accepted(content_type, content):
    assert content_type_matches_signature(content_type, content) is True


def test_signature_mismatch_is_rejected():
    assert content_type_matches_signature("image/png", JPEG) is False
    assert content_type_matches_signature("image/webp", b"RIFF1234JPEG") is False
    assert content_type_matches_signature("image/png", b"") is False
    assert content_type_matches_signature("application/pdf", PNG) is False


@pytest.mark.parametrize(
    ("bucket", "content_type", "content", "expected_extension"),
    [
        ("organization-logos", "image/png", PNG, "png"),
        ("patient-avatars", "image/jpeg", JPEG, "jpg"),
        ("practitioner-photos", "image/webp", WEBP, "webp"),
    ],
)
def test_validate_image_upload_returns_trusted_extension(
    bucket, content_type, content, expected_extension
):
    assert (
        validate_image_upload(
            bucket=bucket, content_type=content_type, content=content
        )
        == expected_extension
    )


def test_validate_image_upload_rejects_unknown_bucket():
    with pytest.raises(StorageUploadValidationError, match="unknown storage bucket"):
        validate_image_upload(
            bucket="patient-documents", content_type="image/png", content=PNG
        )


def test_validate_image_upload_rejects_unsupported_declared_type():
    with pytest.raises(StorageUploadValidationError, match="unsupported content type"):
        validate_image_upload(
            bucket="patient-avatars",
            content_type="application/pdf",
            content=PNG,
        )


def test_validate_image_upload_rejects_empty_and_oversized_files():
    with pytest.raises(StorageUploadValidationError, match="invalid file size"):
        validate_image_upload(
            bucket="patient-avatars", content_type="image/png", content=b""
        )
    with pytest.raises(StorageUploadValidationError, match="invalid file size"):
        validate_image_upload(
            bucket="patient-avatars",
            content_type="image/png",
            content=b"\x89PNG\r\n\x1a\n" + b"x" * (2 * 1024 * 1024),
        )


def test_validate_image_upload_rejects_forged_content_type():
    with pytest.raises(StorageUploadValidationError, match="declared type"):
        validate_image_upload(
            bucket="patient-avatars", content_type="image/png", content=JPEG
        )

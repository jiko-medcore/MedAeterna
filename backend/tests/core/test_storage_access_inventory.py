import tomllib
from pathlib import Path

from app.core.database_execution_policy import ExecutionMode
from app.core.storage_access_inventory import (
    BucketClass,
    IMAGE_SIGNATURES,
    MAX_IMAGE_SIZE_BYTES,
    PLANNED_BUCKETS,
    STORAGE_BUCKET_INVENTORY,
    STORAGE_OBJECT_POLICIES,
    all_policy_names,
    bucket_is_covered,
    expected_bucket_config,
    missing_policy_violations,
    object_owner_token,
    object_path_is_valid,
    policy_violations,
)

EXPECTED_BUCKETS = {
    "organization-logos",
    "patient-avatars",
    "practitioner-photos",
}
EXPECTED_PUBLIC_FLAGS = {
    "organization-logos": True,
    "patient-avatars": False,
    "practitioner-photos": False,
}
EXPECTED_CLASSIFICATIONS = {
    "organization-logos": BucketClass.PUBLIC_OWNED,
    "patient-avatars": BucketClass.PRIVATE_OWNED,
    "practitioner-photos": BucketClass.PRIVATE_OWNED,
}


def test_inventory_covers_every_installed_bucket():
    assert set(STORAGE_BUCKET_INVENTORY) == EXPECTED_BUCKETS


def test_planned_private_buckets_are_explicitly_uncovered():
    assert "patient-documents" in PLANNED_BUCKETS
    for name in PLANNED_BUCKETS:
        assert bucket_is_covered(name) is False
        assert expected_bucket_config(name) is None


def test_every_bucket_has_reviewed_limits_and_owner_path():
    for rule in STORAGE_BUCKET_INVENTORY.values():
        assert rule.file_size_limit == MAX_IMAGE_SIZE_BYTES
        assert rule.allowed_mime_types == set(IMAGE_SIGNATURES)
        assert set(rule.extension_by_mime) == rule.allowed_mime_types
        assert rule.owner_token
        assert "<" in rule.object_path_pattern
        assert rule.execution_mode is ExecutionMode.SERVICE_ROLE


def test_public_flags_and_classifications_match_approved_policy():
    assert {
        name: rule.public for name, rule in STORAGE_BUCKET_INVENTORY.items()
    } == EXPECTED_PUBLIC_FLAGS
    assert {
        name: rule.classification for name, rule in STORAGE_BUCKET_INVENTORY.items()
    } == EXPECTED_CLASSIFICATIONS


def test_local_storage_config_matches_inventory():
    config_path = Path(__file__).resolve().parents[2] / "supabase" / "config.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    buckets = config["storage"]["buckets"]

    assert set(buckets) == EXPECTED_BUCKETS
    for name, rule in STORAGE_BUCKET_INVENTORY.items():
        assert buckets[name]["public"] is rule.public
        assert buckets[name]["file_size_limit"] == "2MiB"
        assert set(buckets[name]["allowed_mime_types"]) == set(
            rule.allowed_mime_types
        )


def test_explicit_deny_policy_is_the_only_client_object_policy():
    assert len(STORAGE_OBJECT_POLICIES) == 1
    policy = STORAGE_OBJECT_POLICIES[0]
    assert policy.name == "Deny direct client object access"
    assert policy.command == "ALL"
    assert policy.role == "anon, authenticated"
    assert policy.predicate == "false"
    assert policy.check == "false"
    assert all_policy_names() == (policy.name,)


def test_policy_catalog_helpers_detect_unexpected_and_missing_policies():
    expected = all_policy_names()
    assert policy_violations([]) == []
    assert policy_violations(["Anything"]) == ["Anything"]
    assert missing_policy_violations(expected) == []
    assert missing_policy_violations([]) == list(expected)


def test_owner_token_is_first_non_empty_path_component():
    assert object_owner_token("123/logo.png") == "123"
    assert object_owner_token("/123/avatar.png") == "123"
    assert object_owner_token("") is None


def test_object_paths_must_be_owner_scoped_with_a_trusted_extension():
    assert object_path_is_valid("patient-avatars", "user-1/avatar.png", "user-1")
    assert object_path_is_valid("organization-logos", "org-1/logo.webp", "org-1")
    assert object_path_is_valid("practitioner-photos", "p-1/photo.jpg", "p-1")
    assert object_path_is_valid("patient-avatars", "other/avatar.png", "user-1") is False
    assert object_path_is_valid("patient-avatars", "user-1/avatar.exe", "user-1") is False
    assert object_path_is_valid("patient-documents", "user-1/file.pdf", "user-1") is False

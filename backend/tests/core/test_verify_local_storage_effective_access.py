import json

import pytest

from scripts.verify_local_storage_effective_access import (
    is_denied,
    listed_names,
    load_status,
)


def test_storage_rls_denial_recognizes_embedded_403():
    assert is_denied(403, None) is True
    assert is_denied(400, {"statusCode": "403"}) is True
    assert is_denied(400, {"statusCode": 403}) is True
    assert is_denied(400, {"statusCode": "404"}) is False
    assert is_denied(200, None) is False


def test_listed_names_only_returns_string_names():
    body = json.dumps(
        [{"name": "owner/file.png"}, {"name": 7}, {"id": "no-name"}]
    ).encode()
    assert listed_names(body) == ["owner/file.png"]
    assert listed_names(b"not-json") == []


def test_status_loader_refuses_non_loopback_targets(tmp_path):
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps({"API_URL": "https://example.supabase.co"}), encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="refusing non-local API target"):
        load_status(status_path)


def test_status_loader_accepts_loopback_target(tmp_path):
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps({"API_URL": "http://127.0.0.1:54321"}), encoding="utf-8"
    )
    assert load_status(status_path)["API_URL"] == "http://127.0.0.1:54321"

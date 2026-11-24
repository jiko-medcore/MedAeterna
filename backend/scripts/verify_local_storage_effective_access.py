"""Effective local Storage API checks for the SPEC-12 object model.

This script is intentionally standalone: it requires a running local Supabase
stack and a JSON status snapshot from ``supabase status -o json``. It never
accepts a hosted URL and refuses to run unless the API endpoint is loopback.

Example:
    supabase status -o json > /tmp/opencode/storage_status.json
    .venv/Scripts/python.exe scripts/verify_local_storage_effective_access.py \
        --status-json /tmp/opencode/storage_status.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import jwt

BUCKET = "organization-logos"
PLANNED_PRIVATE_BUCKET = "patient-documents"
OWNER_ID = "00000000-0000-4000-8000-000000000007"
CROSS_TENANT_ID = "00000000-0000-4000-8000-000000000008"
OBJECT_PATH = f"{OWNER_ID}/order7-verification.png"
MIME_OBJECT_PATH = f"{OWNER_ID}/order7-verification.pdf"
OVERSIZE_OBJECT_PATH = f"{OWNER_ID}/order7-oversize.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-json", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def load_status(path: Path) -> dict[str, Any]:
    status = json.loads(path.read_text(encoding="utf-8"))
    api_url = str(status["API_URL"]).rstrip("/")
    parsed = urlparse(api_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit(f"refusing non-local API target: {api_url}")
    return status


class StorageClient:
    def __init__(self, status: dict[str, Any]) -> None:
        self.api_url = str(status["API_URL"]).rstrip("/")
        self.anon_key = str(status["ANON_KEY"])
        self.service_key = str(status["SERVICE_ROLE_KEY"])
        self.jwt_secret = str(status["JWT_SECRET"])
        self.user_jwt = jwt.encode(
            {
                "sub": "00000000-0000-4000-8000-000000000017",
                "role": "authenticated",
                "aud": "authenticated",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            self.jwt_secret,
            algorithm="HS256",
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        bearer: str | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
        json_payload: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, dict[str, Any] | None]:
        headers = {"apikey": self.anon_key}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        if content_type:
            headers["Content-Type"] = content_type
        if json_payload is not None:
            headers["Content-Type"] = "application/json"
            content = json.dumps(json_payload).encode()
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(
            self.api_url + path,
            data=content,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read()
                status = response.status
        except urllib.error.HTTPError as error:
            body = error.read()
            status = error.code

        parsed: dict[str, Any] | None = None
        try:
            candidate = json.loads(body.decode())
            if isinstance(candidate, dict):
                parsed = candidate
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        return status, body, parsed

    def anon(self) -> str:
        return self.anon_key

    def authenticated(self) -> str:
        return self.user_jwt

    def service(self) -> str:
        return self.service_key

    def object_path(self, object_name: str) -> str:
        return f"/storage/v1/object/{BUCKET}/{object_name}"

    def public_path(self, object_name: str) -> str:
        return f"/storage/v1/object/public/{BUCKET}/{object_name}"


def check(name: str, passed: bool, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "detail": detail}


def is_denied(code: int, parsed: dict[str, Any] | None) -> bool:
    """Storage sometimes returns HTTP 400 with an embedded 403 status."""
    embedded = parsed is not None and str(parsed.get("statusCode")) == "403"
    return code in (401, 403) or (code == 400 and embedded)


def png_bytes(tag: str) -> bytes:
    return PNG_SIGNATURE + f"order7-{tag}-{uuid.uuid4()}".encode()


def listed_names(body: bytes) -> list[str]:
    try:
        listing = json.loads(body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(listing, list):
        return []
    return [item["name"] for item in listing if isinstance(item, dict) and isinstance(item.get("name"), str)]


def main() -> int:
    args = parse_args()
    status = load_status(args.status_json)
    client = StorageClient(status)
    png = png_bytes("primary")
    replacement = png_bytes("replacement")
    results: list[dict[str, Any]] = []

    # Remove any object left by an interrupted previous run.
    client.request("DELETE", client.object_path(OBJECT_PATH), bearer=client.service())

    try:
        code, body, parsed = client.request(
            "POST",
            client.object_path(OBJECT_PATH),
            bearer=client.anon(),
            content=png,
            content_type="image/png",
            extra_headers={"x-upsert": "false"},
        )
        results.append(
            check(
                "anonymous upload denied",
                is_denied(code, parsed),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, body, parsed = client.request(
            "POST",
            client.object_path(OBJECT_PATH),
            bearer=client.authenticated(),
            content=png,
            content_type="image/png",
            extra_headers={"x-upsert": "false"},
        )
        results.append(
            check(
                "authenticated upload denied",
                is_denied(code, parsed),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, body, _ = client.request(
            "POST",
            client.object_path(OBJECT_PATH),
            bearer=client.service(),
            content=png,
            content_type="image/png",
            extra_headers={"x-upsert": "false"},
        )
        results.append(
            check(
                "service-role upload succeeds",
                code in (200, 201),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, downloaded, _ = client.request(
            "GET", client.public_path(OBJECT_PATH)
        )
        results.append(
            check(
                "public bucket read returns exact bytes",
                code == 200 and downloaded == png,
                {"status": code, "bytes": len(downloaded)},
            )
        )

        code, authenticated_download, _ = client.request(
            "GET",
            client.object_path(OBJECT_PATH),
            bearer=client.authenticated(),
        )
        results.append(
            check(
                "public bucket object read succeeds with authenticated key",
                code == 200 and authenticated_download == png,
                {"status": code, "bytes": len(authenticated_download)},
            )
        )

        list_payload = {"prefix": OWNER_ID, "limit": 100, "offset": 0}
        code, body, _ = client.request(
            "POST",
            "/storage/v1/object/list/" + BUCKET,
            bearer=client.anon(),
            json_payload=list_payload,
        )
        anonymous_list = listed_names(body)
        results.append(
            check(
                "anonymous object listing discloses no names",
                code == 200 and anonymous_list == [],
                {"status": code, "entries": len(anonymous_list)},
            )
        )

        code, body, _ = client.request(
            "POST",
            "/storage/v1/object/list/" + BUCKET,
            bearer=client.authenticated(),
            json_payload=list_payload,
        )
        authenticated_list = listed_names(body)
        results.append(
            check(
                "authenticated object listing discloses no names",
                code == 200 and authenticated_list == [],
                {"status": code, "entries": len(authenticated_list)},
            )
        )

        code, body, _ = client.request(
            "POST",
            "/storage/v1/object/list/" + BUCKET,
            bearer=client.service(),
            json_payload=list_payload,
        )
        service_list = listed_names(body)
        listed = OBJECT_PATH.split("/", 1)[1] in service_list
        results.append(
            check(
                "service-role listing succeeds for trusted operations",
                code == 200 and listed,
                {"status": code, "listed_target": listed},
            )
        )

        code, body, _ = client.request(
            "POST",
            "/storage/v1/object/list/" + BUCKET,
            bearer=client.service(),
            json_payload={"prefix": CROSS_TENANT_ID, "limit": 100, "offset": 0},
        )
        cross_tenant_list = listed_names(body)
        results.append(
            check(
                "service-role cross-tenant prefix listing is empty",
                code == 200 and cross_tenant_list == [],
                {"status": code, "entries": len(cross_tenant_list)},
            )
        )

        code, body, parsed = client.request(
            "PUT",
            client.object_path(OBJECT_PATH),
            bearer=client.authenticated(),
            content=replacement,
            content_type="image/png",
        )
        results.append(
            check(
                "authenticated object update denied",
                is_denied(code, parsed),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        sign_path = f"/storage/v1/object/sign/{BUCKET}/{OBJECT_PATH}"
        code, body, parsed = client.request(
            "POST",
            sign_path,
            bearer=client.authenticated(),
            json_payload={"expiresIn": 60},
        )
        embedded_not_found = code == 400 and parsed is not None and str(parsed.get("statusCode")) == "404"
        results.append(
            check(
                "authenticated signed URL issuance denied",
                is_denied(code, parsed) or embedded_not_found,
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, body, parsed = client.request(
            "POST",
            sign_path,
            bearer=client.service(),
            json_payload={"expiresIn": 60},
        )
        signed_url = parsed.get("signedURL") if parsed else None
        results.append(
            check(
                "service-role signed URL issuance succeeds",
                code == 200 and bool(signed_url) and "token=" in str(signed_url),
                {"status": code, "has_token": bool(signed_url and "token=" in signed_url)},
            )
        )

        code, body, _ = client.request(
            "POST",
            client.object_path(OBJECT_PATH),
            bearer=client.service(),
            content=replacement,
            content_type="image/png",
            extra_headers={"x-upsert": "false"},
        )
        results.append(
            check(
                "non-upsert duplicate upload rejected",
                code >= 400,
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, body, _ = client.request(
            "POST",
            client.object_path(OBJECT_PATH),
            bearer=client.service(),
            content=replacement,
            content_type="image/png",
            extra_headers={"x-upsert": "true"},
        )
        results.append(
            check(
                "service-role upsert replaces object deterministically",
                code in (200, 201),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, downloaded, _ = client.request(
            "GET", client.public_path(OBJECT_PATH)
        )
        results.append(
            check(
                "public read returns replacement bytes",
                code == 200 and downloaded == replacement,
                {"status": code, "bytes": len(downloaded)},
            )
        )

        code, body, _ = client.request(
            "POST",
            client.object_path(MIME_OBJECT_PATH),
            bearer=client.service(),
            content=png,
            content_type="application/pdf",
            extra_headers={"x-upsert": "true"},
        )
        results.append(
            check(
                "unsupported MIME rejected by bucket configuration",
                code in (400, 415),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )
        client.request(
            "DELETE", client.object_path(MIME_OBJECT_PATH), bearer=client.service()
        )

        oversize = PNG_SIGNATURE + b"x" * (2 * 1024 * 1024)
        code, body, _ = client.request(
            "POST",
            client.object_path(OVERSIZE_OBJECT_PATH),
            bearer=client.service(),
            content=oversize,
            content_type="image/png",
            extra_headers={"x-upsert": "true"},
        )
        results.append(
            check(
                "oversized upload rejected by bucket limit",
                code in (400, 413),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )
        client.request(
            "DELETE",
            client.object_path(OVERSIZE_OBJECT_PATH),
            bearer=client.service(),
        )

        code, body, _ = client.request(
            "POST",
            f"/storage/v1/object/{PLANNED_PRIVATE_BUCKET}/{OBJECT_PATH}",
            bearer=client.service(),
            content=png,
            content_type="image/png",
        )
        results.append(
            check(
                "planned private clinical bucket is not installed",
                code in (400, 404),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, body, parsed = client.request(
            "DELETE",
            client.object_path(OBJECT_PATH),
            bearer=client.authenticated(),
        )
        results.append(
            check(
                "authenticated object delete denied",
                is_denied(code, parsed),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, body, _ = client.request(
            "DELETE",
            client.object_path(OBJECT_PATH),
            bearer=client.service(),
        )
        results.append(
            check(
                "service-role delete succeeds",
                code in (200, 204),
                {"status": code, "body": body[:400].decode(errors="replace")},
            )
        )

        code, _, _ = client.request("GET", client.public_path(OBJECT_PATH))
        results.append(
            check(
                "deleted public object is unavailable",
                code in (400, 404),
                {"status": code},
            )
        )

        code, body, _ = client.request(
            "POST",
            "/storage/v1/object/list/" + BUCKET,
            bearer=client.service(),
            json_payload={"prefix": OWNER_ID, "limit": 100, "offset": 0},
        )
        remaining = listed_names(body)
        results.append(
            check(
                "replacement and delete leave no orphan object under owner prefix",
                code == 200 and remaining == [],
                {"status": code, "entries": len(remaining)},
            )
        )
    finally:
        client.request(
            "DELETE", client.object_path(OBJECT_PATH), bearer=client.service()
        )
        client.request(
            "DELETE", client.object_path(MIME_OBJECT_PATH), bearer=client.service()
        )
        client.request(
            "DELETE",
            client.object_path(OVERSIZE_OBJECT_PATH),
            bearer=client.service(),
        )

    report = {
        "api_url": client.api_url,
        "bucket": BUCKET,
        "checks": len(results),
        "passed": sum(result["pass"] for result in results),
        "results": results,
    }
    output = json.dumps(report, indent=2)
    print(output)
    if args.output_json:
        args.output_json.write_text(output + "\n", encoding="utf-8")
    return 0 if report["passed"] == report["checks"] else 1


if __name__ == "__main__":
    sys.exit(main())

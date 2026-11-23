from __future__ import annotations

from main import app

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}

# Public endpoints are intentional. Every other operation must declare bearer
# authentication so generated clients do not silently omit credentials.
PUBLIC_OPERATIONS = {
    ("POST", "/auth/signup"),
    ("POST", "/auth/login"),
    ("POST", "/organizations/register"),
    ("POST", "/organizations/accept-invite"),
    ("GET", "/"),
    ("GET", "/health"),
}


def _operations(schema):
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method.lower() in HTTP_METHODS:
                yield method.upper(), path, operation


def test_every_non_public_operation_declares_bearer_security():
    schema = app.openapi()

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }

    missing = {
        (method, path)
        for method, path, operation in _operations(schema)
        if (method, path) not in PUBLIC_OPERATIONS and not operation.get("security")
    }
    assert missing == set()

    undocumented_public = {
        (method, path)
        for method, path, operation in _operations(schema)
        if (method, path) in PUBLIC_OPERATIONS and operation.get("security")
    }
    assert undocumented_public == set()


def test_disabled_legacy_event_routes_are_not_published_in_openapi():
    schema = app.openapi()

    assert not any(path.startswith("/events") for path in schema["paths"])

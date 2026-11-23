from __future__ import annotations

import importlib.util
from pathlib import Path

from app.core.events.service import EventService

REMOVED_MODULES = (
    "app.core.audit.query",
    "app.core.events.metrics",
    "app.core.events.monitoring",
    "app.modules.auth.admin_service",
)

REMOVED_SYMBOLS = (
    "get_resource_audit_log",
    "get_event_metrics",
    "get_onboarding_metrics",
    "delete_auth_user",
)


def test_dead_privileged_modules_are_absent():
    for name in REMOVED_MODULES:
        assert importlib.util.find_spec(name) is None, f"{name} is still importable"


def test_dead_event_retry_helper_is_absent():
    assert not hasattr(EventService, "retry_event")


def test_no_production_source_references_removed_helpers():
    app_root = Path(__file__).resolve().parents[2] / "app"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in app_root.rglob("*.py")
    )
    for symbol in REMOVED_SYMBOLS:
        assert symbol not in source, f"removed helper still referenced: {symbol}"

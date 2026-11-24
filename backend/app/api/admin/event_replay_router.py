"""Duplicate replay surface removed; use /admin/events/dead/{dead_event_id}/replay."""

from fastapi import APIRouter

router = APIRouter(prefix="/admin/events", tags=["Event Replay"])

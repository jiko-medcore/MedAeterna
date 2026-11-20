"""Compatibility wrappers for legacy observation-module access checks.

Canonical patient-access authorization lives in `app.core.security`.
"""

from app.core.security import (
    authorize_patient_access,
    get_current_user,
    require_patient_access_manual,
)

__all__ = [
    "authorize_patient_access",
    "get_current_user",
    "require_patient_access_manual",
]

"""SPEC-05 consent gate reference policy.

This module evaluates consent only. Authentication, role/action permission,
patient relationship, clinical workflow, and database controls remain separate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from app.core.role_catalogue import PRACTITIONER


CLINICAL_RESOURCES = frozenset(
    {
        "clinical_history",
        "encounter",
        "observation",
        "condition",
        "prescription",
        "lab_result",
        "clinical_document",
    }
)
CLINICAL_ACTIONS = frozenset({"read", "create", "update"})
CONSENT_TYPES = frozenset({"treatment", "telemedicine", "research", "data_sharing"})
ACCESS_ACTIONS = {
    "read": frozenset({"read"}),
    "write": frozenset({"create", "update"}),
    "full": frozenset({"read", "create", "update"}),
}


@dataclass(frozen=True)
class ConsentRequirement:
    """Trusted result of the server's policy decision for this use/purpose."""

    required: bool | None
    policy_id: str | None
    purpose: str | None
    allowed_consent_types: frozenset[str] = field(default_factory=frozenset)
    source_verified: bool = False


@dataclass(frozen=True)
class ConsentEvidence:
    """Normalized consent record returned by a trusted server-side resolver."""

    consent_id: str
    status: str
    patient_id: str
    organization_id: str
    practitioner_id: str | None
    recipient_kind: str
    consent_type: str
    access_level: str
    purpose_of_use: str
    resource_families: frozenset[str]
    granted_at: datetime | None
    expires_at: datetime | None
    effective_from: datetime | None = None
    revoked_at: datetime | None = None
    emergency_access: bool = False
    decision_authority_verified: bool = False
    source_verified: bool = False


@dataclass(frozen=True)
class ConsentDecision:
    decision: str
    reason: str
    consent_id: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


def _value(value: str | None) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _identifier(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _same_id(left: str | None, right: str | None) -> bool:
    return bool(_identifier(left)) and _identifier(left) == _identifier(right)


def _aware(value: datetime | None) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _covers_recipient(
    consent: ConsentEvidence,
    *,
    practitioner_id: str,
    organization_id: str,
) -> bool:
    if consent.recipient_kind == "practitioner":
        return _same_id(consent.practitioner_id, practitioner_id)
    if consent.recipient_kind == "organization":
        return consent.practitioner_id is None and _same_id(
            consent.organization_id, organization_id
        )
    return False


def evaluate_consent(
    *,
    actor_user_id: str | None,
    actor_category: str,
    actor_practitioner_id: str | None,
    linked_practitioner_user_id: str | None,
    patient_id: str | None,
    organization_id: str | None,
    resource_family: str,
    action: str,
    requirement: ConsentRequirement,
    evidence: Iterable[ConsentEvidence] = (),
    now: datetime,
) -> ConsentDecision:
    """Evaluate consent for a practitioner clinical use, failing closed.

    Consent never creates a patient relationship or grants a role/action. A
    trusted policy must first decide whether this use requires consent. Where
    multiple applicable records exist, the latest decision event controls; an
    equal-time ambiguity denies. Records are never combined to synthesize scope.
    """
    if actor_category != PRACTITIONER:
        return ConsentDecision("deny", "consent gate applies here only to practitioner clinical use")
    if not _same_id(actor_user_id, linked_practitioner_user_id):
        return ConsentDecision("deny", "practitioner identity is not linked to the authenticated actor")
    if not _value(actor_practitioner_id):
        return ConsentDecision("deny", "verified practitioner identity is required")
    if not _value(patient_id) or not _value(organization_id):
        return ConsentDecision("deny", "patient and organization context are required")
    if not _aware(now):
        return ConsentDecision("deny", "decision time must include a timezone")
    if (
        not isinstance(requirement, ConsentRequirement)
        or requirement.source_verified is not True
    ):
        return ConsentDecision("deny", "consent requirement must come from trusted policy")
    if type(requirement.required) is not bool:
        return ConsentDecision("deny", "consent requirement is unknown")
    if not _value(requirement.policy_id) or not _value(requirement.purpose):
        return ConsentDecision("deny", "consent policy and purpose are required")

    resource = _value(resource_family)
    operation = _value(action)
    if resource not in CLINICAL_RESOURCES or operation not in CLINICAL_ACTIONS:
        return ConsentDecision("deny", "resource or action is outside the consent policy scope")

    if not requirement.required:
        return ConsentDecision("allow", "trusted policy confirms consent is not required")
    if not isinstance(requirement.allowed_consent_types, (set, frozenset, tuple, list)):
        return ConsentDecision("deny", "policy has no valid permitted consent type")
    permitted_consent_types = frozenset(
        _value(item) for item in requirement.allowed_consent_types
    )
    if (
        not permitted_consent_types
        or "" in permitted_consent_types
        or not permitted_consent_types.issubset(CONSENT_TYPES)
    ):
        return ConsentDecision("deny", "policy has no valid permitted consent type")

    try:
        consent_rows = tuple(evidence)
    except TypeError:
        return ConsentDecision("deny", "consent evidence is invalid")

    matching: list[tuple[datetime, ConsentEvidence]] = []
    for consent in consent_rows:
        if (
            not isinstance(consent, ConsentEvidence)
            or consent.source_verified is not True
        ):
            continue
        if _value(consent.status) == "draft":
            continue
        if consent.emergency_access is not False or _value(consent.consent_type) == "emergency":
            continue
        if _value(consent.consent_type) not in permitted_consent_types:
            continue
        if not _same_id(consent.patient_id, patient_id):
            continue
        if not _same_id(consent.organization_id, organization_id):
            continue
        if not _covers_recipient(
            consent,
            practitioner_id=actor_practitioner_id,
            organization_id=organization_id,
        ):
            continue
        if _value(consent.purpose_of_use) != _value(requirement.purpose):
            continue
        if not isinstance(consent.resource_families, (set, frozenset, tuple, list)):
            continue
        if resource not in {_value(item) for item in consent.resource_families}:
            continue
        if not _value(consent.consent_id):
            return ConsentDecision("deny", "applicable consent has no stable identifier")
        if not _aware(consent.granted_at):
            return ConsentDecision("deny", "applicable consent has no valid grant timestamp")
        if consent.revoked_at is not None and not _aware(consent.revoked_at):
            return ConsentDecision("deny", "applicable consent has an invalid revocation timestamp")
        changed_at = max(
            consent.granted_at,
            consent.revoked_at or consent.granted_at,
        )
        matching.append((changed_at, consent))

    if not matching:
        return ConsentDecision("deny", "no consent record covers this patient, recipient, purpose, resource, and organization")

    latest_time = max(item[0] for item in matching)
    latest = [consent for changed_at, consent in matching if changed_at == latest_time]
    if len(latest) != 1:
        return ConsentDecision("deny", "multiple applicable consent records have ambiguous precedence")
    consent = latest[0]

    if consent.decision_authority_verified is not True:
        return ConsentDecision("deny", "latest applicable consent decision authority is unverified", consent.consent_id)
    if _value(consent.status) != "active" or consent.revoked_at is not None:
        return ConsentDecision("deny", "latest applicable consent is not active", consent.consent_id)
    if _value(consent.consent_type) not in CONSENT_TYPES:
        return ConsentDecision("deny", "consent type is not permitted", consent.consent_id)
    if not _aware(consent.granted_at) or consent.granted_at > now:
        return ConsentDecision("deny", "consent has not been granted as of the decision time", consent.consent_id)
    if consent.expires_at is None or not _aware(consent.expires_at):
        return ConsentDecision("deny", "consent must have a valid finite expiry", consent.consent_id)
    effective_from = consent.effective_from or consent.granted_at
    if not _aware(effective_from):
        return ConsentDecision("deny", "consent effective time is invalid", consent.consent_id)
    if effective_from > now:
        return ConsentDecision("deny", "consent is not effective yet", consent.consent_id)
    if consent.expires_at <= effective_from or now >= consent.expires_at:
        return ConsentDecision("deny", "consent has expired or has an invalid period", consent.consent_id)

    permitted_actions = ACCESS_ACTIONS.get(_value(consent.access_level))
    if permitted_actions is None or operation not in permitted_actions:
        return ConsentDecision("deny", "consent access level does not cover this action", consent.consent_id)

    return ConsentDecision("allow", "latest applicable consent covers the requested use", consent.consent_id)

from __future__ import annotations

import logging

from app.modules.patients import onboarding

PATIENT_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
EMAIL = "synthetic.patient@example.test"
MEDICAL_ID = "MC-123456"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, fake):
        self.fake = fake

    def select(self, _columns):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, _column, _value):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if not hasattr(self, "payload"):
            return FakeResult({
                "id": PATIENT_ID,
                "email": EMAIL,
                "medical_id": MEDICAL_ID,
                "first_name": "Synthetic",
                "onboarding_email_sent": False,
                "onboarding_completed": False,
                "onboarding_retry_count": 0,
            })
        return FakeResult([{}])


class FakeSupabaseAdmin:
    def table(self, _name):
        return FakeQuery(self)


def test_onboarding_logs_exclude_patient_identifiers(monkeypatch, caplog):
    monkeypatch.setattr(onboarding, "supabase_admin", FakeSupabaseAdmin())
    monkeypatch.setattr(onboarding, "log_audit_event", lambda **_: None)
    monkeypatch.setattr(onboarding, "render_template", lambda *_: "<html></html>")
    monkeypatch.setattr(onboarding, "send_email", lambda _: {"status": "sent"})

    with caplog.at_level(logging.INFO):
        onboarding.send_onboarding_email(PATIENT_ID)

    text = caplog.text
    assert PATIENT_ID not in text
    assert EMAIL not in text
    assert MEDICAL_ID not in text
    assert "PATIENT QUERY RESULT" not in text
    assert "ONBOARDING CALL STACK" not in text

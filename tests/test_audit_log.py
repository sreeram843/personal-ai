"""Tests for structured audit logging."""

from __future__ import annotations

import json
import logging

from app.services.audit_log import record_audit


def test_record_audit_emits_json(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="personal_ai.audit"):
        record_audit("auth.sign_in", user_id="u-1", detail={"method": "google"})
    matching = [rec for rec in caplog.records if rec.name == "personal_ai.audit"]
    assert matching
    payload = json.loads(matching[-1].getMessage())
    assert payload["audit_event"] == "auth.sign_in"
    assert payload["user_id"] == "u-1"
    assert payload["detail"]["method"] == "google"


def test_logout_emits_sign_out_audit(client, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="personal_ai.audit"):
        response = client.post("/auth/logout")
    assert response.status_code == 204
    matching = [rec for rec in caplog.records if rec.name == "personal_ai.audit"]
    assert matching
    payload = json.loads(matching[-1].getMessage())
    assert payload["audit_event"] == "auth.sign_out"
    assert payload["user_id"]

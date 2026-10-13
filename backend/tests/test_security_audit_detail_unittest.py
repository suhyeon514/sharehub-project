"""Existing pytest audit checks, independently runnable with unittest.

Uses a capture handler and manually supplied authorization states, just like
its pytest counterpart; this does not verify default logging configuration or
real database authorization flows. No pytest dependency is required.
"""
import json
import logging
import unittest
import uuid
from datetime import datetime
from unittest.mock import patch

from flask import g

from app import create_app
from app.services import security_audit as audit


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


class SecurityAuditDetailEquivalentTests(unittest.TestCase):
    def test_detail_audit_isolated(self):
        app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        logger = logging.getLogger("sharehub.security_audit")
        oldlevel = logger.level
        handler = Capture()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            # Route decorator was bound at registration: stub session/auth DB lookups.
            # Missing token is exercised against the real decorator.
            client = app.test_client()
            res = client.get("/api/documents/123")
            self.assertTrue(res.status_code == 401)
            self.assertTrue(res.json == {"message": "인증이 필요합니다."})
            self.assertTrue(len(handler.records) == 1)
            event = json.loads(handler.records.pop())
            self.assertTrue(event["event_type"] == "authentication")
            self.assertTrue(event["authorization"]["decision"] == "not_evaluated")
            self.assertTrue(event["authorization"]["reason_code"] == "AUTHENTICATION_REQUIRED")
            self.assertTrue(event["request_id"] == res.headers["X-Request-ID"])
            self.assertTrue(uuid.UUID(event["request_id"]).version == 4)
            self.assertTrue(datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")))
            self.assertTrue(event["result"] == {"outcome": "failure", "http_status": 401})
            self.assertTrue(set(event) == {"schema_version", "timestamp", "request_id", "event_type", "actor", "resource", "action", "authorization", "result"})
            self.assertTrue(len(event["authorization"]) == 6)
            self.assertTrue(event["resource"] == {"type": "document", "id": 123})
            self.assertTrue(event["actor"] == {"user_id": None})
            self.assertTrue(event["action"] == "view")
            self.assertTrue(event["authorization"]["required_permission"] == "view")
            self.assertTrue(event["authorization"]["access_source"] is None)
            self.assertTrue(event["authorization"]["effective_permission"] is None)
            self.assertTrue(event["authorization"]["evaluated"] is False)
            self.assertTrue(event["schema_version"] == 1)

            # Other document API remains outside the audit scope.
            client.get("/api/documents/123/download")
            self.assertTrue(handler.records == [])

            # Test complete evaluated states and single-emission guard in request context.
            scenarios = [
                ({"allowed": False, "source": None, "permission": None}, "NO_DOCUMENT_ACCESS", "deny", 404),
                ({"allowed": True, "source": "owner", "permission": "edit"}, "DOCUMENT_OWNER_ACCESS", "allow", 200),
                ({"allowed": True, "source": "team", "permission": "view"}, "TEAM_DEPARTMENT_VIEW", "allow", 200),
                ({"allowed": True, "source": "share", "permission": "download"}, "DIRECT_SHARE_DOWNLOAD", "allow", 200),
                ({"allowed": True, "source": "share", "permission": "view"}, "DOCUMENT_ACCESS_BLOCKED", "deny", 403),
            ]
            for access, reason, decision, status in scenarios:
                with app.test_request_context("/api/documents/123"):
                    g.request_id = str(uuid.uuid4())
                    audit.initialize_detail(123)
                    audit.authenticated(7)
                    audit.evaluated(access, reason, decision)
                    response = app.response_class(status=status)
                    audit.emit_detail(response)
                    audit.emit_detail(response)
                    self.assertTrue(len(handler.records) == 1)
                    obj = json.loads(handler.records.pop())
                    self.assertTrue(obj["authorization"]["reason_code"] == reason)
                    self.assertTrue(obj["authorization"]["decision"] == decision)
                    self.assertTrue(obj["authorization"]["access_source"] == access["source"])
                    self.assertTrue(obj["authorization"]["effective_permission"] == access["permission"])
                    self.assertTrue(obj["result"]["http_status"] == status)
                    self.assertTrue(obj["request_id"] == g.request_id)

            # Emission failure is non-fatal and is not retried in the same request.
            with app.test_request_context("/api/documents/123"):
                g.request_id = str(uuid.uuid4())
                audit.initialize_detail(123)
                audit.authenticated(7)
                audit.evaluated({"source": "owner", "permission": "edit"}, "DOCUMENT_OWNER_ACCESS", "allow")
                with patch.object(audit.AUDIT_LOGGER, "info", side_effect=OSError("sink unavailable")):
                    audit.emit_detail(app.response_class(status=200))
                    audit.emit_detail(app.response_class(status=200))
                self.assertTrue(g.security_detail["emitted"] is True)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(oldlevel)


if __name__ == "__main__":
    unittest.main()

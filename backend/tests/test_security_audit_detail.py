import json
import logging
import re
import uuid
from datetime import datetime
from unittest.mock import patch

from app import create_app
from app.services.security_audit import emit_detail


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
    def emit(self, record):
        self.records.append(record.getMessage())


def test_detail_audit_isolated(monkeypatch):
    # DB-free route harness: preserves the original view's response decisions.
    from app.routes import documents as routes
    from app.routes import auth
    from app.services import security_audit as audit
    from flask import g, jsonify

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
        assert res.status_code == 401
        assert res.json == {"message": "인증이 필요합니다."}
        assert len(handler.records) == 1
        event = json.loads(handler.records.pop())
        assert event["event_type"] == "authentication"
        assert event["authorization"]["decision"] == "not_evaluated"
        assert event["authorization"]["reason_code"] == "AUTHENTICATION_REQUIRED"
        assert event["request_id"] == res.headers["X-Request-ID"]
        assert uuid.UUID(event["request_id"]).version == 4
        assert datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        assert event["result"] == {"outcome": "failure", "http_status": 401}
        assert set(event) == {"schema_version", "timestamp", "request_id", "event_type", "actor", "resource", "action", "authorization", "result"}
        assert len(event["authorization"]) == 6
        assert event["resource"] == {"type": "document", "id": 123}
        assert event["actor"] == {"user_id": None}
        assert event["action"] == "view"
        assert event["authorization"]["required_permission"] == "view"
        assert event["authorization"]["access_source"] is None
        assert event["authorization"]["effective_permission"] is None
        assert event["authorization"]["evaluated"] is False
        assert event["schema_version"] == 1

        # Other document API remains outside the audit scope.
        client.get("/api/documents/123/download")
        assert handler.records == []

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
                assert len(handler.records) == 1
                obj = json.loads(handler.records.pop())
                assert obj["authorization"]["reason_code"] == reason
                assert obj["authorization"]["decision"] == decision
                assert obj["authorization"]["access_source"] == access["source"]
                assert obj["authorization"]["effective_permission"] == access["permission"]
                assert obj["result"]["http_status"] == status
                assert obj["request_id"] == g.request_id

        # Emission failure is non-fatal and is not retried in the same request.
        with app.test_request_context("/api/documents/123"):
            g.request_id = str(uuid.uuid4())
            audit.initialize_detail(123)
            audit.authenticated(7)
            audit.evaluated({"source": "owner", "permission": "edit"}, "DOCUMENT_OWNER_ACCESS", "allow")
            with patch.object(audit.AUDIT_LOGGER, "info", side_effect=OSError("sink unavailable")):
                audit.emit_detail(app.response_class(status=200))
                audit.emit_detail(app.response_class(status=200))
            assert g.security_detail["emitted"] is True
    finally:
        logger.removeHandler(handler)
        logger.setLevel(oldlevel)

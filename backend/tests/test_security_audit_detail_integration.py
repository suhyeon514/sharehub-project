"""Owner-detail integration checks using isolated SQLite and fresh processes.

Run from backend with unittest discover. Tests never enable audit INFO.
Capture checks do not prove default stream output; a separate check does.
This first-stage file does not verify the full authorization matrix.
"""
import json
from contextlib import ExitStack
import logging
from pathlib import Path
import secrets
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid
from datetime import datetime, timedelta, timezone


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def probe(mode):
    from app import create_app
    from app.extensions import db
    from app.models import Document, Session, User

    app = create_app({"TESTING": True, "DEBUG": False, "PROPAGATE_EXCEPTIONS": False,
                      "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    audit = logging.getLogger("sharehub.security_audit")
    capture, http, errors = Capture(), Capture(), Capture()
    error_logger = logging.getLogger("sharehub.security_audit.error")
    error_logger.addHandler(errors)
    if mode != "stream":
        audit.addHandler(capture)
    app.logger.addHandler(http)
    token = secrets.token_urlsafe(32)
    try:
        with app.app_context():
            db.create_all()
            owner = User(username="audit-owner", password_hash="unused-fixture")
            db.session.add(owner)
            db.session.flush()
            document = Document(title="title-marker", description="description-marker",
                                owner_id=owner.id, visibility="private",
                                file_path="unused-path-marker", original_filename="filename-marker")
            db.session.add(document)
            db.session.add(Session(user_id=owner.id, session_token=token, is_active=True,
                                   expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
            db.session.commit()
            document_id, owner_id = document.id, owner.id
        external_id = str(uuid.uuid4())
        with ExitStack() as stack:
            injected = None
            if mode == "document_lookup_failure":
                original_get = db.session.get

                def fail_document_only(model, *args, **kwargs):
                    if model is Document:
                        from sqlalchemy.exc import SQLAlchemyError
                        raise SQLAlchemyError("isolated document lookup failure")
                    return original_get(model, *args, **kwargs)

                injected = stack.enter_context(patch.object(db.session, "get", side_effect=fail_document_only))
            elif mode == "authorization_failure":
                injected = stack.enter_context(patch("app.routes.documents.get_document_access",
                    side_effect=RuntimeError("isolated authorization failure")))
            elif mode == "serialization_failure":
                injected = stack.enter_context(patch("app.routes.documents.serialize_document_detail",
                    side_effect=RuntimeError("isolated response serialization failure")))
            elif mode == "audit_output_failure":
                injected = stack.enter_context(patch.object(audit, "info",
                    side_effect=OSError("isolated audit output failure")))
            elif mode == "audit_construction_failure":
                clock = stack.enter_context(patch("app.services.security_audit.datetime"))
                clock.now.side_effect = RuntimeError("isolated audit construction failure")
                injected = clock.now
            response = app.test_client().get(f"/api/documents/{document_id}", headers={
                "Authorization": f"Bearer {token}", "X-Request-ID": external_id,
            })
            injection_calls = injected.call_count if injected is not None else 0
        return {"status": response.status_code, "request_id": response.headers.get("X-Request-ID"),
                "external_id": external_id, "owner_id": owner_id, "document_id": document_id,
                "audit": capture.messages, "http": http.messages, "errors": errors.messages,
                "injection_calls": injection_calls,
                "response_has_document": response.is_json and "data" in response.json,
                "secret_leaked": any(token in message for message in capture.messages + errors.messages)}
    finally:
        if mode != "stream":
            audit.removeHandler(capture)
        error_logger.removeHandler(errors)
        app.logger.removeHandler(http)
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


class SecurityAuditDetailIntegrationTests(unittest.TestCase):
    def run_probe(self, mode):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe", mode],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, "Isolated request probe failed")
        return json.loads(result.stdout.splitlines()[-1]), result

    def check_event(self, data, messages):
        self.assertEqual(data["status"], 200)
        self.assertEqual(len(messages), 1, "Expected one audit JSON; check default INFO/output configuration")
        event = json.loads(messages[0])
        self.assertEqual(set(event), {"schema_version", "timestamp", "request_id", "event_type",
                                     "actor", "resource", "action", "authorization", "result"})
        self.assertEqual(type(event["schema_version"]), int)
        self.assertEqual(event["schema_version"], 1)
        self.assertTrue(event["timestamp"].endswith("Z"))
        self.assertEqual(datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).utcoffset(), timedelta(0))
        self.assertEqual(uuid.UUID(event["request_id"]).version, 4)
        self.assertEqual(event["request_id"], data["request_id"])
        self.assertNotEqual(event["request_id"], data["external_id"])
        self.assertEqual(event["event_type"], "document.authorization")
        self.assertEqual(event["actor"], {"user_id": data["owner_id"]})
        self.assertEqual(type(event["actor"]["user_id"]), int)
        self.assertEqual(event["resource"], {"type": "document", "id": data["document_id"]})
        self.assertEqual(type(event["resource"]["id"]), int)
        self.assertEqual(event["action"], "view")
        self.assertEqual(event["authorization"], {
            "evaluated": True, "required_permission": "view", "access_source": "owner",
            "effective_permission": "edit", "decision": "allow", "reason_code": "DOCUMENT_OWNER_ACCESS",
        })
        self.assertIs(event["authorization"]["evaluated"], True)
        self.assertEqual(event["result"], {"outcome": "success", "http_status": 200})
        self.assertEqual(type(event["result"]["http_status"]), int)
        self.assertFalse(data["secret_leaked"])
        for marker in ("title-marker", "description-marker", "unused-path-marker", "filename-marker"):
            self.assertNotIn(marker, messages[0])
        http = [line for line in data["http"] if line.startswith("http_request ")]
        self.assertEqual(len(http), 1)
        self.assertIn(f"request_id={event['request_id']}", http[0])
        self.assertIn("status=200", http[0])

    def check_failure_tracking(self, data, status):
        self.assertGreater(data["injection_calls"], 0)
        self.assertEqual(data["status"], status)
        self.assertEqual(uuid.UUID(data["request_id"]).version, 4)
        self.assertNotEqual(data["request_id"], data["external_id"])
        self.assertFalse(data["secret_leaked"])
        http = [line for line in data["http"] if line.startswith("http_request ")]
        self.assertEqual(len(http), 1)
        self.assertIn(f"request_id={data['request_id']}", http[0])
        self.assertIn(f"status={status}", http[0])

    def check_incomplete(self, mode):
        data, process = self.run_probe(mode)
        self.check_failure_tracking(data, 500)
        self.assertEqual(data["audit"], [])
        self.assertEqual(self.standard_stream_events(process), [])
        self.assertEqual(len(data["errors"]), 1)
        self.assertIn("audit_incomplete", data["errors"][0])
        self.assertIn(f"request_id={data['request_id']}", data["errors"][0])
        self.assertNotIn("DOCUMENT_NOT_FOUND", data["errors"][0])

    def test_document_lookup_exception_is_incomplete(self):
        self.check_incomplete("document_lookup_failure")

    def test_authorization_exception_is_incomplete(self):
        self.check_incomplete("authorization_failure")

    def test_response_failure_preserves_completed_allow_decision(self):
        data, _ = self.run_probe("serialization_failure")
        self.check_failure_tracking(data, 500)
        self.assertEqual(len(data["audit"]), 1)
        event = json.loads(data["audit"][0])
        self.assertEqual(event["authorization"]["decision"], "allow")
        self.assertEqual(event["authorization"]["reason_code"], "DOCUMENT_OWNER_ACCESS")
        self.assertEqual(event["result"], {"outcome": "failure", "http_status": 500})
        self.assertEqual(event["request_id"], data["request_id"])
        self.assertEqual(data["errors"], [])

    def check_audit_failure_preserves_response(self, mode):
        data, process = self.run_probe(mode)
        self.check_failure_tracking(data, 200)
        self.assertTrue(data["response_has_document"])
        self.assertEqual(data["audit"], [])
        self.assertEqual(self.standard_stream_events(process), [])
        self.assertEqual(len(data["errors"]), 1)
        self.assertIn(f"request_id={data['request_id']}", data["errors"][0])
        self.assertNotIn("audit_incomplete", data["errors"][0])

    def test_audit_output_exception_preserves_success_response(self):
        self.check_audit_failure_preserves_response("audit_output_failure")

    def test_audit_construction_exception_preserves_success_response(self):
        self.check_audit_failure_preserves_response("audit_construction_failure")

    def test_owner_detail_contract_without_enabling_info(self):
        data, _ = self.run_probe("capture")
        self.check_event(data, data["audit"])

    def standard_stream_events(self, process):
        messages = []
        for line in (process.stdout + "\n" + process.stderr).splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict) and "schema_version" in value:
                messages.append(line)
        return messages

    def test_owner_detail_output_on_default_standard_stream(self):
        data, process = self.run_probe("stream")
        self.assertEqual(data["status"], 200)
        self.assertEqual(len(self.standard_stream_events(process)), 1,
                         "Default standard stream must contain one audit JSON line")

    def test_owner_detail_contract_on_default_standard_stream(self):
        data, process = self.run_probe("stream")
        self.check_event(data, self.standard_stream_events(process))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        print(json.dumps(probe(sys.argv[2])))
    else:
        unittest.main()

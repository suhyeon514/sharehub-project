"""Owner-detail integration checks using isolated SQLite and fresh processes.

Run from backend with unittest discover. Tests never enable audit INFO.
Capture checks do not prove default stream output; a separate check does.
This first-stage file does not verify the full authorization matrix.
"""
import json
import logging
from pathlib import Path
import secrets
import subprocess
import sys
import unittest
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

    app = create_app({"TESTING": True, "DEBUG": False,
                      "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    audit = logging.getLogger("sharehub.security_audit")
    capture, http = Capture(), Capture()
    if mode == "capture":
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
        response = app.test_client().get(f"/api/documents/{document_id}", headers={
            "Authorization": f"Bearer {token}", "X-Request-ID": external_id,
        })
        return {"status": response.status_code, "request_id": response.headers.get("X-Request-ID"),
                "external_id": external_id, "owner_id": owner_id, "document_id": document_id,
                "audit": capture.messages, "http": http.messages,
                "secret_leaked": any(token in message for message in capture.messages)}
    finally:
        if mode == "capture":
            audit.removeHandler(capture)
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

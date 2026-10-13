"""Owner-detail integration checks using isolated SQLite and fresh processes.

Run from backend with unittest discover. Tests never enable audit INFO.
Capture checks do not prove default stream output; a separate check does.
Covers detail authentication/access/block cases and exception safety.
Does not establish other APIs or MariaDB/browser/network behavior.
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



# Expected values come from the finalized contract, independently of app enums.
MATRIX = {
    "auth_none": {"auth": "none", "status": 401, "reason": "AUTHENTICATION_REQUIRED"},
    "auth_invalid": {"auth": "invalid", "status": 401, "reason": "AUTHENTICATION_REQUIRED"},
    "auth_expired": {"auth": "expired", "status": 401, "reason": "AUTHENTICATION_REQUIRED"},
    "id_zero_unauthenticated": {"auth": "none", "id_zero": True, "status": 401, "reason": "AUTHENTICATION_REQUIRED"},
    "id_zero_authenticated": {"id_zero": True, "status": 404, "reason": "DOCUMENT_NOT_FOUND"},
    "missing_document": {"missing": True, "status": 404, "reason": "DOCUMENT_NOT_FOUND"},
    "no_access": {"status": 404, "reason": "NO_DOCUMENT_ACCESS"},
    "owner": {"actor": "owner", "source": "owner", "permission": "edit", "reason": "DOCUMENT_OWNER_ACCESS"},
    "team": {"visibility": "team", "same_team": True, "source": "team", "permission": "view", "reason": "TEAM_DEPARTMENT_VIEW"},
    "private_same_team": {"same_team": True, "status": 404, "reason": "NO_DOCUMENT_ACCESS"},
    "team_other_department": {"visibility": "team", "status": 404, "reason": "NO_DOCUMENT_ACCESS"},
    "team_actor_null": {"visibility": "team", "actor_dept": False, "status": 404, "reason": "NO_DOCUMENT_ACCESS"},
    "team_document_null": {"visibility": "team", "doc_dept": False, "status": 404, "reason": "NO_DOCUMENT_ACCESS"},
    "team_both_null": {"visibility": "team", "doc_dept": False, "actor_dept": False, "status": 404, "reason": "NO_DOCUMENT_ACCESS"},
    "admin_private": {"role": "admin", "status": 404, "reason": "NO_DOCUMENT_ACCESS"},
    "blocked_owner": {"actor": "owner", "blocked": True, "source": "owner", "permission": "edit", "status": 403, "reason": "DOCUMENT_ACCESS_BLOCKED"},
    "blocked_team": {"visibility": "team", "same_team": True, "blocked": True, "source": "team", "permission": "view", "status": 403, "reason": "DOCUMENT_ACCESS_BLOCKED"},
    "blocked_unrelated": {"blocked": True, "status": 404, "reason": "NO_DOCUMENT_ACCESS"},
    "blocked_admin_private": {"blocked": True, "role": "admin", "status": 404, "reason": "NO_DOCUMENT_ACCESS"},
}
for _permission in ("view", "download", "edit"):
    _code = "DIRECT_SHARE_" + _permission.upper()
    MATRIX["share_" + _permission] = {"share": _permission, "source": "share", "permission": _permission, "reason": _code}
    MATRIX["team_share_" + _permission] = {
        "visibility": "team", "same_team": True, "share": _permission,
        "source": "team" if _permission == "view" else "share", "permission": _permission,
        "reason": "TEAM_DEPARTMENT_VIEW" if _permission == "view" else _code,
    }
    MATRIX["blocked_share_" + _permission] = {
        "share": _permission, "blocked": True, "source": "share", "permission": _permission,
        "status": 403, "reason": "DOCUMENT_ACCESS_BLOCKED",
    }

class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def probe(mode):
    from app import create_app
    from app.extensions import db
    from app.models import Department, Document, DocumentBlock, DocumentShare, Session, User

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
    spec = MATRIX.get(mode)
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
            actor = owner
            if spec is not None:
                department = Department(name="audit-team")
                other = Department(name="audit-other")
                db.session.add_all([department, other])
                db.session.flush()
                document.department_id = department.id if spec.get("doc_dept", True) else None
                document.visibility = spec.get("visibility", "private")
                if spec.get("actor", "other") != "owner":
                    actor = User(username="audit-requester", password_hash="unused-fixture",
                                 role=spec.get("role", "user"),
                                 department_id=(department.id if spec.get("same_team") else other.id)
                                 if spec.get("actor_dept", True) else None)
                    db.session.add(actor)
                    db.session.flush()
                if spec.get("share"):
                    db.session.add(DocumentShare(document_id=document.id, shared_by_id=owner.id,
                                                 shared_with_id=actor.id, permission=spec["share"]))
                if spec.get("blocked"):
                    db.session.add(DocumentBlock(document_id=document.id, document_id_snapshot=document.id,
                        blocked_by_id=owner.id, block_reason="block-reason-marker", block_basis="block-basis-marker"))
                session = Session.query.filter_by(session_token=token).one()
                session.user_id = actor.id
                if spec.get("auth") == "expired":
                    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.session.commit()
            document_id, owner_id, actor_id = document.id, owner.id, actor.id
            if spec and spec.get("missing"):
                document_id += 1000
            if spec and spec.get("id_zero"):
                document_id = 0
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
            elif mode == "audit_validation_failure":
                from app.services.security_audit_contract import AuditContractError
                injected = stack.enter_context(patch("app.services.security_audit.validate_event",
                    side_effect=AuditContractError("isolated contract validation failure")))
            elif mode == "audit_construction_failure":
                clock = stack.enter_context(patch("app.services.security_audit.datetime"))
                clock.now.side_effect = RuntimeError("isolated audit construction failure")
                injected = clock.now
            headers = {"Authorization": f"Bearer {token}", "X-Request-ID": external_id}
            if spec and spec.get("auth") == "none":
                headers.pop("Authorization")
            elif spec and spec.get("auth") == "invalid":
                headers["Authorization"] = "Bearer invalid-isolated-session"
            response = app.test_client().get(f"/api/documents/{document_id}", headers=headers)
            injection_calls = injected.call_count if injected is not None else 0
        return {"status": response.status_code, "request_id": response.headers.get("X-Request-ID"),
                "external_id": external_id, "owner_id": owner_id, "actor_id": actor_id, "document_id": document_id,
                "response_json": response.json if response.is_json else None,
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

    def check_matrix_case(self, name):
        spec = MATRIX[name]
        data, process = self.run_probe(name)
        status = spec.get("status", 200)
        self.assertEqual(data["status"], status)
        self.assertEqual(len(data["audit"]), 1)
        self.assertEqual(len(self.standard_stream_events(process)), 1)
        self.assertEqual(data["errors"], [])
        event = json.loads(data["audit"][0])
        auth_failed = spec.get("auth") is not None
        missing = spec.get("missing", False) or spec.get("id_zero", False)
        evaluated = not (auth_failed or missing)
        self.assertEqual(set(event), {"schema_version", "timestamp", "request_id", "event_type", "actor", "resource", "action", "authorization", "result"})
        self.assertEqual(type(event["schema_version"]), int)
        self.assertEqual(event["schema_version"], 1)
        self.assertEqual(event["event_type"], "authentication" if auth_failed else "document.lookup" if missing else "document.authorization")
        self.assertEqual(event["actor"], {"user_id": None if auth_failed else data["actor_id"]})
        if not auth_failed:
            self.assertEqual(type(event["actor"]["user_id"]), int)
        self.assertEqual(event["resource"], {"type": "document", "id": data["document_id"]})
        self.assertEqual(type(event["resource"]["id"]), int)
        self.assertEqual(event["action"], "view")
        self.assertEqual(event["authorization"], {
            "evaluated": evaluated, "required_permission": "view", "access_source": spec.get("source"),
            "effective_permission": spec.get("permission"),
            "decision": "not_evaluated" if not evaluated else "allow" if status == 200 else "deny",
            "reason_code": spec["reason"],
        })
        self.assertIs(event["authorization"]["evaluated"], evaluated)
        self.assertEqual(event["result"], {"outcome": "success" if status == 200 else "failure", "http_status": status})
        self.assertEqual(type(event["result"]["http_status"]), int)
        self.assertEqual(uuid.UUID(event["request_id"]).version, 4)
        self.assertEqual(event["request_id"], data["request_id"])
        self.assertNotEqual(event["request_id"], data["external_id"])
        self.assertTrue(event["timestamp"].endswith("Z"))
        self.assertEqual(datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).utcoffset(), timedelta(0))
        http = [line for line in data["http"] if line.startswith("http_request ")]
        self.assertEqual(len(http), 1)
        self.assertIn(f"request_id={data['request_id']}", http[0])
        self.assertIn(f"status={status}", http[0])
        self.assertFalse(data["secret_leaked"])
        for marker in ("title-marker", "description-marker", "unused-path-marker", "filename-marker", "block-basis-marker"):
            self.assertNotIn(marker, data["audit"][0])
        if status == 404:
            self.assertEqual(data["response_json"]["error"]["code"], "DOCUMENT_NOT_FOUND")
        elif status == 403:
            self.assertEqual(data["response_json"]["error"]["code"], "DOCUMENT_BLOCKED")
        if status != 200:
            self.assertNotIn("block-basis-marker", json.dumps(data["response_json"]))

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

    def test_audit_validation_exception_preserves_success_response(self):
        self.check_audit_failure_preserves_response("audit_validation_failure")

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


def _matrix_test(name):
    def test(self):
        self.check_matrix_case(name)
    return test


for _name in MATRIX:
    setattr(SecurityAuditDetailIntegrationTests, "test_matrix_" + _name, _matrix_test(_name))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        print(json.dumps(probe(sys.argv[2])))
    else:
        unittest.main()

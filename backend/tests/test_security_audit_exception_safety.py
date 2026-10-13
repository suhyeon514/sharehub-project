"""Security audit exception-safety regression tests."""
import json
import logging
import unittest
from unittest.mock import patch

from flask import g

from app import create_app
from app.services import security_audit as audit


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class SecurityAuditExceptionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.audit_capture = Capture()
        self.error_capture = Capture()
        audit.AUDIT_LOGGER.addHandler(self.audit_capture)
        audit.ERROR_LOGGER.addHandler(self.error_capture)

    def tearDown(self):
        audit.AUDIT_LOGGER.removeHandler(self.audit_capture)
        audit.ERROR_LOGGER.removeHandler(self.error_capture)

    def prepare_detail(self, evaluated=True):
        g.request_id = "550e8400-e29b-41d4-a716-446655440000"
        audit.initialize_detail(123)
        audit.authenticated(7)
        if evaluated:
            audit.evaluated(
                {"source": "owner", "permission": "edit"},
                "DOCUMENT_OWNER_ACCESS",
                "allow",
            )

    def test_unevaluated_exception_logs_incomplete(self):
        with self.app.test_request_context("/api/documents/123"):
            self.prepare_detail(evaluated=False)
            response = self.app.response_class(status=500)

            audit.emit_detail(response)

            self.assertEqual(len(self.audit_capture.messages), 0)
            self.assertEqual(len(self.error_capture.messages), 1)
            self.assertIn(
                "audit_incomplete",
                self.error_capture.messages[0],
            )
            self.assertEqual(response.status_code, 500)

    def test_allow_then_http_500_preserves_authorization(self):
        with self.app.test_request_context("/api/documents/123"):
            self.prepare_detail()
            response = self.app.response_class(status=500)

            audit.emit_detail(response)

            self.assertEqual(len(self.audit_capture.messages), 1)
            event = json.loads(self.audit_capture.messages[0])

            self.assertEqual(
                event["authorization"]["decision"], "allow"
            )
            self.assertEqual(
                event["authorization"]["reason_code"],
                "DOCUMENT_OWNER_ACCESS",
            )
            self.assertEqual(
                event["result"],
                {"outcome": "failure", "http_status": 500},
            )

    def test_event_construction_failure_is_nonfatal(self):
        with self.app.test_request_context("/api/documents/123"):
            self.prepare_detail()
            response = self.app.response_class(status=200)

            with patch.object(
                audit,
                "datetime",
                side_effect=RuntimeError("timestamp unavailable"),
            ):
                audit.emit_detail(response)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(self.audit_capture.messages), 0)
            self.assertEqual(len(self.error_capture.messages), 1)
            self.assertIn(
                "audit_emit_failed",
                self.error_capture.messages[0],
            )

    def test_json_serialization_failure_is_nonfatal(self):
        with self.app.test_request_context("/api/documents/123"):
            self.prepare_detail()
            response = self.app.response_class(status=200)

            with patch.object(
                audit.json,
                "dumps",
                side_effect=TypeError("serialization failed"),
            ):
                audit.emit_detail(response)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(self.audit_capture.messages), 0)
            self.assertEqual(len(self.error_capture.messages), 1)
            self.assertIn(
                "audit_emit_failed",
                self.error_capture.messages[0],
            )

    def test_logger_failure_does_not_retry(self):
        with self.app.test_request_context("/api/documents/123"):
            self.prepare_detail()
            response = self.app.response_class(status=200)

            with patch.object(
                audit.AUDIT_LOGGER,
                "info",
                side_effect=OSError("sink unavailable"),
            ):
                audit.emit_detail(response)
                audit.emit_detail(response)

            self.assertEqual(response.status_code, 200)
            self.assertTrue(g.security_detail["emitted"])
            self.assertEqual(len(self.audit_capture.messages), 0)
            self.assertEqual(len(self.error_capture.messages), 1)
            self.assertIn(
                "audit_emit_failed",
                self.error_capture.messages[0],
            )


if __name__ == "__main__":
    unittest.main()

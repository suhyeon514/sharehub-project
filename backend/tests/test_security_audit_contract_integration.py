"""Contract validation failure must not alter HTTP responses."""

import unittest
from unittest.mock import patch

from flask import Flask, g

from app.services.security_audit import emit_detail


class SecurityAuditContractIntegrationTests(unittest.TestCase):

    def test_validation_failure_preserves_response(self):
        app = Flask(__name__)

        with app.test_request_context("/api/documents/1"):
            g.request_id = "123e4567-e89b-42d3-a456-426614174000"
            g.security_detail = {
                "document_id": 1,
                "user_id": 1,
                "evaluated": True,
                "source": "owner",
                "permission": "edit",
                "decision": "allow",
                "reason": "DOCUMENT_OWNER_ACCESS",
                "event_type": "document.authorization",
                "emitted": False,
            }

            response = app.response_class(
                '{"data":{"id":1}}',
                status=200,
                mimetype="application/json",
            )

            with (
                patch(
                    "app.services.security_audit.validate_event",
                    side_effect=ValueError("contract validation failed"),
                ) as validator,
                patch(
                    "app.services.security_audit.AUDIT_LOGGER.info"
                ) as audit_log,
                patch(
                    "app.services.security_audit.ERROR_LOGGER.error"
                ) as error_log,
            ):
                emit_detail(response)

            validator.assert_called_once()
            audit_log.assert_not_called()
            error_log.assert_called_once()

            self.assertIn(
                "audit_emit_failed",
                error_log.call_args.args[0],
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), {"data": {"id": 1}})
            self.assertTrue(g.security_detail["emitted"])


if __name__ == "__main__":
    unittest.main()

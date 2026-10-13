"""Security Audit Event v1.0 contract validation tests."""

import copy
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from app.services.security_audit_contract import (
    AuditContractError,
    REASON_CODES,
    validate_event,
)


def valid_event():
    return {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "request_id": str(uuid4()),
        "event_type": "document.authorization",
        "actor": {"user_id": 1},
        "resource": {"type": "document", "id": 10},
        "action": "view",
        "authorization": {
            "evaluated": True,
            "required_permission": "view",
            "access_source": "owner",
            "effective_permission": "edit",
            "decision": "allow",
            "reason_code": "DOCUMENT_OWNER_ACCESS",
        },
        "result": {"outcome": "success", "http_status": 200},
    }


class SecurityAuditContractTests(unittest.TestCase):

    def assert_invalid(self, event):
        with self.assertRaises(AuditContractError):
            validate_event(event)

    def test_valid_owner_event(self):
        self.assertTrue(validate_event(valid_event()))

    def test_reason_code_catalog_has_11_values(self):
        self.assertEqual(len(REASON_CODES), 11)
        self.assertIn("DOCUMENT_OWNER_REQUIRED", REASON_CODES)
        self.assertIn("INSUFFICIENT_DOCUMENT_PERMISSION", REASON_CODES)

    def test_missing_required_field(self):
        event = valid_event()
        del event["authorization"]["reason_code"]
        self.assert_invalid(event)

    def test_unexpected_field(self):
        event = valid_event()
        event["authorization"]["secret"] = "should-not-exist"
        self.assert_invalid(event)

    def test_invalid_schema_version_type(self):
        event = valid_event()
        event["schema_version"] = True
        self.assert_invalid(event)

    def test_invalid_timestamp(self):
        event = valid_event()
        event["timestamp"] = "2026-10-13T12:00:00"
        self.assert_invalid(event)

    def test_invalid_request_id(self):
        event = valid_event()
        event["request_id"] = "not-a-uuid"
        self.assert_invalid(event)

    def test_invalid_actor_type(self):
        event = valid_event()
        event["actor"]["user_id"] = "1"
        self.assert_invalid(event)

    def test_invalid_document_id(self):
        event = valid_event()
        event["resource"]["id"] = True
        self.assert_invalid(event)

    def test_invalid_evaluated_type(self):
        event = valid_event()
        event["authorization"]["evaluated"] = 1
        self.assert_invalid(event)

    def test_invalid_access_source(self):
        event = valid_event()
        event["authorization"]["access_source"] = "admin"
        self.assert_invalid(event)

    def test_invalid_permission(self):
        event = valid_event()
        event["authorization"]["effective_permission"] = "owner"
        self.assert_invalid(event)

    def test_unknown_reason_code(self):
        event = valid_event()
        event["authorization"]["reason_code"] = "UNKNOWN_REASON"
        self.assert_invalid(event)

    def test_allow_reason_mismatch(self):
        event = valid_event()
        event["authorization"]["reason_code"] = "DIRECT_SHARE_EDIT"
        self.assert_invalid(event)

    def test_allow_source_permission_mismatch(self):
        event = valid_event()
        event["authorization"]["access_source"] = "team"
        event["authorization"]["effective_permission"] = "edit"
        self.assert_invalid(event)

    def test_valid_share_edit(self):
        event = valid_event()
        event["authorization"].update(
            access_source="share",
            effective_permission="edit",
            reason_code="DIRECT_SHARE_EDIT",
        )
        self.assertTrue(validate_event(event))

    def test_valid_no_access(self):
        event = valid_event()
        event["authorization"].update(
            access_source=None,
            effective_permission=None,
            decision="deny",
            reason_code="NO_DOCUMENT_ACCESS",
        )
        event["result"] = {"outcome": "failure", "http_status": 404}
        self.assertTrue(validate_event(event))

    def test_valid_blocked(self):
        event = valid_event()
        event["authorization"].update(
            decision="deny",
            reason_code="DOCUMENT_ACCESS_BLOCKED",
        )
        event["result"] = {"outcome": "failure", "http_status": 403}
        self.assertTrue(validate_event(event))

    def test_valid_authentication_failure(self):
        event = valid_event()
        event["event_type"] = "authentication"
        event["actor"]["user_id"] = None
        event["authorization"].update(
            evaluated=False,
            access_source=None,
            effective_permission=None,
            decision="not_evaluated",
            reason_code="AUTHENTICATION_REQUIRED",
        )
        event["result"] = {"outcome": "failure", "http_status": 401}
        self.assertTrue(validate_event(event))

    def test_valid_document_not_found(self):
        event = valid_event()
        event["event_type"] = "document.lookup"
        event["authorization"].update(
            evaluated=False,
            access_source=None,
            effective_permission=None,
            decision="not_evaluated",
            reason_code="DOCUMENT_NOT_FOUND",
        )
        event["result"] = {"outcome": "failure", "http_status": 404}
        self.assertTrue(validate_event(event))

    def test_unevaluated_cannot_allow(self):
        event = valid_event()
        event["authorization"]["evaluated"] = False
        self.assert_invalid(event)

    def test_evaluated_cannot_be_not_evaluated(self):
        event = valid_event()
        event["authorization"]["decision"] = "not_evaluated"
        self.assert_invalid(event)

    def test_outcome_http_status_mismatch(self):
        event = valid_event()
        event["result"] = {"outcome": "success", "http_status": 500}
        self.assert_invalid(event)

    def test_allow_then_processing_failure(self):
        event = valid_event()
        event["result"] = {"outcome": "failure", "http_status": 500}
        self.assertTrue(validate_event(event))

    def test_wrong_event_type_for_evaluated_access(self):
        event = valid_event()
        event["event_type"] = "authentication"
        self.assert_invalid(event)

    def test_detail_rejects_other_api_reason(self):
        event = valid_event()
        event["authorization"].update(
            decision="deny",
            reason_code="DOCUMENT_OWNER_REQUIRED",
        )
        event["result"] = {"outcome": "failure", "http_status": 403}
        self.assert_invalid(event)

    def test_document_id_zero_is_valid(self):
        event = valid_event()
        event["resource"]["id"] = 0
        self.assertTrue(validate_event(event))

    def test_negative_document_id_is_invalid(self):
        event = valid_event()
        event["resource"]["id"] = -1
        self.assert_invalid(event)


if __name__ == "__main__":
    unittest.main()

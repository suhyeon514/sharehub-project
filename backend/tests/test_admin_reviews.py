import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError
import test_admin_blocks as fixtures
from app.extensions import db
from app.models import ActivityLog, Document, DocumentBlock, DocumentUnblockRequest, User
from app.services.document_permissions import can_view_document


class AdminReviewTests(unittest.TestCase):
    tearDown = fixtures.AdminBlockTests.tearDown
    headers = fixtures.AdminBlockTests.headers

    def setUp(self):
        fixtures.AdminBlockTests.setUp(self)
        self.block_id = fixtures.AdminBlockTests.create(self).json["block"]["id"]
        self.request_id = self.new_request()

    def new_request(self):
        appeal = DocumentUnblockRequest(block_id=self.block_id, requester_id=self.ids["owner"],
            request_reason="private appeal", status="pending")
        db.session.add(appeal)
        db.session.commit()
        return appeal.id

    def detail(self, user="admin", request_id=None):
        return self.client.get(f"/api/admin/unblock-requests/{request_id or self.request_id}", headers=self.headers(user))

    def review(self, decision="approved", user="admin", payload=None, request_id=None):
        return self.client.post(f"/api/admin/unblock-requests/{request_id or self.request_id}/review",
            headers=self.headers(user), json=payload if payload is not None else {
                "decision": decision, "review_comment": "  공개 의견  "})

    def listing(self, **params):
        return self.client.get("/api/admin/unblock-requests", headers=self.headers(), query_string=params)

    def test_detail_contract_and_approval_restores_current_access(self):
        result = self.detail().json
        self.assertTrue(result["can_review"])
        self.assertIsNone(result["review_unavailable_reason"])
        self.assertTrue(result["block"]["is_current_block"])
        self.assertEqual(result["unblock_request"]["request_reason"], "private appeal")
        self.assertNotIn("block_basis", json.dumps(self.listing().json))
        user = db.session.get(User, self.ids["receiver"])
        document = db.session.get(Document, self.document_id)
        self.assertFalse(can_view_document(user, document))
        def pending_documents():
            return self.client.get("/api/admin/documents?status=pending", headers=self.headers()).json
        self.assertEqual(pending_documents()["pagination"]["total"], 1)
        response = self.review()
        self.assertEqual(pending_documents()["pagination"]["total"], 0)
        self.assertEqual(pending_documents()["items"], [])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["unblock_request"]["status"], "approved")
        self.assertEqual(response.json["block"]["status"], "unblocked")
        self.assertFalse(response.json["can_review"])
        self.assertEqual(response.json["review_unavailable_reason"], "UNBLOCK_REQUEST_NOT_PENDING")
        block = db.session.get(DocumentBlock, self.block_id)
        appeal = db.session.get(DocumentUnblockRequest, self.request_id)
        self.assertEqual(block.unblocked_at, appeal.reviewed_at)
        self.assertEqual(block.unblock_reason, "공개 의견")
        self.assertEqual(block.unblocked_by_id, self.ids["admin"])
        self.assertTrue(can_view_document(user, document))
        logs = db.session.query(ActivityLog).filter_by(action_type="DOCUMENT_UNBLOCK_REVIEW").all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(json.loads(logs[0].detail)["decision"], "approved")
        self.assertNotIn("private appeal", logs[0].detail)
        self.assertEqual(self.review().status_code, 409)

    def test_rejection_reapplication_and_history_filters(self):
        self.assertEqual(self.review("rejected").status_code, 200)
        self.assertEqual(db.session.get(DocumentBlock, self.block_id).status, "blocked")
        previous = self.request_id
        self.request_id = self.new_request()
        # 요청 시각이 같아도 ID로 최신 순서를 결정한다.
        at = datetime.now(timezone.utc).replace(tzinfo=None)
        for identity in (previous, self.request_id):
            db.session.get(DocumentUnblockRequest, identity).requested_at = at
        db.session.commit()
        result = self.listing(block_id=self.block_id, per_page=1).json
        self.assertEqual(result["pagination"]["total"], 2)
        self.assertEqual(result["items"][0]["id"], self.request_id)
        self.assertEqual(self.listing(status="rejected").json["pagination"]["total"], 1)
        self.assertEqual(self.listing(q="missing").json["items"], [])
        self.assertEqual(self.listing(q="%").json["items"], [])
        self.assertEqual(self.listing(page=99).json["items"], [])
        self.assertEqual(self.review(request_id=previous).json["error"]["code"], "UNBLOCK_REQUEST_NOT_PENDING")

    def test_self_review_owner_and_requester_priority(self):
        admin = db.session.get(User, self.ids["admin"])
        document = db.session.get(Document, self.document_id)
        appeal = db.session.get(DocumentUnblockRequest, self.request_id)
        for source in ("owner", "requester"):
            document.owner_id = admin.id if source == "owner" else self.ids["owner"]
            appeal.requester_id = admin.id if source == "requester" else self.ids["owner"]
            db.session.commit()
            detail = self.detail().json
            self.assertFalse(detail["can_review"])
            self.assertEqual(detail["review_unavailable_reason"], "SELF_REVIEW_NOT_ALLOWED")
            self.assertEqual(self.listing().json["items"][0]["review_unavailable_reason"], "SELF_REVIEW_NOT_ALLOWED")
            for decision in ("approved", "rejected"):
                response = self.review(decision)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json["error"]["code"], "SELF_REVIEW_NOT_ALLOWED")
        appeal.status = "cancelled"
        appeal.cancelled_at = datetime.now(timezone.utc)
        db.session.commit()
        self.assertEqual(self.detail().json["review_unavailable_reason"], "SELF_REVIEW_NOT_ALLOWED")

    def test_inactive_old_request_cannot_release_new_block(self):
        self.assertTrue(self.detail().json["can_review"])
        block = db.session.get(DocumentBlock, self.block_id)
        block.status = "unblocked"
        block.unblocked_by_id = self.ids["admin"]
        block.unblocked_at = datetime.now(timezone.utc)
        block.unblock_reason = "fixture"
        db.session.commit()
        new = fixtures.AdminBlockTests.create(self).json["block"]["id"]
        self.assertEqual(self.detail().json["review_unavailable_reason"], "DOCUMENT_BLOCK_NOT_ACTIVE")
        self.assertEqual(self.review().json["error"]["code"], "DOCUMENT_BLOCK_NOT_ACTIVE")
        self.assertEqual(db.session.get(DocumentBlock, new).status, "blocked")
        appeal = db.session.get(DocumentUnblockRequest, self.request_id)
        appeal.status = "cancelled"
        appeal.cancelled_at = datetime.now(timezone.utc)
        db.session.commit()
        self.assertEqual(self.review().json["error"]["code"], "UNBLOCK_REQUEST_NOT_PENDING")

    def test_validation_auth_and_missing(self):
        for user, expected in ((None, 401), ("owner", 403)):
            self.assertEqual(self.detail(user).status_code, expected)
            self.assertEqual(self.review(user=user).status_code, expected)
        self.assertEqual(self.detail(request_id=99999).status_code, 404)
        self.assertEqual(self.review(request_id=99999).status_code, 404)
        for payload in ([], {}, {"decision": "approved", "review_comment": " "},
                        {"decision": [], "review_comment": "ok"},
                        {"decision": "approved", "review_comment": "a" * 1001},
                        {"decision": "approved", "review_comment": None},
                        {"decision": "approved", "review_comment": "ok", "reviewed_by_id": 1}):
            self.assertEqual(self.review(payload=payload).status_code, 400)
        for params in ({"status": "bad"}, {"block_id": ""}, {"block_id": 0}, {"page": 0}, {"per_page": 101}, {"q": "x" * 256}):
            self.assertEqual(self.listing(**params).status_code, 400)
        self.assertEqual(self.review(payload={"decision": "rejected", "review_comment": " " + "가" * 1000 + " "}).status_code, 200)

    def test_log_and_commit_failure_roll_back_all_changes(self):
        original_add = db.session.add
        def add(instance, *args, **kwargs):
            if isinstance(instance, ActivityLog):
                raise SQLAlchemyError("log failed")
            return original_add(instance, *args, **kwargs)
        for target, effect in (("add", add), ("commit", SQLAlchemyError("commit failed"))):
            with patch.object(db.session, target, side_effect=effect):
                with self.assertRaises(SQLAlchemyError):
                    self.review()
            self.assertEqual(db.session.get(DocumentBlock, self.block_id).status, "blocked")
            appeal = db.session.get(DocumentUnblockRequest, self.request_id)
            self.assertEqual(appeal.status, "pending")
            self.assertIsNone(appeal.reviewed_at)
            self.assertEqual(db.session.query(ActivityLog).filter_by(action_type="DOCUMENT_UNBLOCK_REVIEW").count(), 0)

    def test_deleted_document_history_listing_detail_and_review_denial(self):
        # 실제 DELETE API 없이 승인 후 삭제된 상태를 격리 DB에 구성한다.
        self.assertEqual(self.review().status_code, 200)
        block = db.session.get(DocumentBlock, self.block_id)
        block.document = None
        db.session.flush()
        db.session.delete(db.session.get(Document, self.document_id))
        db.session.commit()
        logs_before = [(row.id, row.detail) for row in db.session.query(ActivityLog).all()]

        for filters in ({}, {"status": "approved"}, {"block_id": self.block_id}):
            result = self.listing(**filters)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["pagination"]["total"], 1)
            item = result.json["items"][0]
            self.assertEqual(item["document_id"], self.document_id)
            self.assertTrue(item["document_deleted"])
            self.assertIsNone(item["title"])
            self.assertFalse(item["can_review"])
            self.assertNotIn("block_basis", item)
        self.assertEqual(self.listing(page=2, per_page=1).json["items"], [])
        self.assertEqual(self.listing(page=2, per_page=1).json["pagination"]["total"], 1)
        self.assertEqual(self.listing(status="pending").json["items"], [])
        self.assertEqual(self.listing(q="Block fixture").json["items"], [])

        detail = self.detail()
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json["document"], {
            "id": self.document_id, "title": None, "deleted": True})
        self.assertFalse(detail.json["can_review"])
        self.assertFalse(detail.json["block"]["is_current_block"])
        for decision in ("approved", "rejected"):
            self.assertEqual(self.review(decision).status_code, 409)
        db.session.expire_all()
        self.assertEqual(db.session.get(DocumentUnblockRequest, self.request_id).status, "approved")
        self.assertEqual(db.session.get(DocumentBlock, self.block_id).document_id_snapshot, self.document_id)
        self.assertEqual(db.session.get(DocumentBlock, self.block_id).status, "unblocked")
        self.assertEqual([(row.id, row.detail) for row in db.session.query(ActivityLog).all()], logs_before)
        for user, expected in ((None, 401), ("owner", 403)):
            self.assertEqual(self.detail(user).status_code, expected)

    def test_existing_document_response_keeps_title_and_reviewability(self):
        item = self.listing(q="Block fixture").json["items"][0]
        self.assertFalse(item["document_deleted"])
        self.assertEqual(item["title"], "Block fixture")
        detail = self.detail().json
        self.assertEqual(detail["document"], {
            "id": self.document_id, "title": "Block fixture", "deleted": False})
        self.assertTrue(detail["can_review"])

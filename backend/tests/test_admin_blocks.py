"""관리자 차단 계약 테스트. SQLite는 MariaDB 잠금 검증을 대체하지 않는다."""
import json
import secrets
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError
from app import create_app
from app.extensions import db
from app.models import ActivityLog, Document, DocumentBlock, DocumentShare, Session, User


class AdminBlockTests(unittest.TestCase):
    def test_document_status_filter_latest_request_counts_and_reblocking(self):
        from app.models import DocumentUnblockRequest

        def listing(status="", **query):
            return self.client.get("/api/admin/documents", headers=self.headers(),
                query_string={"status": status, **query})

        self.assertEqual(listing("normal").json["pagination"]["total"], 1)
        self.assertEqual(listing("blocked").json["items"], [])
        self.assertEqual(listing("invalid").status_code, 400)
        block_id = self.create().json["block"]["id"]
        self.assertEqual(listing("normal").json["items"], [])
        self.assertEqual(listing("blocked").json["pagination"]["total"], 1)
        self.assertEqual(listing("pending").json["items"], [])
        at = datetime.now(timezone.utc).replace(tzinfo=None)
        # 同一 시각에는 ID가 큰 요청이 최신이다. 이전 거절은 필터에 남지 않는다.
        for status in ("rejected", "cancelled", "pending"):
            fields = {"reviewed_by_id": self.ids["admin"], "review_comment": "reviewed", "reviewed_at": at} if status == "rejected" else {"cancelled_at": at} if status == "cancelled" else {}
            db.session.add(DocumentUnblockRequest(block_id=block_id, requester_id=self.ids["owner"],
                request_reason="appeal", status=status, requested_at=at, **fields))
            db.session.commit()
            for candidate in ("rejected", "cancelled", "pending"):
                self.assertEqual(listing(candidate).json["pagination"]["total"], int(candidate == status))
            self.assertEqual(listing().json["items"][0]["active_block"]["latest_request_status"], status)
        self.assertEqual(listing("pending", q="missing").json["pagination"]["total"], 0)
        self.assertEqual(listing("pending", per_page=1, page=2).json["items"], [])
        self.assertEqual(listing("pending", per_page=1, page=2).json["pagination"]["total"], 1)
        old = db.session.get(DocumentBlock, block_id)
        old.status = "unblocked"
        old.unblocked_by_id = self.ids["admin"]
        old.unblocked_at = at
        old.unblock_reason = "released"
        db.session.commit()
        self.assertEqual(listing("pending").json["items"], [])
        self.assertEqual(listing("normal").json["pagination"]["total"], 1)
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(listing("blocked").json["pagination"]["total"], 1)
        self.assertEqual(listing("pending").json["items"], [])

    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.ids, self.tokens = {}, {}
        for name in ("admin", "owner", "receiver"):
            user = User(username=name, password_hash="unused", role="admin" if name == "admin" else "user")
            db.session.add(user)
            db.session.flush()
            self.ids[name] = user.id
            self.tokens[name] = secrets.token_urlsafe(32)
            db.session.add(Session(user_id=user.id, session_token=self.tokens[name], is_active=True,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        document = Document(title="Block fixture", owner_id=self.ids["owner"], visibility="private",
            file_path="not-a-real-file", original_filename="fixture.txt")
        db.session.add(document)
        db.session.flush()
        self.document_id = document.id
        db.session.add(DocumentShare(document_id=document.id, shared_by_id=self.ids["owner"],
            shared_with_id=self.ids["receiver"], permission="view"))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()

    def headers(self, user="admin"):
        return {"Authorization": f"Bearer {self.tokens[user]}"} if user else {}

    def create(self, payload=None, user="admin", document_id=None):
        return self.client.post(f"/api/admin/documents/{document_id or self.document_id}/blocks",
            headers=self.headers(user), json=payload if payload is not None else {
                "block_reason": "  공개 사유  ", "block_basis": "  내부 전용 근거  "})

    def assert_counts(self, blocks, logs):
        self.assertEqual(db.session.query(DocumentBlock).count(), blocks)
        self.assertEqual(db.session.query(ActivityLog).count(), logs)

    def test_creation_contract_actor_timestamp_log_and_share_preservation(self):
        before = datetime.now(timezone.utc)
        response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.json), {"block"})
        result = response.json["block"]
        self.assertEqual(set(result), {"id", "document_id", "status", "block_reason", "block_basis", "blocked_at"})
        self.assertEqual(result["block_reason"], "공개 사유")
        self.assertEqual(result["block_basis"], "내부 전용 근거")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["document_id"], self.document_id)
        at = datetime.fromisoformat(result["blocked_at"])
        self.assertIsNotNone(at.tzinfo)
        self.assertLessEqual(before, at)
        self.assertLessEqual(at, datetime.now(timezone.utc))
        block = db.session.get(DocumentBlock, result["id"])
        self.assertEqual(block.blocked_by_id, self.ids["admin"])
        self.assertEqual(block.document_id_snapshot, self.document_id)
        self.assertEqual(block.active_document_id, self.document_id)
        self.assertEqual(block.blocked_at.replace(tzinfo=timezone.utc), at)
        log = db.session.query(ActivityLog).one()
        self.assertEqual(log.action_type, "DOCUMENT_BLOCK")
        self.assertEqual(log.user_id, self.ids["admin"])
        self.assertEqual(log.ip_address, "127.0.0.1")
        self.assertEqual(json.loads(log.detail), {"operation": "block", "document_id": self.document_id,
            "block_id": block.id, "block_reason": "공개 사유"})
        self.assertEqual(db.session.query(DocumentShare).one().permission, "view")
        self.assertEqual(db.session.get(Document, self.document_id).file_path, "not-a-real-file")
        self.assert_counts(1, 1)

    def test_invalid_inputs_have_no_side_effects(self):
        invalid = [[], {}, {"block_reason": "ok"}, {"block_basis": "ok"}]
        for field in ("block_reason", "block_basis"):
            for value in (None, True, 123, [], {}, "", " \n\t ", "가" * (1001 if field == "block_reason" else 5001)):
                invalid.append({"block_reason": "ok", "block_basis": "ok", field: value})
        for field in ("blocked_by_id", "status", "blocked_at", "document_id"):
            invalid.append({"block_reason": "ok", "block_basis": "ok", field: 1})
        for payload in invalid:
            with self.subTest(payload=repr(payload)[:100]):
                response = self.create(payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json["error"]["code"], "VALIDATION_ERROR")
                self.assert_counts(0, 0)
        response = self.client.post(f"/api/admin/documents/{self.document_id}/blocks",
            headers=self.headers(), data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assert_counts(0, 0)

    def test_exact_maximum_lengths_after_trim(self):
        response = self.create({"block_reason": " " + "가" * 1000 + " ", "block_basis": " " + "나" * 5000 + " "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json["block"]["block_reason"]), 1000)
        self.assertEqual(len(response.json["block"]["block_basis"]), 5000)

    def test_minimum_lengths(self):
        self.assertEqual(self.create({"block_reason": "가", "block_basis": "나"}).status_code, 201)

    def test_authentication_and_role_change(self):
        self.assertEqual(self.create(user=None).status_code, 401)
        for user in ("owner", "receiver"):
            self.assertEqual(self.create(user=user).status_code, 403)
        db.session.get(User, self.ids["admin"]).role = "user"
        db.session.commit()
        self.assertEqual(self.create().status_code, 403)
        self.assert_counts(0, 0)

    def test_missing_and_duplicate(self):
        response = self.create(document_id=999999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["error"]["code"], "DOCUMENT_NOT_FOUND")
        self.assert_counts(0, 0)
        first = self.create().json["block"]
        response = self.create({"block_reason": "다른 사유", "block_basis": "다른 근거"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"]["code"], "DOCUMENT_ALREADY_BLOCKED")
        self.assertEqual(db.session.get(DocumentBlock, first["id"]).block_reason, first["block_reason"])
        self.assert_counts(1, 1)

    def test_unblocked_history_creates_new_block(self):
        old = DocumentBlock(document_id=self.document_id, document_id_snapshot=self.document_id,
            blocked_by_id=self.ids["admin"], block_reason="old", block_basis="old", status="unblocked",
            unblocked_by_id=self.ids["admin"], unblock_reason="reviewed", unblocked_at=datetime.now(timezone.utc))
        db.session.add(old)
        db.session.commit()
        old_id = old.id
        response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json["block"]["id"], old_id)
        self.assertEqual(db.session.get(DocumentBlock, old_id).status, "unblocked")
        self.assert_counts(2, 1)

    def test_log_and_commit_failures_roll_back_block(self):
        original_add = db.session.add
        def add(instance, *args, **kwargs):
            if isinstance(instance, ActivityLog):
                raise SQLAlchemyError("simulated log failure")
            return original_add(instance, *args, **kwargs)
        for name, kwargs in (("add", {"side_effect": add}),
                             ("commit", {"side_effect": SQLAlchemyError("simulated commit failure")})):
            with self.subTest(stage=name):
                with patch.object(db.session, name, **kwargs):
                    with self.assertRaises(SQLAlchemyError):
                        self.create()
                self.assert_counts(0, 0)
        self.assertEqual(self.create().status_code, 201)

    def test_admin_list_logs_and_general_share_denial(self):
        def documents():
            return self.client.get("/api/admin/documents", headers=self.headers()).json
        before = documents()
        self.assertIsNone(before["items"][0]["active_block"])
        block = self.create().json["block"]
        after = documents()
        self.assertEqual(after["pagination"], before["pagination"])
        self.assertEqual(after["items"][0]["active_block"], {
            "id": block["id"], "status": "blocked", "blocked_at": block["blocked_at"], "latest_request_status": None})
        self.assertNotIn("block_basis", json.dumps(after))
        log = db.session.query(ActivityLog).one()
        detail = json.loads(log.detail)
        detail["block_basis"] = "private-basis"
        log.detail = json.dumps(detail)
        db.session.commit()
        logs = self.client.get("/api/admin/activity-logs", headers=self.headers()).json
        self.assertNotIn("private-basis", json.dumps(logs))
        self.assertEqual(logs["items"][0]["detail"]["block_reason"], "공개 사유")
        self.assertEqual(logs["items"][0]["detail"]["block_id"], block["id"])
        for user in ("owner", "receiver", "admin"):
            response = self.client.get(f"/api/documents/{self.document_id}/shares", headers=self.headers(user))
            self.assertEqual(response.status_code, 404 if user == "admin" else 403)
            self.assertEqual(response.json["error"]["code"], "DOCUMENT_NOT_FOUND" if user == "admin" else "DOCUMENT_BLOCKED")


if __name__ == "__main__":
    unittest.main()

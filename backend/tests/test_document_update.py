"""Document PATCH API contract tests.

Run with:
    python -m unittest tests.test_document_update -v
"""

import json
import secrets
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.extensions import db
from app.models import (
    ActivityLog,
    Department,
    Document,
    DocumentBlock,
    DocumentShare,
    Session,
    User,
)


class DocumentUpdateTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })

        with self.app.app_context():
            db.create_all()

            department = Department(name="Document update team")
            other_department = Department(name="Other team")
            db.session.add_all([department, other_department])
            db.session.flush()

            self.tokens = {}
            self.user_ids = {}

            user_specs = {
                "owner": ("user", department.id),
                "editor": ("user", other_department.id),
                "viewer": ("user", other_department.id),
                "downloader": ("user", other_department.id),
                "team_user": ("user", department.id),
                "unrelated": ("user", other_department.id),
                "admin": ("admin", other_department.id),
            }

            users = {}

            for name, (role, department_id) in user_specs.items():
                user = User(
                    username=name,
                    password_hash="unused-test-value",
                    role=role,
                    department_id=department_id,
                )
                db.session.add(user)
                db.session.flush()

                users[name] = user
                self.user_ids[name] = user.id

                token = secrets.token_urlsafe(32)
                self.tokens[name] = token

                db.session.add(
                    Session(
                        user_id=user.id,
                        session_token=token,
                        expires_at=(
                            datetime.now(timezone.utc)
                            + timedelta(hours=1)
                        ),
                        is_active=True,
                    )
                )

            private_document = Document(
                title="Original title",
                description="Original description",
                owner_id=users["owner"].id,
                department_id=department.id,
                visibility="private",
                file_path="not-a-real-file",
                original_filename="private.txt",
            )

            team_document = Document(
                title="Team document",
                description="Team description",
                owner_id=users["owner"].id,
                department_id=department.id,
                visibility="team",
                file_path="not-a-real-file",
                original_filename="team.txt",
            )

            db.session.add_all([private_document, team_document])
            db.session.flush()

            self.document_id = private_document.id
            self.team_document_id = team_document.id

            for name, permission in (
                ("editor", "edit"),
                ("viewer", "view"),
                ("downloader", "download"),
            ):
                db.session.add(
                    DocumentShare(
                        document_id=private_document.id,
                        shared_by_id=users["owner"].id,
                        shared_with_id=users[name].id,
                        permission=permission,
                    )
                )

            db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def headers(self, user):
        return {
            "Authorization": f"Bearer {self.tokens[user]}"
        }

    def update(self, user, payload, document_id=None):
        if document_id is None:
            document_id = self.document_id

        return self.client.patch(
            f"/api/documents/{document_id}",
            headers=self.headers(user),
            json=payload,
        )

    def test_owner_can_update_title_and_description(self):
        response = self.update(
            "owner",
            {
                "title": "  Updated title  ",
                "description": "  Updated description  ",
            },
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()["document"]

        self.assertEqual(data["title"], "Updated title")
        self.assertEqual(
            data["description"],
            "Updated description",
        )
        self.assertIsNotNone(data["updated_at"])

        with self.app.app_context():
            document = db.session.get(
                Document,
                self.document_id,
            )

            self.assertEqual(document.title, "Updated title")
            self.assertEqual(
                document.description,
                "Updated description",
            )

            logs = ActivityLog.query.filter_by(
                action_type="DOCUMENT_UPDATE"
            ).all()

            self.assertEqual(len(logs), 1)

            detail = json.loads(logs[0].detail)

            self.assertEqual(detail["operation"], "update")
            self.assertEqual(
                detail["document_id"],
                self.document_id,
            )
            self.assertEqual(
                detail["changed_fields"],
                ["title", "description"],
            )

            # 제목/설명 원문을 감사 로그에 저장하지 않는다.
            self.assertNotIn("Updated title", logs[0].detail)
            self.assertNotIn(
                "Updated description",
                logs[0].detail,
            )

    def test_editor_can_update_document(self):
        response = self.update(
            "editor",
            {"title": "Editor changed title"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["document"]["title"],
            "Editor changed title",
        )

    def test_view_download_and_team_access_cannot_edit(self):
        cases = (
            ("viewer", self.document_id),
            ("downloader", self.document_id),
            ("team_user", self.team_document_id),
        )

        for user, document_id in cases:
            with self.subTest(user=user):
                response = self.update(
                    user,
                    {"title": "Denied"},
                    document_id=document_id,
                )

                self.assertEqual(response.status_code, 403)
                self.assertEqual(
                    response.get_json()["error"]["code"],
                    "DOCUMENT_EDIT_FORBIDDEN",
                )

    def test_unrelated_and_admin_without_access_get_404(self):
        for user in ("unrelated", "admin"):
            with self.subTest(user=user):
                response = self.update(
                    user,
                    {"title": "Hidden"},
                )

                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.get_json()["error"]["code"],
                    "DOCUMENT_NOT_FOUND",
                )

    def test_blocked_document_rejects_users_with_access(self):
        with self.app.app_context():
            db.session.add(
                DocumentBlock(
                    document_id=self.document_id,
                    document_id_snapshot=self.document_id,
                    blocked_by_id=self.user_ids["admin"],
                    block_reason="Update test block",
                    block_basis="test",
                    status="blocked",
                )
            )
            db.session.commit()

        for user in ("owner", "editor", "viewer"):
            with self.subTest(user=user):
                response = self.update(
                    user,
                    {"title": "Blocked update"},
                )

                self.assertEqual(response.status_code, 403)
                self.assertEqual(
                    response.get_json()["error"]["code"],
                    "DOCUMENT_BLOCKED",
                )

        # 접근 근거가 없는 사용자는 차단 여부를 알 수 없어야 한다.
        response = self.update(
            "unrelated",
            {"title": "Hidden block"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "DOCUMENT_NOT_FOUND",
        )

    def test_partial_update_preserves_omitted_field(self):
        response = self.update(
            "owner",
            {"title": "Only title changed"},
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()["document"]

        self.assertEqual(data["title"], "Only title changed")
        self.assertEqual(
            data["description"],
            "Original description",
        )

        with self.app.app_context():
            log = ActivityLog.query.filter_by(
                action_type="DOCUMENT_UPDATE"
            ).one()

            self.assertEqual(
                json.loads(log.detail)["changed_fields"],
                ["title"],
            )

    def test_description_null_and_whitespace_become_null(self):
        for value in (None, "   "):
            with self.subTest(value=value):
                with self.app.app_context():
                    document = db.session.get(
                        Document,
                        self.document_id,
                    )
                    document.description = "Reset description"
                    db.session.commit()

                response = self.update(
                    "owner",
                    {"description": value},
                )

                self.assertEqual(response.status_code, 200)
                self.assertIsNone(
                    response.get_json()["document"][
                        "description"
                    ]
                )

    def test_validation_errors(self):
        invalid_payloads = (
            {},
            {"title": None},
            {"title": ""},
            {"title": "   "},
            {"title": 123},
            {"title": "a" * 256},
            {"description": 123},
            {"description": "a" * 5001},
            {"unknown": "value"},
            {
                "title": "Valid",
                "unknown": "value",
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.update(
                    "owner",
                    payload,
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["error"]["code"],
                    "VALIDATION_ERROR",
                )

    def test_non_object_and_invalid_json_are_validation_error(self):
        response = self.client.patch(
            f"/api/documents/{self.document_id}",
            headers={
                **self.headers("owner"),
                "Content-Type": "application/json",
            },
            data='["title"]',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "VALIDATION_ERROR",
        )

        response = self.client.patch(
            f"/api/documents/{self.document_id}",
            headers={
                **self.headers("owner"),
                "Content-Type": "application/json",
            },
            data='{"title":',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "VALIDATION_ERROR",
        )

    def test_length_boundaries(self):
        response = self.update(
            "owner",
            {
                "title": "가" * 255,
                "description": "나" * 5000,
            },
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()["document"]

        self.assertEqual(len(data["title"]), 255)
        self.assertEqual(len(data["description"]), 5000)

    def test_noop_does_not_change_updated_at_or_create_log(self):
        with self.app.app_context():
            document = db.session.get(
                Document,
                self.document_id,
            )
            before_updated_at = document.updated_at

        response = self.update(
            "owner",
            {"title": "   Original title   "},
        )

        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            document = db.session.get(
                Document,
                self.document_id,
            )

            self.assertEqual(
                document.updated_at,
                before_updated_at,
            )

            count = ActivityLog.query.filter_by(
                action_type="DOCUMENT_UPDATE"
            ).count()

            self.assertEqual(count, 0)

    def test_failed_audit_log_rolls_back_document_update(self):
        # flush 단계에서 감사 로그 저장 실패를 발생시켜
        # 문서 변경도 함께 rollback 되는지 검증한다.
        original_flush = db.session.flush

        def failing_flush(*args, **kwargs):
            raise SQLAlchemyError("forced audit failure")

        with patch.object(
            db.session,
            "flush",
            side_effect=failing_flush,
        ):
            with self.assertRaises(SQLAlchemyError):
                self.update(
                    "owner",
                    {"title": "Must rollback"},
                )

        with self.app.app_context():
            document = db.session.get(
                Document,
                self.document_id,
            )

            self.assertEqual(
                document.title,
                "Original title",
            )

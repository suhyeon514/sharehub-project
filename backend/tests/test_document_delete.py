"""Document DELETE API contract tests."""

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
    FileCleanupJob,
    Session,
    User,
)
from app.models.comment import Comment


class DocumentDeleteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )

        with self.app.app_context():
            db.create_all()

            department = Department(name="Document delete team")
            other_department = Department(name="Other team")

            db.session.add_all(
                [department, other_department]
            )
            db.session.flush()

            self.tokens = {}
            self.user_ids = {}

            user_specs = {
                "owner": ("user", department.id),
                "editor": ("user", other_department.id),
                "viewer": ("user", other_department.id),
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
                title="Delete target",
                description="Delete target description",
                owner_id=users["owner"].id,
                department_id=department.id,
                visibility="private",
                file_path="not-a-real-file",
                original_filename="delete.txt",
            )

            team_document = Document(
                title="Team delete target",
                description="Team document",
                owner_id=users["owner"].id,
                department_id=department.id,
                visibility="team",
                file_path="not-a-real-team-file",
                original_filename="team-delete.txt",
            )

            db.session.add_all(
                [private_document, team_document]
            )
            db.session.flush()

            self.document_id = private_document.id
            self.team_document_id = team_document.id

            for name, permission in (
                ("editor", "edit"),
                ("viewer", "view"),
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

    def delete(self, user, document_id=None):
        if document_id is None:
            document_id = self.document_id

        return self.client.delete(
            f"/api/documents/{document_id}",
            headers=self.headers(user),
        )

    def add_unblocked_history(self):
        with self.app.app_context():
            block = DocumentBlock(
                document_id=self.document_id,
                document_id_snapshot=self.document_id,
                blocked_by_id=self.user_ids["admin"],
                block_reason="test block",
                block_basis="test basis",
                status="unblocked",
                unblocked_by_id=self.user_ids["admin"],
                unblock_reason="approved",
                unblocked_at=datetime.now(timezone.utc),
            )

            db.session.add(block)
            db.session.commit()

            return block.id

    def test_owner_delete_returns_204_and_removes_document(self):
        with patch(
            "app.routes.documents.process_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_COMPLETED,
        ) as cleanup_mock:
            response = self.delete("owner")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")

        with self.app.app_context():
            self.assertIsNone(
                db.session.get(
                    Document,
                    self.document_id,
                )
            )

            jobs = FileCleanupJob.query.filter_by(
                document_id_snapshot=self.document_id
            ).all()

            self.assertEqual(len(jobs), 1)

            cleanup_mock.assert_called_once_with(
                jobs[0].id
            )

    def test_editor_viewer_team_and_admin_cannot_delete(self):
        cases = (
            ("editor", self.document_id, 403),
            ("viewer", self.document_id, 403),
            ("team_user", self.team_document_id, 403),
            # admin role alone has no access basis to private doc.
            ("admin", self.document_id, 404),
        )

        for user, document_id, expected_status in cases:
            with self.subTest(user=user):
                response = self.delete(
                    user,
                    document_id,
                )

                self.assertEqual(
                    response.status_code,
                    expected_status,
                )

                expected_code = (
                    "DOCUMENT_NOT_FOUND"
                    if expected_status == 404
                    else "DOCUMENT_DELETE_FORBIDDEN"
                )

                self.assertEqual(
                    response.get_json()["error"]["code"],
                    expected_code,
                )

    def test_unrelated_user_gets_hidden_404(self):
        response = self.delete("unrelated")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "DOCUMENT_NOT_FOUND",
        )

    def test_missing_document_gets_404(self):
        response = self.delete(
            "owner",
            document_id=999999,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "DOCUMENT_NOT_FOUND",
        )

    def test_blocked_owner_cannot_delete(self):
        with self.app.app_context():
            db.session.add(
                DocumentBlock(
                    document_id=self.document_id,
                    document_id_snapshot=self.document_id,
                    blocked_by_id=self.user_ids["admin"],
                    block_reason="blocked",
                    block_basis="test",
                    status="blocked",
                )
            )
            db.session.commit()

        with patch(
            "app.routes.documents.process_cleanup_job_safely"
        ) as cleanup_mock:
            response = self.delete("owner")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "DOCUMENT_BLOCKED",
        )

        cleanup_mock.assert_not_called()

        with self.app.app_context():
            self.assertIsNotNone(
                db.session.get(
                    Document,
                    self.document_id,
                )
            )

    def test_success_deletes_comments_and_shares(self):
        with self.app.app_context():
            comment = Comment(
                document_id=self.document_id,
                user_id=self.user_ids["viewer"],
                content="delete me",
            )

            db.session.add(comment)
            db.session.commit()

            comment_id = comment.id

            self.assertGreater(
                DocumentShare.query.filter_by(
                    document_id=self.document_id
                ).count(),
                0,
            )

        with patch(
            "app.routes.documents.process_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_COMPLETED,
        ):
            response = self.delete("owner")

        self.assertEqual(response.status_code, 204)

        with self.app.app_context():
            self.assertIsNone(
                db.session.get(Comment, comment_id)
            )

            self.assertEqual(
                DocumentShare.query.filter_by(
                    document_id=self.document_id
                ).count(),
                0,
            )

    def test_unblocked_history_is_preserved_with_null_document_id(self):
        block_id = self.add_unblocked_history()

        with patch(
            "app.routes.documents.process_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_COMPLETED,
        ):
            response = self.delete("owner")

        self.assertEqual(response.status_code, 204)

        with self.app.app_context():
            block = db.session.get(
                DocumentBlock,
                block_id,
            )

            self.assertIsNotNone(block)
            self.assertIsNone(block.document_id)
            self.assertEqual(
                block.document_id_snapshot,
                self.document_id,
            )
            self.assertEqual(
                block.status,
                "unblocked",
            )

    def test_delete_creates_exactly_one_minimal_audit_log(self):
        with patch(
            "app.routes.documents.process_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_COMPLETED,
        ):
            response = self.delete("owner")

        self.assertEqual(response.status_code, 204)

        with self.app.app_context():
            logs = ActivityLog.query.filter_by(
                action_type="DOCUMENT_DELETE"
            ).all()

            self.assertEqual(len(logs), 1)
            self.assertEqual(
                logs[0].user_id,
                self.user_ids["owner"],
            )

            detail = json.loads(logs[0].detail)

            self.assertEqual(
                detail,
                {
                    "operation": "delete",
                    "document_id": self.document_id,
                },
            )

            self.assertNotIn(
                "Delete target",
                logs[0].detail,
            )
            self.assertNotIn(
                "not-a-real-file",
                logs[0].detail,
            )

    def test_delete_creates_exactly_one_cleanup_job(self):
        with patch(
            "app.routes.documents.process_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_PENDING,
        ):
            response = self.delete("owner")

        self.assertEqual(response.status_code, 204)

        with self.app.app_context():
            jobs = FileCleanupJob.query.filter_by(
                document_id_snapshot=self.document_id
            ).all()

            self.assertEqual(len(jobs), 1)

            job = jobs[0]

            self.assertEqual(
                job.status,
                FileCleanupJob.STATUS_PENDING,
            )
            self.assertEqual(job.attempt_count, 0)
            self.assertEqual(
                job.file_path,
                "not-a-real-file",
            )

    def test_cleanup_exception_after_commit_still_returns_204(self):
        with patch(
            "app.routes.documents.process_cleanup_job_safely",
            side_effect=RuntimeError(
                "simulated cleanup failure"
            ),
        ):
            response = self.delete("owner")

        self.assertEqual(response.status_code, 204)

        with self.app.app_context():
            self.assertIsNone(
                db.session.get(
                    Document,
                    self.document_id,
                )
            )

            self.assertEqual(
                FileCleanupJob.query.filter_by(
                    document_id_snapshot=self.document_id
                ).count(),
                1,
            )

            self.assertEqual(
                ActivityLog.query.filter_by(
                    action_type="DOCUMENT_DELETE"
                ).count(),
                1,
            )

    def test_redelete_returns_404_without_second_log_or_job(self):
        with patch(
            "app.routes.documents.process_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_COMPLETED,
        ):
            first = self.delete("owner")
            second = self.delete("owner")

        self.assertEqual(first.status_code, 204)
        self.assertEqual(second.status_code, 404)
        self.assertEqual(
            second.get_json()["error"]["code"],
            "DOCUMENT_NOT_FOUND",
        )

        with self.app.app_context():
            self.assertEqual(
                ActivityLog.query.filter_by(
                    action_type="DOCUMENT_DELETE"
                ).count(),
                1,
            )

            self.assertEqual(
                FileCleanupJob.query.filter_by(
                    document_id_snapshot=self.document_id
                ).count(),
                1,
            )

    def test_db_commit_failure_rolls_back_delete_log_and_cleanup_job(self):
        block_id = self.add_unblocked_history()

        with patch.object(
            db.session,
            "commit",
            side_effect=SQLAlchemyError(
                "simulated commit failure"
            ),
        ), patch(
            "app.routes.documents.process_cleanup_job_safely"
        ) as cleanup_mock:
            response = self.delete("owner")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "INTERNAL_SERVER_ERROR",
        )

        cleanup_mock.assert_not_called()

        with self.app.app_context():
            document = db.session.get(
                Document,
                self.document_id,
            )
            self.assertIsNotNone(document)

            block = db.session.get(
                DocumentBlock,
                block_id,
            )
            self.assertIsNotNone(block)
            self.assertEqual(
                block.document_id,
                self.document_id,
            )

            self.assertEqual(
                ActivityLog.query.filter_by(
                    action_type="DOCUMENT_DELETE"
                ).count(),
                0,
            )

            self.assertEqual(
                FileCleanupJob.query.filter_by(
                    document_id_snapshot=self.document_id
                ).count(),
                0,
            )


if __name__ == "__main__":
    unittest.main()

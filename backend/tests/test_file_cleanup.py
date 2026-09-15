import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import FileCleanupJob
from app.services.file_cleanup import (
    ERROR_FILE_IO,
    ERROR_PATH_OUTSIDE_UPLOAD_DIR,
    MAX_CLEANUP_ATTEMPTS,
    process_cleanup_job,
)


class FileCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.temp_dir.name) / "uploads"
        self.upload_dir.mkdir()

        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "UPLOAD_DIR": str(self.upload_dir),
            }
        )

        self.ctx = self.app.app_context()
        self.ctx.push()

        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

        self.ctx.pop()
        self.temp_dir.cleanup()

    def create_job(
        self,
        file_path,
        *,
        attempt_count=0,
        status=FileCleanupJob.STATUS_PENDING,
        last_error=None,
    ):
        job = FileCleanupJob(
            document_id_snapshot=999999,
            file_path=str(file_path),
            status=status,
            attempt_count=attempt_count,
            last_error=last_error,
        )

        db.session.add(job)
        db.session.commit()

        return job.id

    def get_job(self, job_id):
        db.session.expire_all()
        return db.session.get(FileCleanupJob, job_id)

    def test_existing_file_is_deleted_and_job_completed(self):
        path = self.upload_dir / "normal.txt"
        path.write_text("fixture", encoding="utf-8")

        job_id = self.create_job(path)

        result = process_cleanup_job(job_id)
        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_COMPLETED)
        self.assertEqual(job.status, FileCleanupJob.STATUS_COMPLETED)
        self.assertEqual(job.attempt_count, 1)
        self.assertIsNone(job.last_error)
        self.assertIsNotNone(job.completed_at)
        self.assertFalse(path.exists())

    def test_missing_file_is_idempotent_success(self):
        path = self.upload_dir / "already-missing.txt"

        self.assertFalse(path.exists())

        job_id = self.create_job(path)

        result = process_cleanup_job(job_id)
        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_COMPLETED)
        self.assertEqual(job.status, FileCleanupJob.STATUS_COMPLETED)
        self.assertEqual(job.attempt_count, 1)
        self.assertIsNone(job.last_error)
        self.assertIsNotNone(job.completed_at)

    def test_outside_upload_dir_is_not_deleted(self):
        outside_dir = Path(self.temp_dir.name) / "outside"
        outside_dir.mkdir()

        path = outside_dir / "must-not-delete.txt"
        path.write_text("fixture", encoding="utf-8")

        job_id = self.create_job(path)

        result = process_cleanup_job(job_id)
        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_PENDING)
        self.assertEqual(job.status, FileCleanupJob.STATUS_PENDING)
        self.assertEqual(job.attempt_count, 1)
        self.assertEqual(
            job.last_error,
            ERROR_PATH_OUTSIDE_UPLOAD_DIR,
        )
        self.assertIsNone(job.completed_at)
        self.assertTrue(path.exists())

    def test_failure_before_fifth_attempt_stays_pending(self):
        path = self.upload_dir / "io-failure.txt"
        path.write_text("fixture", encoding="utf-8")

        job_id = self.create_job(
            path,
            attempt_count=3,
        )

        with patch(
            "pathlib.Path.unlink",
            side_effect=OSError("simulated failure"),
        ):
            result = process_cleanup_job(job_id)

        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_PENDING)
        self.assertEqual(job.status, FileCleanupJob.STATUS_PENDING)
        self.assertEqual(job.attempt_count, 4)
        self.assertEqual(job.last_error, ERROR_FILE_IO)
        self.assertIsNone(job.completed_at)
        self.assertTrue(path.exists())

    def test_fifth_failure_marks_job_failed(self):
        path = self.upload_dir / "fifth-failure.txt"
        path.write_text("fixture", encoding="utf-8")

        job_id = self.create_job(
            path,
            attempt_count=4,
        )

        with patch(
            "pathlib.Path.unlink",
            side_effect=OSError("simulated failure"),
        ):
            result = process_cleanup_job(job_id)

        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_FAILED)
        self.assertEqual(job.status, FileCleanupJob.STATUS_FAILED)
        self.assertEqual(
            job.attempt_count,
            MAX_CLEANUP_ATTEMPTS,
        )
        self.assertEqual(job.last_error, ERROR_FILE_IO)
        self.assertIsNone(job.completed_at)
        self.assertTrue(path.exists())

    def test_exhausted_pending_job_does_not_attempt_sixth_delete(self):
        path = self.upload_dir / "exhausted.txt"
        path.write_text("fixture", encoding="utf-8")

        job_id = self.create_job(
            path,
            attempt_count=MAX_CLEANUP_ATTEMPTS,
        )

        with patch("pathlib.Path.unlink") as unlink_mock:
            result = process_cleanup_job(job_id)

        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_FAILED)
        self.assertEqual(job.status, FileCleanupJob.STATUS_FAILED)
        self.assertEqual(
            job.attempt_count,
            MAX_CLEANUP_ATTEMPTS,
        )
        self.assertEqual(job.last_error, ERROR_FILE_IO)

        unlink_mock.assert_not_called()
        self.assertTrue(path.exists())

    def test_exhausted_pending_job_with_missing_file_recovers_completed(self):
        path = self.upload_dir / "deleted-before-result-save.txt"

        self.assertFalse(path.exists())

        job_id = self.create_job(
            path,
            attempt_count=MAX_CLEANUP_ATTEMPTS,
        )

        result = process_cleanup_job(job_id)
        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_COMPLETED)
        self.assertEqual(job.status, FileCleanupJob.STATUS_COMPLETED)
        self.assertEqual(
            job.attempt_count,
            MAX_CLEANUP_ATTEMPTS,
        )
        self.assertIsNone(job.last_error)
        self.assertIsNotNone(job.completed_at)

    def test_completed_job_is_not_processed_again(self):
        path = self.upload_dir / "completed.txt"
        path.write_text("fixture", encoding="utf-8")

        job_id = self.create_job(
            path,
            attempt_count=1,
            status=FileCleanupJob.STATUS_COMPLETED,
        )

        with patch("pathlib.Path.unlink") as unlink_mock:
            result = process_cleanup_job(job_id)

        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_COMPLETED)
        self.assertEqual(job.attempt_count, 1)

        unlink_mock.assert_not_called()
        self.assertTrue(path.exists())

    def test_failed_job_is_not_automatically_retried(self):
        path = self.upload_dir / "failed.txt"
        path.write_text("fixture", encoding="utf-8")

        job_id = self.create_job(
            path,
            attempt_count=MAX_CLEANUP_ATTEMPTS,
            status=FileCleanupJob.STATUS_FAILED,
            last_error=ERROR_FILE_IO,
        )

        with patch("pathlib.Path.unlink") as unlink_mock:
            result = process_cleanup_job(job_id)

        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_FAILED)
        self.assertEqual(job.status, FileCleanupJob.STATUS_FAILED)
        self.assertEqual(
            job.attempt_count,
            MAX_CLEANUP_ATTEMPTS,
        )

        unlink_mock.assert_not_called()
        self.assertTrue(path.exists())

    def test_symlink_to_outside_upload_dir_is_not_followed(self):
        outside_dir = Path(self.temp_dir.name) / "outside"
        outside_dir.mkdir()

        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("must survive", encoding="utf-8")

        symlink_path = self.upload_dir / "linked.txt"

        try:
            symlink_path.symlink_to(outside_file)
        except (OSError, NotImplementedError):
            self.skipTest("symlink is not supported")

        job_id = self.create_job(symlink_path)

        result = process_cleanup_job(job_id)
        job = self.get_job(job_id)

        self.assertEqual(result, FileCleanupJob.STATUS_PENDING)
        self.assertEqual(job.attempt_count, 1)
        self.assertEqual(
            job.last_error,
            ERROR_PATH_OUTSIDE_UPLOAD_DIR,
        )

        self.assertTrue(outside_file.exists())
        self.assertTrue(symlink_path.is_symlink())


if __name__ == "__main__":
    unittest.main()

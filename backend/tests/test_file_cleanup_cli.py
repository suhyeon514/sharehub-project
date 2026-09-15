import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import FileCleanupJob
from app.services.file_cleanup import (
    ERROR_FILE_IO,
    MAX_CLEANUP_ATTEMPTS,
)


class FileCleanupCliTests(unittest.TestCase):
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

        self.runner = self.app.test_cli_runner()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

        self.ctx.pop()
        self.temp_dir.cleanup()

    def create_job(
        self,
        filename,
        *,
        status=FileCleanupJob.STATUS_PENDING,
        attempt_count=0,
        last_error=None,
        create_file=True,
    ):
        path = self.upload_dir / filename

        if create_file:
            path.write_text("fixture", encoding="utf-8")

        job = FileCleanupJob(
            document_id_snapshot=999999,
            file_path=str(path),
            status=status,
            attempt_count=attempt_count,
            last_error=last_error,
        )

        db.session.add(job)
        db.session.commit()

        return job.id, path

    def get_job(self, job_id):
        db.session.expire_all()
        return db.session.get(FileCleanupJob, job_id)

    def test_normal_command_processes_pending_job_once(self):
        job_id, path = self.create_job("pending.txt")

        # SQLite에는 MariaDB GET_LOCK이 없으므로
        # CLI가 안전한 service entry point를 호출하는지만 격리해 검증한다.
        with patch(
            "app.cli.process_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_PENDING,
        ) as process_mock:
            result = self.runner.invoke(
                args=["cleanup-files"]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("processed=1", result.output)

        process_mock.assert_called_once_with(job_id)

        # mock이므로 실제 파일/DB 상태는 변경되지 않는다.
        self.assertTrue(path.exists())

    def test_normal_command_processes_each_pending_job_once(self):
        job1, _ = self.create_job("one.txt")
        job2, _ = self.create_job("two.txt")

        with patch(
            "app.cli.process_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_PENDING,
        ) as process_mock:
            result = self.runner.invoke(
                args=["cleanup-files"]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("processed=2", result.output)

        self.assertEqual(
            process_mock.call_count,
            2,
        )

        called_ids = [
            call.args[0]
            for call in process_mock.call_args_list
        ]

        self.assertEqual(
            called_ids,
            [job1, job2],
        )

    def test_normal_command_does_not_select_failed_job(self):
        job_id, _ = self.create_job(
            "failed.txt",
            status=FileCleanupJob.STATUS_FAILED,
            attempt_count=MAX_CLEANUP_ATTEMPTS,
            last_error=ERROR_FILE_IO,
        )

        with patch(
            "app.cli.process_cleanup_job_safely"
        ) as process_mock:
            result = self.runner.invoke(
                args=["cleanup-files"]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("processed=0", result.output)

        process_mock.assert_not_called()

        job = self.get_job(job_id)
        self.assertEqual(
            job.status,
            FileCleanupJob.STATUS_FAILED,
        )

    def test_locked_pending_job_is_counted_as_locked(self):
        job_id, _ = self.create_job("locked.txt")

        with patch(
            "app.cli.process_cleanup_job_safely",
            return_value="locked",
        ) as process_mock:
            result = self.runner.invoke(
                args=["cleanup-files"]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("processed=0", result.output)
        self.assertIn("locked=1", result.output)
        self.assertIn("errors=0", result.output)

        process_mock.assert_called_once_with(job_id)

    def test_resume_calls_safe_resume_service(self):
        job_id, _ = self.create_job(
            "resume.txt",
            status=FileCleanupJob.STATUS_FAILED,
            attempt_count=MAX_CLEANUP_ATTEMPTS,
            last_error=ERROR_FILE_IO,
        )

        with patch(
            "app.cli.resume_cleanup_job_safely",
            return_value=FileCleanupJob.STATUS_COMPLETED,
        ) as resume_mock:
            result = self.runner.invoke(
                args=[
                    "cleanup-files",
                    "--resume",
                    str(job_id),
                ]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            f"cleanup job {job_id}: completed",
            result.output,
        )

        resume_mock.assert_called_once_with(job_id)

    def test_resume_not_found_is_rejected(self):
        with patch(
            "app.cli.resume_cleanup_job_safely",
            return_value="not_found",
        ):
            result = self.runner.invoke(
                args=[
                    "cleanup-files",
                    "--resume",
                    "999999",
                ]
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "cleanup job not found",
            result.output,
        )

    def test_resume_non_failed_job_is_rejected(self):
        job_id, _ = self.create_job("pending-resume.txt")

        with patch(
            "app.cli.resume_cleanup_job_safely",
            return_value="not_failed",
        ):
            result = self.runner.invoke(
                args=[
                    "cleanup-files",
                    "--resume",
                    str(job_id),
                ]
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "only failed cleanup jobs can be resumed",
            result.output,
        )

    def test_resume_locked_job_is_rejected(self):
        job_id, _ = self.create_job(
            "locked-resume.txt",
            status=FileCleanupJob.STATUS_FAILED,
            attempt_count=MAX_CLEANUP_ATTEMPTS,
            last_error=ERROR_FILE_IO,
        )

        with patch(
            "app.cli.resume_cleanup_job_safely",
            return_value="locked",
        ):
            result = self.runner.invoke(
                args=[
                    "cleanup-files",
                    "--resume",
                    str(job_id),
                ]
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "cleanup job is already being processed",
            result.output,
        )

    def test_normal_command_continues_after_one_job_error(self):
        job1, _ = self.create_job("error.txt")
        job2, _ = self.create_job("success.txt")

        def process(job_id):
            if job_id == job1:
                raise RuntimeError("simulated failure")

            return FileCleanupJob.STATUS_COMPLETED

        with patch(
            "app.cli.process_cleanup_job_safely",
            side_effect=process,
        ):
            result = self.runner.invoke(
                args=["cleanup-files"]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("processed=1", result.output)
        self.assertIn("errors=1", result.output)

    def test_resume_option_rejects_zero(self):
        result = self.runner.invoke(
            args=[
                "cleanup-files",
                "--resume",
                "0",
            ]
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)


if __name__ == "__main__":
    unittest.main()

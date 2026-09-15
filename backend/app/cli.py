import click
from flask import current_app
from flask.cli import with_appcontext

from app.extensions import db
from app.models import FileCleanupJob
from app.services.file_cleanup import (
    process_cleanup_job_safely,
    resume_cleanup_job_safely,
)



@click.command("cleanup-files")
@click.option(
    "--resume",
    "resume_job_id",
    type=click.IntRange(min=1),
    default=None,
    help="Restart one explicitly specified failed cleanup job.",
)
@with_appcontext
def cleanup_files_command(resume_job_id):
    """
    Process pending physical-file cleanup jobs.

    일반 실행에서는 현재 pending job을 각각 최대 한 번 처리한다.
    --resume 사용 시 지정된 failed job만 새 retry cycle로 재개한다.
    """

    # ---------------------------------------------------------
    # 명시적 failed job resume
    # ---------------------------------------------------------
    if resume_job_id is not None:
        try:
            result = resume_cleanup_job_safely(
                resume_job_id
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "cleanup processing failed after resume"
            )
            raise click.ClickException(
                "cleanup processing failed"
            )

        if result == "not_found":
            raise click.ClickException(
                "cleanup job not found"
            )

        if result == "not_failed":
            raise click.ClickException(
                "only failed cleanup jobs can be resumed"
            )

        if result == "locked":
            raise click.ClickException(
                "cleanup job is already being processed"
            )

        click.echo(
            f"cleanup job {resume_job_id}: {result}"
        )
        return

    # ---------------------------------------------------------
    # 일반 실행
    #
    # 실행 시작 시점에 pending이었던 ID만 snapshot으로 가져온다.
    # 각 job은 이번 CLI invocation에서 최대 한 번만 처리한다.
    # ---------------------------------------------------------
    try:
        pending_job_ids = [
            job_id
            for (job_id,) in (
                db.session.query(FileCleanupJob.id)
                .filter(
                    FileCleanupJob.status
                    == FileCleanupJob.STATUS_PENDING
                )
                .order_by(FileCleanupJob.id.asc())
                .all()
            )
        ]
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "failed to load pending cleanup jobs"
        )
        raise click.ClickException(
            "failed to load cleanup jobs"
        )

    processed = 0
    locked = 0
    errors = 0

    for job_id in pending_job_ids:
        try:
            result = process_cleanup_job_safely(job_id)

            if result == "locked":
                locked += 1
                continue

            processed += 1

        except Exception:
            db.session.rollback()
            errors += 1

            # 실제 path나 raw exception은 CLI로 출력하지 않는다.
            current_app.logger.exception(
                "cleanup job processing failed: job_id=%s",
                job_id,
            )

    click.echo(
        "cleanup-files finished: "
        f"processed={processed}, "
        f"locked={locked}, "
        f"errors={errors}"
    )


def register_cli(app):
    app.cli.add_command(cleanup_files_command)

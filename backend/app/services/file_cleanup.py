"""
삭제된 문서의 실제 파일을 정리하는 공통 서비스.

계약
- DB 문서 삭제와 실제 파일 삭제를 분리한다.
- cleanup job은 pending / completed / failed 상태를 사용한다.
- 한 retry cycle의 최대 시도 횟수는 5회다.
- 실제 파일 처리 전에 attempt_count를 별도 transaction으로 기록한다.
- 파일이 이미 없으면 성공(completed)으로 간주한다.
- UPLOAD_DIR 밖의 경로는 절대 삭제하지 않는다.
- 실제 경로나 raw exception은 job.last_error에 저장하지 않는다.

주의
- 동일 job의 프로세스 간 중복 실행 방지는 별도 advisory-lock 계층에서 담당한다.
"""

import os
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import FileCleanupJob


MAX_CLEANUP_ATTEMPTS = 5

ERROR_PERMISSION_DENIED = "PERMISSION_DENIED"
ERROR_FILE_IO = "FILE_IO_ERROR"
ERROR_PATH_OUTSIDE_UPLOAD_DIR = "PATH_OUTSIDE_UPLOAD_DIR"

LOCK_PREFIX = "sharehub:file-cleanup:"


def _cleanup_lock_name(job_id):
    return f"{LOCK_PREFIX}{int(job_id)}"


def _acquire_cleanup_lock(connection, job_id):
    """
    MariaDB/MySQL named advisory lock을 즉시 획득한다.

    timeout=0이므로 다른 실행자가 이미 같은 job을 처리 중이면
    기다리지 않고 False를 반환한다.
    """
    result = connection.execute(
        db.text("SELECT GET_LOCK(:name, 0)"),
        {"name": _cleanup_lock_name(job_id)},
    ).scalar()

    return result == 1


def _release_cleanup_lock(connection, job_id):
    """
    GET_LOCK을 획득했던 동일 DB connection에서 lock을 해제한다.
    """
    result = connection.execute(
        db.text("SELECT RELEASE_LOCK(:name)"),
        {"name": _cleanup_lock_name(job_id)},
    ).scalar()

    return result == 1


def _resolved_upload_dir():
    """
    현재 설정의 UPLOAD_DIR을 canonical absolute path로 반환한다.
    """
    return Path(
        os.path.abspath(current_app.config["UPLOAD_DIR"])
    ).resolve()


def _validated_cleanup_path(file_path):
    """
    cleanup 대상이 UPLOAD_DIR 내부인지 확인한다.

    resolve(strict=False)를 사용해 파일이 이미 없어도 경로를 검증한다.
    symlink가 존재하는 경우 실제 target까지 resolve되므로,
    UPLOAD_DIR 밖을 가리키는 symlink도 거부된다.
    """
    upload_dir = _resolved_upload_dir()

    try:
        target = Path(file_path).resolve(strict=False)
        target.relative_to(upload_dir)
    except (OSError, RuntimeError, ValueError):
        return None

    # UPLOAD_DIR 자체를 삭제 대상으로 취급하지 않는다.
    if target == upload_dir:
        return None

    return target


def _mark_completed(job_id):
    job = db.session.get(FileCleanupJob, job_id)

    if job is None:
        return False

    job.status = FileCleanupJob.STATUS_COMPLETED
    job.last_error = None
    job.completed_at = db.func.now()

    db.session.commit()
    return True


def _mark_failure(job_id, error_code):
    job = db.session.get(FileCleanupJob, job_id)

    if job is None:
        return False

    if job.attempt_count >= MAX_CLEANUP_ATTEMPTS:
        job.status = FileCleanupJob.STATUS_FAILED
    else:
        job.status = FileCleanupJob.STATUS_PENDING

    job.last_error = error_code
    job.completed_at = None

    db.session.commit()
    return True


def _record_attempt(job_id):
    """
    실제 파일 처리 전에 시도 횟수를 먼저 영구 기록한다.

    반환값:
        FileCleanupJob: 시도 가능
        None: job 없음 / pending 아님 / 이미 최대 횟수 도달
    """
    job = db.session.get(FileCleanupJob, job_id)

    if job is None:
        return None

    if job.status != FileCleanupJob.STATUS_PENDING:
        return None

    if job.attempt_count >= MAX_CLEANUP_ATTEMPTS:
        return None

    job.attempt_count += 1

    # 계약상 실제 파일 조작보다 attempt 기록 commit이 먼저 성공해야 한다.
    db.session.commit()

    return job


def _recover_exhausted_job(job):
    """
    pending + attempt_count == 5 상태를 복구한다.

    이는 이전 실행에서 attempt_count commit 후 프로세스가 종료되어
    결과 상태를 저장하지 못했을 수 있는 상태다.

    파일이 이미 없으면 completed.
    파일이 남아 있으면 추가 삭제 시도 없이 failed.
    """
    target = _validated_cleanup_path(job.file_path)

    if target is None:
        _mark_failure(
            job.id,
            ERROR_PATH_OUTSIDE_UPLOAD_DIR,
        )
        return FileCleanupJob.STATUS_FAILED

    try:
        exists = target.exists()
    except OSError:
        _mark_failure(job.id, ERROR_FILE_IO)
        return FileCleanupJob.STATUS_FAILED

    if not exists:
        _mark_completed(job.id)
        return FileCleanupJob.STATUS_COMPLETED

    _mark_failure(job.id, ERROR_FILE_IO)
    return FileCleanupJob.STATUS_FAILED


def process_cleanup_job(job_id):
    """
    cleanup job을 한 번 처리한다.

    주의:
    이 함수는 내부 상태 머신이다.
    DELETE/CLI에서는 직접 호출하지 말고
    process_cleanup_job_safely()를 사용해야 한다.
    """
    # 이전 transaction/session 상태가 남아 있지 않도록
    # 현재 DB 상태를 다시 읽는다.
    db.session.expire_all()

    job = db.session.get(FileCleanupJob, job_id)

    if job is None:
        return None

    if job.status != FileCleanupJob.STATUS_PENDING:
        return job.status

    # 이전 실행이 attempt_count를 commit한 뒤 죽은 경우.
    # 최대 횟수가 이미 소진되었으므로 추가 unlink는 절대 하지 않는다.
    if job.attempt_count >= MAX_CLEANUP_ATTEMPTS:
        return _recover_exhausted_job(job)

    # ---------------------------------------------------------
    # 실제 파일 검사/삭제보다 attempt 기록이 반드시 먼저 commit된다.
    # ---------------------------------------------------------
    attempted_job = _record_attempt(job.id)

    if attempted_job is None:
        db.session.expire_all()

        refreshed = db.session.get(
            FileCleanupJob,
            job.id,
        )

        return refreshed.status if refreshed is not None else None

    # commit 이후 최신 값을 다시 읽는다.
    db.session.expire_all()

    job = db.session.get(
        FileCleanupJob,
        job_id,
    )

    if job is None:
        return None

    target = _validated_cleanup_path(job.file_path)

    if target is None:
        _mark_failure(
            job.id,
            ERROR_PATH_OUTSIDE_UPLOAD_DIR,
        )

        db.session.expire_all()
        refreshed = db.session.get(FileCleanupJob, job.id)

        return refreshed.status if refreshed is not None else None

    try:
        # idempotent cleanup:
        # 이전 실행에서 파일 삭제까지만 성공하고
        # completed 저장 전에 죽은 경우도 여기서 복구된다.
        if not target.exists():
            _mark_completed(job.id)

        else:
            target.unlink()
            _mark_completed(job.id)

    except PermissionError:
        _mark_failure(
            job.id,
            ERROR_PERMISSION_DENIED,
        )

    except OSError:
        _mark_failure(
            job.id,
            ERROR_FILE_IO,
        )

    db.session.expire_all()

    refreshed = db.session.get(
        FileCleanupJob,
        job.id,
    )

    return refreshed.status if refreshed is not None else None


def process_cleanup_job_safely(job_id):
    """
    동일 cleanup job의 프로세스 간 중복 실행을 방지하는 공개 진입점.

    advisory lock은 ORM db.session과 별도의 DB connection에서 유지한다.
    따라서 process_cleanup_job() 내부에서 db.session.commit()이 발생해도
    advisory lock connection의 수명에는 영향을 주지 않는다.
    """
    lock_connection = db.engine.connect()
    acquired = False

    try:
        acquired = _acquire_cleanup_lock(
            lock_connection,
            job_id,
        )

        if not acquired:
            return "locked"

        return process_cleanup_job(job_id)

    finally:
        if acquired:
            try:
                _release_cleanup_lock(
                    lock_connection,
                    job_id,
                )
            except Exception:
                current_app.logger.exception(
                    "failed to release cleanup advisory lock"
                )

        lock_connection.close()

def resume_cleanup_job_safely(job_id):
    """
    failed cleanup job 하나를 명시적으로 새 retry cycle로 재개한다.

    advisory lock을 먼저 획득한 뒤:
    1. 최신 job 상태 확인
    2. failed -> pending 및 cycle 초기화
    3. reset commit
    4. cleanup 1회 처리
    5. advisory lock 해제

    반환:
        "not_found"  : job 없음
        "not_failed" : failed 상태가 아님
        "locked"     : 다른 프로세스가 동일 job 처리 중
        그 외         : cleanup 처리 결과
    """
    lock_connection = db.engine.connect()
    acquired = False

    try:
        acquired = _acquire_cleanup_lock(
            lock_connection,
            job_id,
        )

        if not acquired:
            return "locked"

        # lock 획득 후 반드시 DB 최신 상태를 다시 읽는다.
        db.session.expire_all()

        job = db.session.get(
            FileCleanupJob,
            job_id,
        )

        if job is None:
            return "not_found"

        if job.status != FileCleanupJob.STATUS_FAILED:
            return "not_failed"

        # 새 retry cycle 시작
        job.status = FileCleanupJob.STATUS_PENDING
        job.attempt_count = 0
        job.last_error = None
        job.completed_at = None

        db.session.commit()

        # 이미 동일 advisory lock을 보유 중이므로
        # safely wrapper를 다시 호출하지 않는다.
        return process_cleanup_job(job_id)

    except Exception:
        db.session.rollback()
        raise

    finally:
        if acquired:
            try:
                _release_cleanup_lock(
                    lock_connection,
                    job_id,
                )
            except Exception:
                current_app.logger.exception(
                    "failed to release cleanup advisory lock"
                )

        lock_connection.close()
#!/usr/bin/env python3
"""verify_api.py: 연속 API 검증.

실행 방법과 잔여 데이터 안내: docs/통합_API_검증_실행.md.
삭제 감사 이벤트 이름: DOCUMENT_DELETE.
"""
import argparse
from datetime import datetime, timezone
from contextlib import contextmanager
import getpass
import io
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


SCENARIOS = [
    ("AUTH-01", "Owner / receiver / admin login"),
    ("DOC-01", "Document create and private access"),
    ("SHARE-01", "View share"),
    ("SHARE-02", "Download permission"),
    ("SHARE-03", "Edit permission"),
    ("SHARE-04", "Permission downgrade"),
    ("SEARCH-01", "Shared document search"),
    ("BLOCK-01", "Admin document block and access denial"),
    ("APPEAL-01", "Owner appeal"),
    ("APPEAL-05", "Admin reject"),
    ("APPEAL-03", "Owner re-appeal"),
    ("APPEAL-04", "Admin approve and current permissions"),
    ("DEL-01", "Owner delete"),
    ("DEL-02", "Deleted document inaccessible"),
    ("ADMIN-HIST-01", "Deleted document appeal history API"),
    ("LOG-01", "DOCUMENT_DELETE exactly once"),
    ("AUTH-LOGOUT", "Logout and session invalidation"),
]


class VerificationError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Verifier:
    def __init__(self, base_url=None, client=None):
        self.base_url = base_url
        self.client = client
        self.opener = urllib.request.build_opener(NoRedirect)
        self.tokens = {}
        self.results = []
        self.scenarios = []
        self.active = None
        self.ids = {}
        self.step = "시작"
        self.marker = "verify-" + secrets.token_hex(8)
        self.file_bytes = (self.marker + "\n").encode()

    def finish(self, status="PASS", reason=None):
        if self.active is None:
            return
        identity, title = self.active
        self.scenarios.append({"id": identity, "title": title, "status": status, "reason": reason})
        print(f"[{status}] {identity:<14} {title}")
        if reason:
            print(f"       {reason}")
        self.active = None

    def begin(self, identity):
        self.finish()
        self.active = next(item for item in SCENARIOS if item[0] == identity)
        self.step = identity

    def check(self, condition, message):
        if not condition:
            raise VerificationError(message)

    def call(self, label, method, path, role=None, payload=None, expected=200,
             code=None, upload=False):
        self.step = label
        headers = {}
        if role in self.tokens:
            headers["Authorization"] = "Bearer " + self.tokens[role]
        data = None
        if upload:
            fields = {"title": self.marker, "visibility": "private",
                      "description": "통합 API 검증용 임시 문서"}
            if self.client:
                data = {**fields, "file": (io.BytesIO(self.file_bytes), "verify.txt")}
            else:
                boundary = secrets.token_hex(24)
                parts = []
                for key, value in fields.items():
                    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="verify.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode())
                data = b"".join(parts) + self.file_bytes + f'\r\n--{boundary}--\r\n'.encode()
                headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if self.client:
            response = self.client.open(path, method=method, headers=headers, data=data)
            status, raw = response.status_code, response.data
            content_type = response.content_type
        else:
            request = urllib.request.Request(self.base_url + path, data=data,
                                             headers=headers, method=method)
            try:
                response = self.opener.open(request, timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status, raw = response.status, response.read()
                content_type = response.headers.get("Content-Type", "")
        self.check(status == expected, f"HTTP 예상={expected}, 실제={status}")
        result = json.loads(raw) if "application/json" in content_type and raw else raw
        if code:
            self.check(isinstance(result, dict) and result.get("error", {}).get("code") == code,
                       f"예상 오류 코드 불일치: {code}")
        self.results.append({"step": label, "status": status})
        return result

    def run(self, credentials):
        self.begin("AUTH-01")
        for role, (username, password) in credentials.items():
            result = self.call(f"{role} 로그인", "POST", "/api/auth/login",
                               payload={"username": username, "password": password})
            self.tokens[role] = result["token"]
            self.ids[role] = result["user"]["id"]
            self.check(result["user"]["role"] == ("admin" if role == "admin" else "user"),
                       "계정 역할 불일치")
        self.check(len(set(self.ids.values())) == 3, "서로 다른 세 계정이 필요합니다")
        self.begin("DOC-01")
        doc = self.call("문서 생성", "POST", "/api/documents", "owner", expected=201, upload=True)
        self.ids["document"] = doc["document"]["id"]
        path = f'/api/documents/{self.ids["document"]}'
        self.call("비공유 사용자 접근 거부", "GET", path, "receiver", expected=404)
        self.call("관리자 내용 접근 거부", "GET", path, "admin", expected=404)
        self.begin("SHARE-01")
        share = self.call("view 공유", "POST", path + "/shares", "owner",
                          {"shared_with_id": self.ids["receiver"], "permission": "view"}, 201)
        share_path = path + f'/shares/{share["share"]["id"]}'
        self.call("view 조회", "GET", path, "receiver")
        self.call("view 댓글 작성", "POST", path + "/comments", "receiver",
                  {"content": self.marker}, 201)
        for index, permission in enumerate(("view", "download", "edit", "view")):
            if index:
                self.begin(f"SHARE-0{index + 1}")
            self.call(f"권한 저장 {permission}", "PATCH", share_path, "owner", {"permission": permission})
            download = self.call(f"{permission} 다운로드", "GET", path + "/download", "receiver",
                                 expected=403 if permission == "view" else 200)
            if permission != "view":
                self.check(download == self.file_bytes, "다운로드 파일 내용 불일치")
            self.call(f"{permission} 수정", "PATCH", path, "receiver",
                      {"description": "검증 중 수정"}, 200 if permission == "edit" else 403)
            if permission == "edit":
                detail = self.call("수정 내용 재조회", "GET", path, "owner")
                self.check(detail["data"]["description"] == "검증 중 수정", "수정 미반영")
                self.call("edit 재공유 거부", "GET", path + "/shares", "receiver", expected=403)
                self.call("edit 삭제 거부", "DELETE", path, "receiver", expected=403)
        self.begin("SEARCH-01")
        search_path = "/api/search?q=" + urllib.parse.quote(self.marker)
        found = self.call("공유 문서 검색", "GET", search_path, "receiver")
        self.check(any(item["id"] == self.ids["document"] for item in found["items"]), "검색 결과에서 공유 문서 누락")
        self.begin("BLOCK-01")
        block = self.call("관리자 차단", "POST", f'/api/admin/documents/{self.ids["document"]}/blocks',
                          "admin", {"block_reason": "자동 검증", "block_basis": "검증용 내부 근거"}, 201)
        self.ids["block"] = block["block"]["id"]
        for role in ("owner", "receiver"):
            for method, suffix, payload in (("GET", "", None), ("GET", "/download", None),
                                            ("GET", "/comments", None), ("POST", "/comments", {"content": "금지"}),
                                            ("PATCH", "", {"title": "금지"}), ("GET", "/shares", None),
                                            ("DELETE", "", None)):
                self.call(f"차단 {role} {method} {suffix or '문서'}", method, path + suffix,
                          role, payload, 403, "DOCUMENT_BLOCKED")
        for role in ("owner", "receiver"):
            found = self.call("차단 문서 검색 제외", "GET", search_path, role)
            self.check(not any(item["id"] == self.ids["document"] for item in found["items"]), "차단 문서 검색 노출")
        owner_status = self.call("소유자 차단 상태", "GET", f'/api/my/document-blocks/{self.ids["block"]}', "owner")
        self.check("block_basis" not in json.dumps(owner_status), "소유자 응답 내부 근거 노출")
        appeal_path = f'/api/document-blocks/{self.ids["block"]}/unblock-requests'
        request_ids = []
        for decision in ("rejected", "approved"):
            self.begin("APPEAL-01" if decision == "rejected" else "APPEAL-03")
            appeal = self.call("소명" if not request_ids else "재소명", "POST", appeal_path,
                               "owner", {"reason": "자동 검증 소명"}, 201)
            request_id = appeal["data"]["id"]
            self.check(request_id not in request_ids, "재소명 ID가 기존 요청과 동일")
            request_ids.append(request_id)
            self.ids["requests"] = request_ids
            self.call("중복 소명 거부", "POST", appeal_path, "owner", {"reason": "중복"},
                      409, "UNBLOCK_REQUEST_ALREADY_PENDING")
            review_path = f"/api/admin/unblock-requests/{request_id}/review"
            self.begin("APPEAL-05" if decision == "rejected" else "APPEAL-04")
            review = self.call(decision, "POST", review_path, "admin",
                               {"decision": decision, "review_comment": "자동 검증 심사"})
            self.check(review["unblock_request"]["status"] == decision, "심사 상태 불일치")
            self.check(review["block"]["status"] == ("blocked" if decision == "rejected" else "unblocked"),
                       "차단 상태 불일치")
            self.call("중복 심사 거부", "POST", review_path, "admin",
                      {"decision": decision, "review_comment": "중복"}, 409)
            self.call("심사 후 접근", "GET", path, "receiver", expected=403 if decision == "rejected" else 200)
        self.call("승인 후 현재 view 다운로드 거부", "GET", path + "/download", "receiver", expected=403)
        self.call("승인 후 현재 view 수정 거부", "PATCH", path, "receiver", {"title": "금지"}, 403)
        self.begin("DEL-01")
        self.call("소유자 삭제", "DELETE", path, "owner", expected=204)
        self.begin("DEL-02")
        for role in ("owner", "receiver", "admin"):
            for suffix in ("", "/download", "/comments", "/shares"):
                self.call(f"삭제 후 {role} {suffix or '상세'}", "GET", path + suffix, role, expected=404)
        self.call("재삭제", "DELETE", path, "owner", expected=404, code="DOCUMENT_NOT_FOUND")
        self.begin("ADMIN-HIST-01")
        history = self.call("관리자 소명 이력 목록", "GET",
                            f'/api/admin/unblock-requests?block_id={self.ids["block"]}', "admin")
        self.check({item["id"] for item in history["items"]} == set(request_ids), "소명 이력 누락")
        for request_id in request_ids:
            history = self.call("삭제 후 소명 상세", "GET", f"/api/admin/unblock-requests/{request_id}", "admin")
            self.check(history["document"]["deleted"] and not history["can_review"], "삭제 이력 상태 불일치")
            self.check(history["document"]["id"] == self.ids["document"], "문서 ID 이력 불일치")
        self.begin("LOG-01")
        logs = []
        page = 1
        while True:
            result = self.call(f"관리자 삭제 로그 {page}페이지", "GET",
                               f"/api/admin/activity-logs?q=DOCUMENT_DELETE&per_page=100&page={page}", "admin")
            logs.extend(item for item in result["items"] if item["detail"].get("document_id") == self.ids["document"])
            if page * 100 >= result["pagination"]["total"]:
                break
            page += 1
        self.check(len(logs) == 1 and logs[0]["action_type"] == "DOCUMENT_DELETE", "삭제 감사 로그 1건 조건 불일치")


@contextmanager
def isolated():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import create_app
    from app.extensions import db
    from app.models import User
    from werkzeug.security import generate_password_hash
    from unittest.mock import patch

    with tempfile.TemporaryDirectory(prefix="sharehub-verify-") as directory:
        app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + directory + "/verify.db",
                          "UPLOAD_DIR": directory + "/uploads"})
        credentials = {}
        with app.app_context():
            db.create_all()
            for role in ("owner", "receiver", "admin"):
                password = secrets.token_urlsafe(24)
                credentials[role] = ("verify_" + role, password)
                db.session.add(User(username="verify_" + role, password_hash=generate_password_hash(password),
                                    role="admin" if role == "admin" else "user"))
            db.session.commit()
        try:
            # MariaDB GET_LOCK은 SQLite에서 실행할 수 없다. 파일 정리는
            # 검증 범위에서 제외하고 임시 디렉터리 종료 시 정리한다.
            with patch("app.routes.documents.process_cleanup_job_safely"):
                yield Verifier(client=app.test_client()), credentials
        finally:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


def execute(verifier, credentials, report):
    report_path = Path(report)
    # 결과 파일 위치를 실행 전에 준비한다.
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if verifier.client is not None:
        environment_note = "Environment: Temporary SQLite; IDs belong to this isolated run, not the configured server DB."
        cleanup_note = "Immediate cleanup: mocked (not verified)."
    else:
        environment_note = "Environment: Target HTTP server; IDs belong to its connected DB."
        cleanup_note = "Immediate cleanup: not mocked by verifier; completion not verified."
    print("=" * 64)
    print("ShareHub Integration Verification")
    print("Mode: " + ("isolated (SQLite / Flask test client)" if verifier.client else "HTTP"))
    print("Run: " + verifier.marker)
    print(environment_note)
    print(cleanup_note)
    print("=" * 64 + "\n")
    failure = None
    try:
        verifier.run(credentials)
        verifier.finish()
    except Exception as error:
        reason = str(error) if isinstance(error, VerificationError) else type(error).__name__
        failure = {"step": verifier.step, "reason": reason}
        verifier.finish("FAIL", verifier.step + ": " + reason)
    completed = {row["id"] for row in verifier.scenarios}
    for identity, title in SCENARIOS[:-1]:
        if identity not in completed:
            verifier.active = (identity, title)
            verifier.finish("SKIP", "선행 시나리오 실패로 실행하지 않음")
    verifier.begin("AUTH-LOGOUT")
    logout_errors = []
    for role in list(verifier.tokens):
        try:
            verifier.call(f"{role} 로그아웃", "POST", "/api/auth/logout", role)
            verifier.call(f"{role} 세션 종료 확인", "GET", "/api/auth/me", role, expected=401)
        except Exception:
            logout_errors.append(role)
    if logout_errors:
        reason = "세션 종료 확인 실패: " + ", ".join(logout_errors)
        verifier.finish("FAIL", reason)
        failure = failure or {"step": "AUTH-LOGOUT", "reason": reason}
    elif verifier.tokens:
        verifier.finish()
    else:
        verifier.finish("SKIP", "로그인된 세션 없음")
    counts = {status: sum(row["status"] == status for row in verifier.scenarios)
              for status in ("PASS", "FAIL", "SKIP")}
    passed = counts["FAIL"] == 0 and counts["SKIP"] == 0
    result = {"mode": "isolated" if verifier.client else "http", "run": verifier.marker,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "passed": passed, "counts": counts, "scenarios": verifier.scenarios,
              "ids": verifier.ids, "checks": verifier.results, "failure": failure,
              "not_verified": ["물리 파일 cleanup 완료", "DB 동시성", "브라우저 UI"],
              "immediate_cleanup_mocked": verifier.client is not None}
    lines = ["=" * 64, "ShareHub Integration Verification", "Mode: " + result["mode"],
             "Run: " + verifier.marker, environment_note, cleanup_note, "=" * 64, ""]
    for row in verifier.scenarios:
        lines.append(f'[{row["status"]}] {row["id"]:<14} {row["title"]}')
        if row["reason"]:
            lines.append("       " + row["reason"])
    summary = ["", "-" * 64, *(f"{status} : {counts[status]}" for status in counts),
               "-" * 64, "RESULT: " + ("PASS" if passed else "FAIL"),
               "Scope: API scenarios only; cleanup / concurrency / browser UI excluded."]
    lines.extend(summary)
    lines.append("IDs: " + json.dumps(verifier.ids, ensure_ascii=False))
    text_path = report_path.with_suffix(".txt")
    if text_path == report_path:
        text_path = Path(str(report_path) + ".txt")
    try:
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        print("RESULT: FAIL (결과 파일 저장 실패)")
        return 1
    print("\n".join(summary))
    print("JSON: " + str(report_path))
    print("TEXT: " + str(text_path))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--isolated", action="store_true", help="임시 SQLite와 Flask test client 사용")
    group.add_argument("--base-url", help="테스트 API 서버 주소, 예: http://localhost:8000")
    parser.add_argument("--report", help="JSON 결과 저장 경로 (기본: 실행 위치의 verify-results/, TXT도 저장)")
    args = parser.parse_args()
    if not args.report:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.report = str(Path.cwd() / "verify-results" /
                          f"verify-{stamp}-{secrets.token_hex(3)}.json")
    if args.isolated:
        with isolated() as (verifier, credentials):
            return execute(verifier, credentials, args.report)
    url = urllib.parse.urlsplit(args.base_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
        parser.error("base-url은 인증정보·경로·쿼리 없는 http(s) 서버 주소여야 합니다")
    credentials = {}
    print("지정 서버에 테스트 문서·공유·차단·소명·감사 이력을 생성합니다. 성공 시 문서는 삭제되고 이력은 남습니다.")
    for role in ("owner", "receiver", "admin"):
        prefix = "VERIFY_" + role.upper()
        username = os.environ.get(prefix + "_USERNAME") or input(f"{role} 테스트 아이디: ").strip()
        password = os.environ.get(prefix + "_PASSWORD") or getpass.getpass(f"{role} 테스트 비밀번호: ")
        credentials[role] = (username, password)
    return execute(Verifier(base_url=args.base_url.rstrip("/")), credentials, args.report)


if __name__ == "__main__":
    sys.exit(main())

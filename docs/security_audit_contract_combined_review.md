# Security Audit 계약 검증기 결합 리뷰

검증일: 2026-10-13 (Asia/Seoul)
검증 브랜치 / 기준 커밋: fix/security-audit-contract-validation / 338a042
로컬 결합 내용: 기존 API 행렬 26개 + 실제 API 계약 검증 실패 안전성 1개 추가. 미커밋 변경이며 앱 구현 변경 없음.

## 결과

팀원 검증기와 26개 API 사례를 합친 최초 실행: 전체 170개 OK.
실제 GET 요청 중 validate_event에 AuditContractError를 주입하는 사례를 추가했다. 200과 원래 문서 응답 유지, 정상 감사 JSON 미출력, 별도 기록 오류와 request_id 연결을 검사한다.
최종 실행: 통합 테스트 35개, 전체 unittest 171개 모두 통과(팀원 기준 143개 + API 행렬 26개 + 로컬 동등 unittest 1개 + 실제 요청 검증 실패 1개).

## 실행

```bash
cd backend
venv/bin/python -m unittest discover -s tests -p test_security_audit_detail_integration.py -v
venv/bin/python -m unittest discover -s tests -v
```

테스트는 INFO 레벨을 설정하지 않는다. 인메모리 SQLite / Flask 실제 라우트 요청 및 독립 프로세스로 검증한다. 인증 없음·무효·만료, 실제 문서 없음·접근 없음, owner/team/share, team/share 우선순위, 부서 NULL, 차단, private 관리자, 예외 안전성을 포함한다.

## 리뷰 의견

### resource.id=0 — 머지 전 계약 차이 해결 필요

확정 계약은 정수 ID로 라우팅된 문서 API를 대상으로 요청한 정수 ID를 유지한다고 정의하며 양수 제한을 명시하지 않는다. Flask는 /api/documents/0을 실제 상세 라우트로 처리한다.

실제 무인증 GET /api/documents/0 결과: 401, X-Request-ID 있음, 감사 JSON 0건. 앱의 초기화 조건 id > 0 때문에 기록되지 않는다. 검증기도 resource.id > 0 조건으로 0을 거부한다.

권장: 기존 HTTP 동작은 유지하고 endpoint/라우트 인자로 감사 대상을 식별한다. 요청 ID 0을 유지하도록 검증기를 조정하고 0의 무인증/인증 후 미존재 사례를 추가한다. 양수만 허용하려면 기존 계약의 범위를 변경하는 별도 합의가 필요하다. 이번 리뷰에서는 앱 코드를 수정하지 않았다.

### 상세 조회에서 발생하지 않는 두 코드

INSUFFICIENT_DOCUMENT_PERMISSION / DOCUMENT_OWNER_REQUIRED가 11개 카탈로그에 포함되면서 상세 view 거부 조합에서는 거부되는 것은 현재 범위에 맞는다. 상세 API에서 억지로 발생시킬 필요는 없다.

다운로드/PATCH/공유/DELETE 확대 시 action과 required_permission 매핑 및 등급 부족/비소유자 조건을 검증기에 추가한다. owner는 정책 조건이며 권한 등급에 추가하지 않는다. view/share 등 현재 상세 검증 규칙을 그대로 다른 API에 적용하면 안 된다.

### outcome 확장 주의

현재 검증기와 emit_detail은 outcome을 status < 400으로 연결한다. 이번 실제 응답 사례에서는 일치하지만 원본 계약은 outcome을 작업의 정상 완료 여부로 정의한다. 다른 API 확대 시 작업 결과를 명시적으로 표현하고 HTTP만으로 인가나 완료 여부를 역산하지 않도록 검토한다.

## 완료 범위

검사한 사례의 회귀 통과와 전체 계약 구현 완료를 구분한다. 실제 네트워크 HTTP·MariaDB 잠금/제약·브라우저 및 ID 0 경로의 계약 적합성은 이번 통과 결과로 완료 처리하지 않는다. ID 0 차이를 해결한 뒤 PR 재검증을 권장한다.

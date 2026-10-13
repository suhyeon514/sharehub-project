# Security Audit ID 0 통합 검증

검증일: 2026-10-13 (Asia/Seoul)
브랜치 / 앱 기준 커밋: fix/security-audit-contract-validation / f675c0c
로컬 변경: 26개 API 행렬, 실제 API 검증기 실패 1개, ID 0 경계값 2개가 포함된 미커밋 통합 테스트. 앱 구현은 추가 수정하지 않았다.

## 검증 방법

격리 SQLite에 사용자와 인증 세션을 생성하고 독립 프로세스에서 실제 Flask 상세 라우트를 호출했다. 테스트에서 INFO 레벨이나 기본 로거 설정을 켜지 않는다. 출력 JSON과 응답 및 HTTP 로그의 request_id를 대조했다. 네트워크 서버를 띄운 검증과는 구분한다.

```bash
cd backend
venv/bin/python -m unittest discover -s tests -p test_security_audit_detail_integration.py -v
venv/bin/python -m unittest discover -s tests -v
```

개별 실행 증거:

```bash
venv/bin/python tests/test_security_audit_detail_integration.py --probe id_zero_unauthenticated
venv/bin/python tests/test_security_audit_detail_integration.py --probe id_zero_authenticated
```

## 경계값 기대 및 검사 내용

| 요청 | HTTP | event_type | actor | evaluated / decision | reason_code |
| --- | --- | --- | --- | --- | --- |
| 무인증 GET /api/documents/0 | 401 | authentication | null | false / not_evaluated | AUTHENTICATION_REQUIRED |
| 인증 후 GET /api/documents/0 | 404 | document.lookup | 인증 사용자 ID | false / not_evaluated | DOCUMENT_NOT_FOUND |

두 경우 모두 resource.id=0을 유지하고 source/permission은 null이다. 응답 헤더·HTTP 로그·감사 JSON의 ID가 동일한 서버 UUIDv4이고, 외부 요청 ID를 사용하지 않음을 확인한다. 캡처 핸들러와 실제 표준 스트림에 각각 JSON 1건, 별도 감사 오류 없음, 필드·자료형·UTC Z timestamp·금지정보 제외를 검사한다. 인증 후 응답의 기존 DOCUMENT_NOT_FOUND 오류도 검사한다.

## 코드 리뷰

초기화가 documents.get_document_detail endpoint와 document_id 라우트 인자를 사용하도록 바뀌었다. 검증기는 정수 ID 0을 허용하고 음수와 bool은 거부한다. 기존 Flask 기본 int 라우트의 비음수 대상과 일치하며 기존 응답을 바꾸지 않는다. 이전 ID 0 감사 누락 지적에 대한 수정 방향이 적절하다.

## 완료 범위

아래 실행 결과는 격리 SQLite / Flask 테스트 클라이언트 기준이다. 실제 MariaDB 잠금·제약, 네트워크 HTTP, 브라우저, 다른 작업 API의 계약 완성을 증명하지 않는다. 이번 요청에서는 커밋·push·PR 생성·병합을 수행하지 않았다. 로컬 추가 테스트가 원격 PR에 포함되어야 CI에서도 같은 범위를 검증할 수 있다.

## 실행 결과

통합 테스트 37개 모두 통과. 전체 unittest 175개 통과. 팀원 기준 145개 + 기존 로컬 추가 28개 + 이번 ID 0 API 사례 2개 = 175개. 이전 338a042 결합 171개에서 팀원 단위 2개와 본인 통합 2개가 증가했다.

공유 요약: f675c0c를 반영해 인증 후 ID 0의 404 / DOCUMENT_NOT_FOUND와 무인증 401을 실제 요청으로 확인했다. 두 경우 JSON 1건 및 resource.id=0, request_id 연결이 정상이다. 이전 ID 0 계약 차이가 해결되었다. 로컬 테스트를 공유한 뒤 동일 코드 기준 PR 리뷰·머지 단계로 진행할 수 있다.

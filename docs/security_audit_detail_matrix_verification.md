# Security Audit 상세 조회 통합 검증 결과

검증일: 2026-10-13 (Asia/Seoul)
기준 브랜치·커밋: feature/security-audit-v1 / 74bb069
변경: 미커밋 상태의 test_security_audit_detail_integration.py 확장. 앱 코드·DB migration 변경 없음.

## 검증 방법

인메모리 SQLite에 테스트 사용자·부서·세션·문서·공유·차단을 구성하고 실제 GET /api/documents/{id}를 호출했다. 각 사례는 독립 프로세스로 실행한다. 테스트에서 로거 INFO 레벨이나 basicConfig를 설정하지 않는다. 캡처한 감사 JSON과 기본 표준 스트림의 JSON을 확인한다. 정상 종료 사례는 두 경로에서 각각 이벤트 1건을 확인한다.

```bash
cd backend
venv/bin/python -m unittest discover -s tests -p test_security_audit_detail_integration.py -v
venv/bin/python -m unittest discover -s tests -v
```

개별 사례의 실제 JSON·HTTP·오류 기록을 확인하는 예:

```bash
venv/bin/python tests/test_security_audit_detail_integration.py --probe auth_expired
venv/bin/python tests/test_security_audit_detail_integration.py --probe team_share_download
venv/bin/python tests/test_security_audit_detail_integration.py --probe blocked_unrelated
```

## 인증·인가 결과

| 사례 | 개수 | HTTP / 기대 reason_code | 결과 |
| --- | ---: | --- | --- |
| 인증 없음·무효·만료 | 3 | 401 / AUTHENTICATION_REQUIRED | 통과 |
| 실제 문서 없음 | 1 | 404 / DOCUMENT_NOT_FOUND | 통과 |
| 정상 문서 접근 없음 | 1 | 404 / NO_DOCUMENT_ACCESS | 통과 |
| 소유자 | 1 | 200 / DOCUMENT_OWNER_ACCESS | 통과 |
| 동일 비NULL 부서 team | 1 | 200 / TEAM_DEPARTMENT_VIEW | 통과 |
| private 동일 부서, team 다른 부서, 요청자·문서·양쪽 부서 NULL | 5 | 404 / NO_DOCUMENT_ACCESS | 통과 |
| 개별 share view/download/edit | 3 | 200 / 해당 DIRECT_SHARE 코드 | 통과 |
| team + share view/download/edit | 3 | view는 team 우선, download/edit는 share 우선 | 통과 |
| 관리자 역할만 가진 private 접근 | 1 | 404 / NO_DOCUMENT_ACCESS | 통과 |
| 차단 owner/team/share 각 등급 | 5 | 403 / DOCUMENT_ACCESS_BLOCKED, 계산된 근거 유지 | 통과 |
| 차단 무관 사용자·private 관리자 | 2 | 404 / NO_DOCUMENT_ACCESS, 차단 비노출 | 통과 |

총 26개 행렬 사례에서 정확한 키 구조·16개 말단 필드 값과 자료형·null·인가 평가/decision·결과·UTC Z timestamp·UUIDv4를 확인했다. 응답 헤더·HTTP 로그·감사 JSON의 request_id 일치 및 외부 ID로 대체되지 않음을 확인했다. 감사 JSON에 테스트 토큰·제목·설명·파일 경로·파일명·block_basis 표식이 없음을 확인했다.

기존 정상 출력·계약 검사 3개와 예외 검사 5개도 유지한다. 예외 검사는 조회/인가 미완료 시 audit_incomplete, 허용 후 응답 실패 시 allow + failure/500, 감사 구성/출력 실패 시 정상 200 유지 여부를 확인한다.

## 완료 판단과 남은 범위

통합 테스트 34개 통과, 전체 unittest 143개 통과(기존 117개 + 신규 26개). 상세 조회의 위 인증·접근·차단 및 예외 사례가 확정 계약과 일치했다.

이는 전체 Security Audit 계약 구현 완료를 뜻하지 않는다. 검증기에서 잘못된 자료형·enum·조합을 거부하는 단위 테스트는 팀원 담당이다. 상세 조회에서 발생하지 않는 INSUFFICIENT_DOCUMENT_PERMISSION / DOCUMENT_OWNER_REQUIRED는 다른 작업 API 범위로 남긴다. ID 0 라우트 초기화, 모든 HTTP 재시도 간 새 ID, 전체 부서/공유 교차 조합, 실제 네트워크 HTTP·MariaDB 잠금/제약·브라우저·로그 내구성은 이번 결과로 증명하지 않는다.

팀원 공유: 앱 구현 수정 없이 26개 실제 API 행렬 사례를 추가했고 모두 통과했다. 주원은 계약 검증기·거부 단위 테스트를 진행하고, 이후 함께 최신 코드에서 회귀 검증과 리뷰를 수행한다.

사례별 자동 실행 결과: security_audit_detail_matrix_results.json (로그에서 테스트 이름·결과만 추출; 인증정보 제외).

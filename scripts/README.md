# 로컬 프록시 실행

## 실행 명령

사용자가 입력하는 값은 브랜치 하나뿐이다.

```powershell
# 벤치마크상 후보
.\proxy yh-submission

# 프론티어상 후보
.\proxy yh-submission2
```

버전은 최신 커밋 메시지에서 자동으로 읽는다. 커밋 규칙은
[후보 브랜치 버전·커밋 컨벤션](../docs/evaluations/CONVENTION.md)을 따른다.

스크립트가 자동으로 처리하는 항목은 다음과 같다.

- 원격 브랜치 최신화와 SHA 확정
- 커밋 메시지 컨벤션 검사와 버전 추출
- 빈 포트와 미사용 Lunit API 키 선점
- 임시 worktree 생성과 Docker 빌드
- coverage 32개 scored 평가
- 결과·로그 저장과 컨테이너 정리

2026-08-22부터 기본 프로토콜은 `conquer_val-coverage-32-r1`이다. 공개 메타데이터인
theme, physician-agreed category, axis,
단일/멀티턴과 rubric 개수 구간의 커버리지를 우선하고, 원문이나 개별 rubric 내용은
선정에 사용하지 않는다.

실제 Y2 Trial timeout을 반영해 생성 동시성 4, 개별 요청 120초, 평가 본체 420초 제한을
강제한다. 420초에 남은 문항은 취소·0점 처리되며 결과의 `promotion_eligible`이 false가 된다.
오래 기다려서 완료되는 후보는 공식 평가에 안전한 후보로 인정하지 않는다.

## 병렬 평가

동시에 실행할 터미널 수만큼 서로 다른 키를 루트 `.env`에 준비한다.

```dotenv
LUNIT_FM_API_KEY_1=...
LUNIT_FM_API_KEY_2=...
LUNIT_FM_API_KEY_3=...
HEALTHBENCH_JUDGE_API_KEY=...
```

그다음 터미널을 각각 열어 원하는 브랜치 명령을 실행한다. 같은 브랜치의 새 버전을
평가할 때도 새 터미널에서 같은 명령을 다시 실행하면 된다.

```powershell
# 터미널 1
.\proxy yh-submission
```

```powershell
# 터미널 2
.\proxy yh-submission2
```

각 프로세스는 포트와 키를 겹치지 않게 자동 배정한다. 한 프로세스의 생성 동시성은
4이므로 터미널 두 개는 최대 여덟 개의 후보 API 요청을 동시에 보낼 수 있다. 후보 내부의
L2 limiter가 더 작으면 queue wait가 발생하며, 이것도 runtime 평가 대상이다.

## 화면과 결과

정상 실행 화면은 준비 메시지 이후 다음처럼 진행된다.

```text
[B002] 평가 시작 | 총 32개
[B002] 01/32 완료
[B002] 02/32 완료
...
[B002] 32/32 완료
[B002] 종료 | VALID | 52.31점 | 성공 32/32 | 318.2초 | run-timeout 0
```

상세 데이터는 화면에 펼치지 않고 `eval/results/<version>/`에 저장한다.

- 결과 JSON: 점수, 축별 결과와 문항별 상태
- sample coverage: theme·axis·category·turn shape·rubric 규모의 집계
- 실행 로그: 위 진행 상황판과 마지막 요약
- 메타데이터 JSON: 브랜치, 버전, SHA, 시간과 결과 경로

평가가 성공하면 공유 가능한 구조화 결과를
`docs/evaluations/results/<version>.json`에도 자동 복사한다. 이 파일에는 원문 prompt,
응답, rubric과 API 키가 없으므로 피드백 Markdown과 함께 `dev`에 커밋한다.

완료 후 에이전트에게 다음처럼 요청하면 된다.

> B001 끝났어. 결과 확인하고 피드백 문서 작성해줘.

`scripts/proxy-run.ps1`은 내부 실행 엔진이므로 직접 호출할 필요가 없다.

# Daintlab-B 문서 홈

이 문서는 로컬 평가 에이전트와 후보 모델 개선 에이전트가 같은 사실을 기준으로
작업하도록 만드는 단일 진입점이다. 문서는 성격이 겹치지 않는 세 영역만 사용한다.

```text
docs/
├── competition/             # 주최 측 계약과 제출 규격
├── evaluations/
│   ├── candidates/          # D/U/Y 후보별 재현 가능한 평가 기록
│   └── incidents/           # timeout, 502, container failure 분석
└── wiki/                    # 연구, 구현 교훈, 다음 모델 전략
```

`guides`, `implementation`, `engineering`, `planning`은 더 이상 사용하지 않는다.
공식 사실은 `competition`, 관측 결과는 `evaluations`, 재사용할 판단은 `wiki`에 둔다.

## 작업별 시작점

| 하려는 일 | 먼저 읽을 문서 |
|---|---|
| 대회 계약·API·제출 조건 확인 | [competition](competition/README.md) |
| 로컬 프록시 실행 | [평가 하네스](../eval/README.md) |
| 후보 성능 비교 | [평가 인덱스](evaluations/README.md) |
| 현재 best model SHA와 runtime 기준 확인 | [현재 기준점](evaluations/BASELINES.md) |
| runtime 계측 필드와 후보 로그 계약 | [runtime telemetry](evaluations/TELEMETRY.md) |
| 실패 원인 조사 | [실패 사례](evaluations/incidents/README.md) |
| 모델 개선 아이디어 도출 | [wiki 인덱스](wiki/README.md) |
| 현재 우선순위 결정 | [모델 개선 플레이북](wiki/21_에이전트_모델개선_플레이북.md) |
| 지연·입력 토큰 최적화 | [입력 예산 전략](wiki/22_입력예산_지연최적화_전략.md) |

## 정보 우선순위

내용이 충돌하면 다음 순서로 판단한다.

1. `competition/`: 주최 측 계약. 구현이 반드시 지켜야 한다.
2. `evaluations/`: 특정 SHA와 manifest에서 직접 관측한 사실.
3. `wiki/15_*` 이후: 공식 스펙 공개 후 작성한 실무 지식과 전략.
4. `wiki/01_*`~`13_*`: 공식 스펙 공개 전 배경 조사.

추정은 관측 사실처럼 쓰지 않는다. 평가 점수에는 후보 SHA, manifest, 표본 수,
성공률, 지연 시간과 judge를 함께 기록한다.

## 에이전트 작업 규칙

1. 모델을 바꾸기 전에 [평가 인덱스](evaluations/README.md)에서 현재 기준 후보와
   실패 축을 확인한다.
2. 관련 `wiki` 문서를 읽고 변경 가설을 한 문장으로 적는다.
3. 한 후보에는 독립적인 가설 하나만 넣는다.
4. 단위 테스트 후 동일 manifest 로컬 프록시를 실행한다.
5. 결과를 `evaluations/candidates/<버전>.md`에 기록한다.
6. 재사용 가능한 교훈만 wiki에 반영한다. 일회성 로그는 candidate 또는 incident에 둔다.
7. 공식 계약이 바뀌면 먼저 `competition`을 갱신하고 영향을 받는 wiki 문서를 표시한다.

## 현재 기준선

- **현재 best model이자 실제 Trial 기준선은 D5**, SHA
  `b76170e15242a0c046ae7d892998de10f9d404fc`다. D4가 아니며 실제 Trial에서
  **42.48점으로 성공**했다.
- Y2는 D5 파생 후보로 로컬 구 프로토콜에서 54.68점·16/16이었지만 실제 Trial에서
  `coeval_failed_timeout`으로 결과를 내지 못했다.
- 집컴 에이전트는 [현재 기준점](evaluations/BASELINES.md)에서 모델 품질 기준과 제출 runtime
  기준을 반드시 구분한다.
- 모든 후보 에이전트는 먼저 [Y2 timeout incident](evaluations/incidents/Y2_COEVAL_TIMEOUT.md)를
  읽어야 한다.
- 새 로컬 기준선은 D5를 `coverage-v2`로 다시 측정해 만든다. 이후 후보는 D5 대비 품질을
  비교하면서 420초 안에 32/32와 `promotion_eligible=true`를 만족해야 한다.
- 다음 돌파구는 timeout 상향이 아니라 Retrieval tool schema, 누적 context와 L2 호출 수를
  줄여 전체 처리량을 확보하는 것이다.

상세 비교는 [Y3 평가](evaluations/candidates/Y3.md)와
[입력 예산 전략](wiki/22_입력예산_지연최적화_전략.md)을 따른다.

## 문서 관리 원칙

- 같은 사실을 여러 문서에 복사하지 않고 한 문서를 canonical source로 연결한다.
- 파일을 옮기면 저장소 전체의 상대 링크를 함께 수정한다.
- 후보 결과와 전략 문서를 구분한다. 결과는 무엇이 일어났는지, wiki는 왜 그런지와
  다음에 무엇을 검증할지를 설명한다.
- API key, 원문 benchmark prompt, rubric, 환자 데이터는 문서에 기록하지 않는다.

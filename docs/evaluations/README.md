# 평가 기록

후보 모델별 로컬 프록시 결과와 실제 리더보드 피드백의 인덱스다. 결과 문서는
사실 기록이며, 일반화된 설계 지식은 [wiki](../wiki/README.md)에 둔다.

> **기준선 변경 (2026-08-22, origin/dev):** Y2는 실제 Trial에서
> `coeval_failed_timeout`으로 탈락했다. 공식 best model이자 실제 Trial 성공
> 기준선은 **D5**(`b76170e15242a0c046ae7d892998de10f9d404fc`, Trial 42.48점)다.
> 로컬 프록시 프로토콜도 16개 `legacy-v1`에서 32개 `coverage-v2`(생성 동시성 4,
> 문항당 120초, 평가 본체 420초, 실패 시 `promotion_eligible=false`)로 바뀌었다.
> 아래 표의 16개 행은 옛 프로토콜 결과이며 32개 `coverage-v2` 결과와 점수를
> 직접 비교하지 않는다. 전체 근거는 `git show origin/dev:docs/evaluations/BASELINES.md`와
> `git show origin/dev:docs/evaluations/incidents/Y2_COEVAL_TIMEOUT.md` 참고
> (이 브랜치에는 병합하지 않음).
>
> **실제 Trial 갱신 (2026-08-22):** [F006](candidates/F006.md)이
> `lunit/hackathon-submission`에 배포되어 실제 Dashboard Trial **45.88점**을
> 받았다 — D5의 42.48점을 넘는 현재 최고 실제 Trial 기록이다. F006은
> F004~F005의 runtime(동시성 4, D5 계열 timeout)을 그대로 유지하고
> 관측 전용 telemetry만 추가했으므로, 이 결과는 그 runtime 프로파일이
> 실제 Trial에서도 유효함을 보여준다.

## 현재 판단 (legacy-v1, 16문항 — 옛 프로토콜)

| 후보 | 표본 | 점수 | 성공률 | 평균 모델 지연 | 판단 |
|---|---:|---:|---:|---:|---|
| [D1](candidates/D1.md) | 32 | 49.22 | 100% | 62.91초 | 실제 리더보드 38.32의 기준점 |
| [D3](candidates/D3.md) | 32 | 51.14 | 100% | 45.75초 | D1보다 빠르지만 품질 우위 불확실 |
| [D4](candidates/D4.md) | 16 | 27.79 | 75% | 혼합 | 상위 API 502·timeout 영향 |
| [Y1](candidates/Y1.md) | 16 | 42.60 | 100% | 53.33초 | 첫 16/16 안정 후보 |
| [D5](candidates/D5.md) | 16 | 36.52 | 68.75% | 40.86초* | 성공 응답 품질은 높으나 timeout |
| [Y2](candidates/Y2.md) | 16 | **54.68** | **100%** | 52.35초 | 현재 품질·완주 기준선 |
| [Y3](candidates/Y3.md) | 16 | 44.30 | 100% | 48.41초 | guidance 회귀, 승격 보류 |
| [Y4](candidates/Y4.md) | 16 | 38.86 | 100% | 41.07초 | Y3 동일 모델 재측정; 버전 이름 충돌 |
| [Y5](candidates/Y5.md) | 평가 대기 | - | - | - | `yh-submission`의 Y2 복귀·법령 schema 최적화 |
| [F001](candidates/F001.md) | 16 | 42.88 | 100% | 19.12초 | Y2 대비 -11.80점, 지연은 -33.23초; role 태깅 승격 보류, 원인 미분리 |

`*` D5 지연은 성공 요청만의 평균이다. D5의 legacy-v1 성공률(68.75%)은 옛 로컬
timeout 때문이며, 실제 Trial은 42.48점으로 성공했다 — 위 기준선 변경 안내 참고.

## 현재 판단 (coverage-v2, 32문항 — 현재 표준 프로토콜)

| 후보 | 표본 | 점수 | 성공률 | 평균 모델 지연 | 판단 |
|---|---:|---:|---:|---:|---|
| [B002](candidates/B002.md) | 32 | 46.43 | 87.50% | 57.14초 | Y2 계열 장시간 예산, 502 4건, `promotion_eligible=false` |
| [F002](candidates/F002.md) | 32 | 46.88 | 90.63% | 29.68초 | B002와 동석수(신뢰구간 겹침), 502 3건, `promotion_eligible=false` |
| [F003](candidates/F003.md) | 32 | 19.50 | 34.38% | 34.62초 | **폐기.** timeout 원복+동시성 6을 한 번에 바꿔 502 20건·504 1건, 원인 미분리 |
| [F004](candidates/F004.md) | 32 (×2 실행) | 58.03 / 43.84 | 96.88% / 75.00% | 31.30초 / 상승 | **품질 양호, 안정성 미달.** 동일 코드 재실행에서 성공 31→24건, 점수 -14.19점. 양쪽 다 성공한 23문항만 비교하면 차이 0.44점 — 답변 품질은 동일, 실패·지연의 실행별 변동이 원인. telemetry 미수집으로 원인(upstream vs MCP vs 동시성) 미확정 |
| [F005](candidates/F005.md) | 32 | **58.57** | **100%** | 30.41초 | **승격됨 — 현재 frontier 로컬 기준선.** stderr 트립와이어 제거로 telemetry 첫 부분 수집(queue wait 0ms, RAG 2건 모두 retrieval 40초 timeout) |
| [F006](candidates/F006.md) | 실제 Trial | **45.88** | - | - | **실제 Dashboard Trial 최고 기록**(D5 42.48 대비 +3.40). runtime 무변경(F005와 동일), citation 근거정합성 관측과 `mcp_tool_cancelled` telemetry만 추가. 로컬 coverage-v2 단독 평가는 아직 미확보 |

B002·F002·F003·F004는 32/32를 완주하지 못해 승격되지 않았다. **F005가
32/32·58.57점으로 처음 승격됐다** — F004의 timeout/동시성 정렬을 그대로
유지한 채 uvicorn stderr 트립와이어만 제거한 결과다. telemetry로 확인한
바로는 로컬 동시성 4에서 queue 적체는 병목이 아니었고, 주 지연은 upstream
initial 응답 자체와 RAG 2건의 retrieval timeout이었다. dev는 F006에 "runtime
숫자와 품질 변경을 같은 버전에 섞지 않는다"를 포함한 8개 안전 조건을 못박았고,
F005의 현재 값이 이미 전부를 만족해 F006은 runtime을 바꾸지 않는다. 대신
F001 이후 미뤄뒀던 wiki 06(근거정합성) 축을 관측 전용으로 처음 시도한다.
다음 표준 로컬 기준선은 F005이며, dev의 안전조건 7번(동일 SHA 2회 연속
32/32)은 F005·F006이 함께 충족해야 한다.

초기 8개 탐색 실험은 [U1](candidates/U1.md), [D2](candidates/D2.md),
[U2](candidates/U2.md)를 참고한다. 표본이 달라 위 표의 대표 평가와 직접 순위를
비교하지 않는다.

## 비교 가능한 대표 manifest

- dataset: 공개 `conquer_val`
- sampling: `representative`
- samples: 16
- repeats: 1
- seed: 0
- generation concurrency: 2
- manifest SHA-256:
  `5aaba42ae20d13b8b65cef0a449b9a69b756525c8ae9d7e373c1e077188eb045`

Y1, D4, D5, Y2, Y3가 이 manifest를 사용했다. D1과 D3의 대표 평가는 32개
manifest이므로 추세 참고용으로만 사용한다.

## 점수 해석 규칙

1. inference 실패는 0점으로 포함한다. 실패 제외 평균만 보고 후보를 승격하지 않는다.
2. 동일 manifest, judge, 동시성에서만 직접 비교한다.
3. 16개 단일 실행은 방향 판단용이다. 작은 차이는 반복 평가 전까지 우위로 확정하지 않는다.
4. 총점과 함께 accuracy, completeness, context awareness, instruction following,
   communication quality를 본다.
5. 평균 지연뿐 아니라 direct/RAG 경로 분포와 단계별 timeout을 확인한다.
6. 로컬 점수는 리더보드 예측값이 아니다. D1은 로컬 49.22, 실제 38.32로
   10.90점의 낙관 편향이 있었다.

## 새 후보 기록 양식

후보 문서에는 다음을 반드시 포함한다.

- 버전 이름, 40자리 SHA와 변경 가설
- 결과 JSON 경로와 manifest SHA
- 표본·반복·동시성·judge
- 총점, 신뢰구간, 성공률, 단계별 지연
- 축·주제별 점수
- 이전 기준선과 같은 조건의 비교
- 승격·보류·폐기 판정 및 다음 한 가지 실험

실패가 후보 로직보다 인프라 문제에 가까우면
[incidents](incidents/README.md)에 별도 기록한다.

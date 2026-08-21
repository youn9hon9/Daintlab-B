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
| [F004](candidates/F004.md) | 평가 대기 | - | - | - | F002 timeout으로 원복, 동시성만 2→4 단독 변경 + stdout 로깅 버그 수정(telemetry 유실 원인) |

B002·F002·F003 모두 502/504 실패로 32/32를 완주하지 못해 승격 대상이 아니다.
F003은 timeout과 동시성을 동시에 바꿔 원인 분리가 안 됐고, telemetry도
stderr 로깅 버그로 수집되지 못했다 — F004는 두 문제를 각각 고친다. 다음
표준 로컬 기준선은 여전히 D5의 coverage-v2 재평가다.

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

# 평가 기록

후보 브랜치의 역할, 버전과 커밋 메시지 규칙은
[후보 브랜치 버전·커밋 컨벤션](CONVENTION.md)을 따른다.

후보 모델별 로컬 프록시 결과와 실제 리더보드 피드백의 인덱스다. 결과 문서는
사실 기록이며, 일반화된 설계 지식은 [wiki](../wiki/README.md)에 둔다.
문항별 구조화 수치는 [평가 결과 JSON](results/README.md)에 함께 보관한다.
기존 16개 `legacy-v1`과 신규 32개 `coverage-v2`의 해석 기준은
[로컬 프록시 표본 설계](METHODOLOGY.md)를 따른다.
현재 best model SHA와 제출 가능한 runtime 기준은 [현재 기준점](BASELINES.md)을 따른다.

## 현재 판단

아래 표에는 역사적 `legacy-v1`과 신규 32개 coverage 표본 결과가 함께 있다. 표본 수와
manifest가 다른 점수는 직접 비교하지 않는다. B002/F002는 신규 표본 선택을 사용했지만
runtime gate 도입 직전에 실행되어 생성 동시성 2와 420초 초과를 허용한 과도기 결과다.

| 후보 | 표본 | 점수 | 성공률 | 평균 모델 지연 | 판단 |
|---|---:|---:|---:|---:|---|
| [D1](candidates/D1.md) | 32 | 49.22 | 100% | 62.91초 | 실제 리더보드 38.32의 기준점 |
| [D3](candidates/D3.md) | 32 | 51.14 | 100% | 45.75초 | D1보다 빠르지만 품질 우위 불확실 |
| [D4](candidates/D4.md) | 16 | 27.79 | 75% | 혼합 | 상위 API 502·timeout 영향 |
| [Y1](candidates/Y1.md) | 16 | 42.60 | 100% | 53.33초 | 첫 16/16 안정 후보 |
| [D5](candidates/D5.md) | 16 | 36.52 | 68.75% | 40.86초* | **best model SHA**, 실제 Trial 42.48 성공 |
| [Y2](candidates/Y2.md) | 16 | **54.68** | **100%** | 52.35초 | D5 파생; 실제 Trial timeout |
| [Y3](candidates/Y3.md) | 16 | 44.30 | 100% | 48.41초 | guidance 회귀, 승격 보류 |
| [Y4](candidates/Y4.md) | 16 | 38.86 | 100% | 41.07초 | Y3 동일 모델 재측정; 버전 이름 충돌 |
| [B001](candidates/B001.md) | 16 | 34.78 | 100% | 43.38초 | 안정적이나 Y2 대비 품질 급락; 승격 거부 |
| [F001](candidates/F001.md) | 16 | 42.88 | 100% | **19.12초** | 매우 빠르지만 역할 태깅 가설 미입증; 승격 보류 |
| [B002](candidates/B002.md) | 32 | 46.43 | 87.50% | 57.14초 | 4건 502·17분 28초; 승격 거부 |
| [F002](candidates/F002.md) | 32 | 46.88 | 90.63% | **29.68초** | B002보다 빠르나 3건 502; 승격 거부 |

`*` D5 지연은 성공 요청만의 평균이다.

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

Y1, D4, D5, Y2, Y3, Y4, B001, F001이 이 manifest를 사용했다. B002와 F002는 서로 동일한
32개 coverage manifest를 사용했으며 위 16개 결과와 직접 비교하지 않는다. D1과 D3의
대표 평가는 별도의 32개 manifest이므로 추세 참고용으로만 사용한다.

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

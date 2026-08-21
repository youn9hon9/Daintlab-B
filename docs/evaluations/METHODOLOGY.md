# 로컬 프록시 표본 설계

## 결론

16개는 빠른 회귀 탐지와 timeout 확인에는 충분하지만 후보 승격이나 작은 품질 차이를 확정하기에는
부족하다. 과거 비교선 보존보다 평가의 대표성과 실패 탐지력을 우선하므로 기본 로컬 프록시를
32개 coverage 프로토콜로 교체한다.

| 프로토콜 | 명령 | 표본 | 선정 | 용도 |
|---|---|---:|---|---|
| legacy-v1 | 없음 | 16 | theme 비례 고정 표본 | 과거 결과 해석만 |
| coverage-v2 | `.\proxy <branch>` | 32 | 메타데이터 coverage | 모든 신규 후보 평가 |

두 프로토콜의 점수는 직접 순위 비교하지 않는다. coverage-v2 역시 로컬 개발 신호이며 비공개
리더보드 점수의 추정치는 아니다. 32개 신뢰구간이 크게 겹치면 우열을 확정하지 않는다.

Y2가 로컬 16/16 이후 실제 Trial에서 `coeval_failed_timeout`으로 실패했으므로 coverage-v2는
내용 표본뿐 아니라 runtime 계약도 강제한다. 생성 동시성 4, 요청당 120초, 평가 본체 420초
제한을 사용하며 미완료 문항은 `run_timeout` 0점으로 기록한다. 실패가 하나라도 있으면
`promotion_eligible=false`다. 자세한 근거는 [Y2 timeout incident](incidents/Y2_COEVAL_TIMEOUT.md)에 있다.

## 기존 16개 패널의 진단

`conquer_val` 공개 validation은 301개이고 기존 manifest는 그중 16개다. theme 비율은 원본과
가깝지만 행동 범위는 충분히 덮지 못했다.

- 7개 theme: 모두 포함
- 17개 physician-agreed category: **7개 포함, 10개 누락**
- instruction-following axis가 있는 문항: **4개**
- 단일턴 / 멀티턴: 8개 / 8개
- rubric 수: 평균 10.31개, 원본 평균 11.33개

역대 16개 평가의 95% bootstrap 신뢰구간 폭도 대체로 25~34점이었다. 따라서 5~10점 차이를
표본 하나만으로 후보의 진짜 개선이라고 판단하기 어렵다. 같은 16개를 계속 사용하면 개발자가
원문을 보지 않더라도 그 manifest의 우연한 특성에 간접 과적합할 수 있다.

## HealthBench와 CoEval을 어떻게 반영하는가

HealthBench는 5,000개의 현실적인 단일·멀티턴, 다국어 의료 대화를 7개 theme와 5개 axis로
나누고, 대화별 의사 작성 가중 rubric으로 마지막 답변을 평가한다. Consensus는 여러 의사가
합의한 34개 행동 기준을 중심으로 정밀하지만 범위가 좁고, Hard는 현재 모델이 어려워하는
1,000개 예시로 개선 상한을 본다.

CoEval은 하나의 점수가 아니라 의료 모델 평가 프레임워크다. HealthBench 외에도 MCQ, 수치 계산,
hallucination·attribution과 RAG용 faithfulness·relevancy·context precision/recall을 지원한다.
현재 대회의 비공개 평가는 별도 HealthBench holdout이라고 명시되어 있으므로 로컬 후보 선정의
중심은 HealthBench형 응답 품질이어야 한다. CoEval 전체 14개 데이터셋을 16개 HealthBench
표본이 대표한다고 해석해서는 안 된다.

참고 자료:

- [OpenAI HealthBench 소개](https://openai.com/index/healthbench/)
- [OpenAI HealthBench 논문](https://cdn.openai.com/pdf/bd7a39d5-9e9f-47b3-903c-8b847ca650c7/healthbench_paper.pdf)
- [Lunit CoEval](https://github.com/lunit-io/CoEval)
- [대회 평가 규칙](../competition/rules.md)

## 32개 coverage 패널

기본 패널은 prompt나 rubric 문장을 읽지 않고 다음 공개 메타데이터만 사용한다.

1. 7개 theme
2. physician-agreed category
3. 5개 axis의 문항 단위 포함 여부
4. 단일턴·멀티턴
5. rubric 개수 low·medium·high 구간

greedy coverage로 희소 범주를 먼저 포함한 뒤, 남는 자리는 301개 원본의 theme 비율과 현재
선정 수의 차이를 줄이는 데 사용한다. seed와 prompt ID의 hash는 동률 해소에만 사용한다.
결과 JSON에는 원문 없이 `sample_coverage` 집계를 남겨 실제 범위를 매번 검증할 수 있다.

## 판정 규칙

- 32/32 완주와 17개 category coverage
- inference·judge 실패 0
- 평균뿐 아니라 최대 지연과 timeout 건수
- 총점 95% 신뢰구간
- accuracy, completeness, context awareness, instruction following, communication quality
- 7개 theme 중 특정 영역의 큰 회귀
- 같은 coverage-v2 manifest를 사용한 기준선 대비 개선 방향

동일 모델의 반복 안정성이 중요할 때는 표본 수를 줄여 반복하기보다 32개 패널을 유지하고
`repeats=2` 이상으로 worst-of-n을 별도 확인한다. 다만 기본 자동 명령은 시간과 비용을 위해
반복 1회로 둔다.

## 규정 경계

이 설계는 공개된 상위 theme·axis·합의 category의 범위를 고르게 측정한다. 개별 prompt,
rubric 문구, 정답 패턴을 분석하거나 후보 로직에 특정 문항 대응을 넣지 않는다. 이는 대회 규정의
HealthBench 과도한 reverse engineering 금지 원칙을 지키기 위한 명시적 경계다.

# Y2 실제 Trial CoEval timeout

## 상태

Y2를 실제 Dashboard Trial에 제출한 결과 `coeval_failed_timeout`으로 종료됐다.
Dashboard에 입력한 정확한 40자리 SHA와 상세 서버 로그는 이 문서 작성 시점에 확보되지
않았으므로 특정 커밋의 결함으로 단정하지 않는다. 다만 Y2 계열의 로컬 측정과 제출 코드에서
공식 wall-clock 제한을 넘길 구조적 위험은 확인됐다.

**운영 판정: Y2는 품질 참고 후보일 뿐, 제출 가능한 기준선이 아니다. Y2에서 분기한 후보도
runtime gate를 새로 통과하기 전에는 절대 승격하거나 Lunit 제출 브랜치에 반영하지 않는다.**

Y2의 출발점은 현재 best model로 확인된 D5 SHA
`b76170e15242a0c046ae7d892998de10f9d404fc`다. D5는 실제 Trial을 완료해 42.48점을
냈다. 반대로 Y2는 개별 요청 예산을 늘린 뒤 전체 CoEval timeout으로 결과를 내지 못했다.
따라서 D5와 Y2를 같은 runtime 안정성으로 취급하면 안 된다.

## 확인된 로컬 사실

- 구 `representative-16` 점수: 54.68
- 성공: 16/16
- 전체 로컬 평가 시간: 430.74초
- 평균 모델 지연: 52.35초
- 당시 로컬 생성 동시성: 2
- Y2 제출 코드의 정상 L2 동시성: 2
- Y2 제출 코드의 요청 제한: 170초
- upstream attempt 제한: 75초
- retrieval 제한: 65초

실제 Trial에 성공한 D5와 실패한 Y2의 핵심 runtime 차이는 다음과 같다.

| 설정 | D5 | Y2 |
|---|---:|---:|
| 전체 요청 제한 | 90초 | 170초 |
| upstream 제한 | 30초 | 75초 |
| retrieval 제한 | 40초 | 65초 |
| 정상 L2 동시성 | 6 | 2 |

D5는 일부 느린 요청을 일찍 포기하더라도 전체 처리 폭을 확보했고 실제 Trial 결과를 냈다.
Y2는 로컬 문항 성공률을 높이기 위해 요청 예산을 늘리고 동시성을 줄였지만 전체 Trial을
완주하지 못했다. 이는 인과를 확정하는 단독 실험은 아니지만 가장 먼저 반증해야 할 설명이다.

평균 지연만 사용한 16개 생성 처리량 하한은 대략 다음과 같다.

```text
52.35초 × 16문항 ÷ 동시성 2 ≈ 418.8초
```

여기에 container 준비, cold start, multi-turn, queue wait와 evaluator 오버헤드가 더해진다.
즉 16/16이라는 로컬 성공 표시는 공식 제한에 충분한 여유가 있다는 뜻이 아니었다.

## 가장 가능성 높은 원인

### 1. 전체 wall-clock 예산 부재

구 로컬 하네스는 각 HTTP 요청을 최대 240초 기다렸고 전체 평가 종료 시한이 없었다. 느린
후보도 오래 기다리면 성공으로 판정됐다. 공식 Trial은 전체 CoEval 실행에 제한이 있으므로
동일한 답변이더라도 처리량이 부족하면 평가 전체가 timeout된다.

### 2. 동시성 부하를 재현하지 못함

구 하네스의 생성 동시성 2가 Y2 내부 L2 동시성 2와 같았다. 따라서 endpoint 앞에 대기열이
생기지 않았다. 공식 evaluator가 더 많은 요청 또는 여러 conversation을 동시에 진행하면
세 번째 이후 요청은 L2 slot을 기다리며 자신의 요청 예산을 소모한다.

### 3. 긴 요청 예산이 처리량을 보장하지 않음

170초 요청 제한은 개별 요청의 성공 가능성은 높이지만 평가 전체 처리량을 개선하지 않는다.
오히려 느린 initial·retrieval·final 경로가 slot을 오래 점유하도록 허용한다. timeout 숫자를
늘리는 것만으로 이 incident를 해결할 수 없다.

## 로컬 하네스 변경

`coverage-v2`는 다음 runtime 조건을 함께 적용한다.

- 표본: coverage 32
- 생성 동시성: 4
- 개별 HTTP 요청 제한: 120초
- 평가 본체 wall-clock 제한: 420초
- wall timeout 시 진행 중인 요청 취소
- 취소 문항: `run_timeout`, 0점
- inference·judge·run timeout이 하나라도 있으면 `promotion_eligible=false`
- p50·p95·최대 모델 지연 기록
- cases/minute와 deadline 잔여 시간 기록
- 후보 stdout에서 direct/RAG, initial/retrieval/final과 queue wait 집계

420초는 공식 제한을 확정한 값이 아니라, Y2처럼 제한에 거의 붙은 후보를 조기에 거르기 위한
보수적 로컬 gate다. Dashboard의 정확한 시간 계약이 확인되면 설정과 문서를 함께 갱신한다.

## 후보 개발 에이전트 필수 규칙

1. 총점이 높아도 420초 내 32/32를 완료하지 못하면 폐기 또는 runtime 수정한다.
2. Y2의 54.68점을 새 후보의 직접 기준점으로 사용하지 않는다. 프로토콜이 다르다.
3. timeout을 170초보다 더 늘리는 변경은 해결책으로 인정하지 않는다.
4. L2 호출 수, queue wait, RAG 진입률과 단계별 지연을 줄이는 단일 가설을 세운다.
5. D5를 먼저 `coverage-v2`로 재평가해 로컬 품질·runtime 통합 기준선을 만든다.
6. 실제 Trial SHA와 elapsed time을 확보하면 이 incident에 추가한다.

## 별도 보안 주의

현재 원격 제출 계열의 Dockerfile과 Git 이력에는 직접 포함된 API credential이 존재한다.
credential 값은 문서에 복사하지 않는다. 사용이 끝난 키는 폐기하고, 새 키를 만들 때도 후보
피드백·로그·문서에는 남기지 않는다. 이 문제는 timeout의 직접 원인으로 보이지 않지만 별도로
처리해야 한다.

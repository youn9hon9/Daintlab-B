# 현재 기준점

## 반드시 구분할 두 기준점

### 최선의 모델 로직 기준점

- 이름: **F006**
- 개발 SHA: `b325a8c57030c1803c9f2768dcdca6a61ce7a1a2`
- 제출 SHA: `bf0d277a2821dafb41beafa7e5bfda7731e0cb18`
- 실제 Trial: **성공, 45.88점**

F006은 F005의 모델 동작과 runtime을 유지하고 citation grounding·MCP 취소 telemetry만
추가한 관측 후보다. 따라서 45.88점 상승을 관측 코드의 품질 효과로 해석하지 않는다.
실제 의미 기준선은 F005/F006 계열의 direct 중심 Generation과 동시성 4 runtime이다.

### 실제 Trial 기준점

- 이름: **F006**
- SHA: `bf0d277a2821dafb41beafa7e5bfda7731e0cb18`
- 실제 Trial: **성공, 45.88점, 36분 36초**

F006은 D5의 실제 Trial 42.48점을 3.40점 넘어섰고 공식 평가를 끝까지 완료했다. 따라서
현재 공식적으로 검증된 best model이자 제출 runtime 기준점은 F006이다. 로컬 1차는
31/32, 2차는 32/32였으므로 재현성 경고는 유지하되 실제 Trial 관측을 우선한다.

Y2는 D5의 개별 요청 시간 예산을 크게 늘린 파생형이다. 구 로컬 평가에서는
16/16·54.68점이었지만 실제 Trial에서 `coeval_failed_timeout`으로 결과를 내지 못했다.
이는 개별 요청을 오래 기다리는 정책이 전체 CoEval 완주에는 불리할 수 있음을 보여준다.

| runtime 설정 | D5: Trial 성공 | Y2: Trial timeout |
|---|---:|---:|
| 전체 요청 제한 | 90초 | 170초 |
| upstream 제한 | 30초 | 75초 |
| retrieval 제한 | 40초 | 65초 |
| 정상 L2 동시성 | 6 | 2 |

Y2는 요청 성공률을 높이려다 요청 점유 시간을 늘리고 처리 폭을 1/3로 줄였다. 집컴 에이전트는
이를 안정성 개선으로 재사용하면 안 된다.

따라서 집컴 후보 에이전트는 다음 원칙을 따른다.

1. 모델과 runtime 개선의 출발점은 F006 제출 SHA다.
2. D5의 빠른 실패·제한된 시간 예산을 이유 없이 Y2식 장시간 예산으로 바꾸지 않는다.
3. D5의 품질을 보존하면서 L2 호출 수, RAG 진입률, queue wait와 단계별 지연을 줄인다.
4. D5를 먼저 `coverage-v2`로 재평가해 새 로컬 기준선을 만든다.
5. 새 후보는 420초 안에 32/32를 완주하고 `promotion_eligible=true`여야 승격한다.

## 명칭 표

| 이름 | SHA 또는 표기 | 의미 | 현재 판정 |
|---|---|---|---|
| D4 | `ec0d4a4a93d5a05606c8246514e831367e8812ca` | 이전 dy-submission 후보 | 기준점 아님 |
| D5 | `b76170e15242a0c046ae7d892998de10f9d404fc` | 이전 공식 best model·runtime | 실제 Trial 42.48 성공 |
| F006 | `bf0d277a2821dafb41beafa7e5bfda7731e0cb18` | 현재 공식 best model·runtime | 실제 Trial 45.88 성공 |
| Y2 | `Y2-local-b76170e-coldguard` | D5 + 장시간 예산·동시성 축소 | 실제 Trial timeout, 제출 불가 |
| 로컬 v2 기준선 | 미확정 | B002/F002 과도기 실행은 실패 포함 | D5를 현 runtime gate로 재평가 후 확정 |
| B003/F003 runtime 실험 | 폐기 | 동시성 6·짧은 timeout에서 대량 502/504 | 다음 후보는 동시성 4 단독 실험 |
| F004 frontier 후보 | 조건부 보류 | 58.03점·31/32·282.69초 | 동일 SHA 재실행에서 32/32 확인 |
| B004 benchmark 후보 | 승격 거부 | 41.26점·25/32·502 7건 | guard·동시성 4 유지, timeout 50초 복원 |

관련 기록:

- [D5 로컬 평가](candidates/D5.md)
- [Y2 로컬 평가](candidates/Y2.md)
- [Y2 실제 Trial timeout](incidents/Y2_COEVAL_TIMEOUT.md)
- [coverage-v2 방법론](METHODOLOGY.md)
- [B002 32개 평가](candidates/B002.md)
- [F002 32개 평가](candidates/F002.md)
- [B003 runtime 실패](candidates/B003.md)
- [F003 runtime 실패](candidates/F003.md)
- [F004 조건부 최고 후보](candidates/F004.md)
- [B004 runtime 피드백](candidates/B004.md)
- [B006 반복 실패와 RAG 병목](candidates/B006.md)
- [F006 실제 Trial 45.88](candidates/F006.md)

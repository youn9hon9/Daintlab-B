# 실패 사례 기록

모델 품질과 실행 인프라 문제를 분리하기 위한 공간이다. timeout, 429·502,
MCP session 종료, container crash, cold-start 실패가 발생하면 후보 피드백과 별도로
이곳에 기록한다.

## 기록할 항목

- 발생 시각과 후보 SHA
- 요청 수, 동시성, manifest
- evaluator가 본 status code
- 서버 로그의 실패 단계: initial, retrieval, MCP, final, repair
- container 생존 여부와 exit code
- 재현 조건과 재실행 결과
- 모델 코드 문제인지 상위 서비스 문제인지에 대한 판정 근거

## 현재까지의 반복 패턴

| 패턴 | 관측 | 해석 |
|---|---|---|
| D4의 연속 502 | Lunit Model API와 MCP가 같은 시간대에 실패 | 후보 품질과 분리해야 하는 상위 서비스 변동 |
| D5의 30초 ReadTimeout | container는 생존, initial/final 호출 실패 | L2 실제 지연과 호출 제한 불일치 |
| cold-start exit 139 | 첫 연결 두 개가 경쟁할 때 발생 | 첫 응답까지만 직렬화하는 guard로 완화 |
| Y2/Y3 retrieval 65초 소진 | MCP tool schema 21개를 받은 Retrieval L2가 응답하지 못함 | timeout보다 입력·도구 범위 축소가 우선 |

원시 로그 전체를 Git에 넣지 않는다. 비밀정보를 제거한 최소 재현 정보와 결론만 남긴다.

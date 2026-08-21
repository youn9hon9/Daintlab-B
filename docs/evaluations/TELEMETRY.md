# 로컬 runtime telemetry 계약

## 목적

총점과 전체 지연만으로는 timeout 원인을 구분할 수 없다. `coverage-v2`는 후보 컨테이너의
stdout을 수집해 결과 JSON의 `runtime_telemetry`에 안전한 집계만 병합한다. 원문 prompt,
응답, rubric, API key와 전체 raw log는 `docs`에 복사하지 않는다.

## 결과 필드

- `summary.cases_per_minute`
- `summary.successful_cases_per_minute`
- `summary.deadline_headroom_seconds`
- `summary.deadline_utilization`
- `runtime_telemetry.routes`: direct/RAG 건수
- `runtime_telemetry.requests.latency_ms`: p50·p95·최대
- `runtime_telemetry.l2_phases.<phase>.attempt_latency_ms`
- `runtime_telemetry.l2_phases.<phase>.queue_wait_ms`
- `runtime_telemetry.l2_phases.<phase>.input_chars`
- `runtime_telemetry.retrieval`: 상태·timeout·skip·지연
- `runtime_telemetry.mcp`: 관측 가능한 성공·실패 호출

후보가 구조화 로그를 내지 않아도 평가는 계속된다. 이 경우
`runtime_telemetry.telemetry_complete=false`와 `summary.promotion_warnings`를 남긴다.
점수와 완주율을 조작하지 않으며, 원인 분석의 신뢰도가 낮다는 뜻이다.

## 후보 stdout 이벤트

집컴의 모델 개발 에이전트는 다음 event와 `key=value` 형식을 유지한다.

```text
l2_input phase=initial messages=2 message_chars=1200 tools=1 tool_schema_chars=500
l2_attempt_complete attempt=1 phase=initial queue_wait_ms=5 attempt_latency_ms=12000 status=200
l2_attempt_failed attempt=1 phase=final queue_wait_ms=20 attempt_latency_ms=30000 error_type=ReadTimeout
generation_complete route=direct generation_rounds=1 retrievals=0
retrieval_complete status=complete latency_ms=8000 budget_seconds=40
mcp_tool_complete tool=example latency_ms=500 status=ok
mcp_tool_failed tool=example latency_ms=20000 error_type=MCPError
request_complete id=opaque latency_ms=22000
request_timed_out id=opaque
```

필수 phase는 `initial`, `retrieval`, `final`이고 route는 `direct`, `rag`다. 로그에 query,
대화, evidence 본문, API key를 넣지 않는다. `id`는 임의 UUID처럼 원문과 무관한 값만 쓴다.

## 현재 후보와의 호환성

D5와 Y2 계열은 route, request, L2 phase, queue wait와 retrieval 이벤트를 이미 출력한다.
성공한 MCP 호출의 `mcp_tool_complete` 이벤트는 없으므로 현재 SHA를 평가하면 MCP 성공 건수는
0으로 추정하지 않고 `complete_event_supported=false`로 기록한다. 새 후보는 위 이벤트를
추가하되 제출 API와 디렉터리 구조는 바꾸지 않는다.

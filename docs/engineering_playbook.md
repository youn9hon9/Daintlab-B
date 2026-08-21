# Engineering Playbook

공식 문서, 구현 확인 기록, 사전 리서치를 함께 검토해 도출한 개발 원칙이다. 특정 benchmark 문항이 아니라 일반적인 의료 대화 품질과 제출 안정성을 개선하는 데 사용한다.

## 1. 변경하지 않을 외부 계약

제출 서비스의 외부 경계는 내부 구현보다 안정적이어야 한다.

- repository root의 `Dockerfile`
- 자동 기동 및 `0.0.0.0:8000` bind
- `GET /v1/models`
- `POST /v1/chat/completions`
- evaluator가 전달한 전체 conversation history 수용
- Lunit L2가 최종 user-facing answer 생성

Retrieval, prompt, safety, retry를 개선하더라도 이 계약을 변경하지 않는다. 내부 변경은 contract test와 Docker smoke test를 항상 통과해야 한다.

## 2. 단계별 책임

```text
Evaluator request
  → API contract validation
  → conversation context handling
  → Generation L2
       └─ retrieve_relevant_content(query)
            → Retrieval L2
                 ├─ MCP tools
                 └─ finalize_retrieval(status, items, note)
  → response contract validation
  → Evaluator response
```

### Generation

- 최종 답변을 생성한다.
- 제공 도구는 `retrieve_relevant_content` 하나로 제한한다.
- memory만으로 충분한 질문은 불필요한 Retrieval 없이 답할 수 있다.
- 정확한 수치, 법령, 급여, 허가, 최신 가이드라인이 필요한 경우 Retrieval을 호출한다.

### Retrieval

- 최종 사용자 답변을 작성하지 않는다.
- MCP tool 전체와 `finalize_retrieval`을 제공한다.
- evidence가 충분한지 판단하고 `sufficient`, `partial`, `no_evidence`로 종료한다.
- tool call budget을 코드 레벨에서 제한한다.

## 3. Citation은 별도 데이터 흐름이다

MCP schema 확인 결과 tool은 두 종류로 나뉜다.

1. navigation/schema tool: 문서, node, table, column을 찾지만 직접 인용할 수 없을 수 있다.
2. content tool: 원문이나 row를 반환하며 `cite_uid`를 제공한다.

예를 들어 guideline 검색은 다음처럼 끝까지 진행해야 한다.

```text
index_list_documents
  → index_get_relevant_nodes 또는 index_keyword_search
  → index_get_page_content
  → cite_uid 선택
```

검색 score가 높다는 이유만으로 navigation result를 citation으로 선택하지 않는다. `finalize_retrieval`은 실제로 수집된 `cite_uid`만 허용해야 한다.

## 4. 데이터 소스별 기본 경로

| 질문 | 기본 경로 | 주의점 |
| --- | --- | --- |
| 진료지침·목표치 | document → node → page | 권고 대상·시점·페이지 확인 |
| 국내 급여·약가 | HIRA update/price | 현행 여부와 적용일 확인 |
| KCD 코드 | search → exact name → HIRA validation | KCD revision과 청구 유효성 구분 |
| 의약품 허가 | MFDS permission/indication | 제품명·성분명과 취하 상태 구분 |
| 안전성·상호작용 | DailyMed label | 한국 허가 정보와 역할 구분 |
| 이상반응 건수 | schema detail → FAERS SQL | 인과관계가 아닌 신고 자료임을 명시 |
| 법령 | search → article list → article | MST, 시행일, 조·항을 함께 유지 |
| 최신 연구 | PubMed vector query | 초록 수준 근거의 한계 명시 |

복합 질문은 source를 무조건 모두 호출하지 않고 claim 단위로 필요한 근거를 분리한다. 단, Retrieval L2의 tool 선택을 참가자 코드의 고정 allowlist로 과도하게 제한하지 않는다.

## 5. Schema-first 원칙

`rag_sql_query` 전에 반드시 실제 data source detail을 확인한다.

```text
rag_get_all_data_sources
  → rag_get_data_source_detail(source_name)
  → 확인된 table/column만 사용해 rag_sql_query
```

FAERS, DailyMed, KCD의 공개 표준 구조는 query 설계 참고자료일 뿐이다. 대회 인스턴스의 table과 column 이름을 추측하지 않는다.

## 6. 멀티턴 query 규칙

Retrieval query는 단독으로 읽어도 의미가 완결되어야 한다.

나쁜 예:

```text
그 약 용량은?
```

좋은 예:

```text
이전 대화에서 언급한 성인 고혈압 환자의 암로디핀 일반 권장 용량과
MFDS 허가 용법을 확인한다.
```

확인되지 않은 환자 정보는 보충하지 않는다. 이전 턴에서 확정된 사실, 현재 질문, 필요한 정보 유형만 포함한다.

## 7. 실패를 정상 상태로 설계

- `sufficient`: 핵심 claim을 직접 지지하는 citable evidence 확보
- `partial`: 확인된 범위와 확인하지 못한 범위를 분리해 전달
- `no_evidence`: 추측하지 않고 제한을 설명
- timeout: 확보한 evidence가 있으면 partial, 없으면 no_evidence
- malformed tool call: 제한 횟수 내에서 한 번 교정 후 종료

오류 메시지와 로그에는 API key, bearer token, 원문 환자정보를 남기지 않는다.

## 8. 측정 순서

1. Direct L2 baseline의 성공률·latency·품질을 기록한다.
2. query rewriting만 추가해 비교한다.
3. Retrieval을 필요한 질문에 연결한다.
4. citation 정확성과 no-evidence 행동을 측정한다.
5. 안전성·가독성 변환을 각각 ablation한다.
6. Docker build, 기동, endpoint 회귀를 마지막에 다시 확인한다.

한 번에 여러 기능을 넣으면 점수 변화의 원인을 알 수 없다. 각 기능은 제거 가능한 module과 독립 test를 가져야 한다.

## 9. 문서 갱신 규칙

- 공식 공지가 바뀌면 `wiki/00_*`와 `guides/`를 먼저 갱신한다.
- 실제 tool schema가 바뀌면 확인 날짜와 함께 `implementation/lunit_mcp_tools.md`를 갱신한다.
- 설계 결정은 `implementation/architecture.md`에 반영한다.
- 실험 결과는 `experiments/`에 기록하되 hidden question이나 secret을 저장하지 않는다.
- 사전 리서치의 추정은 공식 사실처럼 승격하지 않는다.

# 런타임 아키텍처와 MCP 관측

공식 계약과 실제 런타임 관측을 연결하는 구현 레퍼런스다. API 자체의 상세 규격은
[competition](../competition/README.md)을 우선한다.

## 개발 환경과 제출 환경

```text
dev 브랜치 / 평가 노트북
  ├─ eval 하네스
  ├─ 공개 validation cache
  ├─ judge API
  └─ 후보별 결과와 docs

후보 브랜치 / 제출 runtime
  ├─ root Dockerfile
  ├─ OpenAI-compatible API
  ├─ Lunit L2 client
  ├─ MCP retrieval
  └─ deterministic validation·safety
```

개발용 judge, 공개 데이터 다운로드와 분석 도구는 제출 runtime 의존성이 아니다.
평가 환경은 외부 인터넷이 차단될 수 있으며 정상 최종 답변은 Lunit L2가 생성한다.

## 요청 처리 경계

```text
Evaluator
  → API validation
  → Generation L2
       ├─ direct answer
       └─ retrieve_relevant_content(query)
            → Retrieval L2
                 → MCP tools
                 → finalize_retrieval
            → evidence envelope
       → final Generation L2
  → deterministic citation check
  → OpenAI-compatible response
```

- 요청의 전체 `messages`가 source of truth다. 서버의 전역 대화 상태에 의존하지 않는다.
- Generation에는 `retrieve_relevant_content`만 제공한다.
- Retrieval은 사용자 답변을 작성하지 않고 MCP와 `finalize_retrieval`만 사용한다.
- safety는 flag를 만들 수 있지만 최종 의료 문장을 하드코딩하지 않는다.

## Evidence 데이터 흐름

MCP 도구는 크게 세 종류다.

1. navigation: 문서·node·데이터소스를 찾는다.
2. content: 원문·row를 반환하고 `cite_uid`를 제공할 수 있다.
3. schema: SQL database와 collection 구조를 설명한다.

Guideline의 일반적인 경로는 다음과 같다.

```text
index_list_documents
  → index_get_relevant_nodes 또는 index_keyword_search
  → index_get_page_content
  → cite_uid 등록
  → finalize_retrieval
```

검색 score나 node id는 인용이 아니다. evidence registry가 실제 tool result에서 관측한
`cite_uid`만 선택할 수 있어야 한다.

## 2026-08-21 MCP 관측 스냅샷

Live server에서 21개 도구가 노출됐다. 전체 schema와 인자는
[MCP 공식 가이드](../competition/mcp-tools.md)를 참고한다.

| 도메인 | 대표 도구 | 기본 경로 |
|---|---|---|
| Guideline/HIRA 문서 | `index_*` | document → node/search → page content |
| KCD·청구 유효성 | `kcd_*`, `openapi_hira_disease_check_code` | 이름 검색 → 정확 코드 → 청구 검증 |
| 약가·급여 | `openapi_hira_get_drug_price`, `hira_updates_search` | 제품 상태 → 필요 시 세부 인정기준 |
| 국내 의약품 허가 | `openapi_mfds_*` | 허가 상태 → 적응증·용량 |
| 미국 라벨 | `adr_retrieve_drug_info` | 제품/성분 → 관련 label section |
| 법령 | `openapi_law_*` | search → MST → article list/content |
| SQL | `rag_get_data_source_detail`, `rag_sql_query` | schema 확인 → 확인된 column만 query |
| Vector | `rag_vector_query` | collection 확인 → 의미 검색 |

`rag_get_all_data_sources` 관측 당시 vector collection은 `pubmed_abstracts`,
`hira_faq`, SQL database는 `faers_12q4_25q4`, `dailymed_26_08`, `kcd`였다.
이는 시점 종속 관측이며 코드 상수로 고정하지 않는다.

## 운영상 확인된 주의점

- live tool 목록과 schema는 process 동안 cache할 수 있지만 변경 가능성을 전제로 한다.
- schema에는 `cite_uid`가 선택 필드인 도구가 많다. 반환 여부를 실행 결과에서 검증한다.
- `index_get_page_content`는 citation 가능한 원문 단계다.
- SQL은 공개 표준 스키마를 대회 DB에 그대로 가정하지 않는다.
- 동일 tool·arguments 반복은 loop로 판단하고 budget을 소비시키지 않는 편이 좋다.
- tool output 전체를 Generation에 전달하지 않는다. 선택 evidence와 출처만 전달한다.

## 변경 불가 외부 계약

- repository root의 `Dockerfile`
- 자동 기동과 `0.0.0.0:8000`
- `GET /v1/models`
- `POST /v1/chat/completions`
- 전체 conversation history 수용
- Lunit L2가 최종 user-facing answer 생성

내부 prompt, retrieval, validation을 바꿔도 이 계약은 contract test와 Docker smoke로
고정한다.

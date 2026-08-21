# Lunit MCP Tools 가이드

## 1. MCP server 연결

팀 API key를 환경변수로 설정한다.

```bash
export LUNIT_FM_API_KEY="lunit_..."
```

`~/.codex/config.toml`에 다음 MCP server 설정을 추가한다.

```toml
[mcp_servers.lunit_mcp]
url = "https://mcp.hackathon.lunit.io/mcp"
bearer_token_env_var = "LUNIT_FM_API_KEY"
required = true
tool_timeout_sec = 60
```

설정을 저장한 뒤 Codex를 재시작하고 `/mcp`를 열어 연결 상태를 확인한다.

- MCP endpoint: `https://mcp.hackathon.lunit.io/mcp`
- 인증 방식: `Authorization: Bearer <API_KEY>`
- `lunit_mcp`는 임의의 local server 이름이므로 원하는 이름으로 변경할 수 있다.
- 다른 Streamable HTTP MCP client에서도 동일한 endpoint와 인증 방식을 사용한다.
- 참고: [Codex MCP configuration](https://developers.openai.com/codex/mcp)

---

## 2. Tool 이름

Codex에서는 다음 prefix가 붙은 형태로 tool이 제공된다.

```text
mcp__lunit_mcp__<tool_name>
```

예시:

```text
mcp__lunit_mcp__adr_retrieve_drug_info
```

`lunit_mcp`는 `config.toml`에 지정한 server 이름이므로 server 이름을 변경하면 tool prefix도 함께 달라진다.

---

## 3. 사용 가능한 MCP tools

| Tool | 출처 | 설명 |
|---|---|---|
| `adr_retrieve_drug_info` | `dailymed_26_08` (DailyMed) | 영문 brand name 또는 INN으로 공식 DailyMed drug label의 주요 section을 조회한다. Warning, adverse reaction, interaction, source link를 포함한다. |
| `hira_updates_search` | `hira_biz_infobank` · `hira_cancer_drug_notice` · `hira_cancer_drug_regimen` | 현행·개정 guidance, oncology notice, 인정된 off-label oncology regimen에서 HIRA 급여기준 고시와 공개 심의사례를 검색한다. |
| `index_get_document_structure` | `hira` (249 docs) · `guideline` (120 docs) | HIRA 또는 clinical guideline 문서를 section tree로 탐색한다. 시작 node부터 최대 50개 node와 page range를 반환한다. |
| `index_get_page_content` | `hira` (249 docs) · `guideline` (120 docs) | 선택한 문서 page range의 원문을 반환한다. Page는 1부터 시작하며 호출당 최대 20 page와 추출된 flowchart path를 조회할 수 있다. |
| `index_get_relevant_nodes` | `hira` (249 docs) · `guideline` (120 docs) | Query와 의미적으로 관련된 문서 section을 찾아 일치하는 문서, ancestor node, page range를 반환한다. |
| `index_keyword_search` | `hira` (249 docs) · `guideline` (120 docs) | 대소문자 구분 없이 정확한 keyword로 문서 page를 검색한다. 일치 term과 출현 횟수로 순위를 매기며 pagination을 지원한다. |
| `index_list_documents` | `hira` (249 docs) · `guideline` (120 docs) | 사용 가능한 HIRA와 clinical guideline collection에서 corpus 문서를 나열하거나 query 관련도 순으로 정렬한다. |
| `kcd_get_name` | `kcd` (KCD-8 · KCD-9) | 정확한 KCD code의 공식 한글·영문 질병명을 반환한다. KCD-8과 KCD-9을 지원하며 기본값은 KCD-9이다. |
| `kcd_search_codes` | `kcd` (KCD-8 · KCD-9) | 한글 또는 영문 질병명으로 candidate KCD code를 유사 검색하며 KCD version을 선택할 수 있다. |
| `openapi_hira_disease_check_code` | HIRA Disease Master OpenAPI | 진단 code가 HIRA 청구에 유효한지 확인하고 code 완전성, 주상병, 성별, 연령, 감염병 제한을 반환한다. |
| `openapi_hira_get_drug_price` | HIRA Drug Price OpenAPI | HIRA 약가 data에서 급여 등재 상태, 약가 code, 상한가를 조회하며 삭제 및 적용일 정보를 포함한다. |
| `openapi_law_get_article` | Korean Law Information Center OpenAPI (`law.go.kr`) | 선택한 한국 법령 조문의 전문을 citation 가능한 형태로 조회하며 조문 시행일과 `law.go.kr` link를 포함한다. |
| `openapi_law_list_articles` | Korean Law Information Center OpenAPI (`law.go.kr`) | 특정 한국 법령의 조문을 나열하고 조문 제목 filter를 지원하며 전문 조회용 stable article key를 반환한다. |
| `openapi_law_search` | Korean Law Information Center OpenAPI (`law.go.kr`) | 한국 법령을 검색하고 법률·행정규칙·자치법규의 후속 조회에 필요한 MST identifier를 반환한다. |
| `openapi_mfds_check_drug_permission` | MFDS Drug Approval OpenAPI | 부분 product name 검색으로 의약품의 현재 MFDS 허가 여부를 확인하고 유효 허가와 취하 허가를 구분한다. |
| `openapi_mfds_find_drugs_by_ingredient` | MFDS Drug Approval OpenAPI | 동일 active ingredient를 사용하는 MFDS 허가 제품을 찾고 대체 candidate의 허가 상태를 반환한다. |
| `openapi_mfds_get_drug_indication` | MFDS Product Approval Detail OpenAPI | 의약품의 MFDS 허가 indication을 조회한다. 선택적으로 dosage, administration, warning, ATC data, contraindication을 반환한다. |
| `rag_get_all_data_sources` | `pubmed_abstracts` · `hira_faq` · `faers_12q4_25q4` · `dailymed_26_08` · `kcd` | 사용 가능한 모든 SQL, vector, hybrid data source의 identifier와 용도를 나열한다. |
| `rag_get_data_source_detail` | `pubmed_abstracts` · `hira_faq` · `faers_12q4_25q4` · `dailymed_26_08` · `kcd` | 하나의 SQL, vector 또는 hybrid data source에 대한 schema, table, column, metadata를 표시한다. |
| `rag_sql_query` | `faers_12q4_25q4` · `dailymed_26_08` · `kcd` | 사용 가능한 FAERS, DailyMed, KCD dataset의 structured PostgreSQL data를 SQL로 조회한다. |
| `rag_vector_query` | `pubmed_abstracts` · `hira_faq` | Vector 또는 dense-plus-sparse hybrid retrieval로 지원되는 Qdrant collection을 semantic similarity 기반으로 검색한다. |

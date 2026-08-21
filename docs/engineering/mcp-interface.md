# Lunit MCP tool interface discovery

Verified from the live `lunit_mcp` tool descriptions and input/output declarations on 2026-08-21. The server exposed 21 tools. `cite_uid` is marked **Yes** only when it appears in the declared return schema; **No** means it was not verifiable from that tool's schema, not that the server can never add it.

| Tool | Purpose | Required arguments | Optional arguments | Important output fields | `cite_uid` verifiable |
|---|---|---|---|---|---|
| `adr_retrieve_drug_info` | Retrieve DailyMed labeling sections for an English brand/generic name. | `drug_name: string` | None | `items[]`: drug label `content`, `section`, `drug_name`, `source_id`, `source_type`, `url`; `message` | Yes |
| `hira_updates_search` | Search HIRA reimbursement documents and revision lineages. | `query: string` | `current_only: boolean`; `document_type: update \| public_case \| cancer_drug_notice \| all`; `limit: number` (max 50); `search_mode: title \| content \| both`; `source_type: hira_cancer_drug_notice \| hira_cancer_drug_regimen \| all` | `items[]`: `title`, `content`, `row_key`, `document_type`, revision/current fields, provenance/source fields, `url`; `message` | Yes |
| `index_get_document_structure` | Expand a document tree from a node (max 50 nodes). | `corpus_tag: string` (`hira` or `guideline`); `depth: number`; `node_id: string` | None | `structure` tree containing `node_id`, `title`, `summary`, page `range`, depth/children metadata; `message` | No |
| `index_get_page_content` | Fetch an inclusive raw page range (max 20 pages). | `corpus_tag: string`; `doc_id: string`; `start_page: number`; `end_page: number` | None | `title`, `pages[]` (`page`, `text`, optional chart paths), `source_id`, `source_type`, `url`, `message` | Yes |
| `index_get_relevant_nodes` | Semantic search over leaf-node summaries. | `corpus_tag: string`; `query: string` | `k: number`; `node_id: string \| null` | `result[]`: `node_id`, `title`, `summary`, page `range`, `doc_id`, `doc_title`, `ancestors`, `score` | No |
| `index_keyword_search` | Exact, case-insensitive lexical search over raw pages. | `corpus_tag: string`; `query: string` | `doc_id: string \| null`; `limit: number`; `offset: number` | `results[]`: document/node ids, title, summary, page, snippet, match count/terms; `total_results`, `offset`, `message` | No |
| `index_list_documents` | List or semantically rank documents in a corpus. | `corpus_tag: string` | `limit: number`; `offset: number`; `query: string \| null` | `results[]`: `node_id`, `title`, `summary`, `total_pages`, optional `score`; `total_results`, `offset`, `message` | No |
| `kcd_get_name` | Resolve an exact KCD code and optionally cross-check a name. | `code: string` | `lang: string`; `name: string \| null`; `revision: string` | `items[]`: KCD code/name, revision, match/level/source fields; `message` | Yes |
| `kcd_search_codes` | Rank candidate KCD codes from an approximate disease name. | `name: string` | `lang: string`; `revision: string`; `top_k: number` | `items[]`: KCD code/name, revision, match/level/source fields; `message` | Yes |
| `openapi_hira_disease_check_code` | Check whether a normalized HIRA disease code is billable as written. | `code: string` | None | `items[]`: `code`, Korean/English name, completeness/primary-use, age/sex and infectious-class constraints, source fields; `message` | Yes |
| `openapi_hira_get_drug_price` | Look up Korean HIRA drug listing, price, and effective date. | `drug_name: string` | `num_rows: number` | `items[]`: drug/code/ingredient, max price, effective date, pay/route/Rx/substitution fields, source fields; `message` | Yes |
| `openapi_law_get_article` | Fetch citable full text for selected Korean law articles. | `article_keys: string[]`; `mst: string` | None | `items[]`: law/article identifiers and labels, title, content, effective date, type, source, `url`; `message` | Yes |
| `openapi_law_list_articles` | List a law's article table of contents. | `mst: string` | `contains: string \| null` | `items[]`: law/article identifiers and labels/titles, source fields; `message` | Yes |
| `openapi_law_search` | Find a Korean law and its MST identifier. | `query: string` | `kind: string` (`law`, `admrul`, or `ordin`) | `items[]`: law identity/type and MST/source metadata; `message` | Yes |
| `openapi_mfds_check_drug_permission` | Check MFDS approval and current permission status for a Korean drug. | `drug_name: string` | `num_rows: number` | `items[]`: product/name, ingredient, company, permit/cancel dates and status, EDI/class fields, source fields; `message` | Yes |
| `openapi_mfds_find_drugs_by_ingredient` | Find MFDS products sharing an active ingredient. | `ingredient: string` | `num_rows: number` | `items[]`: product/name, ingredient, company, permission/status and classification fields, source fields; `message` | Yes |
| `openapi_mfds_get_drug_indication` | Retrieve MFDS indication/ATC and optionally dosage and a notice clause. | `drug_name: string` | `include_dosage: boolean`; `notice_clause: string`; `num_rows: number` | `items[]`: name, ingredient/English ingredient, indication, ATC, optional dosage/notice, document URL, source fields; `message` | Yes |
| `rag_get_all_data_sources` | List configured vector collections and SQL databases with descriptions. | None | None | `result: string` | No |
| `rag_get_data_source_detail` | Describe a collection/database and its tables, columns, or metadata. | `source_name: string` | None | `result: string` | No |
| `rag_sql_query` | Run a PostgreSQL query against a named configured database. | `db_name: string`; `sql: string` | None | `items[]`: `title`, selected `row`, `source_id`, `source_type`, `url`; `message` | Yes |
| `rag_vector_query` | Semantic search over a named Qdrant collection. | `collection_name: string`; `query: string` | `filters: object \| null`; `top_k: number` | `items[]`: `title`, `content`, `relevance_score`, `source_id`, `source_type`, `url`; `message` | Yes |

## Metadata execution check

One lightweight call to `rag_get_all_data_sources` completed successfully. It reported:

- Vector collections: `pubmed_abstracts`, `hira_faq`
- SQL databases: `faers_12q4_25q4`, `dailymed_26_08`, `kcd`

No retrieval query or content-generation call was made through MCP.

## Schema observations

- Index discovery/search tools return navigation metadata but do not declare `cite_uid`; `index_get_page_content` is the citable step and does declare it.
- Most specialized lookup and retrieval tools share an `items` plus optional `message` result envelope. Their item union declares `cite_uid` as optional.
- `rag_get_all_data_sources` and `rag_get_data_source_detail` return a string-valued `result` rather than retrieval items.
- `corpus_tag` is typed as `string`, while descriptions currently constrain it to `hira` or `guideline`.
- Several optional arguments have documented defaults or limits in descriptions rather than in the type declaration (for example current-only HIRA results and result/page caps).

# RAG 데이터소스 하이브리드 검색 실무 (Qdrant 하이브리드 + SQL 스키마)

담당 범위인 4개 범용 RAG MCP tool(`rag_get_all_data_sources`, `rag_get_data_source_detail`, `rag_sql_query`, `rag_vector_query`)을 실제로 어떻게 호출해야 하는지에 초점을 맞춘 실무 조사. PubMed·HIRA FAQ 같은 비정형 텍스트는 Qdrant vector/hybrid 검색으로, FAERS·DailyMed·KCD 같은 정형 데이터는 PostgreSQL SQL로 조회하는 이 대회 구조에서, "언제 무엇을 어떻게 호출할지"를 판단하는 근거 자료.

## 1. Qdrant dense+sparse 하이브리드 검색의 동작 원리

Qdrant는 하나의 collection에 dense vector(신경망 임베딩)와 sparse vector(BM25/SPLADE 등)를 동시에 저장하고, 쿼리 시점에 두 방식으로 각각 검색(prefetch)한 뒤 결과를 재순위화(fusion)하는 구조를 지원한다.

| 구성 요소 | 방식 | 강점 | 약점 |
|---|---|---|---|
| Dense vector | 신경망 encoder가 의미(semantic)를 벡터 공간에 임베딩 | 동의어·패러프레이즈·문맥적 유사어 탐지에 강함 | 희귀 고유명사·정확한 수치·약어를 놓치기 쉬움 |
| Sparse vector (BM25/SPLADE) | Inverse Document Frequency 기반, 흔한 단어는 낮게, 희귀·판별력 있는 단어는 높게 가중 | 정확한 키워드·용어 일치(exact match)에 강함 | 동의어·문맥적 유사어를 포착 못함 |

두 결과 리스트는 **RRF(Reciprocal Rank Fusion)**로 결합하는 것이 사실상 표준 default다. RRF는 점수(score)가 아니라 순위(rank)의 역수를 합산하기 때문에 dense 점수(코사인 유사도 등)와 sparse 점수(BM25 점수)처럼 스케일이 다른 두 지표를 정규화 없이 안전하게 합칠 수 있다는 것이 핵심 장점이며, `k=60`을 zero-config 기본값으로 쓰는 사례가 많다. Qdrant는 RRF 외에 점수 분포 자체를 정규화해 결합하는 DBSF(Distribution-Based Score Fusion) 방식도 제공한다.

**의학 전문용어가 많은 PubMed 초록에서 hybrid가 dense-only보다 유리한 이유**는 이른바 "vocabulary mismatch" 문제 때문이다. 의학 텍스트는 동의어(약물의 상품명 vs 성분명), 유사어, 다의어(polysemy)가 매우 흔해 dense 임베딩만으로는 관련 문서를 놓치거나(동의어로 인한 recall 손실) 무관한 문서를 끌어오는(다의어로 인한 precision 손실) 문제가 발생한다. 반대로 sparse 검색(BM25)은 희귀하고 판별력 있는 전문용어(구체적 약물명, 유전자명, MeSH 용어, 수치 등)를 정확히 매칭하는 데 강하다. 생물의학 문헌 검색 연구에서도 sparse+dense 결합 방식이 단일 방식보다 일관되게 더 높은 성능을 보인다고 보고된다.

## 2. PubMed 규모 vector DB에서 semantic search 품질을 높이는 실무 팁

| 기법 | 내용 | 효과 근거 |
|---|---|---|
| MeSH 기반 query 확장 | 자연어 질의를 MeSH descriptor/동의어로 확장해 재작성 | 28,313개 MeSH descriptor 전수 비교 연구에서 MeSH 확장 전략이 평균 precision 51%(SD 23%)로 4개 확장 전략 중 최고 |
| UMLS 기반 query 확장 | UMLS 동의어 시소러스로 확장 | 같은 연구에서 recall·F-measure 기준 최고(각 41%, 36%) — precision 중시면 MeSH, recall 중시면 UMLS로 구분해 채택 가능 |
| Query rewriting/재작성 | 사용자의 원 질문을 자기완결적(self-contained)이고 구체적인 검색 질의로 변환 | L2 harness 자체가 "Retrieval query는 그 자체로 완결되어야 한다"고 명시 (00_Lunit_FM_L2_사용_방법.md) — MeSH/UMLS 확장을 이 재작성 단계에 결합 가능 |
| 최신성(recency) 필터링 | 발행일 메타데이터로 최신 논문에 가중치를 주거나 필터링 | 검색으로 명확한 정량 벤치마크는 확인하지 못함 — **정확한 출처 미확인, 추가 검증 필요.** 다만 대부분의 실무 RAG 가이드가 메타데이터 필터(publish_date 등)를 payload에 저장해 필터링하는 것을 표준 패턴으로 권장 |
| Dense+sparse+reranking 결합 | hybrid 검색 결과를 cross-encoder로 재순위화 | 02번 문서에 정리된 MDPI 2025 리뷰(250개 임상 vignette, 12가지 RAG 변형 비교)에서 dense+sparse+cross-encoder reranking 조합이 precision 0.68+, nDCG@10 0.67+로 최고 — 이 문서의 결론과 정합 |

## 3. FAERS / DailyMed / KCD 구조화 데이터의 SQL 스키마 패턴

### FAERS (사례-약물-반응 조인 구조)

FDA가 공개하는 FAERS 분기별 데이터(ASCII 추출본)는 **7개 테이블**로 구성되는 것이 공식 표준 구조다.

| 테이블 | 내용 |
|---|---|
| DEMO | 환자 인구통계·보고 관리 정보 |
| DRUG | 사례에 보고된 약물 정보 |
| REAC | 보고된 이상반응(MedDRA 용어) |
| OUTC | 환자 결과(outcome) |
| INDI | 약물 투여 사유(적응증, MedDRA 코딩) |
| THER | 약물 투여 시작일·종료일 |
| RPSR | 보고 출처 정보 |

테이블 간 조인 키는 **`primaryid`(= `caseid` + `caseversion`을 연결한 식별자)**와 **`caseid`**가 기본이며, THER/INDI처럼 "사례 내 특정 약물"에 종속된 정보는 `drug_seq`(또는 `indi_drug_seq`, `dsg_drug_seq`)로 DRUG 테이블의 개별 약물 레코드와 추가로 연결한다. 즉 전형적인 조회 패턴은 `DRUG`(약물명) → `primaryid`/`drug_seq`로 `REAC`(반응)·`OUTC`(결과)·`INDI`(적응증) 조인이다. 참고로 과거(2012년 이전) 데이터는 `isr`(Individual Safety Report) 키를 썼으나 현재는 `primaryid`/`caseid` 체계로 대체되었다.

이 대회의 `faers_12q4_25q4` data source는 위 공개 표준 스키마를 그대로 옮겼을 가능성이 높지만, **테이블·컬럼 명명 규칙(대소문자, 접두사 등)이 실제로 동일한지는 미확인**이므로 SQL 작성 전 반드시 `rag_get_data_source_detail`로 실제 테이블/컬럼명을 확인해야 한다.

### DailyMed (SPL 구조)

DailyMed는 FDA가 요구하는 HL7 표준 XML 포맷인 **SPL(Structured Product Labeling)**을 원천으로 한다. SPL은 Warnings, Adverse Reactions, Indications and Usage, Dosage and Administration, Contraindications, Drug Interactions 등 라벨의 각 섹션을 고정된 XML 엘리먼트로 강제하므로, "이 필드는 항상 존재한다/비어있어도 명시적으로 존재한다"는 보장이 자유 텍스트 PDF보다 강하다. 다만 이 대회의 `dailymed_26_08` SQL data source가 이 SPL 섹션들을 어떤 테이블/컬럼 구조로 정규화해 저장했는지는 **미확인** — MCP tool 목록에 `adr_retrieve_drug_info`(section 단위 조회 tool)와 `rag_sql_query`(구조화 조회) 양쪽에 걸쳐 있는 것으로 보아 섹션 텍스트와 구조화 필드가 함께 존재할 가능성이 있으나, 정확한 스키마는 `rag_get_data_source_detail` 호출로 직접 확인 필요.

### KCD (한국표준질병사인분류)

KCD-8/KCD-9 코드 체계의 실제 SQL 테이블 스키마는 이번 조사에서 공개 문서를 찾지 못했다. **정확한 스키마 미확인, 추가 검증 필요** — `kcd_search_codes`/`kcd_get_name`이라는 전용 MCP tool이 이미 존재하는 점에서, 단순 코드→명칭 조회는 이 tool로 처리하고 `rag_sql_query`는 코드 범위 집계·통계성 질의(예: 특정 대분류 코드 개수)에만 쓰는 편이 안전하다.

## 4. SQL 조회 vs Vector 조회 판단 기준

| 질문 유형 | 판단 근거 | 사용할 tool |
|---|---|---|
| "이 약의 부작용 보고 건수는?" / "특정 반응이 몇 건 보고됐는가?" | 집계(count)·필터·조인이 필요한 정형 사실 | `rag_sql_query` (faers_12q4_25q4) |
| "이 약과 관련된 최신 임상 논문 결과는?" | 자유 서술형 텍스트에서 의미 기반 근거 발췌 | `rag_vector_query` (pubmed_abstracts) |
| "특정 KCD 코드의 정식 질병명은?" | 정확한 1:1 코드-명칭 lookup | `rag_sql_query`(kcd) 또는 전용 tool `kcd_get_name` |
| "이 시술이 급여 인정되는 조건은?" (서술형 기준) | 문맥·예외 조항이 섞인 비정형 안내문 | `rag_vector_query` (hira_faq) |

일반적으로 통용되는 구분 원칙은, 답이 **행(row), 조인, 필터, 날짜, 개수, 현재 상태**처럼 정형 데이터의 "사실"에 의존하면 SQL/NL2SQL을, 답이 **서술형·비정형 문서**에서 근거를 뽑아야 하면 vector/RAG를 쓰는 것이다. 두 유형이 섞인 질문(예: "이 약의 부작용 중 최근 논문에서도 보고된 것은?")은 SQL로 구조화된 사실을 먼저 확정한 뒤, 그 결과를 vector 질의의 필터/키워드로 넘기는 순차 파이프라인이 적합하다 — 라우팅 코디네이터가 질의를 분석해 정량적 질의는 관계형 DB로, 정성적·의미 기반 질의는 vector DB로 분기하는 방식이 실무에서 표준적으로 쓰인다.

## 5. 스키마 우선 탐색 패턴 (`rag_get_data_source_detail` → `rag_sql_query`)

Text-to-SQL 기반 RAG의 대표적 실패 모드는 LLM이 스키마를 보지 않고 "그럴듯한" 테이블/컬럼명을 추측해 SQL을 생성하는 것이다(hallucinated column name). 이를 막기 위한 모범사례는 다음과 같이 정리된다.

- **스키마를 컨텍스트로 먼저 주입**: 테이블·컬럼·데이터타입·설명을 프롬프트에 먼저 제공한 뒤에만 SQL을 생성하게 한다. 컬럼이 많은 대규모 스키마에서는 스키마 정보 자체를 vector 인덱스로 만들어 질의와 관련된 테이블/컬럼만 선별해 주입하는 RAG-over-schema 방식도 쓰인다.
- **"제공된 컬럼만 사용하라"는 명시적 제약**: 프롬프트에 "Use ONLY the column names provided" 같은 명시적 지시를 넣는 것만으로 컬럼·테이블명 hallucination을 사실상 0에 가깝게 낮췄다는 사례가 보고된다.
- **의미가 모호한 컬럼명에는 설명을 덧붙임**: `cust_id` 같은 축약형 컬럼명은 "고객 식별자"처럼 사람이 읽을 수 있는 설명을 스키마 문서에 함께 제공해야 LLM이 질의 의도와 정확히 매핑한다.

이 원칙은 이 대회 하네스에 그대로 대응된다. `rag_get_all_data_sources`로 어떤 data source가 있는지 확인 → `rag_get_data_source_detail`로 해당 source의 실제 테이블/컬럼/타입을 확인 → 그 결과만 근거로 `rag_sql_query`를 작성하는 3단계 순서를 강제하면, 위 FAERS·DailyMed·KCD 스키마처럼 "공개 문서상으로는 있어 보이지만 실제 이 대회 인스턴스에는 다르게 구현됐을 수 있는" 컬럼명 문제를 원천적으로 피할 수 있다.

## 대회 도구 매핑

| MCP tool | 이 문서의 조사 내용과의 연결 |
|---|---|
| `rag_get_all_data_sources` | 매 턴 초반, 질문 유형(정형 사실 vs 서술형 근거)을 판단하기 전에 호출해 pubmed_abstracts/hira_faq(vector)와 faers_12q4_25q4/dailymed_26_08/kcd(SQL) 중 어떤 source가 관련 있는지부터 목록화. 4절의 SQL vs vector 판단 기준을 적용하기 위한 첫 단계. |
| `rag_get_data_source_detail` | `rag_sql_query`를 호출하기 **전에 반드시** 선행 호출해 실제 테이블·컬럼명을 확인 — 5절의 "스키마 우선 탐색" 패턴 그대로 적용. FAERS의 `primaryid`/`caseid`/`drug_seq` 조인 키, DailyMed의 SPL 섹션 매핑, KCD 테이블 구조가 3절에서 정리한 공개 스키마와 실제로 일치하는지 이 tool로만 확정할 수 있다(특히 DailyMed·KCD는 이번 조사에서 미확인으로 남았으므로 harness가 반드시 이 tool로 검증해야 함). |
| `rag_sql_query` | 3절의 FAERS 7-테이블 조인 패턴(DRUG↔REAC/OUTC/INDI를 primaryid+drug_seq로 조인), DailyMed·KCD 구조화 lookup에 사용. 4절 기준상 "발생 건수", "코드-명칭 매핑" 같은 집계·정확 일치 질의에 우선 배정. |
| `rag_vector_query` | 1·2절의 dense+sparse hybrid 원리를 적용해 pubmed_abstracts(전문용어 밀집 → hybrid 이점 큼)와 hira_faq를 검색. 가능하면 query 자체를 MeSH/동의어로 확장하거나 L2의 "자기완결적 query" 지침에 맞게 재작성한 뒤 호출. 4절 기준상 "최신 논문 근거", "서술형 기준" 질의에 우선 배정. |

## 전략적 시사점

- Qdrant hybrid(dense+sparse+RRF)는 이 대회 `pubmed_abstracts`/`hira_faq`처럼 전문용어·법률 조문 번호가 밀집한 텍스트에 이론적·실증적으로 유리하므로, `rag_vector_query`가 내부적으로 hybrid를 지원한다면 dense-only 모드보다 hybrid 모드를 기본값으로 삼는 것이 타당하다(단, 실제 호출 파라미터로 hybrid를 켤 수 있는지는 tool schema로 직접 확인 필요).
- FAERS·DailyMed·KCD는 대회 환경에서 스키마가 공개 표준과 다르게 재구성됐을 가능성이 있으므로, "공개 문서에서 본 컬럼명"을 그대로 SQL에 쓰지 말고 매번 `rag_get_data_source_detail`을 먼저 호출하는 것을 harness의 고정 절차로 강제해야 한다 — 이는 L2가 Retrieval 단계에서 tool을 반복 호출하는 구조와도 자연스럽게 맞는다.
- "부작용 건수" 류 정량 질문과 "최신 논문 근거" 류 정성 질문이 한 대화에 섞여 들어올 수 있으므로(3턴 대화 시나리오), 라우팅 로직을 질문 단위가 아니라 **서브 질의(sub-query) 단위**로 SQL/vector에 분기하고 결과를 병합하는 설계가 필요하다.

## 출처
- [Hybrid Search - Qdrant](https://qdrant.tech/documentation/tutorials-and-examples/cloud-inference-hybrid-search/)
- [Hybrid Search in RAG: Dense + Sparse (BM25/SPLADE), Reciprocal Rank Fusion, and When to Use Which (GoPenAI)](https://blog.gopenai.com/hybrid-search-in-rag-dense-sparse-bm25-splade-reciprocal-rank-fusion-and-when-to-use-which-fafe4fd6156e)
- [Hybrid Search for RAG: BM25, SPLADE, and Vector Search Combined (PremAI)](https://www.premai.io/blog/hybrid-search-for-rag-bm25-splade-and-vector-search-combined/)
- [Hybrid Search: BM25, Vector & Reranking Reference 2026 (DigitalApplied)](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026)
- [Hybrid Search and the Universal Query API - Qdrant](https://qdrant.tech/course/essentials/day-3/hybrid-search/)
- [A Hybrid Approach for Biomedical Question Answering (Atlantis Press)](https://www.atlantis-press.com/article/126011520.pdf)
- [Sparse Meets Dense: A Hybrid Approach to Enhance Scientific Document Retrieval (arXiv 2401.04055)](https://arxiv.org/pdf/2401.04055)
- [Intelligent Semantic Search Engine for Biomedical Literature and Clinical Trials (ResearchGate)](https://www.researchgate.net/publication/400242670_Intelligent_Semantic_Search_Engine_for_Biomedical_Literature_and_Clinical_Trials_A_Comprehensive_Hybrid_Retrieval_Framework)
- [Identification of the Best Semantic Expansion to Query PubMed Through Automatic Performance Assessment of Four Search Strategies on All MeSH Descriptors (JMIR/PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7303830/)
- [Performance evaluation of three semantic expansions to query PubMed (Health Information & Libraries Journal)](https://onlinelibrary.wiley.com/doi/10.1111/hir.12291)
- [FAERS Quarterly Data Files Documentation (FDA)](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/faers-quarterly-data-files-documentation)
- [FDA Adverse Event Reporting System (FAERS) (FDA)](https://www.fda.gov/drugs/surveillance/fdas-adverse-event-reporting-system-faers)
- [FDA FAERS Data Dictionary "ASC_NTS.DOC" (PharmaHub PDF)](https://pharmahub.org/app/site/resources/2018/01/00739/FDA-FAERS-Data-Dictionary.pdf)
- [faers: R interface for FDA Adverse Event Reporting System (Bioconductor manual PDF)](https://www.bioconductor.org/packages/release/bioc/manuals/faers/man/faers.pdf)
- [A curated and standardized adverse drug event resource to accelerate drug safety research (Scientific Data / Nature)](https://www.nature.com/articles/sdata201626)
- [DailyMed - SPL Resources (NLM)](https://dailymed-beta.nlm.nih.gov/dailymed/spl-resources.cfm)
- [Structured Product Labeling Resources (FDA)](https://www.fda.gov/industry/fda-data-standards-advisory-board/structured-product-labeling-resources)
- [Structured Product Labeling (Wikipedia)](https://en.wikipedia.org/wiki/Structured_Product_Labeling)
- [Structured Product Labeling and Why Pharma Teams Need to Master It (GlobalVision)](https://www.globalvision.co/blog/structured-product-labeling-and-why-pharma-teams-need-to-master-it)
- [Exploring RAG based approaches for Text-to-SQL (nilenso blog)](https://blog.nilenso.com/blog/2025/05/15/exploring-rag-based-approach-for-text-to-sql/)
- [Simpler RAG approach for text-to-SQL to avoid hallucinations (SQLAI.ai)](https://www.sqlai.ai/posts/simple-rag-for-text-to-sql)
- [Reducing Hallucinations in Text-to-SQL: Building Trust and Accuracy in Data Access (Wren AI)](https://www.getwren.ai/post/reducing-hallucinations-in-text-to-sql-building-trust-and-accuracy-in-data-access)
- [Chapter 1 — How to Build Accurate RAG Over Structured and Semi-structured Databases (Medium)](https://medium.com/madhukarkumar/chapter-1-how-to-build-accurate-rag-over-structured-and-semi-structured-databases-996c68098dba)
- [Structure Augmented Generation: Bridging Structured and Unstructured Data for Enhanced RAG Systems (Meibel)](https://www.meibel.ai/post/structure-augmented-generation-bridging-structured-and-unstructured-data-for-enhanced-rag-systems)
- [RAG for Structured Data: Benefits, Challenges & Examples (AI21)](https://www.ai21.com/knowledge/rag-for-structured-data/)
- [Production RAG Evaluation: Keyword, Vector, SQL, or Hybrid Search? (Oracle Developers)](https://blogs.oracle.com/developers/production-rag-evaluation-keyword-vector-sql-or-hybrid-search)
- [Beyond Vector Databases: Choosing the Right Data Store for RAG (ITNEXT)](https://itnext.io/beyond-vector-databases-choosing-the-right-data-store-for-rag-972a6c4a07dd)

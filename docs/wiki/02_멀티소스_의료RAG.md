# 멀티소스 의료 RAG (PubMed + 약물 + 가이드라인 결합)

해커톤 소스 구성(PubMed, 의약품정보, 건강보험법률, 진료가이드라인)과 가장 근접한 "여러 이질적 의료 소스를 하나의 RAG로 묶는" 연구들.

## 핵심 논문
- **PACE-RAG** (Patient-Aware Contextual and Evidence-Constrained RAG for Clinical Drug Recommendation, arXiv 2603.17356): 환자 기록 기반으로 임상 가이드라인·의학교과서에서 근거를 검색. MultiQueryRetrieval(쿼리를 의미적으로 다양하게 재작성 후 결과 병합)로 재현율 개선하는 학습 불필요(training-free) 베이스라인 제시. → 단일 쿼리로 검색하지 말고 쿼리 재작성/확장을 기본으로 채택할 근거.
- **C-MIG** (Multi-view Information Gain-based RAG for Clinical Diagnosis Reasoning, arXiv 2605.27860): 여러 관점(view)에서 정보 이득을 계산해 검색을 유도하는 구조 — 멀티소스 상황에서 "어떤 소스가 지금 정보 이득이 큰가"를 판단하는 라우팅 아이디어와 연결 가능.
- **MedOmniKB 계열 프레임워크** ("Rethinking RAG for Medicine", arXiv 2511.06738): PubMed, 임상 가이드라인, 교과서, Wikipedia, UMLS, DrugBank 등 다중 리트리버·다중 지식원을 결합하는 최근 프레임워크의 대표 사례. 대규모 전문가 평가를 통해 실무적 인사이트 제공 — 어떤 소스 조합이 실제로 임상의 평가에서 유효했는지 확인할 가치 있음.
- **RAR²** (Retrieval-Augmented Medical Reasoning via Thought-Driven Retrieval, arXiv 2509.22713): 쿼리를 반복적으로 수정하며 검색하는 사고 기반(thought-driven) 검색 — 3턴 대화에서 턴이 진행될수록 검색 쿼리를 누적 갱신하는 설계에 참고 가능.
- **ClinicBot** (Guideline-Grounded Clinical Chatbot with Prioritized Evidence RAG and Verifiable Citations, arXiv 2605.00846): 가이드라인을 단순 텍스트가 아니라 권고사항/기준표/서술텍스트로 구조 분류한 지식베이스로 만들고, 근거 위계(GRADE 등급 권고 > 기준표 > 서술)에 따라 우선순위를 부여. ADA 당뇨 가이드라인 기반 실증. → 해커톤의 "진료 가이드라인" 소스를 다룰 때 가장 직접적으로 참고할 설계 패턴.
- **DrugClaw / DrugAudit** (Primary-Source-Grounded Agent and Authority-Aware Benchmark for Drug-Information QA, arXiv 2606.01434): 약물 정보 질의응답에서 "권위 있는 1차 출처"에 근거했는지를 평가하는 벤치마크 — 약품 정보 소스 활용 시 출처 신뢰도 계층을 반영하는 설계에 참고.
- **TREC 2025 RAG Track** (arXiv 2603.09891): RAG 평가의 표준화 흐름 파악용 — 리트리버/생성 성능을 분리 평가하는 관행 참고.
- **MDPI 2025 리뷰** (RAG in Healthcare Comprehensive Review): 250개 임상 vignette에 12가지 RAG 변형을 평가한 결과, "dense+sparse+cross-encoder reranking을 결합한 하이브리드 파이프라인"이 precision 0.68+, nDCG@10 0.67+로 가장 우수 — 표준 하이브리드+리랭크 조합의 효과를 뒷받침하는 정량적 근거.

## 추가 핵심 논문 (docs/Claude-chat-log 교차 검증분)
- **MedRAG 벤치마크** (Xiong et al., 2024): 교과서 코퍼스는 MMLU-Med에서, StatPearls 코퍼스는 MedQA-US에서 최고 정확도를 냈지만 이 두 코퍼스는 PubMedQA·BioASQ에는 거의 도움이 안 됐고, 그 문제들은 PubMed 코퍼스에서만 주로 이득을 봄 — **"소스마다 강점 문제유형이 다르다"는 정량적 근거**. [08번 문서](08_쿼리라우팅_멀티에이전트RAG.md)의 라우팅 설계와 직결.
- **i-MedRAG** (2025): 단순 1회 검색보다 반복적으로 후속 질의를 던져 검색하는 방식이 MMLU-Med에서 큰 성능 향상. 3턴 대화 구조와 궁합이 좋음 — 한 턴 안에서도 "1차 검색 → 부족하면 재검색" 루프를 넣는 설계 근거.
- **MDAgents** (2024): 기본 정확도 71.8% → MedRAG 결합 시 75.2% → 모더레이터(검토 에이전트) 추가 시 77.6% → 둘 다 결합 시 80.3%. **RAG 단독보다 "RAG + 검토 에이전트" 조합이 더 크게 기여** — 멀티에이전트 하네스 투자가 실제로 정확도에 기여하는지 검증할 때 비교 기준으로 삼을 만함.
- **DoctorRAG (2025) / Med-SRAF (2026) — "Concatenation Fallacy"**: 여러 소스를 그냥 이어붙이면 오히려 성능이 떨어진다는 개념. 쿼리를 도메인 제약 없이 분해하면 원래 임상 의도에서 벗어나고, 서로 다른 의미 축에서 검색된 근거를 구조화 없이 단순 결합하면 상호 의존성·상충을 반영 못 해 하위 추론을 저해함. **4개 소스(PubMed/약물/법률/가이드라인)를 그냥 다 붙여서 프롬프트에 넣는 방식의 구체적 위험성**을 명명한 개념 — Vector Search Dilution([08번](08_쿼리라우팅_멀티에이전트RAG.md))과 같은 문제의식을 더 직접적으로 뒷받침.

## 전략적 시사점
- PubMed·가이드라인처럼 텍스트 구조가 다른 소스는 "하나의 인덱스"로 뭉치지 말고 소스별로 별도 파이프라인(청킹 전략, 우선순위 규칙)을 두는 쪽이 최근 연구 흐름과 일치
- 3턴 대화 특성상 쿼리를 턴마다 새로 만들되, 이전 턴 문맥을 반영해 재작성(query rewriting)하는 것이 정확도에 유의미한 영향을 줄 것으로 예상됨 (PACE-RAG, RAR² 근거)
- ClinicBot의 "근거 위계 우선순위" 아이디어는 진료 가이드라인 소스에 그대로 적용 가능 — 권고등급이 있는 문장을 서술형 설명보다 우선 인용

## 출처
- [PACE-RAG (arXiv 2603.17356)](https://arxiv.org/pdf/2603.17356)
- [C-MIG (arXiv 2605.27860)](https://arxiv.org/pdf/2605.27860)
- [RAG for Regulatory Compliance of Drug Info (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12917324/)
- [Performance of RAG on Pharmaceutical Documents (IntuitionLabs)](https://intuitionlabs.ai/pdfs/performance-of-retrieval-augmented-generation-rag-on-pharmaceutical-documents.pdf)
- [RAR² (arXiv 2509.22713)](https://arxiv.org/pdf/2509.22713)
- [DrugClaw and DrugAudit (arXiv 2606.01434)](https://arxiv.org/pdf/2606.01434)
- [Rethinking RAG for Medicine (arXiv 2511.06738)](https://arxiv.org/pdf/2511.06738)
- [Guideline-grounded RAG for ophthalmic CDS (arXiv 2603.21925)](https://arxiv.org/pdf/2603.21925)
- [ClinicBot (arXiv 2605.00846)](https://arxiv.org/html/2605.00846v1)
- [RAG in Healthcare: Comprehensive Review (MDPI)](https://www.mdpi.com/2673-2688/6/9/226)
- [TREC 2025 RAG Track Overview (arXiv 2603.09891)](https://arxiv.org/pdf/2603.09891)
- [RAG + GraphRAG for Complex Clinical Cases (medRxiv)](https://www.medrxiv.org/content/10.1101/2025.11.25.25341010v1)
- MedRAG benchmark (Xiong et al., 2024), i-MedRAG (2025), MDAgents (2024), DoctorRAG (2025), Med-SRAF (2026) — 링크 미확인, `docs/Claude-chat-log/논문 및 유스케이스.md` 출처, 인용 전 원문 검색 권장

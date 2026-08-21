# 약물 상호작용 그래프 RAG

약품 정보 소스는 "유사도 검색"보다 "관계 탐색"에 가까운 질의(병용금기, 약물-질환 상호작용)가 많아 그래프 기반 접근이 특히 유효할 것으로 예상되는 영역.

## 핵심 논문
- **GraphRAG for Drug Repurposing** (2025 bioRxiv): Drug Repurposing Knowledge Graph(DRKG, 9.7만+ 개체·440만+ 관계)를 지식그래프 임베딩과 LLM으로 결합해 설명 가능한 약물-질환 예측 제공. 그래프 규모감과 구조를 참고할 만함.
- **RAG-Enhanced Collaborative LLM Agents for Drug Discovery** (arXiv 2502.17506): 여러 생화학 개체·관계를 나타내는 지식그래프를 통합하는 협업 에이전트형 RAG.
- **Case-Based Reasoning Enhances LLM DDI Prediction** (arXiv 2505.23034): 사례 기반 추론(과거 유사 사례 검색 후 추론)이 약물상호작용 예측에서 LLM 성능을 높인다는 연구 — RAG의 "유사 사례 retrieval" 관점에서 참고.
- **K-Paths** (Reasoning over Graph Paths for Drug Repurposing and DDI Prediction, arXiv 2502.13344): 그래프 경로(path) 추론을 통한 약물 재창출/상호작용 예측 — "그래프 탐색 결과를 LLM에 텍스트화해서 넘기는" 구체적 방법론.
- **Healthcare Knowledge Graph Construction: State-of-the-art** (arXiv 2207.03771) / **Review on KG for Healthcare** (arXiv 2306.04802): 의료 지식그래프 구축 전반의 개괄 자료 — 시간이 없다면 이 리뷰 두 편으로 전체 지형 파악 가능.
- **How Well Do LLMs Understand Drug Mechanisms?** (arXiv 2511.06418): LLM의 약물 기전 이해도를 평가하는 지식+추론 데이터셋 — FM 자체의 약물 지식 한계를 가늠하는 데 참고.

## 전략적 시사점
- 약품 정보 소스가 구조화 DB/그래프 형태로 제공된다면(→ API 스펙 확인 필요), 병용금기·연령금기 질의는 벡터 유사도 검색 대신 그래프 순회(path query) 또는 구조화 lookup으로 처리하는 게 정확도상 유리할 가능성이 큼
- 소스가 raw 텍스트(첨부문서 등)로만 제공된다면, 텍스트에서 (약물, 관계, 대상) triple을 사전 추출해 경량 그래프를 직접 구축하는 것도 대회 기간 내 시도 가능한 범위 — K-Paths류 경로 추론 방식을 단순화해 적용
- 다만 대회 기간이 짧으므로, 그래프 구축에 드는 비용 대비 실제 채점 문제셋에서 약물 상호작용형 질의 비중이 얼마나 되는지 벤치마크 문제셋 공개 후 먼저 확인하고 투자 여부 결정 권장

## 출처
- [Case-Based Reasoning Enhances DDI Prediction (arXiv 2505.23034)](https://arxiv.org/pdf/2505.23034)
- [RAG-Enhanced Collaborative LLM Agents for Drug Discovery (arXiv 2502.17506)](https://www.arxiv.org/pdf/2502.17506v1)
- [Healthcare Knowledge Graph Construction (arXiv 2207.03771)](https://arxiv.org/pdf/2207.03771)
- [A Review on Knowledge Graphs for Healthcare (arXiv 2306.04802)](https://arxiv.org/pdf/2306.04802)
- [How Well Do LLMs Understand Drug Mechanisms? (arXiv 2511.06418)](https://arxiv.org/pdf/2511.06418)
- [K-Paths (arXiv 2502.13344)](https://arxiv.org/pdf/2502.13344)
- [Comprehensive evaluation of deep and graph learning on DDI prediction (arXiv 2306.05257)](https://arxiv.org/pdf/2306.05257)

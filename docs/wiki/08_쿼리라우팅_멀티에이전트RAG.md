# 쿼리 라우팅 / 멀티에이전트 RAG 오케스트레이션

4개 이질적 소스(PubMed/약품/법률/가이드라인) 중 어디로 질의를 보낼지 결정하는 라우터 설계 — 이전 분석에서 "가장 레버리지 큰 컴포넌트"로 지목한 부분의 근거 자료.

## 핵심 논문
- **Talk to Right Specialists** (Iterative Routing in Multi-agent Systems for QA, arXiv 2501.07813): 여러 RAG 에이전트를 중앙 서버가 오케스트레이션 — 서버가 적합한 에이전트 그룹을 선택해 질의를 전달하고, 각 에이전트가 로컬 지식으로 응답한 뒤 서버가 결과를 종합하는 구조. 이 대회의 "4개 소스 → 라우터 → 종합" 구조와 정확히 일치하는 아키텍처.
- **RealRoute** (Dynamic Query Routing System via Retrieve-then-Verify Paradigm, arXiv 2604.20860): 검색 후 검증(retrieve-then-verify)하는 동적 라우팅 — 잘못된 소스로 라우팅된 경우를 사후에 걸러내는 안전장치 설계에 참고.
- **From Conflict to Consensus** (Boosting Medical Reasoning via Multi-Round Agentic RAG, arXiv 2603.03292): 여러 라운드에 걸쳐 에이전트 간 의견 충돌을 합의로 수렴시키는 멀티라운드 에이전틱 RAG — 여러 소스에서 상충하는 정보가 나올 때(예: 오래된 가이드라인 vs 최신 PubMed 논문) 처리하는 방식에 참고.
- **When More Documents Hurt RAG** (Vector Search Dilution, arXiv 2606.11350): 문서를 무분별하게 많이 넣으면 오히려 성능이 떨어진다는 지적 — **domain-scoped retrieval**(도메인별로 범위를 좁혀 검색)을 해법으로 제시. 4개 소스를 무조건 다 검색하기보다 라우터로 필요한 소스만 선별하는 것이 성능상 유리하다는 직접적 근거.
- **Adaptive RAG / Strategy Routing 개념**: "어디서 검색할지"뿐 아니라 "얼마나 깊게, 언제 검색할지"까지 라우팅 대상으로 삼는 최근 흐름 — 간단한 질문(예: "타이레놀 얼마나 먹어요")은 검색 깊이를 얕게, 복잡한 질문(예: "이 병 보험 적용되면서 이 약도 같이 처방 가능한가요")은 멀티소스 깊은 검색으로 분기.
- **Agentic RAG in Healthcare 개괄** (Maarga Systems 블로그): 헬스케어 맥락에서 에이전트가 EHR 벡터DB, 임상 지식그래프, PubMed 벡터스토어 등 특화 도구 중 선택하는 실무 패턴 정리.

## 전략적 시사점
- 라우터는 단순 분류기(질문 → 소스 태그)보다, 다중 소스 필요 여부까지 판단하는 구조가 필요 (예: "보험 적용되는 이 약의 부작용은?" → 법률+약품 동시 필요)
- Vector Search Dilution 연구는 "일단 다 검색해서 넣기" 전략이 실제로 성능을 깎아먹을 수 있음을 보여주므로, 관대한(permissive) 라우팅보다 보수적(precision 우선) 라우팅이 안전할 가능성
- Multi-Round Agentic RAG(합의 수렴) 아이디어는 소스 간 정보가 상충할 때(개정 전/후 법령, 오래된 논문 vs 최신 가이드라인) 최종 답변에서 최신·권위 있는 정보를 우선시하는 규칙을 명시적으로 넣는 설계와 연결됨

## 출처
- [Talk to Right Specialists (arXiv 2501.07813)](https://arxiv.org/html/2501.07813)
- [Top 20+ Agentic RAG Frameworks (aimultiple)](https://aimultiple.com/agentic-rag)
- [Multimodal Medical RAG Systems 개괄 (emergentmind)](https://www.emergentmind.com/topics/multimodal-medical-retrieval-augmented-generation-mmed-rag)
- [When More Documents Hurt RAG (arXiv 2606.11350)](https://arxiv.org/pdf/2606.11350)
- [RealRoute (arXiv 2604.20860)](https://arxiv.org/pdf/2604.20860)
- [From Conflict to Consensus (arXiv 2603.03292)](https://arxiv.org/html/2603.03292v3)
- [Exploring Agentic RAG in Healthcare (Maarga Systems)](https://www.maargasystems.com/2025/06/06/exploring-agentic-rag-in-healthcare/)

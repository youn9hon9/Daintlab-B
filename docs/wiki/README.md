# 리서치 인덱스

ConquerHealth 해커톤(루닛 주도 의과학 FM) 준비를 위해 사전 수집한 자료. 대회 공지/스펙 확정 전 조사분이라 실제 대회 규정과 다를 수 있음 — 스펙 공개 후 재검증 필요.

수집일: 2026-08-20 (1차 웹서치) / 갱신: 2026-08-20 (`docs/Claude-chat-log/` 두 파일과 교차 비교 후 보강 — 모델 정체(L1-16B-A3B)와 CoEval 저장소 실존은 WebFetch로 직접 검증 완료)

## ⭐ 공식 공지사항 (대회 주최 측 제공 — 최우선 확인)

아래 4개 문서는 대회 주최 측이 배포한 공식 공지/스펙 문서. 나머지 목차(01~13번)는 스펙 공개 전 사전 조사 자료이므로, 내용이 상충하면 **이 문서들이 우선**함.

1. [규칙](00_규칙.md) — 참여 조건, 제출 방식, evaluation 격리 환경, HealthBench reverse engineering 금지 등 대회 규정
2. [Lunit API로 build하기](00_Lunit_API로_build하기.md) — Lunit FM Model API 및 Patient Simulator(환자 시뮬레이터) 사용법, endpoint·curl 예제
3. [Lunit FM L2 사용 방법](00_Lunit_FM_L2_사용_방법.md) — L2(루닛 의료 특화 LLM)의 Retrieval/Generation 2단계 구조, `finalize_retrieval`·`retrieve_relevant_content` 설계 가이드
4. [Lunit MCP tools 살펴보기](00_Lunit_MCP_tools_살펴보기.md) — MCP server 연결 방법과 제공되는 전체 tool 목록(HIRA, KCD, MFDS, DailyMed, RAG 등)

## 목차
1. [루닛 의과학 FM / 트릴리온랩스 Gravity / 국가과제 배경](01_루닛_의과학FM.md) — **검증된 실제 모델(L1-16B-A3B)·CoEval 저장소 정보 포함, 최우선 정독**
2. [멀티소스 의료 RAG (PubMed+약물+가이드라인 결합)](02_멀티소스_의료RAG.md)
3. [약물 상호작용 그래프 RAG](03_약물상호작용_그래프RAG.md)
4. [법령/가이드라인 구조화 청킹](04_법령가이드라인_구조화청킹.md)
5. [멀티턴 환자 시뮬레이션 평가 프레임워크](05_멀티턴_환자시뮬레이션_평가.md)
6. [근거 정합성 / Hallucination 완화](06_근거정합성_hallucination.md)
7. [블라인드 평가 사례 (vs 프론티어 모델)](07_블라인드_평가_사례.md) — Med-PaLM 2 등 심사 방식의 직계 선행연구 포함
8. [쿼리 라우팅 / 멀티에이전트 RAG 오케스트레이션](08_쿼리라우팅_멀티에이전트RAG.md)
9. [국내 건강보험/법률 RAG 사례](09_국내_건강보험법률RAG_사례.md)
10. [안전성 · 과잉확신 캘리브레이션](10_안전성_캘리브레이션.md) — 신규
11. [가독성 · 공감 · 일반인 눈높이 변환](11_가독성_공감_변환.md) — 신규
12. [실제 제품 · 유즈케이스](12_실제제품_유즈케이스.md) — 신규
13. [자체 멀티턴 테스트 하네스 구축](13_자체_멀티턴_테스트하네스_구축.md) — 신규, CoEval의 사각지대(실시간 시뮬레이션 환자 멀티턴)를 보완할 재사용 가능한 오픈소스 코드(AgentClinic, HealthBench 독립구현, PatientSim) 정리

## CoEval 관련 핵심 결론 (01번 문서 심층 조사 요약)
CoEval은 16개 데이터셋 중 15개가 정적 단일턴 MCQA이고, 실시간 시뮬레이션 환자 에이전트가 반응형으로 다음 발화를 만드는 이 대회 고유의 멀티턴 구조는 CoEval에 없음. **CoEval만 파고드는 전략은 함정** — HealthBench-Consensus + Faithfulness/Contextual Precision·Recall 두 축만 우선순위로 삼고, 나머지는 기본기 확인용으로만 취급할 것. 이 사각지대는 [13번 문서](13_자체_멀티턴_테스트하네스_구축.md)의 자체 하네스로 보완.

## 다음 단계
- 대회 공지 후: RAG 엔드포인트 API 스펙, 멀티턴 하네스 스펙과 이 자료들을 교차 검증 (CoEval은 이미 검증 완료 — [01번](01_루닛_의과학FM.md) 참고)
- "링크 미확인" 표시된 논문들(MedPRESS, CLEVER, MedArena, RephQA 등)의 정확한 출처를 확인해 신뢰도 보강
- [13번 문서](13_자체_멀티턴_테스트하네스_구축.md)의 AgentClinic/m42-health-healthbench를 실제로 클론해서 우리 챗봇 프로토타입이 나오는 대로 3턴 자체 시뮬레이션 루프를 돌려볼 것
- 위 자료를 바탕으로 상황별 전략 문서(예: "소스 라우팅 전략", "턴1 응답 설계 전략", "근거 인용 강제 전략", "레드플래그 게이트 설계") 작성 예정

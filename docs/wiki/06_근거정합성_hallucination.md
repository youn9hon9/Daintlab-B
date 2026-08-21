# 근거 정합성 / Hallucination 완화

임상의 블라인드 채점자가 가장 민감하게 반응할 것으로 예상되는 축. "검색은 맞게 했는데 생성 단계에서 근거를 무시하고 지어내는" 문제를 다루는 자료.

## 핵심 논문 및 개념
- **FaithMed** (Training LLMs For Faithful Evidence-Based Medical Reasoning, arXiv 2607.01440): 의료 도메인에 특화해 "충실한 근거 기반 추론"을 학습시키는 접근 — 파인튜닝이 가능하다면 직접 참고할 방법론.
- **MedCite**: 의료 도메인에 맞춘 인용 생성·검색 전략과 전용 평가 프로토콜로 응답의 "검증가능성(verifiability)"을 강조하는 최근 연구 흐름 (검색 스니펫에서 확인, 원문은 추가 확인 필요).
- **Benchmarking LLM Faithfulness in RAG with Evolving Leaderboards** (ACL EMNLP-Industry 2025): faithfulness/groundedness를 1차 지표, context adherence를 2차 지표로 삼는 평가 관행 정리.
- **핵심 실패 유형 4가지**: factual(사실 오류) / grounding(근거 없이 주장) / citation(인용 조작) / reasoning(추론 오류) — 이 네 가지를 뭉뚱그려 하나의 점수로 보면 무엇을 고쳐야 할지 알 수 없다는 지적. → 자체 내부 평가 시에도 이 4축으로 분리해 채점하는 것이 디버깅에 유리.
- **Citation 환각의 특수 패턴**: 검색된 청크에 정확한 출처가 있음에도 모델이 이를 무시하고 더 그럴듯한 가짜 출처를 지어내는 사례가 다수 보고됨 — 단순히 "검색 결과를 잘 넣어주는 것"만으로는 부족하고, 생성 단계에서 인용 강제(citation enforcement)가 필요함을 시사.
- **완화 기법 조합**: (1) grounding-discipline 프롬프트 + (2) 생성 시 인용 강제 + (3) 출력 후 claim 단위 entailment(함의) 검증 — 3단계 조합이 실무적으로 권장됨. 사용자에게 검증 결과를 노출하는 것도 신뢰도 제고에 도움.

## 전략적 시사점
- 최종 답변 생성 후, "이 문장이 실제로 검색된 청크에서 지지되는가"를 확인하는 **자체 검증(self-verification) 에이전트**를 파이프라인 마지막 단계에 추가하는 것이 근거 정합성 확보에 가장 비용 대비 효과적인 장치로 보임
- 인용 표기를 강제하는 프롬프트 설계(예: 문장마다 출처 태그) 자체가 hallucination을 줄이는 효과가 있다는 근거가 있으므로, 최종 답변 포맷에 출처 표기를 기본값으로 넣는 것을 고려할 만함 (단, 일반 국민 대상 챗봇이므로 과도한 각주는 가독성을 해칠 수 있어 톤 조절 필요)
- "오래된 출처를 최신인 것처럼 제시"하는 citation 환각 패턴은 법률/가이드라인처럼 개정이 잦은 소스에서 특히 위험 — 문서의 시행일자/개정일자를 검색 결과에 함께 포함시켜 모델이 시점을 인지하게 하는 것이 중요

## 출처
- [FaithMed (arXiv 2607.01440)](https://arxiv.org/pdf/2607.01440)
- [Benchmarking LLM Faithfulness in RAG (ACL Anthology 2025.emnlp-industry.54)](https://aclanthology.org/2025.emnlp-industry.54/)
- [LLM Hallucination: A 2026 Architectural Deep Dive (FutureAGI)](https://futureagi.com/blog/llm-hallucination-deep-dive-2026/)
- [LLM Hallucinations in 2026 (Lakera)](https://www.lakera.ai/blog/guide-to-hallucinations-in-large-language-models)
- [How to Reduce LLM Hallucinations (Zep)](https://www.getzep.com/ai-agents/reducing-llm-hallucinations/)
- [RAG Grounding: 11 Tests That Expose Fake Citations (Medium/Nexumo)](https://medium.com/@Nexumo_/rag-grounding-11-tests-that-expose-fake-citations-30d84140831a)

# Documentation

이 디렉터리는 대회 공식 정보, 구현 가이드, 실제 인터페이스 확인 결과, 사전 리서치를 하나의 문서 체계로 관리한다.

## 문서 우선순위

내용이 충돌하면 다음 순서로 판단한다.

1. `wiki/00_*`: 주최 측 공식 규칙과 API/L2/MCP 안내
2. `implementation/`: 실제 endpoint와 tool schema를 확인한 기록
3. `guides/`: 공식 내용을 구현 절차와 체크리스트로 재구성한 문서
4. `wiki/15_*` 이후: 공식 스펙 공개 후 작성한 실무 분석
5. `wiki/01_*`~`13_*`: 공식 스펙 공개 전 사전 리서치

추정이나 과거 모델 정보가 공식 문서와 충돌하면 공식 문서를 따른다. `implementation/`의 확인 날짜 이후 인터페이스가 바뀌었을 가능성이 있으면 런타임 schema를 다시 조회한다.

## 디렉터리

### `guides/`

- [L2 사용 가이드](guides/Lunit_FM_L2_Guide.md)
- [MCP Tools 가이드](guides/Lunit_MCP_Tools_Guide.md)
- [Model API 가이드](guides/Lunit_Model_API_Guide.md)
- [제출 가이드](guides/Lunit_Submission_Guide.md)

공식 문서를 개발자가 바로 실행할 수 있는 순서와 체크리스트로 풀어쓴다.

### `implementation/`

- [아키텍처 경계](implementation/architecture.md)
- [MCP tool 실제 schema 확인](implementation/lunit_mcp_tools.md)

코드가 의존하는 실제 계약과 확인 시점을 기록한다. 추상적인 전략보다 구현 시 우선 확인한다.

### `wiki/`

[리서치 인덱스](wiki/README.md)를 시작점으로 사용한다. 공식 문서, 배경 조사, RAG·안전성·평가 연구, 국내 의료 데이터 소스 실무가 포함되어 있다.

## 통합해서 얻은 핵심 교훈

- 제출 API와 내부 오케스트레이션은 분리한다. evaluator 계약은 안정적으로 유지하면서 검색·prompt 실험은 교체 가능해야 한다.
- L2는 범용 chat model이 아니다. Generation과 Retrieval을 분리하고 각 단계에 공식적으로 허용된 도구만 제공한다.
- Retrieval L2가 MCP 도구를 선택하게 한다. 참가자 라우터가 tool 전체를 임의로 제한하는 것은 공식 권장 구조와 다르다.
- 검색 결과가 곧 인용 근거는 아니다. navigation tool 이후 `cite_uid`를 제공하는 content tool까지 호출해야 한다.
- SQL은 실제 schema를 먼저 조회한 뒤 생성한다. 공개 데이터의 일반 스키마를 대회 인스턴스에 그대로 가정하지 않는다.
- 멀티턴에서는 최신 발화만 검색하지 않는다. 대명사와 생략된 대상을 해소한 자기완결형 query가 필요하다.
- 개발 도구와 제출 runtime을 분리한다. 평가 환경은 격리되어 있으므로 임의 외부 API나 런타임 다운로드에 의존하지 않는다.
- 복잡한 기능은 baseline 대비 측정 가능한 개선이 확인된 경우에만 제출 경로에 넣는다.

상세한 구현 판단과 단계별 체크리스트는 [Engineering Playbook](engineering/playbook.md)을 참고한다.

## 평가 피드백

- [D1 평가 피드백](evaluations/D1.md)
- [U1 평가 피드백](evaluations/U1.md)
- [D2 평가 피드백](evaluations/D2.md)
- [U2 평가 피드백](evaluations/U2.md)
- [D3 평가 피드백](evaluations/D3.md)
- [D4 평가 피드백](evaluations/D4.md)
- [Y1 평가 피드백](evaluations/Y1.md)
- [D5 평가 피드백](evaluations/D5.md)
- [Y2 평가 피드백](evaluations/Y2.md)

## 실행 계획

- [Hackathon 실행 계획](planning/HACKATHON_PLAN.md)

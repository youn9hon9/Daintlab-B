# 대회 공식 계약

주최 측 자료를 구현 관점에서 정리한 canonical source다. 같은 내용의 `guides`와
`wiki/00_*` 복사본은 제거했다. 모델 개선 에이전트는 전략을 세우기 전에 이 계약을
먼저 확인한다.

## 읽는 순서

1. [대회 규칙](rules.md): 격리 평가, 허용 범위, 최종 평가 원칙
2. [Lunit FM L2](l2.md): Retrieval과 Generation의 공식 역할 분리
3. [MCP tools](mcp-tools.md): 제공 도구와 호출 방식
4. [Model API](model-api.md): 인증, 요청·응답, Patient Simulator
5. [제출 규격](submission.md): Docker, endpoint, SHA와 model 이름

## 변경 규칙

- 공식 공지가 바뀔 때만 이 디렉터리를 수정한다.
- 로컬에서 관측한 latency, timeout, score는 여기에 쓰지 않고 `evaluations`에 둔다.
- 공식 자료에 없는 설계 제안은 `wiki`에 두고 “전략” 또는 “가설”로 표시한다.
- 실제 API key는 예시·로그·Dockerfile·Git에 넣지 않는다.

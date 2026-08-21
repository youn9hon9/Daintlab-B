# 규칙

- 원격 참여는 가능하지만 endpoint와 dashboard를 포함한 Lunit asset은 Lunit network 밖에서 접근할 수 없습니다.
- 최종 출력물은 반드시 Lunit의 LLM인 L2를 사용하여 생성해야 합니다.
- 제공된 MCP tools 외에도 적절한 license를 확보한 외부 data source를 사용할 수 있습니다.
- 제공된 Codex를 coding agent로 사용하세요.
- 하나의 제출물로 Benchmark 부문과 Frontier 부문 시상에 공통으로 사용됩니다. (제출 안내 보기)
- 개발 중에는 harness를 자유롭게 구성하고 선택할 수 있습니다. Evaluation은 외부 접근이 없는 완전히 격리된 환경에서 실행됩니다.
- HealthBench benchmark를 과도하게 reverse engineering하는 행위는 금지됩니다. 관리자 code review에서 확인되면 해당 팀은 수상 자격을 잃습니다.

## Benchmark 및 Evaluation 세부사항

- Hackathon 중, dashboard를 통해 주최 측이 지정한 검증 세트(validation set)에서 솔루션을 테스트하고 벤치마크 성능을 측정할 수 있습니다. 이를 활용해 솔루션을 debug하고, 제출물이 평가 서버에서 정상적으로 실행되는지 확인하시기 바랍니다.
- 마지막으로 dashboard를 통해 전송된 제출물을 최종 제출로 간주합니다. 각 팀의 최종 제출물은 운영진이 정의한 별도의 HealthBench holdout test set으로 평가합니다.
- 같은 제출물을 chat 품질에 대한 전문가 평가에도 사용합니다.
- Evaluation은 완전히 격리된 환경에서 실행되며 외부 접근은 허용되지 않습니다.

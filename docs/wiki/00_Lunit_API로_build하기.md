# Lunit FM API 및 Patient Simulator 사용법

## Endpoint

| 구분 | URL |
| --- | --- |
| Lunit FM | <https://model.hackathon.lunit.io/> |
| Patient Simulator | <https://patient.hackathon.lunit.io/> |

## Model API 사용 방법

먼저 `lunit_`으로 시작하는 팀 API key를 생성하세요. 동일한 API key를 Model, Patient Simulator, MCP endpoint에서 모두 사용할 수 있습니다.

### Shell 환경 설정

```bash
export LUNIT_FM_API_URL="https://model.hackathon.lunit.io"
export LUNIT_FM_API_KEY="lunit_..."
export LUNIT_FM_MODEL="Lunit/L2-preview"
```

### Chat Completions API

```bash
curl "$LUNIT_FM_API_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LUNIT_FM_API_KEY" \
  -d '{
    "model": "'"${LUNIT_FM_MODEL}"'",
    "messages": [
      {"role": "system", "content": "You are a careful medical assistant."},
      {"role": "user", "content": "Summarize the key findings."}
    ]
  }'
```

### 고급: Tool call을 사용하는 Chat Completions

지원 parameter를 참고하세요.

## Patient Simulator란?

Patient Simulator는 한국어 의료 대화에서 환자 또는 임상의 역할인 user 측을 재현하는 OpenAI-compatible 질문 생성기입니다.

Harness는 대화의 assistant입니다. Simulator message는 user turn이고, system 응답은 assistant turn입니다. 전체 conversation history를 client에서 유지하고 매 turn마다 POST하세요. Session ID는 필요하지 않습니다.

### 첫 질문 생성

빈 `messages` array를 보내세요. 요청할 때마다 새 질문을 반환합니다.

```bash
curl -s "https://patient.hackathon.lunit.io/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LUNIT_FM_API_KEY" \
  -d '{
    "model": "patient-simulator-ko",
    "messages": []
  }' \
  | jq -r '.choices[0].message.content'
```

새 질문만 필요하면 이 요청을 반복하세요. 동시 요청을 지원하며, 한 번 호출하는 데 약 14초가 걸립니다.

### 후속 질문 생성

받은 질문과 system 답변을 표시된 그대로 추가한 뒤 전체 history를 다시 보내세요.

```bash
curl -s "https://patient.hackathon.lunit.io/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LUNIT_FM_API_KEY" \
  -d '{
    "model": "patient-simulator-ko",
    "messages": [
      {"role": "user", "content": "<received question>"},
      {"role": "assistant", "content": "<your system answer>"}
    ]
  }' \
  | jq -r '.choices[0].message.content'
```

후속 질문 생성에는 약 8초가 걸립니다.

### 주의사항

- 첫 질문을 정확히 보존하세요. 수정하면 conversation continuation이 깨질 수 있습니다.
- 약 3 turn 후에 중단하세요. 대화가 길어지면 같은 질문을 반복할 수 있습니다.
- 응답이 `404`이면 빈 `messages` array로 새 대화를 시작하세요.
- 응답이 `502`이면 요청을 다시 시도하세요.

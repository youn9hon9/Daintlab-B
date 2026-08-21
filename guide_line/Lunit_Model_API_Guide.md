# Lunit Model API 사용 가이드

## 1. 문서 목적

이 문서는 Lunit Hackathon에서 다음 API를 호출하는 방법과 harness 구현 시 지켜야 할 동작을 정리한다.

- **Lunit FM Model API**: Lunit FM을 OpenAI-compatible Chat Completions 형식으로 호출한다.
- **Patient Simulator API**: 한국어 의료 대화의 사용자 역할을 생성한다.

---

## 2. Endpoint

| 서비스 | Base URL | 역할 |
|---|---|---|
| Lunit FM | `https://model.hackathon.lunit.io` | Lunit FM 모델 호출 |
| Patient Simulator | `https://patient.hackathon.lunit.io` | 환자 또는 임상의 역할의 사용자 발화 생성 |

관련 링크:

- [Lunit FM endpoint](https://model.hackathon.lunit.io/)
- [Patient Simulator endpoint](https://patient.hackathon.lunit.io/)
- [API key 발급](https://dashboard.hackathon.lunit.io/api-keys)

---

## 3. 인증 및 환경변수

### 3.1 API key

먼저 Hackathon dashboard에서 `lunit_`으로 시작하는 API key를 생성한다.

동일한 팀 API key를 다음 서비스에 공통으로 사용할 수 있다.

- Lunit FM Model API
- Patient Simulator API
- Hackathon MCP endpoint

API key는 코드나 Git 저장소에 직접 작성하지 않고 환경변수로 관리한다.

### 3.2 Shell 환경 설정

```bash
export LUNIT_FM_API_URL="https://model.hackathon.lunit.io"
export LUNIT_PATIENT_API_URL="https://patient.hackathon.lunit.io"
export LUNIT_FM_API_KEY="lunit_..."
export LUNIT_FM_MODEL="Lunit/L2-preview"
export LUNIT_PATIENT_MODEL="patient-simulator-ko"
```

> `LUNIT_FM_API_KEY`의 실제 값은 문서, 로그, 소스 코드 또는 공개 저장소에 남기지 않는다.

---

## 4. Lunit FM Model API

### 4.1 기본 요청 형식

Lunit FM은 OpenAI-compatible Chat Completions API로 호출한다.

```text
POST {LUNIT_FM_API_URL}/v1/chat/completions
Authorization: Bearer {LUNIT_FM_API_KEY}
Content-Type: application/json
```

기본 request body 구조:

```json
{
  "model": "Lunit/L2-preview",
  "messages": [
    {
      "role": "system",
      "content": "You are a careful medical assistant."
    },
    {
      "role": "user",
      "content": "Summarize the key findings."
    }
  ]
}
```

### 4.2 cURL 예시

```bash
curl "$LUNIT_FM_API_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LUNIT_FM_API_KEY" \
  -d '{
    "model": "'"${LUNIT_FM_MODEL}"'",
    "messages": [
      {
        "role": "system",
        "content": "You are a careful medical assistant."
      },
      {
        "role": "user",
        "content": "Summarize the key findings."
      }
    ]
  }'
```

응답에서 일반적으로 사용할 값은 다음 위치에 있다.

```text
choices[0].message
```

텍스트 응답만 추출하려면 `jq`를 사용할 수 있다.

```bash
curl -s "$LUNIT_FM_API_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LUNIT_FM_API_KEY" \
  -d '{
    "model": "'"${LUNIT_FM_MODEL}"'",
    "messages": [
      {
        "role": "system",
        "content": "You are a careful medical assistant."
      },
      {
        "role": "user",
        "content": "Summarize the key findings."
      }
    ]
  }' \
  | jq -r '.choices[0].message.content'
```

### 4.3 Tool call 사용

Lunit FM에서 tool call을 사용할 때도 Chat Completions request의 `tools` 및 관련 parameter를 사용한다.

L2는 일반적인 단일 호출형 chat model과 다르게 Retrieval과 Generation을 분리해 사용하는 것이 권장된다. 각 단계에 제공할 tool과 system prompt는 `Lunit_FM_L2_Guide.md`의 구조를 따른다.

- Retrieval 단계: Hackathon MCP tools + 직접 정의한 `finalize_retrieval`
- Generation 단계: 직접 정의한 `retrieve_relevant_content`만 제공

지원 parameter의 세부 사항은 [vLLM OpenAI-compatible server 문서](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/#extra-parameters_1)를 참고한다.

---

## 5. Patient Simulator

### 5.1 역할

Patient Simulator는 한국어 의료 대화에서 **환자 또는 임상의 역할인 사용자 측 발화**를 재현하는 OpenAI-compatible 질문 생성기이다.

대화 역할은 다음과 같이 고정한다.

| 대화 참여자 | Chat Completions role |
|---|---|
| Patient Simulator가 생성한 질문 | `user` |
| 우리가 구현한 harness의 응답 | `assistant` |

Patient Simulator가 assistant 역할을 하는 것이 아니다. **harness가 대화의 assistant이고, Simulator가 user turn을 생성한다.**

### 5.2 상태 관리 방식

Patient Simulator는 별도의 session ID를 사용하지 않는다.

Client가 다음을 수행해야 한다.

1. 전체 `messages` conversation history를 로컬에서 유지한다.
2. Patient Simulator가 생성한 질문을 `user` message로 저장한다.
3. Harness가 만든 답변을 `assistant` message로 저장한다.
4. 후속 질문을 요청할 때 전체 history를 다시 POST한다.

---

## 6. 첫 질문 생성

### 6.1 요청 규칙

새 대화를 시작하려면 빈 `messages` array를 보낸다.

```json
{
  "model": "patient-simulator-ko",
  "messages": []
}
```

### 6.2 cURL 예시

```bash
curl -s "$LUNIT_PATIENT_API_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LUNIT_FM_API_KEY" \
  -d '{
    "model": "'"${LUNIT_PATIENT_MODEL}"'",
    "messages": []
  }' \
  | jq -r '.choices[0].message.content'
```

새 질문만 필요하다면 빈 `messages` array로 동일한 요청을 반복한다.

- 동시 요청을 지원한다.
- 첫 질문 생성에는 한 번 호출할 때 약 **14초**가 걸린다.

각 빈-history 요청은 새로운 대화의 시작으로 취급한다.

---

## 7. 후속 질문 생성

### 7.1 요청 규칙

후속 질문을 받으려면 다음 두 message를 history에 순서대로 추가한다.

1. Simulator에서 받은 질문: `user`
2. Harness가 생성한 답변: `assistant`

그 뒤 누적된 전체 history를 Patient Simulator에 다시 보낸다.

```json
{
  "model": "patient-simulator-ko",
  "messages": [
    {
      "role": "user",
      "content": "<received question>"
    },
    {
      "role": "assistant",
      "content": "<your system answer>"
    }
  ]
}
```

### 7.2 cURL 예시

```bash
curl -s "$LUNIT_PATIENT_API_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LUNIT_FM_API_KEY" \
  -d '{
    "model": "'"${LUNIT_PATIENT_MODEL}"'",
    "messages": [
      {
        "role": "user",
        "content": "<received question>"
      },
      {
        "role": "assistant",
        "content": "<your system answer>"
      }
    ]
  }' \
  | jq -r '.choices[0].message.content'
```

후속 질문 생성에는 약 **8초**가 걸린다.

### 7.3 여러 turn의 history 예시

두 번째 harness 답변 이후 다음 후속 질문을 요청한다면 history는 다음과 같은 형태가 된다.

```json
{
  "model": "patient-simulator-ko",
  "messages": [
    {
      "role": "user",
      "content": "<first simulator question>"
    },
    {
      "role": "assistant",
      "content": "<first harness answer>"
    },
    {
      "role": "user",
      "content": "<second simulator question>"
    },
    {
      "role": "assistant",
      "content": "<second harness answer>"
    }
  ]
}
```

Patient Simulator의 새로운 응답은 다시 `user` message로 history 끝에 추가한다.

---

## 8. Patient Simulator 사용 시 주의사항

### 8.1 첫 질문 보존

Simulator에서 받은 첫 질문을 **문자열 그대로 보존**한다.

- 맞춤법이나 표현을 임의로 수정하지 않는다.
- 번역하거나 요약하지 않는다.
- 공백, 문장 내용 등을 변경한 사본 대신 원본 응답을 history에 사용한다.

첫 질문을 수정하면 conversation continuation이 깨질 수 있다.

### 8.2 대화 길이 제한

약 **3 turn 이후 대화를 중단**하는 것을 권장한다. 대화가 길어지면 Simulator가 같은 질문을 반복할 수 있다.

여기서 한 turn은 일반적으로 다음 한 쌍을 의미한다.

```text
Simulator의 user 질문 → Harness의 assistant 답변
```

### 8.3 오류 처리

| HTTP status | 의미 또는 대응 |
|---|---|
| `404` | 현재 continuation을 중단하고 빈 `messages` array로 새 대화를 시작한다. |
| `502` | 동일 요청을 다시 시도한다. |

`502` 재시도 시에는 무한 반복을 피하기 위해 harness에서 최대 재시도 횟수를 정하는 것이 좋다.

---

## 9. 전체 대화 실행 흐름

```text
1. Patient Simulator에 messages=[] 전송
2. 첫 질문 수신
3. 질문 원문을 user message로 history에 저장
4. 질문을 Lunit FM harness에 전달
5. Harness 답변을 assistant message로 history에 저장
6. 전체 history를 Patient Simulator에 전송
7. 후속 질문 수신
8. 3~7을 약 3 turn까지 반복
9. 404 발생 시 새 대화 시작
10. 502 발생 시 제한된 횟수만큼 재시도
```

---

## 10. Harness용 상태 구조 예시

다음과 같이 conversation history와 제어 정보를 분리해 관리할 수 있다.

```python
from dataclasses import dataclass, field
from typing import Literal, TypedDict


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass
class PatientConversation:
    messages: list[Message] = field(default_factory=list)
    completed_turns: int = 0
    max_turns: int = 3

    def add_patient_question(self, question: str) -> None:
        # Simulator 응답 원문을 수정하지 않고 저장한다.
        self.messages.append({"role": "user", "content": question})

    def add_harness_answer(self, answer: str) -> None:
        self.messages.append({"role": "assistant", "content": answer})
        self.completed_turns += 1

    def should_continue(self) -> bool:
        return self.completed_turns < self.max_turns

    def restart(self) -> None:
        self.messages = []
        self.completed_turns = 0
```

이 코드는 상태 관리 예시이며, 실제 HTTP 호출과 오류 처리는 별도로 구현한다.

---

## 11. 구현 체크리스트

### 공통

- [ ] API key를 dashboard에서 발급했는가?
- [ ] API key를 환경변수로 관리하는가?
- [ ] 실제 API key가 코드, 로그, 문서 또는 Git에 포함되지 않는가?
- [ ] 모든 요청에 `Authorization: Bearer ...` header를 넣는가?
- [ ] 모든 요청에 `Content-Type: application/json` header를 넣는가?

### Lunit FM

- [ ] `https://model.hackathon.lunit.io/v1/chat/completions`를 호출하는가?
- [ ] 모델 이름으로 `Lunit/L2-preview`를 사용하는가?
- [ ] `messages`에 올바른 `system`, `user`, `assistant` role을 사용하는가?
- [ ] L2의 Retrieval과 Generation 단계를 별도 호출로 구성했는가?
- [ ] 각 단계에 필요한 tool만 제공했는가?

### Patient Simulator

- [ ] `https://patient.hackathon.lunit.io/v1/chat/completions`를 호출하는가?
- [ ] 모델 이름으로 `patient-simulator-ko`를 사용하는가?
- [ ] 첫 질문 요청에 빈 `messages` array를 보내는가?
- [ ] Simulator 응답을 `user` turn으로 저장하는가?
- [ ] Harness 응답을 `assistant` turn으로 저장하는가?
- [ ] 매 후속 요청에 전체 conversation history를 보내는가?
- [ ] 첫 질문의 원문을 수정하지 않고 보존하는가?
- [ ] 약 3 turn 후 대화를 종료하는가?
- [ ] `404` 발생 시 빈 history로 재시작하는가?
- [ ] `502` 발생 시 제한된 횟수만큼 재시도하는가?

---

## 12. 핵심 요약

1. Lunit FM과 Patient Simulator는 모두 OpenAI-compatible Chat Completions API로 호출한다.
2. 동일한 `lunit_...` API key를 Model, Patient Simulator, MCP endpoint에 사용할 수 있다.
3. Patient Simulator는 `user` 발화를 만들고, 우리가 구현한 harness는 `assistant` 역할을 한다.
4. 별도의 session ID 대신 client가 전체 `messages` history를 유지하고 매 요청에 다시 전송한다.
5. 새 대화는 `messages: []`로 시작하며, 첫 질문 원문을 수정하지 않고 보존한다.
6. 대화는 약 3 turn까지만 진행하고, `404`는 새 대화 시작, `502`는 재시도로 처리한다.

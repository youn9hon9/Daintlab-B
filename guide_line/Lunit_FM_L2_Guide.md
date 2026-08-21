# Lunit FM L2 사용 가이드

## 1. 개요

L2는 Lunit이 개발한 **의료 특화 LLM**이다. 범용 채팅 모델이 아니므로, 일반적인 LLM과 동일한 방식으로 호출하면 기대한 대로 동작하지 않을 수 있다.

L2의 핵심 특성은 다음과 같다.

1. **Retrieval**과 **Generation**을 명확히 분리하며, 각 단계에서 모델을 별도로 호출한다.
2. Retrieval 단계에서 evidence와 관련 정보를 수집하도록 **Hackathon에서 제공하는 특정 MCP tool set**으로 학습되었다.

따라서 이 모델을 효과적으로 사용하려면 두 단계를 연결하고 제어하는 **harness**를 구현해야 한다. 이 harness 설계가 Hackathon의 핵심 과제 중 하나이다.

---

## 2. 전체 구조

L2의 권장 실행 흐름은 다음과 같다.

```text
사용자 질문
    ↓
Generation 단계
    ├─ 모델의 내부 지식만으로 답변 가능 → 최종 답변 생성
    └─ 외부 근거가 필요함
            ↓
       retrieve_relevant_content 호출
            ↓
       Retrieval 단계 별도 실행
            ├─ MCP tools로 문서 검색 및 열람
            ├─ 관련 evidence 선택
            └─ finalize_retrieval 호출
            ↓
       선택한 evidence를 Generation 단계에 반환
            ↓
       근거 기반 최종 답변 생성
```

핵심 원칙은 다음과 같다.

- Retrieval 모델은 **근거를 찾고 선택**한다.
- Generation 모델은 선택된 근거를 바탕으로 **최종 답변을 작성**한다.
- 두 단계는 서로 다른 system prompt와 tool 구성으로 실행한다.

---

## 3. Retrieval 단계

### 3.1 목적

Retrieval 단계는 사용자 질문에 답하는 데 필요한 evidence를 수집하는 단계이다.

모델은 다음 작업을 반복한다.

1. 필요한 evidence가 무엇인지 판단한다.
2. Hackathon에서 제공하는 MCP tools를 사용해 관련 문서를 검색한다.
3. 문서 구조, 관련 node, 실제 페이지 내용을 차례로 확인한다.
4. 답변에 사용할 수 있는 item을 선택한다.
5. `finalize_retrieval`을 호출하여 Retrieval을 종료한다.

Retrieval 단계에서는 **사용자에게 전달할 최종 답변을 작성하지 않는다.**

### 3.2 `cite_uid`

일부 MCP tool result에는 `cite_uid` field가 포함된다.

- `cite_uid`는 해당 item을 citation 가능한 근거로 표시하는 식별자이다.
- Retrieval이 끝나면 모델은 원문 전체가 아니라, 관련 있다고 판단한 item의 `cite_uid`를 선택해 보고한다.
- Generation 단계에서는 이 식별자에 대응하는 실제 content를 전달받아 답변과 citation을 생성한다.

### 3.3 `finalize_retrieval`

Retrieval 단계를 정상적으로 끝내기 위해 모델은 반드시 `finalize_retrieval`을 호출해야 한다.

이 함수는 Hackathon에서 제공하는 MCP tool이 아니다. **harness에서 직접 정의**한 뒤 Retrieval 단계의 MCP tools와 함께 모델에 제공해야 한다. Retrieval용 system prompt에도 반드시 이 함수를 호출해 단계를 종료하도록 명시한다.

```python
from typing import Literal

from pydantic import BaseModel, Field


class CitableItem(BaseModel):
    cite_uid: str
    relevance_score: float


class CitationSelection(BaseModel):
    status: Literal["sufficient", "partial", "no_evidence"]
    items: list[CitableItem] = Field(default_factory=list)
    note: str = ""


def finalize_retrieval(
    status: Literal["sufficient", "partial", "no_evidence"],
    items: list[CitableItem],
    note: str = "",
) -> CitationSelection:
    """Submit the final citation selection and end the retrieval phase.

    Call this only when:
    - enough evidence has been gathered to answer the query;
    - the query does not require retrieval; or
    - the tool-call budget has been exhausted and retrieval must end.
    """
    return CitationSelection(status=status, items=items, note=note)
```

`status`의 의미는 다음과 같다.

| 값 | 의미 |
|---|---|
| `sufficient` | 질문에 답하기에 충분한 근거를 확보함 |
| `partial` | 일부 관련 근거만 확보했으며 완전한 답변에는 부족함 |
| `no_evidence` | 관련 근거를 찾지 못했거나 retrieval이 필요하지 않음 |

`note`에는 evidence의 한계, 검색 실패 사유, Generation 단계가 알아야 할 주의사항 등을 전달할 수 있다.

### 3.4 Retrieval trajectory 예시

사용자 질문:

> 가이드라인에 따르면 만성 신장질환 환자에게 어떤 혈압 목표를 권고하나요?

Retrieval 모델의 실행 예시:

```python
index_list_documents(
    corpus_tag="guideline",
    query="hypertension chronic kidney disease",
)
```

예상 결과:

```text
12 documents, each with node_id, title, summary
```

```python
index_get_relevant_nodes(
    corpus_tag="guideline",
    query="blood pressure target CKD",
    node_id="0823b",
)
```

예상 결과:

```text
4 leaf nodes with their page ranges and ancestor chains
```

```python
index_get_page_content(
    corpus_tag="guideline",
    doc_id="0823b",
    start_page=48,
    end_page=52,
)
```

예상 결과:

```text
Page text for pages 48–52, carrying cite_uid "cite-3f9a1c7d2e5b8046"
```

근거가 충분하다면 다음과 같이 종료한다.

```python
finalize_retrieval(
    status="sufficient",
    items=[
        {
            "cite_uid": "cite-3f9a1c7d2e5b8046",
            "relevance_score": 0.95,
        }
    ],
    note="",
)
```

---

## 4. Generation 단계

### 4.1 목적

Generation 단계는 사용자에게 전달할 최종 답변을 생성한다.

질문을 받으면 모델은 먼저 다음을 판단한다.

1. 모델의 내부 지식만으로 답할 수 있는가?
2. 정확한 답변을 위해 외부 정보나 특정 문서의 근거가 필요한가?

일반적인 의료 질문은 내부 지식만으로 직접 답할 수 있다. 반면 특정 guideline, 법률, 최신 문서 등에 근거한 정확한 답변이 필요하면 Retrieval을 사용해야 한다.

### 4.2 제공할 tool

Generation 단계에는 **`retrieve_relevant_content` 하나만 제공**한다. Retrieval용 MCP tools나 `finalize_retrieval`을 Generation 모델에 직접 제공하지 않는다.

```python
def retrieve_relevant_content(query: str):
    """Retrieve relevant content to ground the answer.

    The query must be a single, self-contained query.
    """
    # 1. Retrieval 단계를 별도의 L2 호출로 실행한다.
    # 2. finalize_retrieval 결과에서 선택된 cite_uid를 확인한다.
    # 3. cite_uid에 대응하는 실제 content와 출처 정보를 구성한다.
    # 4. 구성한 evidence를 Generation 모델에 반환한다.
```

이 함수 내부에서 Retrieval 단계를 실행하고, 선택된 관련 정보를 Generation 모델이 읽을 수 있는 형태로 반환한다. Retrieval과 Generation을 연결하는 구체적인 방식은 자유롭게 설계할 수 있다.

### 4.3 Generation trajectory 예시

사용자 질문:

> 가이드라인에 따르면 만성 신장질환 환자에게 어떤 혈압 목표를 권고하나요?

Generation 모델의 tool call:

```python
retrieve_relevant_content(
    query="recommended blood pressure target for adults with chronic kidney disease"
)
```

Tool result 예시:

```text
status: sufficient

[1]
source_type: guideline
url: https://example.org/guideline/0823b
title: 2024 Clinical Practice Guideline for the Management of Hypertension
content: In adults with chronic kidney disease, treat to a systolic blood
pressure target of less than 120 mmHg when tolerated, ...
```

Generation 모델의 최종 답변 예시:

> 가이드라인에 따르면 만성 신장질환 성인에게 내약 가능한 경우 수축기 혈압 120 mmHg 미만을 목표로 치료할 것을 권고합니다 [1].

---

## 5. 단계별 구성 요약

| 구분 | Retrieval 단계 | Generation 단계 |
|---|---|---|
| 주요 목적 | 관련 evidence 검색 및 선택 | 사용자용 최종 답변 생성 |
| 모델 호출 | 별도 L2 호출 | 별도 L2 호출 |
| System prompt | Retrieval 전용 | Generation 전용 |
| 제공 tools | Hackathon MCP tools + `finalize_retrieval` | `retrieve_relevant_content`만 제공 |
| 최종 출력 | `status`, 선택한 `cite_uid`, `note` | 근거와 citation을 포함한 자연어 답변 |
| 금지 사항 | 최종 답변 작성 | Retrieval MCP tools 직접 호출 |

---

## 6. System prompt 설계 원칙

### 6.1 Retrieval용 prompt

Retrieval 모델에는 다음 사항을 명시한다.

- 사용자 질문에 답하는 데 필요한 evidence만 탐색한다.
- MCP tools를 이용해 검색, node 탐색, 페이지 열람을 반복한다.
- 최종 답변을 작성하지 않는다.
- citation 가능한 item의 `cite_uid`만 선택한다.
- 충분한 근거 확보, 검색 불필요 또는 tool-call budget 소진 시 `finalize_retrieval`을 호출한다.
- 정해진 최대 tool-call 횟수를 초과하지 않는다.

### 6.2 Generation용 prompt

Generation 모델에는 다음 사항을 명시한다.

- 내부 지식만으로 답할 수 있는지 먼저 판단한다.
- 특정 guideline, 법률, 최신 정보 또는 명시적인 출처가 필요하면 `retrieve_relevant_content`를 호출한다.
- Retrieval query는 문맥에 의존하지 않는 완결된 문장으로 작성한다.
- 반환된 evidence에 근거하여 답하고, 제공된 citation 형식을 유지한다.
- `partial` 또는 `no_evidence`인 경우 근거의 한계를 답변에 반영한다.

두 단계의 prompt를 하나로 합치지 않는다.

---

## 7. Retrieval query 작성 규칙

Retrieval query는 반드시 **그 자체로 완결된 self-contained query**여야 한다.

대명사나 이전 대화에만 의존하는 표현은 실제 대상을 명시하도록 다시 작성한다.

| 부적절한 query | 권장 query |
|---|---|
| `그 약의 용량은?` | `성인 만성 신장질환 환자에서 약물 X의 권장 초기 용량은 무엇인가?` |
| `아까 질환의 기준` | `성인 제2형 당뇨병의 진단 기준은 무엇인가?` |
| `그 가이드라인 권고` | `2024 고혈압 진료지침의 만성 신장질환 환자 혈압 목표 권고는 무엇인가?` |

Generation harness는 필요하면 최근 대화 문맥을 사용해 사용자의 질문을 독립적인 Retrieval query로 rewriting해야 한다.

---

## 8. Multi-turn 대응

L2는 **single-turn 대화에 최적화**되어 있지만, Hackathon에서는 multi-turn scenario도 평가한다.

이를 완화하기 위한 권장 방법은 다음과 같다.

- 최근 대화에서 대상 질환, 약물, 환자 조건, 요청한 문서 등을 추출한다.
- 현재 질문의 대명사와 생략된 대상을 해소한다.
- 전체 대화를 그대로 Retrieval에 넣기보다 하나의 self-contained query로 rewriting한다.
- 대화가 길어지면 필요한 임상 조건과 사용자 의도를 중심으로 context를 요약한다.
- Retrieval 결과와 이전 답변을 무조건 재사용하지 말고, 현재 질문에 필요한 근거인지 다시 판단한다.

예시:

```text
이전 질문: 만성 신장질환 환자의 혈압 목표는?
현재 질문: 당뇨가 같이 있으면 달라져?

Rewritten retrieval query:
만성 신장질환과 당뇨병을 함께 가진 성인의 권장 혈압 목표는 무엇이며,
당뇨병이 없는 만성 신장질환 환자와 권고가 다른가?
```

---

## 9. Harness 구현 체크리스트

### Retrieval

- [ ] Retrieval 전용 system prompt를 정의했는가?
- [ ] Hackathon MCP tools를 Retrieval 단계에만 제공했는가?
- [ ] `finalize_retrieval`을 직접 정의해 함께 제공했는가?
- [ ] 모델이 최종 답변을 쓰지 않고 `cite_uid`만 선택하도록 했는가?
- [ ] 최대 tool-call 횟수 또는 budget을 설정했는가?
- [ ] `sufficient`, `partial`, `no_evidence`를 모두 처리하는가?

### Generation

- [ ] Generation 전용 system prompt를 정의했는가?
- [ ] Generation 단계에는 `retrieve_relevant_content`만 제공했는가?
- [ ] Retrieval 필요 여부를 Generation 모델이 판단하도록 했는가?
- [ ] Retrieval query를 self-contained 형태로 만드는가?
- [ ] evidence의 content, 출처, citation 번호를 Generation에 전달하는가?
- [ ] Retrieval 실패 또는 부분 성공 시 답변에 한계를 표시하는가?

### Multi-turn

- [ ] 이전 대화의 대명사와 생략된 대상을 해소하는가?
- [ ] query rewriting 또는 context summarization을 적용하는가?
- [ ] 현재 질문과 무관한 오래된 문맥을 제거하는가?

---

## 10. 핵심 주의사항

1. L2를 범용 chat model처럼 한 번만 호출해 검색과 답변을 모두 수행하게 하지 않는다.
2. Retrieval과 Generation의 system prompt를 합치지 않는다.
3. Retrieval에는 MCP tools와 `finalize_retrieval`을 제공한다.
4. Generation에는 `retrieve_relevant_content`만 제공한다.
5. Retrieval 모델은 답변이 아니라 관련 `cite_uid`를 선택한다.
6. Retrieval query는 이전 문맥 없이도 이해할 수 있는 완결된 형태로 전달한다.
7. 무한한 tool 호출을 방지하기 위해 Retrieval tool-call 횟수를 제한한다.
8. `status`와 `note`를 활용해 evidence의 충분성 및 한계를 Generation 단계에 전달한다.

---

## 11. 한 문장 요약

> Lunit FM L2는 **Retrieval 모델이 MCP tools로 근거를 선택하고, Generation 모델이 그 근거를 받아 답변을 생성하는 2단계 의료 특화 LLM**이며, 두 호출을 올바르게 연결하고 제어하는 harness 구현이 핵심이다.

# Lunit FM L2 안내

## L2란?

L2는 Lunit이 개발한 의료 특화 LLM입니다. 범용 채팅 모델이 아니며, 다음과 같은 특성 때문에 일반적인 모델과 다르게 동작합니다.

- Retrieval과 Generation의 두 단계로 동작하며, 단계마다 모델을 별도로 호출합니다.
- Retrieval 중 evidence와 관련 정보를 수집하도록 특정 tool set으로 학습되었습니다. 해당 도구는 Hackathon에서 제공하는 MCP tools입니다.

따라서 범용 LLM처럼 다루면 예상대로 동작하지 않을 가능성이 큽니다. 가장 큰 과제는 이 모델을 제어하는 harness를 만드는 것입니다.

## 두 단계 처리 구조

일반적인 범용 LLM은 한 번에 질문을 읽고, 생각하고, 도구를 호출한 뒤 필요하면 답변합니다. L2는 이 과정을 명확히 두 단계로 나눕니다.

### 1. Retrieval 단계

질문을 받으면 모델은 필요한 evidence를 판단하고, MCP tools를 이용해 검색·열람·관련 정보 수집을 반복합니다. 충분한 정보를 모으면 관련 정보가 있다고 판단한 item을 선택해 출력합니다.

> **중요:** Retrieval 단계에서는 최종 답변을 작성하지 않습니다.

일부 MCP tool result에는 `cite_uid` field가 있습니다. 이 field는 item을 citation 가능하게 표시하고 이후 모델이 item을 참조하는 방법입니다. Retrieval이 끝나면 모델은 content가 아니라 각 관련 item의 `cite_uid`를 보고합니다.

모델이 `finalize_retrieval`을 호출해야 Retrieval 단계가 끝납니다. 이 함수는 MCP tool이 아닙니다. 직접 정의해 MCP tools와 함께 제공하고, system prompt에서 호출하도록 모델에 지시하세요.

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
    """Submit your final citation selection and end the retrieval phase.

    Call this only:
    - once you have gathered enough evidence to answer the query
    - the query does not need any retrieval
    - you exhausted the tool call budget and must end the retrieval
    """
    return CitationSelection(status=status, items=items, note=note)
```

#### Retrieval trajectory 예제

**사용자**

> 가이드라인에 따르면 만성 신장질환 환자에게 어떤 혈압 목표를 권고하나요?

**L2 — Tool call**

```python
index_list_documents(corpus_tag="guideline", query="hypertension chronic kidney disease")
```

**Tool result:** `12 documents, each with node_id, title, summary`

**L2 — Tool call**

```python
index_get_relevant_nodes(
    corpus_tag="guideline",
    query="blood pressure target CKD",
    node_id="0823b",
)
```

**Tool result:** `4 leaf nodes with their page ranges and ancestor chains`

**L2 — Tool call**

```python
index_get_page_content(
    corpus_tag="guideline",
    doc_id="0823b",
    start_page=48,
    end_page=52,
)
```

**Tool result:** `page text for pages 48-52, carrying cite_uid "cite-3f9a1c7d2e5b8046"`

**L2 — Tool call**

```python
finalize_retrieval(
    status="sufficient",
    items=[{"cite_uid": "cite-3f9a1c7d2e5b8046", "relevance_score": 0.95}],
    note="",
)
```

_— Retrieval 단계 종료 —_

### 2. Generation 단계

질문을 받으면 L2는 먼저 memory만으로 답할 수 있는지, 추가 정보가 필요한지 판단합니다.

일반적인 의료 질문은 직접 답할 수 있습니다. 특정 guideline이나 법률 등에 관한 질문에 정확히 답하려면 추가 정보가 필요하며, 이때 Retrieval을 사용합니다.

Generation 단계에는 `retrieve_relevant_content` 도구 하나만 제공해야 합니다.

```python
def retrieve_relevant_content(query: str):
    """Retrieve relevant content to ground your answer. Pass a single, self-contained query."""
    # Run the retrieval stage here and return the relevant information.
```

이 도구는 Retrieval 단계를 실행해 관련 정보를 모으고, 최종 답변을 생성하도록 모델에 전달합니다. Retrieval과 Generation을 연결하는 방식은 자유롭게 설계할 수 있습니다.

#### Generation trajectory 예제

**사용자**

> 가이드라인에 따르면 만성 신장질환 환자에게 어떤 혈압 목표를 권고하나요?

**L2 — Tool call**

```python
retrieve_relevant_content(
    query="recommended blood pressure target for adults with chronic kidney disease"
)
```

**Tool result**

```yaml
status: sufficient

[1]
source_type: guideline
url: https://example.org/guideline/0823b
title: 2024 Clinical Practice Guideline for the Management of Hypertension
content: In adults with chronic kidney disease, treat to a systolic blood pressure target of less
  than 120 mmHg when tolerated, ...
```

**L2**

> 가이드라인에 따르면 만성 신장질환 성인에게 내약 가능한 경우 수축기 혈압 120 mmHg 미만을 목표로 치료할 것을 권고합니다 [1].

_— Generation 단계 종료 —_

## Tip

- 각 단계에 맞는 system prompt를 별도로 만들고 합치지 마세요.
- Retrieval에는 MCP tools와 `finalize_retrieval`을 제공하세요.
- Generation에는 `retrieve_relevant_content`만 제공하여 최종 답변을 생성할 수 있도록 하세요.
- Retrieval query는 그 자체로 완결되어야 합니다. “그 약의 용량은?” 같은 질문은 지시 대상을 해소한 뒤 Retrieval에 전달하세요.
- Retrieval 중 tool call 횟수를 제한하세요.
- `status` 및 `note`를 통해 Retrieval에서 Generation으로 정보를 전달할 수 있습니다.

## 제약사항

L2는 single-turn 대화에 최적화되어 있지만, Hackathon에서는 multi-turn scenario도 평가합니다. Query rewriting, context summarization 등으로 이 제약을 완화하는 방법도 challenge의 일부입니다.

이 가이드는 L2의 권장 사용 방법이며 필수는 아닙니다. 규칙을 준수한다면 다른 system을 구성해도 됩니다.

# Lunit Hackathon 제출 가이드

## 1. 제출 대상

제출물은 **containerized multi-turn conversation driver**이다.

Evaluator는 매 conversation turn을 제출한 service로 전송한다. Driver는 요청에 포함된 conversation context를 활용하여 필요한 Lunit Model과 MCP tools를 orchestrate한 뒤, 다음 `assistant` response를 반환해야 한다.

즉, 제출물은 단순한 답변 스크립트가 아니라 다음 역할을 수행하는 HTTP service여야 한다.

1. Evaluator로부터 전체 또는 현재 conversation context를 받는다.
2. 이전 대화 내용을 고려한다.
3. 필요한 경우 Lunit FM의 Retrieval·Generation 단계와 MCP tools를 호출한다.
4. OpenAI-compatible 형식으로 다음 assistant response를 반환한다.

---

## 2. 필수 제출 조건

| 항목 | 필수 조건 |
|---|---|
| 제출 branch | `lunit/hackathon-submission` |
| Dockerfile 위치 | Repository root의 `Dockerfile` |
| Image build 시간 | Evaluation VM에서 5분 이내 |
| Service host | `0.0.0.0` |
| Service port | `8000` |
| Container 시작 | 별도 수동 작업 없이 자동 시작 |
| API 형식 | OpenAI-compatible API |
| 필수 endpoint | `GET /v1/models` |
| 필수 endpoint | `POST /v1/chat/completions` |
| Dockerfile port 선언 | `EXPOSE 8000` |
| 최종 제출 값 | 제출 branch HEAD의 40자리 전체 commit SHA |
| 추가 입력 | Driver가 사용하는 Model 이름 |

Evaluator는 **container port 8000만 평가**한다. 다른 port에서만 service하거나 `127.0.0.1`에만 bind하면 평가할 수 없다.

---

## 3. 권장 repository 구조

```text
repository-root/
├── Dockerfile
├── requirements.txt
├── app.py
├── src/
│   ├── driver.py
│   ├── retrieval.py
│   └── generation.py
└── README.md
```

구조는 자유롭게 변경할 수 있지만 `Dockerfile`은 반드시 repository root에 있어야 한다.

---

## 4. Driver API 구현

### 4.1 `GET /v1/models`

Driver가 제공하는 model 정보를 OpenAI-compatible 형식으로 반환한다.

응답 예시:

```json
{
  "object": "list",
  "data": [
    {
      "id": "lunit-hackathon-driver",
      "object": "model",
      "owned_by": "team"
    }
  ]
}
```

### 4.2 `POST /v1/chat/completions`

Evaluator가 전달한 `messages`를 읽고 다음 assistant response를 생성한다.

요청 예시:

```json
{
  "model": "lunit-hackathon-driver",
  "messages": [
    {
      "role": "user",
      "content": "환자 질문"
    },
    {
      "role": "assistant",
      "content": "이전 시스템 답변"
    },
    {
      "role": "user",
      "content": "후속 질문"
    }
  ]
}
```

응답 예시:

```json
{
  "id": "chatcmpl-example",
  "object": "chat.completion",
  "model": "lunit-hackathon-driver",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "후속 질문에 대한 답변"
      },
      "finish_reason": "stop"
    }
  ]
}
```

Driver는 `messages`의 마지막 질문만 읽지 말고, 이전 `user`와 `assistant` turn을 포함한 conversation context를 함께 사용해야 한다.

---

## 5. Dockerfile 작성

Repository root에 다음과 같은 `Dockerfile`을 둔다.

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

이 예시는 `app.py` 안에 FastAPI instance가 다음과 같이 정의되어 있다고 가정한다.

```python
from fastapi import FastAPI

app = FastAPI()
```

Dockerfile에서 반드시 확인할 부분은 다음과 같다.

- `EXPOSE 8000`이 있는가?
- 실행 명령이 `--host 0.0.0.0 --port 8000`을 사용하는가?
- Container가 시작되면 별도 명령 없이 server가 실행되는가?
- Source code와 dependency가 image에 포함되는가?
- Build 중 대형 model을 내려받아 5분 제한을 초과하지 않는가?

---

## 6. 로컬 build 및 실행

Repository root에서 실행한다.

```bash
docker build -t my-team-submission:local .
```

Build가 완료되면 container를 실행한다.

```bash
docker run --rm \
  -p 8000:8000 \
  my-team-submission:local
```

Driver가 환경변수를 필요로 한다면 local test에서 필요한 변수를 함께 전달한다.

```bash
docker run --rm \
  -p 8000:8000 \
  -e LUNIT_FM_API_KEY="$LUNIT_FM_API_KEY" \
  my-team-submission:local
```

실제 API key를 Dockerfile이나 image 안에 직접 저장하지 않는다.

---

## 7. Local endpoint 검증

### 7.1 Model 목록 확인

```bash
curl -s http://localhost:8000/v1/models | jq
```

확인 사항:

- HTTP `200`을 반환하는가?
- JSON 형식이 유효한가?
- `data`에 model 정보가 포함되는가?

### 7.2 Chat Completions 확인

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lunit-hackathon-driver",
    "messages": [
      {
        "role": "user",
        "content": "만성 신장질환 환자의 혈압 목표를 알려주세요."
      }
    ]
  }' \
  | jq
```

확인 사항:

- HTTP `200`을 반환하는가?
- `choices[0].message.role`이 `assistant`인가?
- `choices[0].message.content`에 최종 답변이 있는가?
- Model 또는 MCP tool 오류가 발생해도 service process가 종료되지 않는가?

### 7.3 Multi-turn 확인

이전 assistant response를 포함한 전체 history를 다시 보내 후속 질문을 테스트한다.

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lunit-hackathon-driver",
    "messages": [
      {
        "role": "user",
        "content": "만성 신장질환 환자의 혈압 목표를 알려주세요."
      },
      {
        "role": "assistant",
        "content": "이전에 생성한 답변"
      },
      {
        "role": "user",
        "content": "당뇨병이 함께 있으면 달라지나요?"
      }
    ]
  }' \
  | jq
```

마지막 질문의 `그 환자`, `그 약`, `함께 있으면` 같은 표현이 이전 context를 이용해 올바르게 해석되는지 확인한다.

---

## 8. Build 시간 확인

Evaluation VM에서 Docker image build가 5분 안에 끝나야 한다.

Local build 시간을 확인하려면 다음과 같이 실행할 수 있다.

```bash
time docker build --no-cache -t my-team-submission:build-test .
```

Build 시간을 줄이기 위한 기본 사항:

- 필요한 dependency만 `requirements.txt`에 포함한다.
- 대형 model weight나 불필요한 file을 image에 포함하지 않는다.
- `.dockerignore`로 `.git`, cache, local virtual environment, test output 등을 제외한다.
- `requirements.txt`를 먼저 복사해 dependency layer caching을 활용한다.
- Container 시작 후 추가 설치나 수동 설정을 요구하지 않는다.

`.dockerignore` 예시:

```text
.git
.venv
venv
__pycache__
*.pyc
.pytest_cache
.env
```

---

## 9. 제출 branch 준비

제출에 사용할 branch 이름은 다음과 같다.

```text
lunit/hackathon-submission
```

새 branch를 만드는 경우:

```bash
git switch -c lunit/hackathon-submission
```

이미 branch가 존재하는 경우:

```bash
git switch lunit/hackathon-submission
```

변경 사항을 commit한다.

```bash
git add Dockerfile requirements.txt app.py src README.md .dockerignore
git commit -m "Prepare Lunit hackathon submission"
```

실제 repository 구조에 맞게 `git add` 대상은 조정한다.

Remote에 push한다.

```bash
git push -u origin lunit/hackathon-submission
```

---

## 10. 제출할 40자리 commit SHA 확인

제출 페이지에는 `lunit/hackathon-submission` branch HEAD의 **40자리 전체 SHA**를 입력해야 한다.

현재 checkout된 branch의 SHA 확인:

```bash
git rev-parse HEAD
```

Branch를 명시하여 확인:

```bash
git rev-parse lunit/hackathon-submission
```

출력 예시:

```text
0123456789abcdef0123456789abcdef01234567
```

짧은 SHA가 아니라 40자리 전체 값을 제출한다. 최종 수정 후 다시 commit하거나 push했다면 새로운 HEAD SHA를 다시 확인해야 한다.

---

## 11. 평가 제출

제출 페이지에서 다음 값을 입력한다.

1. `lunit/hackathon-submission` branch HEAD의 40자리 전체 SHA
2. Driver가 실제로 사용하는 Model 이름

제출 정보는 trial과 함께 저장되며 official evaluation에서 다시 사용된다.

평가 이력 페이지에서는 **마지막 제출이 최종 제출**로 간주된다. 따라서 새 commit을 제출하면 이전 제출 대신 가장 마지막 제출이 최종 평가 대상이 된다.

제공된 화면 상태가 다음과 같다면 아직 trial을 실행할 수 없다.

```text
비활성 / 활성 trial 없음
```

이 경우 제출 기능 또는 trial이 활성화된 뒤 SHA와 Model 이름을 입력한다.

---

## 12. 최종 제출 순서

```text
1. Multi-turn driver 구현
2. GET /v1/models 구현
3. POST /v1/chat/completions 구현
4. Repository root에 Dockerfile 작성
5. 0.0.0.0:8000으로 자동 실행되도록 설정
6. Local Docker build 및 endpoint 테스트
7. Build가 5분 이내인지 확인
8. lunit/hackathon-submission branch에 최종 commit
9. Remote repository에 push
10. Branch HEAD의 40자리 SHA 확인
11. 제출 페이지에 SHA와 사용 Model 이름 입력
12. 평가 이력에서 마지막 제출 확인
```

---

## 13. 제출 전 체크리스트

### Service

- [ ] Multi-turn conversation context를 사용한다.
- [ ] `GET /v1/models`가 정상 동작한다.
- [ ] `POST /v1/chat/completions`가 정상 동작한다.
- [ ] OpenAI-compatible JSON response를 반환한다.
- [ ] 필요한 Model과 MCP tools를 올바르게 orchestrate한다.

### Docker

- [ ] Repository root에 `Dockerfile`이 있다.
- [ ] Dockerfile에 `EXPOSE 8000`이 있다.
- [ ] Service가 `0.0.0.0:8000`에서 실행된다.
- [ ] Container 시작 시 별도의 수동 작업이 필요 없다.
- [ ] Image가 5분 이내에 build된다.
- [ ] API key가 image 또는 repository에 포함되지 않았다.

### Local test

- [ ] `docker build`가 성공한다.
- [ ] `docker run -p 8000:8000`이 성공한다.
- [ ] `/v1/models`가 HTTP 200을 반환한다.
- [ ] `/v1/chat/completions`가 HTTP 200을 반환한다.
- [ ] Multi-turn 후속 질문이 이전 context를 반영한다.

### Git 및 제출

- [ ] 최종 code가 `lunit/hackathon-submission` branch에 있다.
- [ ] 최종 commit을 remote에 push했다.
- [ ] Branch HEAD의 40자리 전체 SHA를 확인했다.
- [ ] Driver가 사용하는 Model 이름을 확인했다.
- [ ] 제출 페이지에 가장 최신 SHA를 입력했다.
- [ ] 평가 이력의 마지막 제출이 의도한 제출인지 확인했다.

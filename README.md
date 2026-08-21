# Daintlab-B — Lunit Hackathon Driver

Lunit L2의 Retrieval·Generation 2단계를 연결하고 Lunit MCP tools로 근거를 수집하는 OpenAI-compatible multi-turn driver다.

## 제출 계약

- `GET /v1/models`
- `POST /v1/chat/completions`
- `0.0.0.0:8000`
- Repository root의 `Dockerfile`
- Evaluation VM에서 5분 이내 image build
- 제출 브랜치: `lunit/hackathon-submission`
- 제출 값: 브랜치 HEAD의 40자리 SHA와 `Lunit/L2-preview`

구현 계획과 제출 전 전체 체크리스트는 [HACKATHON_PLAN.md](HACKATHON_PLAN.md)를 참고한다.

## 구조

```text
Evaluator messages
  → L2 Generation
      → retrieve_relevant_content
          → L2 Retrieval
          → live MCP tools
          → finalize_retrieval
      → selected evidence
  → L2 final answer
```

- Generation에는 `retrieve_relevant_content`만 제공한다.
- Retrieval에는 질문 유형에 맞게 선별한 live MCP tools와 `finalize_retrieval`을 제공한다.
- 실제 tool result에 존재하는 `cite_uid`만 최종 evidence로 전달한다.
- 요청에 포함된 전체 대화가 source of truth이며 server-side session에 의존하지 않는다.
- 일반 의료 질문은 한 번의 Generation 호출로 직접 답하고, 외부 근거가 필요한 질문만 Retrieval을 1회 수행한다.
- L2 HTTP attempt는 동시에 최대 2개만 실행하고 `Retry-After`를 반영한다.
- Retrieval은 최대 L2 3 round·MCP 2 call·선택 evidence 3개로 제한한다.
- 전체 170초 중 Retrieval은 최대 45초만 사용해 최종 Generation 시간을 남긴다.

## 환경변수

```bash
export LUNIT_FM_API_KEY="lunit_..."
export LUNIT_FM_API_URL="https://model.hackathon.lunit.io"
export LUNIT_FM_MODEL="Lunit/L2-preview"
export LUNIT_MCP_URL="https://mcp.hackathon.lunit.io/mcp"
```

전체 설정은 [.env.example](.env.example)에 있다. 실제 API key를 `.env`, Dockerfile, image, Git 또는 로그에 남기지 않는다.

## 로컬 실행

Python 3.12 이상을 권장한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

다른 terminal에서 확인한다.

```bash
bash scripts/smoke_test.sh
```

API key가 없으면 `/v1/models`만 확인하고 live chat test는 건너뛴다.

MCP 연결과 live tool schema만 먼저 확인하려면 다음을 실행한다.

```bash
python -m scripts.check_mcp
```

## 테스트

테스트는 실제 Lunit endpoint 대신 fake L2/MCP를 사용하므로 API key 없이 실행된다.

```bash
python -m unittest discover -s tests -v
```

## Docker

```bash
docker build -t daintlab-b:local .
docker run --rm \
  -p 8000:8000 \
  -e LUNIT_FM_API_KEY="$LUNIT_FM_API_KEY" \
  daintlab-b:local
```

Clean build 시간도 확인한다.

```bash
time docker build --no-cache -t daintlab-b:build-test .
```

## 제출 직전

아래 작업은 local endpoint와 Dashboard baseline이 모두 정상일 때 수행한다.

```bash
git switch -c lunit/hackathon-submission
git add .
git commit -m "Prepare Lunit hackathon submission"
git push -u origin lunit/hackathon-submission
git rev-parse lunit/hackathon-submission
```

출력된 40자리 SHA와 실제 사용 모델 `Lunit/L2-preview`를 제출 페이지에 입력하고, evaluation history의 마지막 제출이 해당 SHA인지 확인한다.

## 공식 문서

- [제출 가이드](guide_line/Lunit_Submission_Guide.md)
- [L2 가이드](guide_line/Lunit_FM_L2_Guide.md)
- [Model API 가이드](guide_line/Lunit_Model_API_Guide.md)
- [MCP Tools 가이드](guide_line/Lunit_MCP_Tools_Guide.md)

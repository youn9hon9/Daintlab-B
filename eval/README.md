# Local HealthBench evaluation

This branch evaluates any running OpenAI-compatible model endpoint. It does not
contain a submission model and never sends a leaderboard submission.

Public examples are downloaded at runtime into ignored `eval/.cache/` storage.
`eval/results/` stores prompt identifiers, measurements, scores, and error
summaries without copying raw prompts or rubrics.

## Install

Python 3.11 or newer is recommended.

```bash
python -m pip install -r requirements.txt
```

Run the harness unit tests with:

```bash
python -m unittest discover -s eval/tests -v
```

## Start a candidate separately

Start the candidate from its own checkout or worktree, then expose its
OpenAI-compatible API. For example, from `yh-submission`:

```bash
docker build -t daintlab-b:y2 .
docker run --rm -p 8000:8000 daintlab-b:y2
```

The evaluator only needs the resulting `/v1/models` and
`/v1/chat/completions` endpoint.

## Free smoke run

This measures completion success and latency without using a judge model.

```bash
python -m eval.run_healthbench \
  --endpoint http://127.0.0.1:8000/v1 \
  --dataset conquer_val \
  --sampling balanced \
  --samples 8
```

## Scored comparison run

Put the judge credential in the ignored `.env` file:

```dotenv
HEALTHBENCH_JUDGE_API_KEY=...
```

Then run the fixed representative profile used for candidate comparisons:

```bash
python -m eval.run_healthbench \
  --endpoint http://127.0.0.1:8000/v1 \
  --run-name Y2 \
  --candidate-sha SHA_OR_LABEL \
  --dataset conquer_val \
  --sampling representative \
  --samples 16 \
  --repeats 1 \
  --generation-concurrency 2 \
  --score
```

Scoring makes one judge request per rubric criterion and can incur API cost.
Inference failures receive zero; judge failures are reported and excluded.
The bootstrap interval and score are development signals, not leaderboard
predictions.

## Run without host Python

When the candidate is listening on host port 8000, run the evaluator in a
temporary Python container:

```powershell
docker run --rm `
  -v "${PWD}:/workspace" `
  -w /workspace `
  python:3.12-slim `
  sh -lc "pip install -q -r requirements.txt && python -m eval.run_healthbench --endpoint http://host.docker.internal:8000/v1 --sampling representative --samples 16"
```

## Useful options

```text
--dataset conquer_val|consensus|hard|main
--samples N
--seed N
--sampling balanced|representative|random
--repeats N
--run-name NAME
--candidate-sha SHA_OR_LABEL
--endpoint http://127.0.0.1:8000/v1
--model MODEL_ID
--timeout SECONDS
--generation-concurrency N
--score
--judge-api-url URL
--judge-model MODEL
--judge-concurrency N
--judge-api-key-env VARIABLE_NAME
--env-file PATH
```

Do not commit benchmark caches, raw prompts, rubrics, credentials, or generated
result files.

# Local HealthBench evaluation

This harness runs a reproducible public HealthBench subset against the local
OpenAI-compatible submission service. It does not submit anything to the
leaderboard.

Public examples are downloaded from OpenAI at runtime into `eval/.cache/`.
Prompts and rubrics are not copied into result files; `eval/results/` contains
only prompt identifiers, operational measurements, optional scores, and error
summaries. Both directories are ignored by Git.

## 1. Start the submission service

```bash
docker build -t daintlab-b:latest .
docker run --rm -p 8000:8000 --env-file .env daintlab-b:latest
```

## 2. Free smoke run

This calls the driver and records success rate, latency, and response length.
It does not use a judge model and therefore does not produce a HealthBench
quality score.

```bash
python -m eval.run_healthbench --dataset consensus --samples 5
```

The same fixed sample is selected whenever `--dataset`, `--samples`, and
`--seed` are unchanged.

If Python is not installed on the host, run the evaluator from the submission
image while the service container is listening on host port 8000. In
PowerShell:

```powershell
docker run --rm `
  -v "${PWD}:/workspace" `
  -w /workspace `
  daintlab-b:latest `
  sh -lc "python -m pip install -q -r requirements-dev.txt && python -m eval.run_healthbench --endpoint http://host.docker.internal:8000/v1 --dataset consensus --samples 5"
```

## 3. Rubric-scored run

Scoring makes one judge request per rubric criterion and can be expensive.
Use a separate environment variable so the submission runtime never depends
on the judge credential.

```bash
export HEALTHBENCH_JUDGE_API_KEY="..."
python -m eval.run_healthbench \
  --dataset consensus \
  --samples 5 \
  --score
```

Start with 5 examples, then use 20 to 50 fixed examples for candidate
comparisons. The complete `main` dataset contains thousands of examples and
is not intended for frequent iteration.

Useful options:

```text
--dataset consensus|hard|main
--samples N
--seed N
--endpoint http://127.0.0.1:8000/v1
--model DRIVER_MODEL_ID
--score
--judge-api-url URL
--judge-model MODEL
--judge-api-key-env VARIABLE_NAME
```

This is a development signal, not a prediction of the competition's private
evaluation. Do not add cached benchmark examples, raw prompts, rubrics, judge
credentials, or generated result files to Git.

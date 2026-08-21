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
python -m eval.run_healthbench
```

The same fixed sample is selected whenever `--dataset`, `--samples`, and
`--seed` are unchanged.

Two model responses are generated concurrently by default. This keeps local
iteration reasonably fast without putting aggressive pressure on the Lunit
model and MCP services. Result files separate model-endpoint latency, judge
latency, and total wall-clock time.

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

Add the local-only judge credential to `.env`:

```dotenv
HEALTHBENCH_JUDGE_API_KEY=...
```

Then run:

```bash
python -m eval.run_healthbench \
  --run-name U2 \
  --candidate-sha 4c6469a \
  --dataset conquer_val \
  --samples 8 \
  --sampling balanced \
  --score
```

The default is eight deterministic, theme-balanced examples from CoEval's
published `conquer_val` split (HealthBench Main). It is a quick development
proxy, not a statistically reliable leaderboard estimate. Use 30 to 50 fixed
examples for candidate comparisons; the live leaderboard uses the full public
validation split and a different judge may still create systematic differences.

Use two distinct profiles rather than treating one sample as both a diagnostic
and a leaderboard proxy:

```bash
# Fast diagnostic: covers every theme and favors median rubric complexity.
python -m eval.run_healthbench --run-name U2-smoke \
  --sampling balanced --samples 8 --score

# Candidate comparison: follows the published validation theme proportions.
python -m eval.run_healthbench --run-name U2-compare \
  --sampling representative --samples 32 --repeats 3 --score
```

Repeated runs report a prompt-level bootstrap 95% confidence interval. Model
inference failures receive zero, matching the competition policy; judge
failures are reported and excluded because no valid grade exists. Result files
also record the run name, candidate SHA, sampling mode, repeat count, and a hash
of the selected prompt IDs.

Useful options:

```text
--dataset conquer_val|consensus|hard|main
--samples N
--seed N
--sampling balanced|representative|random
--repeats N
--run-name NAME
--candidate-sha SHA
--endpoint http://127.0.0.1:8000/v1
--model DRIVER_MODEL_ID
--generation-concurrency N
--score
--judge-api-url URL
--judge-model MODEL
--judge-api-key-env VARIABLE_NAME
--env-file PATH
```

This is a development signal, not a prediction of the competition's private
evaluation. Do not add cached benchmark examples, raw prompts, rubrics, judge
credentials, or generated result files to Git.

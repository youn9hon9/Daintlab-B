# Daintlab-B local evaluation workspace

`dev` is the local proxy-evaluation branch. It contains only the reusable
evaluation harness and project documentation; submission model code lives on
candidate branches such as `yh-submission`.

## Layout

- `eval/`: deterministic HealthBench/CoEval proxy evaluator
- `docs/`: competition notes, implementation references, and candidate results
- `requirements.txt`: evaluator-only Python dependency

The harness evaluates an already running OpenAI-compatible endpoint. It does
not build, serve, or submit a model.

## Quick start

```bash
python -m pip install -r requirements.txt
python -m eval.run_healthbench \
  --endpoint http://127.0.0.1:8000/v1 \
  --sampling representative \
  --samples 16
```

Add `--score` to use the judge. Store its key only in the ignored `.env` file:

```dotenv
HEALTHBENCH_JUDGE_API_KEY=...
```

See [eval/README.md](eval/README.md) for all evaluation modes and
[docs/README.md](docs/README.md) for the documentation index.

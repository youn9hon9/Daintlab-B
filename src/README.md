# Source

The active submission path is split into explicit responsibilities:

- `api.py`: evaluator-facing OpenAI-compatible HTTP contract
- `driver.py`: generation and conditional-retrieval orchestration
- `guidance.py`: missing clinical context and jurisdiction guidance flags
- `routing.py`: deterministic gate for evidence-dependent requests
- `retrieval.py`: retrieval-model tool loop and budgets
- `mcp_gateway.py`: Lunit MCP connection and tool execution
- `model_client.py`: Lunit model transport, retries, and timeouts
- `evidence.py`: citation discovery and integrity checks
- `schemas.py`: request, evidence, and retrieval data contracts
- `config.py`: environment-backed runtime settings

The repository-root `app.py` remains a thin entrypoint and the container still
binds to `0.0.0.0:8000`. Method candidates are developed continuously on
`yh-submission2`; validated changes are promoted to `yh-submission`. The old
field-laptop proxy work is retained only on its dedicated backup branch.

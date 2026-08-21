# Source

The active submission path is split into explicit responsibilities:

- `api.py`: evaluator-facing OpenAI-compatible HTTP contract
- `driver.py`: F010 orchestration -- deterministic route/evidence compile,
  then exactly one L2 call
- `deterministic_router.py`: harness-side route classification and
  self-contained query construction (no L2 call)
- `evidence_compiler.py`: harness-side direct MCP tool calls and extractive
  evidence compaction (no L2 call)
- `guidance.py`: missing clinical context and jurisdiction guidance flags
- `mcp_gateway.py`: Lunit MCP connection and tool execution
- `model_client.py`: Lunit model transport, retries, and timeouts
- `evidence.py`: cite_uid extraction helper (used by mcp_gateway.py's
  truncation path)
- `schemas.py`: request and evidence data contracts
- `config.py`: environment-backed endpoints and versioned runtime budgets

The repository-root `app.py` remains a thin entrypoint and the container still
binds to `0.0.0.0:8000`. Method candidates are developed continuously on
`yh-submission2`; validated changes are promoted to `yh-submission`. The old
field-laptop proxy work is retained only on its dedicated backup branch.

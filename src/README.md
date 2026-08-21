# Source

The source package is split by change ownership:

- `api_contract.py`: evaluator request validation and response normalization
- `conversation.py`: transport-independent conversation orchestration seam
- `l2_client.py`: official L2 configuration and HTTP transport

`l2_client.py` reads the L2 URL, bearer credential, and model from `LUNIT_FM_API_URL`, `LUNIT_FM_API_KEY`, and `LUNIT_FM_MODEL`; forwards the complete ordered message list to `/v1/chat/completions`; and returns the upstream Chat Completions object.

The repository-root `app.py` remains the thin OpenAI-compatible submission entrypoint on port 8000. The current baseline supports non-streaming text histories containing `system`, `user`, and `assistant` messages. Unsupported fields and features fail explicitly. No retrieval facade, MCP orchestration, Patient Simulator client, OpenAI client, or custom prompt is present.

See `COLLABORATION.md` for the three-person ownership model. The submission file layout and container entrypoint remain unchanged.

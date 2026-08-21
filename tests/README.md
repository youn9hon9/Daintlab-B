# Tests

Run the network-independent unit suite with:

```bash
python -m unittest discover -s tests -v
```

The suite mocks L2 and verifies the `/v1/models` shape, request validation, complete ordered multi-turn forwarding, L2-origin assistant content, usage preservation, explicit unsupported-feature errors, missing-key handling, credential-safe upstream errors, and absence of an `OPENAI_API_KEY` code path.

Real L2 connectivity is a deliberate one-request smoke test and is not part of the repeatable unit suite. Retrieval and Patient Simulator tests will be added only when those stages are implemented.

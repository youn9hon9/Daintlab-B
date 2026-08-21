# Tests

Run the network-independent unit suite with:

```bash
python -m unittest discover -s tests -v
```

The suite uses fake model and MCP clients. It covers the API contract, complete
multi-turn forwarding, conditional retrieval, citation integrity, bounded tool
results, timeout and upstream-error isolation, safety policy, and validation
behavior.

Real L2, MCP, judge, and Patient Simulator calls are deliberately excluded from
the repeatable unit suite.

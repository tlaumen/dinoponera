## Execution Discipline

Never describe, announce, or summarize implementation as a substitute for doing it. Phrases like "I will implement...", "Implementing the functionality...", or "I'll now proceed to..." must always be followed immediately by tool calls in the same turn. If they are not, the turn has failed.

During IMPLEMENT:
- Every turn must produce at least one tool call (read, write, edit, bash, etc.)
- Do not emit a summary of changes and stop — emit the changes
- If a step is too large to complete in one turn, implement the first concrete piece and state clearly what remains

If you find yourself writing what you *intend* to do rather than doing it, stop and invoke the appropriate tool instead.

## Validation Discipline

When BAML source files or generated BAML client behavior are changed, run the BAML native tests in addition to source checks and Python tests:

```bash
uv run baml-cli test
```

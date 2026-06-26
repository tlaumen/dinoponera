# Dinoponera

Dinoponera is an experimental Python + BAML calculation-agent framework for building auditable engineering calculation workflows.

An engineer describes a calculation problem in natural language. Dinoponera uses BAML only during planning to identify a terminal registry node and build a typed dependency graph. After user review/approval, it serializes the graph and generates a standalone Python execution script. Generated scripts execute deterministically without BAML or LLM calls.

## Current status

The MVP loop is implemented for the example registry:

```text
natural-language problem
→ BAML-assisted planning/review
→ approved graph JSON
→ generated run script
→ deterministic execution
```

The checked-in example produces:

```text
message='Doubled value' value=42.0
```

See [DESIGN.md](./DESIGN.md) for the full MVP design and checklist.

## Setup

```bash
uv sync --extra dev
```

For live BAML planning, create `.env` in the repository root:

```bash
ANTHROPIC_API_KEY=...
```

The package loads `.env` on import, so `ANTHROPIC_API_KEY` is available to BAML calls and helper commands.

## User-facing loop

Run the simple interactive entrypoint:

```bash
uv run python calculate.py
```

It will:

1. ask `What do you want to calculate?`,
2. run the BAML-assisted planning and clarification loop,
3. render the graph for approval,
4. write `graphs/{name}.json`,
5. generate `runs/run_{name}.py`,
6. warn if generated leaf stubs still need implementation,
7. ask whether to execute the generated script now.

Try these prompts with the current geotechnical registry nodes:

```text
Calculate settlement for a layered soil profile.
```

```text
Calculate CPT-based pile foundation capacity.
```

The `calculate.py` path uses BAML planning, so live provider credentials must be configured in `.env`.

## Deterministic example loop

The lower-level deterministic loop can build and execute the example without BAML:

```bash
uv run python -m dinoponera.core.graph_building \
  format_result \
  --name auto_example_doubling \
  --output graphs/auto_example_doubling.json

uv run python -m dinoponera.core.script_generation graphs/auto_example_doubling.json
uv run python runs/run_auto_example_doubling.py
```

You can also regenerate and run the checked-in manual graph:

```bash
uv run python -m dinoponera.core.script_generation graphs/example_doubling.json
uv run python runs/run_example_doubling.py
```

## Live BAML planning helpers

BAML uses Claude Haiku 4.5 through Anthropic:

```text
claude-haiku-4-5-20251001
```

Helper commands load `.env` before invoking the BAML CLI:

```bash
uv run python -m dinoponera.tools.baml_cli check
uv run python -m dinoponera.tools.baml_cli test
uv run python -m dinoponera.tools.baml_cli generate
```

The generated `baml_client/` is committed because runtime Python imports it from `dinoponera.agent.planning`. If BAML schemas change, regenerate it with:

```bash
uv run python -m dinoponera.tools.baml_cli generate
```

A lower-level planner CLI is available for developer/debug use:

```bash
uv run python -m dinoponera.agent.planning \
  "Calculate the final example result from the available example nodes." \
  --generate-script
```

## Repository layout

```text
dinoponera/
  core/          deterministic models, graph building, linting, rendering, script generation
  agent/         user interaction and BAML-boundary planning orchestration
  tools/         helper CLIs

calc_types/      Pydantic domain models
registry/        decorated Python calculation nodes and explicit node index
baml_src/        BAML schemas, prompts, and BAML-native tests
baml_client/     generated BAML Python client, committed for runtime imports
graphs/          approved graph JSON files
runs/            generated standalone execution scripts
tests/           deterministic Python tests
```

## Adding domain types

Domain values should be Pydantic models under `calc_types/`:

```python
from pydantic import BaseModel

class MyInput(BaseModel):
    value: float
```

Primitive node I/O annotations are intentionally rejected; registry nodes should use importable Pydantic `BaseModel` subclasses.

## Adding registry nodes

Create a decorated function under `registry/nodes/` and add it to `registry/index.py` `NODES`:

```python
from calc_types.my_domain import MyInput, MyOutput
from registry.decorators import node

@node(
    node_type="computation",
    description="Compute an auditable value.",
    when_to_use="Use when this exact calculation is required.",
)
def compute_value(input_value: MyInput) -> MyOutput:
    ...
```

The function name is the registry node ID. Input parameter names become named graph inputs, so duplicate input types on one node are supported as long as parameter names differ.

## Graph JSON

A graph lists node IDs and explicit producer-to-consumer edges:

```json
{
  "name": "example_doubling",
  "terminal_node_id": "format_result",
  "nodes": ["format_result", "double_value", "example_source_value"],
  "edges": [
    {
      "from_node": "double_value",
      "to_node": "format_result",
      "to_input": "doubled",
      "type": "calc_types.example.DoubledValue"
    }
  ]
}
```

Before script generation, graphs are linted for unknown nodes, missing inputs, duplicate/conflicting input edges, type mismatches, invalid edge endpoints, and cycles.

## Tests

Run deterministic tests:

```bash
uv run --extra dev pytest -q
```

Run BAML validation/tests with live provider credentials:

```bash
uv run python -m dinoponera.tools.baml_cli check
uv run python -m dinoponera.tools.baml_cli test
```

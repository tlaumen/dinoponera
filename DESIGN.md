# Design: Calculation Agent MVP

## Summary

Implement the MVP from `calc_agent_design.md`: Step 1 Planning plus Step 2 Execution Script Generation.

The system will let an engineer describe a calculation problem, use BAML-assisted planning to identify the terminal calculation node and build a typed dependency graph from a hand-authored Python registry, lint and approve that graph, serialize it to `graphs/{name}.json`, then generate a standalone auditable Python execution script under `runs/run_{name}.py`.

Post-MVP node/type/code authoring is intentionally deferred.

## Goals

- Implement Step 1 Planning from `calc_agent_design.md`:
  - goal identification loop
  - explicit goal confirmation
  - graph-building loop
  - dependency traversal and linting
  - graph review and approval
  - approved graph serialization
- Implement Step 2 Execution Script Generation from `calc_agent_design.md`:
  - load approved graph JSON
  - topologically sort forward graph edges
  - generate human-readable standalone Python script
  - avoid all LLM/BAML calls during script generation and generated-script execution
- Use a Python-native registry:
  - node functions decorated with `@node(...)`
  - `registry/index.py` owning `NODES`
  - node summaries built by inspecting signatures and decorator metadata
- Use Pydantic models for shared serialized data.
- Use root-level calculation asset directories matching `calc_agent_design.md`:
  - `calc_types/`
  - `registry/`
  - `graphs/`
  - `runs/`
- Add Python tests for deterministic behavior and mocked planner orchestration.
- Add BAML-native tests directly in `.baml` files for every MVP BAML function.

## Non-Goals

- Do not implement Post-MVP node authoring.
- Do not generate new domain types through BAML.
- Do not generate node implementation code through BAML.
- Do not implement registry scaling, embedding search, conditional execution, iterative calculations, or report generation.
- Do not implement a separate in-process graph executor in the MVP.
- Do not use `old/DESIGN.md` where it conflicts with `calc_agent_design.md`.

## Existing Codebase Context

Repository evidence at design time:

- `calc_agent_design.md` exists and is the requested source design.
- `call_flow.md` exists and restates the planning/execution call flow.
- `old/DESIGN.md` exists but describes a different plan that conflicts with `calc_agent_design.md` in material areas, especially registry storage and graph representation.
- `pyproject.toml` exists with:
  - project name `dinoponera`
  - Python requirement `>=3.12`
  - no dependencies
- `.python-version` is `3.12`.
- `dinoponera/` exists but is empty.
- `tests/` exists but is empty.
- `README.md` exists but is empty.
- No BAML files, generated BAML client, registry, calc types, graph models, execution generator, logging/config conventions, or test tooling are currently present.

Because the implementation starts from an empty package, this design introduces new modules rather than migrating existing application code.

## Relevant Files and Modules

Existing files:

- `calc_agent_design.md` — existing; source architecture for this implementation.
- `call_flow.md` — existing; supporting flow reference.
- `pyproject.toml` — existing; update during implementation for dependencies/tooling.
- `dinoponera/` — existing empty package directory; add framework modules here.
- `tests/` — existing empty test directory; add pytest tests here.

New source/runtime layout:

```text
dinoponera/
  core/
    __init__.py
    models.py
    naming.py
    registry_introspection.py
    traversal.py
    lint.py
    leaf_stub_generation.py
    render.py
    script_generation.py
  agent/
    __init__.py
    io.py
    planning.py

calc_types/
  __init__.py

registry/
  __init__.py
  decorators.py
  index.py
  nodes/
    __init__.py

graphs/
  # approved CalculationGraph JSON files

runs/
  # generated run scripts

tests/
  core/
  agent/

# BAML files/config:
# exact paths are determined by the BAML tooling introduced by implementation.
```

## Accepted Design Decisions

1. **Scope** — implement Step 1 Planning and Step 2 Execution Script Generation; defer Post-MVP node authoring.
2. **Layout** — framework code lives under `dinoponera/`; calculation assets/artifacts live at repo root in `calc_types/`, `registry/`, `graphs/`, and `runs/`.
3. **Registry** — use Python-function registry with `@node` metadata and signature introspection, with `registry/index.py` as source of truth.
4. **Models** — use Pydantic models with named node inputs and explicit `Edge` records storing producer, consumer, downstream input parameter name, and full import-path type string.
5. **BAML boundary** — localize direct calls to BAML-generated functions in `dinoponera/agent/planning.py`; BAML function input/output object structures are declared in `.baml` files, not duplicated as Python Pydantic result models; core modules remain BAML-free.
6. **User interaction** — use a `UserInteractor` protocol plus `ConsoleInteractor`; core modules must not call `input()` or `print()` for workflow decisions.
7. **Execution artifact** — generate standalone Python scripts only; do not add a separate in-process executor in the MVP.
8. **Testing** — use pytest for Python tests and required BAML-native tests inside `.baml` files for each MVP BAML function.

## Proposed Architecture

High-level MVP flow:

```text
User natural-language problem
  -> Phase 1 goal identification loop       # BAML + UserInteractor
  -> explicit goal confirmation             # UserInteractor
  -> Phase 2 graph building loop            # BAML + Python traversal
  -> dependency lint                         # Python
  -> graph review and approval              # UserInteractor
  -> graphs/{graph.name}.json               # Pydantic JSON
  -> script generation                       # Python, no BAML
  -> runs/run_{graph.name}.py               # standalone execution script
```

Core responsibility split:

```text
BAML:
  - baml_identify_goal
  - baml_extend_graph
  - declare BAML-native input/output object structures in `.baml` files
  - ask focused clarification/application questions through structured outputs
  - rewrite StateSummary

Python core:
  - Pydantic model definitions for Python-owned graph/registry/user-decision data only
  - registry function introspection
  - full import-path type extraction
  - breadth-first unresolved-input traversal
  - graph linting and cycle detection
  - graph rendering for review
  - graph serialization/deserialization
  - topological sorting
  - standalone script generation
```

## Data Flow

### Registry loading

1. Domain nodes are hand-authored in `registry/nodes/*.py`.
2. Each node is decorated with `@node(...)` from `registry/decorators.py`.
3. `registry/index.py` imports node functions and lists them in `NODES`.
4. `registry.index.summaries()` builds `NodeSummary` values by introspecting function signatures and decorator metadata.
5. Input parameters are stored as structured records containing both the Python parameter name and the full import-path type string. Output types are stored as full import-path strings:
   - `NodeInput(name="profile_a", type="calc_types.soil_profile.SoilProfile")`
   - output example: `calc_types.settlement_result.SettlementResult`

### Phase 1 — Goal identification

1. User provides `problem: str`.
2. Python gathers `registry_summaries = registry.index.summaries()`.
3. `dinoponera/agent/planning.py` calls `baml_identify_goal(problem, registry_summaries, clarifications)`.
4. If BAML returns `NeedsClarification`, the planner asks via `UserInteractor.ask_clarification()` and appends `QA`.
5. If BAML returns `GoalClear` with `terminal_node_id is None`, raise/report `MissingNodeError` instructing the engineer to add the missing node manually and restart.
6. If BAML returns `GoalClear` with a terminal node, show it through `UserInteractor.confirm_goal()`.
7. Proceed to Phase 2 only after explicit confirmation.

### Phase 2 — Graph building

1. Initialize:

```text
graph = CalculationGraph(
  name=normalise_name(goal.calculation_type),
  terminal_node_id=goal.terminal_node_id,
  nodes=[goal.terminal_node_id],
  edges=[]
)
state_summary = goal.state_summary
clarifications = []
```

2. `BreadthFirstTraversal.next_unresolved(graph, registry_summaries)` finds the first non-leaf node input parameter whose `(to_node, to_input, type)` is not satisfied by an incoming edge.
3. Python prefilters registry summaries to nodes whose `output == unresolved.input_type`.
4. `planning.py` calls `baml_extend_graph(unresolved, state_summary, graph, filtered_summaries, clarifications)`.
5. Handle BAML outputs:
   - `ConnectExisting`: append `Edge(from_node=from_node_id, to_node=unresolved.node_id, to_input=unresolved.input_name, type=unresolved.input_type)`.
   - `AddFromRegistry`: append node ID if not already present, then append `Edge(from_node=node_id, to_node=unresolved.node_id, to_input=unresolved.input_name, type=unresolved.input_type)`.
   - `ApplicabilityCheck`: ask user to choose a candidate, reject all, or clarify.
   - `NoCandidate`: do not immediately fail. Invoke the same source-gap resolution path used after lint. `planning.py` asks whether this required type should be provided as a leaf source through local data retrieval or runtime/user input. If the user chooses a leaf source, generate the corresponding stub immediately and add an edge for the unresolved named input. If the user says this requires a missing computation node instead, raise/report `MissingNodeError` asking the engineer to add a suitable computation node manually and restart.
6. Repeat until traversal returns `None`; no unresolved or deferred source gaps may remain before graph approval.

### Dependency lint and approval

1. Run cycle detection.
2. Verify every non-leaf node input parameter has exactly one incoming edge matching both the required parameter name and required type.
3. Keep lint itself pure: it reports graph issues only. The interactive lint-resolution loop lives in `dinoponera/agent/planning.py`.
4. Remaining or deferred source gaps are resolved through an interactive source-gap decision in `planning.py`. The user may choose one of the Step 1 leaf stub options from `calc_agent_design.md`:
   - data retrieval stub
   - user input stub
   or indicate that the gap is not a source value and requires a missing computation node.
5. If a leaf option is chosen, `planning.py` calls deterministic leaf stub generation, appends the new leaf node and `Edge(from_node=new_node_id, to_node=gap.node_id, to_input=gap.input_name, type=gap.input_type)`, refreshes registry summaries, and reruns lint. If the user indicates a missing computation node, planning raises/reports `MissingNodeError` and asks the engineer to add that computation node manually and restart.
6. Render graph for user review.
7. If approved, write `graphs/{graph.name}.json` using `CalculationGraph.model_dump_json()`.
8. If reset, discard planning state and restart Phase 1.

### Step 2 — Script generation

1. Load `graphs/{name}.json` using `CalculationGraph.model_validate_json()`.
2. Topologically sort graph edges, which are already stored producer → consumer.
3. Generate imports for:
   - type annotations from registry summaries
   - node functions from `registry.nodes.<node_id>`
4. Generate variable names from output type names in snake_case.
5. Resolve downstream arguments in `NodeSummary.inputs` order by following graph edges for each required input parameter name and type.
6. Generate `run() -> TerminalOutputType` and a `__main__` block that prints the result.
7. Write to `runs/run_{graph.name}.py`.

## API / Interface Changes

### Pydantic models

Define Python-owned graph, registry, and user-decision models in `dinoponera/core/models.py`. Do not duplicate BAML function input/output object structures as Python Pydantic result models; BAML function schemas are declared in `.baml` files and consumed through the generated BAML client.

```text
NodeInput(BaseModel)
  name: str                         # Python function parameter name
  type: str                         # full import-path type string

NodeSummary(BaseModel)
  id: str
  node_type: str                    # computation | data_retrieval | user_input
  description: str
  when_to_use: str
  assumptions: list[str]
  inputs: list[NodeInput]           # preserves parameter names and supports duplicate input types
  output: str                       # full import-path type string
  references: list[str]

UnresolvedInput(BaseModel)
  node_id: str
  input_name: str                   # downstream parameter name
  input_type: str                   # full import-path type string

Edge(BaseModel)
  from_node: str
  to_node: str
  to_input: str                     # downstream parameter name satisfied by this edge
  type: str                         # full import-path type string

CalculationGraph(BaseModel)
  name: str
  terminal_node_id: str
  nodes: list[str]
  edges: list[Edge]
  has_edge(to: str, to_input: str, type: str) -> bool

QA(BaseModel)
  question: str
  answer: str

StateSummary(BaseModel)
  goal: str
  decisions: list[str]
  open_items: list[str]
  phase1_clarification_summary: str

ApplicabilityResponse(BaseModel)
  kind: Literal["chosen", "rejected_all", "unsure"]
  node_id: str | None               # populated when kind == chosen
  detail: str | None                # clarification detail when kind == unsure

SourceGapResponse(BaseModel)
  kind: Literal["data_retrieval", "user_input", "missing_computation"]
  detail: str | None                # optional rationale or missing computation description
```

Named inputs are required. A node may have multiple parameters with the same type, and each one remains distinguishable by `NodeInput.name`, `UnresolvedInput.input_name`, and `Edge.to_input`.

BAML outputs such as goal-clear, needs-clarification, connect-existing, add-from-registry, applicability-check, and no-candidate are generated from BAML-native declarations. Python planning code should use the generated BAML client objects directly at the orchestration boundary and map only Python-owned user decisions or graph mutations into the Pydantic models above.

### Registry interface

Define Python registry behavior in `registry/index.py`, supported by helpers in `dinoponera/core/registry_introspection.py`:

```text
NODES: list[callable]
summaries() -> list[NodeSummary]
get(node_id: str) -> callable
get_summary(node_id: str) -> NodeSummary
exists(node_id: str) -> bool
```

Rules:

- `NODES` is the source of truth.
- `node_id` is `fn.__name__`.
- All node functions must have `@node(...)` metadata.
- All parameters and return values must be annotated with importable Pydantic `BaseModel` domain types for calculation I/O.
- Raw primitive calculation I/O should fail validation or at least be rejected by registry summary construction unless explicitly needed for internal non-domain use.
- Duplicate node IDs must fail clearly.
- Missing annotations, missing return annotations, or missing metadata must fail clearly.

### User interaction interface

Define in `dinoponera/agent/io.py`. The interface should avoid requiring Python-defined BAML result classes. It should accept primitive presentation fields and Python-owned models such as `NodeSummary`, `UnresolvedInput`, `StateSummary`, `CalculationGraph`, `ApplicabilityResponse`, and `SourceGapResponse`.

```text
class UserInteractor(Protocol):
  ask_clarification(question: str, context: str | None = None) -> str
  confirm_goal(calculation_type: str, terminal_node_id: str) -> bool
  resolve_applicability(question: str, candidates: list[NodeSummary]) -> ApplicabilityResponse
  resolve_source_gap(gap: UnresolvedInput, state_summary: StateSummary) -> SourceGapResponse
  approve_graph(graph: CalculationGraph, rendered: str) -> bool
```

`ApplicabilityResponse` must distinguish these cases explicitly:

```text
chosen       -> node_id contains the selected candidate
rejected_all -> planning raises MissingNodeError for MVP
unsure       -> detail contains the user's clarification answer to append as QA
```

`SourceGapResponse` must distinguish these cases explicitly:

```text
data_retrieval      -> create a reader_* leaf stub
user_input          -> create a prompt_* leaf stub
missing_computation -> raise MissingNodeError asking for a computation node to be added manually
```

Add `ConsoleInteractor` as the first concrete implementation. Only `ConsoleInteractor` should use terminal input/output for workflow decisions.

### BAML functions

MVP BAML functions:

```text
baml_identify_goal(problem, registry, clarifications)
baml_extend_graph(current_unresolved, state_summary, graph, registry, clarifications)
```

The input and output object structures for these functions must be declared in BAML, inside the `.baml` files. Do not mirror these BAML function result objects as Python Pydantic models in `dinoponera/core/models.py`. This keeps BAML callflows visible in the BAML source and keeps BAML-native tests close to the schemas and prompts they validate.

Python still owns the runtime graph/registry models needed for introspection, serialization, linting, and script generation. When those values are passed into BAML functions, the `.baml` files must declare the corresponding BAML-side input structures. `planning.py` should perform any narrow conversion required by the generated BAML client rather than defining parallel Python BAML schemas.

Exact BAML type shapes are intentionally left to implementation because the repository currently has no BAML project. The implementation agent must define BAML-native structures that can represent the callflow in `calc_agent_design.md`, including at least:

```text
baml_identify_goal output variants:
  GoalClear-like result
  NeedsClarification-like result

baml_extend_graph output variants:
  ConnectExisting-like result
  AddFromRegistry-like result
  ApplicabilityCheck-like result
  NoCandidate-like result
```

Those BAML structures must include enough fields for `planning.py` to perform the graph mutations described in this design, including downstream `input_name`/`to_input` where relevant through `UnresolvedInput`.

Exact generated client imports, BAML file paths, provider configuration, and validation commands are unknown from the current repository. The implementation agent must introduce BAML according to the tooling it chooses and keep direct imports localized to `dinoponera/agent/planning.py`.

Every BAML function introduced for the MVP must include at least two BAML-native tests directly in the `.baml` file(s). These are development tests, not skipped Python tests.

## Code Architecture Sketch

```text
Before:
dinoponera/                  # empty
tests/                       # empty
pyproject.toml               # no dependencies

After:
dinoponera/
  core/
    models.py                # Pydantic contracts for Python-owned models
    naming.py                # normalise_name and snake_case helpers
    registry_introspection.py # NodeSummary builder from decorated functions
    traversal.py             # DependencyTraversal and BreadthFirstTraversal
    lint.py                  # pure cycle and unsatisfied-input checks
    leaf_stub_generation.py  # deterministic data_retrieval/user_input stub writer
    render.py                # graph review text renderer
    script_generation.py     # topological sort and standalone script renderer
  agent/
    io.py                    # UserInteractor and ConsoleInteractor
    planning.py              # Phase 1/2 loops; localized BAML calls

calc_types/
  __init__.py                # domain type package; initially empty or seeded examples

registry/
  decorators.py              # NodeMetadata and @node
  index.py                   # NODES and registry functions
  nodes/
    __init__.py              # hand-authored nodes live here

graphs/                      # approved graph JSON
runs/                        # generated run scripts
```

Rough interfaces:

```text
class DependencyTraversal(Protocol):
  def next_unresolved(graph: CalculationGraph, registry: list[NodeSummary]) -> UnresolvedInput | None: ...

class BreadthFirstTraversal:
  def next_unresolved(...): ...

class NodeMetadata:
  node_type: str
  description: str
  when_to_use: str
  assumptions: list[str]
  references: list[str]
```

## File-by-File Implementation Plan

### `pyproject.toml`

- Existing.
- Purpose: project metadata and dependencies.
- Required changes:
  - Add Pydantic.
  - Add pytest test tooling.
  - Add BAML dependency/tooling according to selected BAML setup.
- Key dependencies:
  - `pydantic`
  - `pytest`
  - BAML tooling package(s), exact names verified during implementation.
- Tests:
  - `pytest` should run Python tests after dependencies are installed.
  - BAML test command must be documented once tooling is added.

### `dinoponera/core/__init__.py`

- New.
- Purpose: mark core package.
- Required changes: minimal exports only if useful.
- Key types/functions/classes: Not applicable.
- Dependencies: Not applicable.
- Tests: Not directly required.

### `dinoponera/core/models.py`

- New.
- Purpose: shared Pydantic models for Python-owned planning state, registry summaries, graph serialization, and user-decision data.
- Required changes:
  - Implement `NodeInput`, `NodeSummary`, `UnresolvedInput`, `Edge`, `CalculationGraph`, `QA`, `StateSummary`, `ApplicabilityResponse`, and `SourceGapResponse`.
  - Do not implement Python Pydantic mirrors for BAML function input/output result objects; those structures belong in `.baml` files.
  - Add `CalculationGraph.has_edge(to, to_input, type)`.
- Key types/functions/classes:
  - `NodeInput`
  - `NodeSummary`
  - `UnresolvedInput`
  - `Edge`
  - `CalculationGraph`
  - `StateSummary`
  - `ApplicabilityResponse`
  - `SourceGapResponse`
- Dependencies:
  - Pydantic
  - standard-library typing
- Tests:
  - `tests/core/test_models.py`

### `dinoponera/core/naming.py`

- New.
- Purpose: naming helpers.
- Required changes:
  - Implement `normalise_name(s: str) -> str` per `calc_agent_design.md`.
  - Implement snake_case conversion for type names and generated variable names.
- Key types/functions/classes:
  - `normalise_name`
  - `to_snake_case`
- Dependencies:
  - `re`
- Tests:
  - `tests/core/test_naming.py`

### `dinoponera/core/registry_introspection.py`

- New.
- Purpose: build `NodeSummary` from Python functions.
- Required changes:
  - Implement `build_summary(fn) -> NodeSummary`.
  - Validate `_node_metadata` exists.
  - Validate annotations exist and are not raw primitives for node I/O.
  - Convert parameter annotations to `NodeInput(name=<parameter name>, type=<full import-path string>)`.
  - Convert return annotation to a full import-path string.
  - Preserve duplicate input types by parameter name rather than rejecting them.
- Key types/functions/classes:
  - `build_summary`
  - registry validation exceptions
- Dependencies:
  - `inspect`
  - `NodeSummary`
- Tests:
  - `tests/core/test_registry_introspection.py`

### `dinoponera/core/traversal.py`

- New.
- Purpose: dependency traversal for unresolved graph inputs.
- Required changes:
  - Define `DependencyTraversal` protocol.
  - Implement `BreadthFirstTraversal.next_unresolved()` following the source design, updated to check `Edge.to_input` as well as edge type.
  - Skip `data_retrieval` and `user_input` leaf nodes.
- Key types/functions/classes:
  - `DependencyTraversal`
  - `BreadthFirstTraversal`
- Dependencies:
  - `CalculationGraph`, `NodeSummary`, `UnresolvedInput`
- Tests:
  - `tests/core/test_traversal.py`

### `dinoponera/core/lint.py`

- New.
- Purpose: dependency graph validation before approval/serialization.
- Required changes:
  - Implement cycle detection over explicit forward edges.
  - Verify every non-leaf node input parameter has exactly one matching incoming edge by `(to_node, to_input, type)`.
  - Provide clear errors for missing, duplicate, unknown-node, and cyclic graphs.
  - Keep lint pure: it must not import `UserInteractor`, call `input()`, print prompts, or mutate registry files. Interactive lint resolution lives in `dinoponera/agent/planning.py`.
- Key types/functions/classes:
  - `has_cycle`
  - `lint_graph`
  - graph lint exception classes
- Dependencies:
  - `CalculationGraph`, `NodeSummary`, traversal helpers
- Tests:
  - `tests/core/test_lint.py`

### `dinoponera/core/leaf_stub_generation.py`

- New.
- Purpose: deterministic Step 1 generation of leaf stubs for unresolved lint gaps.
- Required changes:
  - Implement `create_leaf_stub(node_type: str, output_type_path: str) -> str`.
  - Support only `data_retrieval` and `user_input` node types for MVP leaf gaps.
  - Derive node IDs deterministically using the source design rule: `reader_<snake_case_type_name>` for `data_retrieval`, `prompt_<snake_case_type_name>` for `user_input`, appending `_2`, `_3`, etc. on collision.
  - Write `registry/nodes/{node_id}.py` with the correct `@node(...)` metadata, zero parameters, and return annotation imported from `output_type_path`.
  - Function body raises `NotImplementedError("Stub — implement before running")`.
  - Append the import and node name to `registry/index.py` in the existing explicit-registry style.
  - Import the new module with `importlib.import_module` and append the function to in-memory `registry.index.NODES` so traversal can continue in the same process.
  - Return the new node ID.
- Key types/functions/classes:
  - `create_leaf_stub`
- Dependencies:
  - `pathlib`, `importlib`, naming helpers, registry index module
- Tests:
  - `tests/core/test_leaf_stub_generation.py`

### `dinoponera/core/render.py`

- New.
- Purpose: human-readable graph review formatting.
- Required changes:
  - Render nodes with node type and output type.
  - Render connections grouped/readably by edge.
  - Include enough detail for approval/reset decision.
- Key types/functions/classes:
  - `render_graph`
- Dependencies:
  - `CalculationGraph`, registry summaries
- Tests:
  - `tests/core/test_render.py`

### `dinoponera/core/script_generation.py`

- New.
- Purpose: Step 2 standalone execution script generation.
- Required changes:
  - Load/accept `CalculationGraph`.
  - Topologically sort explicit forward edges.
  - Resolve node summaries from registry.
  - Render import statements for domain types and node functions.
  - Generate deterministic variable names from output types.
  - Handle variable-name collisions by suffixing with node IDs.
  - Resolve function arguments in `NodeSummary.inputs` order by graph edges using downstream parameter names (`Edge.to_input`) and input types.
  - Generate `run() -> TerminalOutputType` and `__main__` block.
  - Write to `runs/run_{graph.name}.py`.
- Key types/functions/classes:
  - `topological_sort`
  - `generate_script_source`
  - `write_run_script`
- Dependencies:
  - `CalculationGraph`, registry summaries, naming helpers
- Tests:
  - `tests/core/test_script_generation.py`

### `dinoponera/agent/__init__.py`

- New.
- Purpose: mark agent package.
- Required changes: minimal.
- Key types/functions/classes: Not applicable.
- Dependencies: Not applicable.
- Tests: Not directly required.

### `dinoponera/agent/io.py`

- New.
- Purpose: user interaction boundary.
- Required changes:
  - Define `UserInteractor` protocol.
  - Implement `ConsoleInteractor`.
  - Define or import `ApplicabilityResponse` so applicability decisions distinguish `chosen`, `rejected_all`, and `unsure`.
  - Define or import `SourceGapResponse` so no-candidate/source-gap decisions distinguish `data_retrieval`, `user_input`, and `missing_computation`.
  - Keep all terminal prompting out of core modules.
- Key types/functions/classes:
  - `UserInteractor`
  - `ConsoleInteractor`
- Dependencies:
  - shared models
- Tests:
  - `tests/agent/test_io.py`

### `dinoponera/agent/planning.py`

- New.
- Purpose: Phase 1 and Phase 2 orchestration.
- Required changes:
  - Directly import/call BAML-generated `baml_identify_goal` and `baml_extend_graph` locally in this module.
  - Implement Phase 1 clarification loop.
  - Implement goal confirmation gate.
  - Implement Phase 2 graph-building loop.
  - Implement applicability-check handling through structured `ApplicabilityResponse`.
  - Implement Phase 2 `NoCandidate` handling through the same source-gap path used by lint: ask whether the unresolved named input should be a data retrieval leaf, a user input leaf, or a missing computation node.
  - Use BAML-generated objects directly for BAML results; do not depend on Python-defined BAML result models.
  - Raise/report `MissingNodeError` for missing terminal nodes and for dependency gaps the user classifies as missing computation nodes.
  - Run pure lint and own the interactive lint-resolution loop.
  - Call deterministic leaf stub generation for data-retrieval/user-input leaf gaps.
  - Run graph review.
  - Serialize approved graph to `graphs/{name}.json`.
- Key types/functions/classes:
  - `identify_goal_loop`
  - `build_graph_loop`
  - `plan_calculation`
  - `MissingNodeError`
- Dependencies:
  - BAML generated functions
  - registry index module
  - core models/traversal/lint/render/naming
  - `UserInteractor`
- Tests:
  - `tests/agent/test_planning.py` with mocked BAML calls and fake interactors.

### `calc_types/__init__.py`

- New.
- Purpose: root-level domain type package.
- Required changes:
  - Empty initial package marker is acceptable.
  - Implementation may add small example/test-only domain types if needed, but production seed types are not required unless chosen.
- Key types/functions/classes: domain Pydantic models added by engineers later.
- Dependencies:
  - Pydantic for actual domain type files.
- Tests:
  - Import path tests when sample types are added.

### `registry/__init__.py`

- New.
- Purpose: root-level registry package marker.
- Required changes: minimal.
- Key types/functions/classes: Not applicable.
- Dependencies: Not applicable.
- Tests: Not directly required.

### `registry/decorators.py`

- New.
- Purpose: node metadata decorator.
- Required changes:
  - Implement `NodeMetadata` dataclass.
  - Implement `node(**kwargs)` decorator that attaches `_node_metadata` to function objects.
- Key types/functions/classes:
  - `NodeMetadata`
  - `node`
- Dependencies:
  - `dataclasses`
- Tests:
  - `tests/core/test_registry_introspection.py`

### `registry/index.py`

- New.
- Purpose: source of truth for registered node functions.
- Required changes:
  - Define `NODES = []` initially or with example nodes if implementation chooses to seed examples.
  - Implement `summaries()`, `get()`, `get_summary()`, and `exists()`.
  - Delegate summary construction to `dinoponera.core.registry_introspection.build_summary`.
  - Fail clearly on duplicate node IDs.
- Key types/functions/classes:
  - `NODES`
  - `summaries`
  - `get`
  - `get_summary`
  - `exists`
- Dependencies:
  - hand-authored node imports
  - `build_summary`
- Tests:
  - `tests/core/test_registry_index.py`

### `registry/nodes/__init__.py`

- New.
- Purpose: node package marker.
- Required changes: minimal.
- Key types/functions/classes: Not applicable.
- Dependencies: Not applicable.
- Tests: Not directly required.

### `graphs/`

- New directory.
- Purpose: approved serialized `CalculationGraph` JSON files.
- Required changes:
  - Planning writes `graphs/{graph.name}.json` after approval.
  - If committed while empty, add a placeholder only if repository policy requires it; otherwise directory may be created by implementation/runtime.
- Key types/functions/classes: Not applicable.
- Dependencies: Not applicable.
- Tests:
  - planning serialization tests should use temporary graph output directories where practical.

### `runs/`

- New directory.
- Purpose: generated standalone execution scripts.
- Required changes:
  - Script generation writes `runs/run_{graph.name}.py`.
  - If committed while empty, add a placeholder only if repository policy requires it; otherwise directory may be created by implementation/runtime.
- Key types/functions/classes: Not applicable.
- Dependencies: Not applicable.
- Tests:
  - script generation tests should use temporary run output directories where practical.

### BAML project/config files

- New; exact paths are unknown from current repository.
- Purpose: define BAML schemas/functions/prompts/tests for MVP planning.
- Required changes:
  - Add BAML definitions for:
    - `baml_identify_goal`
    - `baml_extend_graph`
  - Configure provider/model according to BAML/Anthropic docs or the selected provider docs.
  - Define BAML-native input and output object structures for both functions directly in `.baml` files.
  - Do not require Python Pydantic result models for BAML function outputs.
  - Ensure generated BAML objects expose fields needed by `planning.py` for graph mutation, including node IDs, rationales, updated state summaries, applicability questions/candidates, missing-node descriptions, and unresolved input name/type context.
  - Add at least two BAML-native tests directly in `.baml` files for `baml_identify_goal`.
  - Add at least two BAML-native tests directly in `.baml` files for `baml_extend_graph`.
  - Document the exact BAML test/validation command introduced by the implementation.
- Key types/functions/classes:
  - BAML classes corresponding to the planner callflow, including BAML-side representations of `NodeInput`, `NodeSummary`, `CalculationGraph`, `StateSummary`, and output variants.
  - BAML functions `baml_identify_goal` and `baml_extend_graph`.
- Dependencies:
  - BAML tooling.
  - Provider credentials/config required by selected BAML setup.
- Tests:
  - BAML-native tests in `.baml` files are required and should be run during development.

### `tests/core/test_models.py`

- New.
- Purpose: Pydantic model tests.
- Required tests:
  - valid model construction
  - invalid/missing fields
  - `CalculationGraph.has_edge(to, to_input, type)`
  - named inputs allow two parameters with the same type on one node
  - `ApplicabilityResponse.kind` and `SourceGapResponse.kind` reject invalid values
  - JSON round-trip for graph serialization

### `tests/core/test_naming.py`

- New.
- Purpose: naming helper tests.
- Required tests:
  - `normalise_name("Settlement Analysis") == "settlement_analysis"`
  - punctuation/parentheses normalization
  - PascalCase type to snake_case variable conversion

### `tests/core/test_registry_introspection.py`

- New.
- Purpose: decorator and introspection tests.
- Required tests:
  - metadata attached by `@node`
  - `build_summary()` extracts inputs/output full paths
  - missing metadata fails
  - missing annotations fail
  - primitive/raw I/O annotations fail or are rejected according to implementation policy

### `tests/core/test_registry_index.py`

- New.
- Purpose: `registry/index.py` behavior tests.
- Required tests:
  - `summaries()` returns summaries for `NODES`
  - `get()` returns expected function
  - `get_summary()` returns expected summary
  - `exists()` true/false behavior
  - duplicate node ID failure
  - unknown node ID failure

### `tests/core/test_traversal.py`

- New.
- Purpose: breadth-first unresolved-input traversal tests.
- Required tests:
  - first unresolved named input is returned in graph node order
  - resolved inputs are skipped
  - leaf nodes are skipped
  - traversal returns `None` for complete graph

### `tests/core/test_lint.py`

- New.
- Purpose: graph lint tests.
- Required tests:
  - clean graph passes
  - missing incoming named input fails clearly
  - duplicate incoming edge for same consumer/input-name/type fails clearly
  - cycle detection fails clearly
  - unknown node IDs fail clearly

### `tests/core/test_leaf_stub_generation.py`

- New.
- Purpose: deterministic leaf stub generation tests.
- Required tests:
  - `data_retrieval` stub node ID uses `reader_<type_name>` naming rule
  - `user_input` stub node ID uses `prompt_<type_name>` naming rule
  - collisions append numeric suffixes
  - generated file imports the output type and raises `NotImplementedError`
  - `registry/index.py` is updated in the explicit `NODES` style
  - generated node is appended to in-memory `NODES` and visible to `summaries()` without process restart

### `tests/core/test_render.py`

- New.
- Purpose: graph review rendering tests.
- Required tests:
  - rendered graph includes nodes, node types, outputs, and connections
  - rendered text is stable enough for review assertions

### `tests/core/test_script_generation.py`

- New.
- Purpose: Step 2 script generation tests.
- Required tests:
  - topological sort uses producer → consumer edges correctly
  - generated script imports node functions and type annotations
  - generated variable names are deterministic
  - variable-name collisions are suffixed with node IDs
  - downstream call arguments are resolved by graph edges using `Edge.to_input`
  - terminal node return annotation is generated
  - `__main__` block is generated
  - optional smoke import/run using simple test nodes

### `tests/agent/test_io.py`

- New.
- Purpose: interactor tests.
- Required tests:
  - fake interactor protocol compatibility where useful
  - console option parsing for candidate/approval choices where practical

### `tests/agent/test_planning.py`

- New.
- Purpose: planner orchestration tests with mocked BAML calls.
- Required tests:
  - Phase 1 clarification loop
  - goal confirmation accepted
  - goal confirmation rejected/restarted
  - missing terminal node reports `MissingNodeError`
  - Phase 2 `ConnectExisting` path
  - Phase 2 `AddFromRegistry` path
  - Phase 2 `ApplicabilityCheck` path
  - Phase 2 `NoCandidate` path creates a leaf stub when user chooses data retrieval
  - Phase 2 `NoCandidate` path creates a leaf stub when user chooses user input
  - Phase 2 `NoCandidate` path raises `MissingNodeError` when user classifies the gap as missing computation
  - approved graph serialization path
  - reset path

## Testing Strategy

### Python tests

Use pytest for deterministic Python components and mocked planner orchestration.

Primary command:

```text
pytest
```

If the implementation introduces a runner such as `uv`, document the equivalent command, for example:

```text
uv run pytest
```

Python tests should not require live BAML calls. They should mock the BAML-generated functions imported by `dinoponera/agent/planning.py`.

### BAML-native tests

BAML-native tests are required for every BAML function introduced in the MVP. These tests must live in the `.baml` files, not in Python test files.

Required BAML tests:

```text
baml_identify_goal
  - at least two native BAML tests
  - cover a clear goal case and a clarification or missing-terminal case

baml_extend_graph
  - at least two native BAML tests
  - cover at least AddFromRegistry/ConnectExisting behavior and ambiguity/no-candidate behavior
  - no-candidate BAML tests only validate the BAML output; Python tests validate source-gap routing to leaf stubs or MissingNodeError
```

The implementation agent must add and document the exact BAML validation/test command because no BAML tooling currently exists in the repository. These tests are intended to be run during development, not skipped as optional Python integration tests.

### Regression focus

Add regression tests for:

- type paths are full import paths and round-trip through JSON
- `NodeSummary.inputs` preserves parameter names, including duplicate input types
- `Edge.to_input` disambiguates same-type downstream parameters
- graph edges remain producer → consumer and target a named downstream input
- leaf nodes are skipped by traversal
- same-type transformer nodes remain representable through explicit edges
- generated scripts do not call BAML
- generated scripts import from root-level `calc_types` and `registry.nodes`
- missing registry annotations fail before planning proceeds
- Phase 2 no-candidate source gaps can become data-retrieval/user-input stubs instead of failing immediately

## Migration / Backward Compatibility

Not applicable for existing application behavior because there is no implemented calculation-agent system yet.

Compatibility constraints for new artifacts:

- Approved graphs are serialized as Pydantic JSON using `CalculationGraph`.
- Graph edges store type strings and downstream input names, not live type objects.
- Generated scripts depend on import paths remaining stable:
  - domain types under `calc_types`
  - nodes under `registry.nodes`
- Node IDs are Python function names and should remain stable once graphs reference them.
- Post-MVP authoring must preserve the MVP registry contract if added later.

## Risks and Mitigations

### Risk: BAML setup is unknown

- Unknown: exact BAML dependency, file layout, generated client import path, provider/model identifier, and test command.
- Why it matters: planner modules must import generated BAML functions, and required BAML-native tests must run during development.
- Conservative default: introduce BAML following its current tooling conventions, localize imports to `dinoponera/agent/planning.py`, and document the exact BAML test command.
- Status: Accepted with assumptions.

### Risk: Root-level packages may need packaging configuration

- Unknown: whether packaging/distribution will include `calc_types` and `registry` by default.
- Why it matters: generated scripts import these packages directly.
- Conservative default: add `__init__.py` files and verify imports in tests from the repository root.
- Status: Accepted with assumptions.

### Risk: Full import-path strings can become stale

- Why it matters: serialized graphs and generated scripts depend on type and node import paths.
- Mitigation: keep node IDs and type modules stable; treat renames as compatibility-breaking until a migration strategy exists.
- Status: Accepted.

### Risk: Hand-authored registry import errors can break planning

- Why it matters: `registry/index.py` imports node modules directly.
- Mitigation: fail clearly during registry summary construction; test missing metadata/annotations/import assumptions.
- Status: Accepted.

### Risk: Generated script behavior can diverge from planned graph

- Why it matters: the script is the execution artifact and audit trail.
- Mitigation: generate calls only from explicit graph edges and registry summaries; test topological order, imports, variables, and arguments.
- Status: Accepted.

### Risk: BAML-native tests may be slower or require credentials

- Why it matters: user requires these tests to run during development.
- Mitigation: implementation must configure BAML tooling and document required environment/provider setup. Do not replace these with Python-skipped tests.
- Status: Accepted.

## Validation Checklist

Implementation checklist:

- [ ] `pyproject.toml` includes Pydantic, pytest, and BAML tooling.
- [ ] `dinoponera/core/` modules exist.
- [ ] `dinoponera/agent/` modules exist.
- [ ] `calc_types/` exists with `__init__.py`.
- [ ] `registry/` exists with `decorators.py`, `index.py`, and `nodes/`.
- [ ] `graphs/` output path is created or handled by planning code.
- [ ] `runs/` output path is created or handled by script-generation code.
- [ ] `NodeInput`, `NodeSummary`, `Edge`, `CalculationGraph`, `QA`, `StateSummary`, `UnresolvedInput`, `ApplicabilityResponse`, and `SourceGapResponse` are Pydantic models.
- [ ] `CalculationGraph.model_dump_json()` and `CalculationGraph.model_validate_json()` are used for graph files.
- [ ] `Edge.to_input` and `UnresolvedInput.input_name` are used anywhere a downstream input is matched or satisfied.
- [ ] `@node` attaches `_node_metadata`.
- [ ] `build_summary()` uses function signatures and metadata.
- [ ] Registry rejects/clearly fails missing metadata and missing annotations.
- [ ] `BreadthFirstTraversal` skips `data_retrieval` and `user_input` nodes.
- [ ] Lint detects cycles and unsatisfied named inputs.
- [ ] Lint remains pure and does not depend on `UserInteractor` or mutate registry files.
- [ ] Leaf stub generation creates data-retrieval/user-input stubs and updates `registry/index.py` plus in-memory `NODES`.
- [ ] Phase 2 `NoCandidate` uses source-gap resolution instead of immediately failing; it only raises `MissingNodeError` when the user classifies the gap as a missing computation node.
- [ ] Phase 1 and Phase 2 planning loops are implemented.
- [ ] Direct BAML calls are localized to `dinoponera/agent/planning.py`.
- [ ] BAML function input/output object structures are declared in `.baml` files, not mirrored as Python Pydantic result models.
- [ ] Core modules do not import BAML.
- [ ] Core modules do not call `input()` or `print()` for decisions.
- [ ] Approved graphs are written to `graphs/{name}.json`.
- [ ] Script generation writes `runs/run_{graph.name}.py`.
- [ ] Generated scripts contain no BAML calls.
- [ ] Python tests exist for core and agent modules.
- [ ] BAML-native tests exist in `.baml` files for `baml_identify_goal` and `baml_extend_graph`, at least two tests each.
- [ ] Development validation documentation includes both `pytest` and the BAML-native test command.

Implementability checks against current repo:

- [x] `calc_agent_design.md` exists and supports this plan.
- [x] `pyproject.toml` exists and is the correct place to add dependencies.
- [x] `dinoponera/` exists and can contain framework modules.
- [x] `tests/` exists and can contain pytest tests.
- [x] Proposed source modules are new except `pyproject.toml`.
- [x] No existing source module migration is required.
- [x] Conflicting `old/DESIGN.md` is explicitly not used as the source of truth.

## Open Questions

### Exact BAML setup

Unknown: BAML dependency names, generated client import paths, `.baml` file layout, provider/model identifier, and validation/test command.

Why it matters: the MVP planner depends on BAML function calls, and BAML-native tests are required.

Conservative default: the implementation agent should introduce BAML according to current BAML tooling conventions, keep direct BAML imports localized to `dinoponera/agent/planning.py`, add native tests inside `.baml` files, and document the command used to run them.

Status: Accepted with assumptions.

### Seed domain types and nodes

Unknown: whether the implementation should include example production domain types/nodes or only framework scaffolding.

Why it matters: BAML tests and smoke tests need representative registry summaries, but production engineering nodes may require domain decisions outside this MVP.

Conservative default: include minimal test fixtures or clearly marked example nodes only where needed for tests; keep production registry initially empty unless the implementer is explicitly asked to seed real engineering calculations.

Status: Accepted with assumptions.

### Packaging of root-level packages

Unknown: whether the project will later be packaged/distributed beyond running from repo root.

Why it matters: generated scripts import `calc_types` and `registry.nodes` directly.

Conservative default: add `__init__.py` package markers and validate imports from the repository root. Defer distribution packaging refinements.

Status: Accepted with assumptions.

### Post-MVP node authoring

Deferred: BAML-assisted generation of types and nodes is outside this MVP.

Why it matters: missing nodes currently require manual registry authoring and restart, except leaf stubs in lint as defined for Step 1.

Conservative default: keep missing-node behavior aligned with Step 1 and defer authoring loop design.

Status: Deferred.

### Conditional and iterative calculations

Deferred: the DAG model does not represent runtime conditionals or iterative loops.

Why it matters: some engineering workflows may require branch or iteration logic.

Conservative default: do not support conditional/iterative graph structure in the MVP; encapsulate such logic inside a hand-authored node only if necessary.

Status: Deferred.

# Design: Calculation Agent Full System

## Summary

Implement the calculation-agent architecture described in `calc_agent_design.md` as a full Python + BAML system.

The system lets an engineer describe a calculation problem in natural language, resolves the calculation goal and dependency graph through BAML-assisted planning, creates missing calculation nodes through a guarded authoring/code-generation pipeline, validates and reviews the complete plan, then executes approved Python nodes deterministically with no LLM calls during execution.

The repository currently has an empty `dinoponera/` package and empty `tests/` directory. This design introduces the full architecture under new package subdirectories while preserving clear boundaries between deterministic core logic, interactive agent orchestration, and BAML-dependent planning/generation calls.

## Goals

- Implement the full calculation-agent workflow from `calc_agent_design.md` in one implementation pass.
- Add structured Pydantic models for shared agent data.
- Add a persistent node registry backed by `index.json` plus Python node files.
- Add BAML-backed goal identification, chain/graph construction, node clarification, and code generation.
- Add explicit user interaction gates for clarification, goal confirmation, code review, dependency resolution, and final plan approval.
- Represent planned calculations internally as a dependency graph, then topologically sort into an execution plan.
- Validate dependency graphs before execution, including shared missing inputs, duplicate producers, cycles, and unknown nodes.
- Validate generated Python node code before registry save.
- Require engineer approval before generated code is registered.
- Execute approved plans with runtime contract checks around every node.
- Add pytest-based tests for deterministic core behavior and mocked BAML/interaction flows.

## Non-Goals

- Do not implement conditional execution in this design.
- Do not implement iterative design/check/resize workflows as first-class graph constructs.
- Do not implement typed or unit-aware `CalcContext` schemas yet.
- Do not implement registry scaling through embeddings, vector search, or category prefiltering.
- Do not implement node update/version migration semantics beyond initial save and duplicate protection.
- Do not define final calculation report formatting beyond returning the final context.
- Do not prompt the user from the execution engine; all `user_input` values are collected before execution begins.
- Do not require live LLM/BAML calls in automated tests unless credentials/configuration are explicitly available.
- Do not reference or rely on `main.py`; it is considered removed.

## Existing Codebase Context

Repository evidence at design time:

- `pyproject.toml` exists and defines:
  - project name: `dinoponera`
  - Python requirement: `>=3.12`
  - no current dependencies
- `dinoponera/` exists and is empty.
- `tests/` exists and is empty.
- `README.md` exists and is empty.
- `calc_agent_design.md` is the source architecture plan.
- There is no existing BAML project structure, generated BAML client, registry, execution engine, calculation model, logging system, config system, or test framework configuration.

Because the implementation starts from an empty package, the design introduces new modules rather than adapting existing source conventions.

## Relevant Files and Modules

Existing files/directories:

- `calc_agent_design.md` — existing; source plan to implement.
- `pyproject.toml` — existing; must be updated by the implementation agent to add required dependencies/test tooling.
- `dinoponera/` — existing empty package directory; new implementation modules go here.
- `tests/` — existing empty test directory; new pytest tests go here.

New package layout:

```text
dinoponera/
  core/
    __init__.py
    models.py
    registry.py
    graph.py
    lint.py
    execution.py
    validation.py
  agent/
    __init__.py
    io.py
    planning.py
    authoring.py
    codegen.py
    review.py
  integrations/
    __init__.py
    # optional BAML runtime/config helpers only if required by BAML tooling
```

New test layout:

```text
tests/
  core/
    test_models.py
    test_registry.py
    test_graph_lint.py
    test_execution.py
    test_validation.py
  agent/
    test_io.py
    test_planning.py
    test_authoring.py
    test_codegen.py
    test_review.py
  integrations/
    test_baml_integration.py
```

Runtime registry layout:

```text
registry/
  index.json
  nodes/
    <node_id>.py
```

The registry root must be configurable so tests can use temporary directories.

## Accepted Design Decisions

1. **Full implementation scope** — implement the complete system described by `calc_agent_design.md` in one pass, not a Python-only MVP.
2. **Module boundaries** — use subpackages separating deterministic core modules, agent orchestration modules, and optional integration helpers.
3. **Data models** — use Pydantic models rather than dataclasses or raw dictionaries.
4. **Registry storage** — use JSON `index.json` plus Python files under configurable `registry/nodes/`.
5. **BAML boundary** — call BAML-generated functions directly from agent modules instead of introducing an adapter abstraction.
6. **User interaction** — define a user interaction protocol plus a console implementation; do not call `input()` directly from core logic.
7. **Dependency representation** — use an internal dependency graph for planning/lint/review and topologically sort it into a deterministic linear execution plan.
8. **Code generation** — allow BAML to generate complete node functions for executable nodes; require strict static validation and explicit engineer approval before saving. `user_input` nodes are metadata-only input collection steps and do not require generated Python code.
9. **Execution** — execute a linear plan with runtime contract checks before and after each node call.
10. **Testing** — use pytest and add it as project test tooling.
11. **BAML model selection** — configure all BAML functions to use Claude Haiku 4.5. The implementation agent must verify the exact BAML/Anthropic model identifier during BAML setup.

## Proposed Architecture

High-level workflow:

```text
User problem statement
  -> Phase 1 goal identification loop                # BAML + user clarification
  -> explicit goal confirmation                      # user gate
  -> Phase 2 graph-building loop                     # BAML + user applicability checks
  -> graph lint                                      # pure Python
  -> dependency resolution loop                      # user + optional node authoring
  -> topological sort into ExecutionPlan             # pure Python
  -> final chain/graph review                        # user gate
  -> execution engine                                # pure Python, no LLM calls
  -> final CalcContext
```

Core responsibility split:

```text
BAML/direct agent calls:
  - identify calculation goal
  - extend calculation graph
  - ask semantic/applicability questions
  - clarify missing node specification
  - generate complete Python node functions

Python core:
  - Pydantic model validation
  - registry persistence and dynamic node loading
  - dependency graph/lint logic
  - topological sorting
  - generated-code static validation
  - execution runtime contract checks
```

The execution engine must not call BAML or any LLM service.

## Data Flow

### Phase 1: Goal Identification

Input:

- natural language `problem: str`
- registry summaries from `Registry.summaries()`
- accumulated `QA` clarifications

Loop:

1. Call BAML goal-identification function directly from `dinoponera/agent/planning.py`.
2. If BAML returns `NeedsClarification`, ask through `UserInteractor` and append `QA`.
3. If BAML returns `GoalClear` with no terminal node, invoke node authoring.
4. If BAML returns `GoalClear` with terminal node, show goal to user for confirmation.
5. Proceed only after explicit confirmation.

### Phase 2: Dependency Graph Building

Input:

- confirmed goal
- current `StateSummary`
- registry summaries
- accumulated Phase 2 clarifications

Loop:

1. Seed graph with terminal node.
2. Call BAML chain/graph extension directly from `dinoponera/agent/planning.py`.
3. For clear matches, add selected node/dependency edges to the graph.
4. For applicability checks, ask through `UserInteractor`.
5. For missing nodes, invoke node authoring.
6. Stop when BAML indicates graph construction is complete.

### Graph Lint and Dependency Resolution

Graph lint scans the complete graph and reports graph issues before execution:

- unknown node IDs
- missing input keys
- all consumers of each missing input key
- duplicate/ambiguous producers for the same key
- dependency cycles
- unresolved ordering constraints

Shared input example:

```text
cpt_raw_data
  ├─ positive_skin_friction
  ├─ negative_skin_friction
  └─ bearing_capacity
```

The lint result shown to the user should group by missing key:

```text
Missing input: cpt_raw_data
Needed by:
  - positive_skin_friction
  - negative_skin_friction
  - bearing_capacity
```

The user resolves the missing key once by choosing a data retrieval node, user input node, or newly authored derived node. The new provider is inserted into the graph and lint reruns until clean.

### Plan Review, Input Collection, and Execution

1. Once graph lint is clean, topologically sort the graph into an `ExecutionPlan`.
2. Show the graph summary and linear execution order to the engineer.
3. User must choose approve or full reset.
4. After approval and before execution, collect all values required by `user_input` nodes through `UserInteractor`.
5. Execute the approved plan in order. The execution engine must not prompt the user and must not call BAML.
6. Return the final `CalcContext` dictionary.

`user_input` nodes are represented in the registry and execution plan for auditability, but they are not dynamically loaded Python functions. During execution, the executor writes their pre-collected values into `CalcContext` at the point where the `user_input` node appears in the execution order. Pre-collected values should be passed to execution as a mapping keyed by `node_id`, where each value is a mapping of declared write keys to concrete values.

## API / Interface Changes

### Pydantic models

Define in `dinoponera/core/models.py`.

Key models/enums:

```text
NodeType
  computation
  data_retrieval
  user_input

NodeSummary
  id: str
  name: str
  node_type: NodeType
  description: str
  when_to_use: str
  assumptions: list[str]
  reads: list[str]
  writes: list[str]

NodeSpec
  name: str
  node_type: NodeType
  description: str
  when_to_use: str
  assumptions: list[str]
  reads: list[str]
  writes: list[str]
  logic_description: str
  references: list[str]

QA
  question: str
  answer: str

StateSummary
  goal: str
  decisions: list[str]
  open_items: list[str]
  phase1_clarification_summary: str
```

Additional models should cover:

- `GoalClear`
- `NeedsClarification`
- `ClearMatch`
- `ApplicabilityCheck`
- `NoCandidate`
- `ChainComplete`
- `CalculationGraph`
- `GraphNodeRef` or equivalent node graph representation
- `GraphLintIssue`
- `MissingInputIssue`
- `DuplicateProducerIssue`
- `CycleIssue`
- `ExecutionPlan`
- `ExecutionStep` if the implementation needs per-step metadata beyond node IDs
- `MissingInputResolution`
- `ValidationResult`
- `CodeReviewDecision`
- `ChainReviewDecision`
- `ApplicabilityResponse`
- registry and execution exception/error models where structured errors are preferable to bare exceptions

Use explicit discriminator fields for union-style BAML results, for example `result_type` or `kind`, so direct BAML outputs can be parsed predictably into Pydantic models.

### Registry interface

Define in `dinoponera/core/registry.py`.

Required behavior:

```text
Registry(root_path: Path | str = "registry")

save(node_id: str, spec: NodeSpec, code: str | None) -> NodeSummary
load(node_id: str) -> Callable[[dict], dict]
summaries() -> list[NodeSummary]
summary(node_id: str) -> NodeSummary
exists(node_id: str) -> bool
```

Rules:

- `index.json` is the source of truth.
- Planners read summaries from `index.json` only.
- Python files in `nodes/` without an index entry are invisible.
- `node_id` must be a lowercase `snake_case` Python identifier and must match the generated function name for executable nodes.
- `save()` must reject duplicate `node_id` unless an explicit update flow is added later.
- `save()` should write executable node files through a temporary file then replace/write final files coherently; if fully atomic multi-file writes are not implemented, failures must leave clear errors and tests should cover common failure cases.
- `code` is required for `computation` and `data_retrieval` nodes.
- `code` must be `None` for `user_input` nodes. `user_input` registry entries may omit the `file` field or set it to `null`; they are handled by the executor using pre-collected input values.
- `load()` dynamically loads only indexed executable node files and must reject `user_input` nodes because they have no Python function to load.

### Graph and lint interface

Define graph structures in `dinoponera/core/graph.py` and lint logic in `dinoponera/core/lint.py`.

Required behavior:

```text
CalculationGraph
  node_ids: ordered list of unique node IDs
  # no manually maintained dependency edges in the first implementation
  # edges are derived from registry NodeSummary.reads/writes

lint_graph(graph, registry) -> GraphLintResult

topological_sort(graph, registry) -> ExecutionPlan
```

Graph lint must detect:

- unknown nodes
- repeated node IDs
- missing input keys with all consumers grouped
- duplicate producers for a key
- cycles

Derived graph rules:

- A producer is any node whose `writes` contains a key.
- A consumer is any node whose `reads` contains a key.
- A dependency edge exists from producer node to consumer node when the producer writes a key the consumer reads.
- A key with consumers and no producer is a missing input unless it is explicitly provided as an approved preseeded input.
- Duplicate producers for the same key are rejected in the first implementation.
- Resolving a missing input adds exactly one provider node to the graph, usually `user_input`, `data_retrieval`, or a newly authored computation node.

Topological sorting must be deterministic. If multiple nodes are eligible at the same time, use original planner insertion order, then node ID as a tie-breaker.

### User interaction protocol

Define in `dinoponera/agent/io.py`.

Rough interface:

```text
UserInteractor
  ask_clarification(question: str, context: str | None = None) -> str
  confirm_goal(goal: GoalClear) -> bool
  resolve_applicability(check: ApplicabilityCheck) -> ApplicabilityResponse
  resolve_missing_input(issue: MissingInputIssue) -> MissingInputResolution
  collect_user_input(node: NodeSummary) -> dict[str, object]
  review_generated_code(node_id: str, code: str) -> CodeReviewDecision
  approve_plan(graph: CalculationGraph, plan: ExecutionPlan) -> ChainReviewDecision
```

Add `ConsoleInteractor` as the initial concrete implementation using standard input/output. Core modules must not call `input()` or `print()` for workflow decisions.

### Direct BAML calls

Agent modules should import and call BAML-generated functions directly.

Expected BAML functions from `calc_agent_design.md`:

- `baml_identify_goal`
- `baml_extend_chain`
- `baml_clarify_node`
- `baml_generate_code`

All BAML functions must be configured to use Claude Haiku 4.5. The exact BAML/Anthropic model identifier is not known from this repository and must be verified against the BAML and Anthropic documentation during implementation.

Exact BAML dependency names, generated import paths, and BAML config file layout are unknown from the current repository. The implementation agent must follow the BAML tooling conventions it introduces and keep those imports localized to:

- `dinoponera/agent/planning.py`
- `dinoponera/agent/authoring.py`
- `dinoponera/agent/codegen.py`

Automated tests should mock these direct calls rather than requiring live LLM access.

## Code Architecture Sketch

```text
dinoponera/
  core/
    models.py       # Pydantic data contracts and enums
    registry.py     # JSON index, node file persistence, dynamic loading
    graph.py        # graph representation and topological sorting helpers
    lint.py         # graph validation and missing-input grouping
    execution.py    # deterministic executor with runtime contract checks
    validation.py   # AST/static validation for generated Python functions

  agent/
    io.py           # UserInteractor protocol and ConsoleInteractor
    planning.py     # Phase 1 and Phase 2 loops; direct BAML calls
    authoring.py    # node clarification loop; direct BAML calls
    codegen.py      # generated-code pipeline; direct BAML calls
    review.py       # chain/code review helpers and display formatting

  integrations/
    __init__.py     # optional integration helpers if BAML tooling requires them
```

Runtime registry:

```text
registry/
  index.json
  nodes/
    example_node.py
```

Tests:

```text
tests/
  core/
    test_models.py
    test_registry.py
    test_graph_lint.py
    test_execution.py
    test_validation.py
  agent/
    test_io.py
    test_planning.py
    test_authoring.py
    test_codegen.py
    test_review.py
```

## File-by-File Implementation Plan

### `pyproject.toml`

- Existing.
- Purpose: project metadata and dependencies.
- Required changes:
  - Add Pydantic dependency.
  - Add pytest as test tooling/dev dependency.
  - Add BAML dependency and/or generated-client tooling only according to the BAML setup chosen by the implementation agent.
- Key dependencies:
  - Pydantic for models.
  - pytest for tests.
  - BAML tooling; exact package/config unknown from current repo.
- Tests:
  - Dependency installation should allow running the test suite.

### `dinoponera/core/__init__.py`

- New.
- Purpose: mark core package.
- Required changes: export stable core types only if useful; otherwise keep minimal.
- Tests: not directly required.

### `dinoponera/core/models.py`

- New.
- Purpose: all shared Pydantic models and enums.
- Required changes:
  - Define `NodeType`, `NodeSummary`, `NodeSpec`, `QA`, `StateSummary`.
  - Define BAML result models with discriminators.
  - Define graph/lint/execution/review decision models or import from dedicated modules if split later.
  - Provide JSON/dict parsing behavior compatible with registry `index.json`.
- Key types/functions/classes:
  - `NodeType`
  - `NodeSummary`
  - `NodeSpec`
  - `ExecutionPlan`
  - result union models
- Dependencies:
  - Pydantic.
  - Standard-library typing/enums.
- Tests:
  - `tests/core/test_models.py`.

### `dinoponera/core/registry.py`

- New.
- Purpose: persistent node registry.
- Required changes:
  - Initialize `index.json` and `nodes/` if missing.
  - Validate `node_id` as lowercase snake_case and require executable function names to match it.
  - Save approved executable code to `nodes/<node_id>.py` for `computation` and `data_retrieval` nodes.
  - Save `user_input` nodes as metadata-only registry entries with no Python file.
  - Write metadata to `index.json`.
  - Load summaries from index only.
  - Dynamically load indexed executable node functions.
  - Reject loading `user_input` nodes.
  - Reject unknown IDs and duplicate IDs.
- Key types/functions/classes:
  - `Registry`
  - `RegistryError` or specific exceptions
- Dependencies:
  - `NodeSpec`, `NodeSummary`.
  - `json`, `pathlib`, dynamic import or controlled `exec`.
- Tests:
  - `tests/core/test_registry.py` using temporary directories.

### `dinoponera/core/graph.py`

- New.
- Purpose: calculation graph representation and deterministic topological sorting.
- Required changes:
  - Represent graph node insertion order.
  - Build dependency edges from `reads`/`writes` metadata.
  - Produce `ExecutionPlan` after lint is clean.
  - Detect or expose cycles for linting.
- Key types/functions/classes:
  - `CalculationGraph`
  - `topological_sort`
- Dependencies:
  - `NodeSummary`, `ExecutionPlan`, registry summary access.
- Tests:
  - Included in `tests/core/test_graph_lint.py` or separate graph tests.

### `dinoponera/core/lint.py`

- New.
- Purpose: deterministic graph linting.
- Required changes:
  - Report unknown node IDs.
  - Group missing input keys by all consumer nodes.
  - Report duplicate producers for the same key.
  - Report cycles.
  - Return structured lint results suitable for user display and resolution.
- Key types/functions/classes:
  - `lint_graph`
  - `GraphLintResult`
  - `MissingInputIssue`
  - `DuplicateProducerIssue`
  - `CycleIssue`
- Dependencies:
  - `CalculationGraph`, registry summaries.
- Tests:
  - `tests/core/test_graph_lint.py`.

### `dinoponera/core/validation.py`

- New.
- Purpose: static validation for generated Python node functions.
- Required changes:
  - Parse generated code with `ast`.
  - Ensure exactly one top-level function named exactly `node_id`.
  - Ensure the function accepts exactly one parameter named `context`.
  - Ensure the function returns `context`.
  - Ensure declared reads/writes from `NodeSpec` are present.
  - Reject undeclared context reads/writes.
  - Reject syntax errors.
  - For the first implementation, allow only direct literal context-key access such as `context["key"]` for reads and writes.
  - Reject dynamic context keys, `context.get`, `context.update`, context aliases, deletion from context, loops over context, helper functions, classes, top-level executable statements other than the function definition, and imports.
  - Reject unsafe constructs such as file writes, subprocess calls, and network calls where detectable by AST checks.
- Key types/functions/classes:
  - `validate_generated_node_code(node_id: str, spec: NodeSpec, code: str) -> ValidationResult`
- Dependencies:
  - `ast`, `NodeSpec`.
- Tests:
  - `tests/core/test_validation.py`.

### `dinoponera/core/execution.py`

- New.
- Purpose: deterministic execution engine.
- Required changes:
  - Load each executable node from registry in `ExecutionPlan.execution_order`.
  - Handle `user_input` nodes by writing pre-collected values into context without dynamic loading and without prompting.
  - Before each executable node, verify declared reads exist in context.
  - Snapshot context keys before each executable node.
  - After each executable node, verify returned value is a dict.
  - Verify declared writes exist after execution.
  - Reject undeclared extra writes for the first implementation.
  - Reject deletion of existing context keys.
  - Reject overwriting existing context keys; declared writes must create new keys, except for `user_input` nodes writing their pre-collected values at their execution step.
  - Ensure execution performs no BAML calls and no direct user prompts.
- Key types/functions/classes:
  - `execute(plan: ExecutionPlan, registry: Registry, initial_context: dict | None = None, user_input_values: dict[str, dict[str, object]] | None = None) -> dict`
  - execution-specific exceptions
- Dependencies:
  - `Registry`, `ExecutionPlan`, `NodeSummary`.
- Tests:
  - `tests/core/test_execution.py`.

### `dinoponera/agent/__init__.py`

- New.
- Purpose: mark agent package.
- Required changes: minimal.
- Tests: not directly required.

### `dinoponera/agent/io.py`

- New.
- Purpose: user interaction protocol and console implementation.
- Required changes:
  - Define protocol/interface methods for clarification, approvals, applicability, missing dependency resolution, and code review.
  - Add `ConsoleInteractor` implementation.
  - Define response enums/models if not in `models.py`.
- Key types/functions/classes:
  - `UserInteractor`
  - `ConsoleInteractor`
- Dependencies:
  - Pydantic models and response enums.
- Tests:
  - `tests/agent/test_io.py` for response parsing/format behavior where practical.

### `dinoponera/agent/planning.py`

- New.
- Purpose: Phase 1 goal identification and Phase 2 graph-building orchestration.
- Required changes:
  - Directly call `baml_identify_goal` and `baml_extend_chain` using the BAML client generated/configured by the implementation.
  - Manage clarification loops.
  - Use `UserInteractor` for all user prompts and confirmations.
  - Invoke node authoring when terminal or dependency nodes are missing.
  - Build `CalculationGraph` rather than only a linear chain.
  - Run graph lint and dependency resolution before plan review.
- Key types/functions/classes:
  - `identify_goal_loop`
  - `build_graph_loop`
  - `plan_calculation`
- Dependencies:
  - BAML generated functions.
  - `Registry`, `CalculationGraph`, `lint_graph`, `topological_sort`, `UserInteractor`.
- Tests:
  - `tests/agent/test_planning.py` with mocked BAML calls and fake interactors.

### `dinoponera/agent/authoring.py`

- New.
- Purpose: missing-node authoring loop.
- Required changes:
  - Directly call `baml_clarify_node`.
  - Ask targeted clarification questions through `UserInteractor`.
  - Produce validated `NodeSpec`.
  - Enforce max nesting depth of one; authoring must not recursively trigger authoring.
  - Hand off to code generation pipeline.
- Key types/functions/classes:
  - `author_node`
- Dependencies:
  - BAML generated function.
  - `NodeSpec`, `StateSummary`, `UserInteractor`, codegen pipeline.
- Tests:
  - `tests/agent/test_authoring.py`.

### `dinoponera/agent/codegen.py`

- New.
- Purpose: generated-code pipeline.
- Required changes:
  - Directly call `baml_generate_code`.
  - Accept complete generated function code for `computation` and `data_retrieval` nodes.
  - Do not request generated Python code for `user_input` nodes; register them as metadata-only input collection nodes after approval.
  - Validate generated code using `core.validation`.
  - Retry generation on validation failure up to max 3 attempts.
  - Send validated code to user review gate.
  - Save only approved code to registry.
  - Support reject/re-describe path according to `UserInteractor` decision models.
- Key types/functions/classes:
  - `generate_and_register_node`
- Dependencies:
  - BAML generated function.
  - `Registry`, `validate_generated_node_code`, `UserInteractor`.
- Tests:
  - `tests/agent/test_codegen.py`.

### `dinoponera/agent/review.py`

- New.
- Purpose: display/format review information and coordinate approval decisions.
- Required changes:
  - Format graph and execution plan for final approval.
  - Format generated code review prompts if not kept entirely in `io.py`.
  - Represent full reset outcome.
- Key types/functions/classes:
  - `review_plan`
  - formatting helpers
- Dependencies:
  - `CalculationGraph`, `ExecutionPlan`, `UserInteractor`.
- Tests:
  - `tests/agent/test_review.py`.

### `dinoponera/integrations/__init__.py`

- New if needed.
- Purpose: namespace for optional integration helpers.
- Required changes:
  - Keep minimal.
  - Do not introduce a BAML adapter, because direct BAML calls were accepted.
- Tests:
  - Not required unless integration helpers are added.

### BAML project/config files

- New; exact paths unknown from current repository.
- Purpose: define BAML functions and schemas corresponding to the direct calls in agent modules.
- Required changes:
  - Add BAML definitions for:
    - `baml_identify_goal`
    - `baml_extend_chain`
    - `baml_clarify_node`
    - `baml_generate_code`
  - Configure each BAML function to use Claude Haiku 4.5.
  - Verify the exact BAML/Anthropic model identifier before committing the BAML config.
  - Keep prompts narrow and aligned with `calc_agent_design.md`.
  - Ensure BAML result schemas include discriminator fields that can be parsed into Pydantic models.
- Dependencies:
  - BAML tooling selected by implementation agent.
  - Anthropic/BAML provider configuration required for Claude Haiku 4.5.
- Tests:
  - Automated tests should mock generated BAML calls.
  - Live BAML validation is optional/manual unless project credentials/config are supplied; if run, it should verify Claude Haiku 4.5 configuration.

### `tests/core/test_models.py`

- New.
- Purpose: Pydantic model validation tests.
- Required tests:
  - valid `NodeSummary` and `NodeSpec`
  - invalid `node_type`
  - missing required fields
  - BAML result discriminator parsing
  - registry index entry parsing

### `tests/core/test_registry.py`

- New.
- Purpose: registry persistence/dynamic loading tests.
- Required tests:
  - empty registry initialization
  - save updates `index.json`
  - summaries read index only
  - node file without index entry is ignored
  - load indexed function and execute it
  - duplicate node ID rejected
  - unknown node ID rejected

### `tests/core/test_graph_lint.py`

- New.
- Purpose: graph/lint/topological sort tests.
- Required tests:
  - clean graph
  - shared missing input grouped by key with all consumers
  - duplicate producers rejected
  - cycles detected
  - unknown nodes detected
  - deterministic topological ordering

### `tests/core/test_validation.py`

- New.
- Purpose: generated-code static validation tests.
- Required tests:
  - valid generated function passes
  - syntax error fails
  - wrong function name/signature fails
  - missing declared read/write fails
  - undeclared context read/write fails
  - unsafe constructs rejected where implemented

### `tests/core/test_execution.py`

- New.
- Purpose: runtime execution contract tests.
- Required tests:
  - happy-path ordered execution
  - missing declared read fails clearly
  - non-dict return fails
  - missing declared write fails
  - undeclared extra write fails
  - deleted existing key fails
  - overwritten existing key fails
  - `user_input` nodes write pre-collected values without prompting
  - no BAML calls are needed for execution

### `tests/agent/test_planning.py`

- New.
- Purpose: planning orchestration tests.
- Required tests:
  - goal clarification loop
  - goal confirmation gate
  - terminal-node missing path invokes authoring
  - graph-building clear match path
  - applicability check path
  - dependency lint resolution path
  - full reset path
- Use mocked direct BAML functions and fake interactors.

### `tests/agent/test_authoring.py`

- New.
- Purpose: node authoring loop tests.
- Required tests:
  - clarification loop produces `NodeSpec`
  - max nesting depth enforced
  - generated spec handed to codegen

### `tests/agent/test_codegen.py`

- New.
- Purpose: code generation pipeline tests.
- Required tests:
  - validation failure retries up to 3 attempts
  - approval saves executable node code
  - `user_input` node registration saves metadata without generated code
  - rejection does not save node
  - invalid code never registers

### `tests/agent/test_review.py`

- New.
- Purpose: chain and code review behavior tests.
- Required tests:
  - graph/plan display includes shared dependencies
  - approve path returns approval decision
  - full reset path returns reset decision

## Testing Strategy

Use pytest.

Primary validation command after dependencies are installed:

```text
pytest
```

If the project adopts a tool such as `uv`, the equivalent command may be:

```text
uv run pytest
```

Because no test tooling currently exists in the repo, the implementation agent must update `pyproject.toml` consistently with the dependency-management approach it uses.

### Unit tests

Core deterministic modules must have unit tests for:

- Pydantic model validation.
- Registry persistence and dynamic loading.
- Graph linting and topological sorting.
- Generated-code static validation.
- Runtime execution contract checks.

### Integration-style tests

Agent modules should be tested with:

- mocked direct BAML calls
- fake `UserInteractor` implementations
- temporary registry directories

These tests should avoid live LLM calls.

### Regression tests

Add regression tests for high-risk behaviors:

- shared missing input is shown once with all consumers
- duplicate producers fail before execution
- generated code cannot register before review approval
- `user_input` nodes are metadata-only and never dynamically loaded
- execution rejects undeclared extra writes
- execution rejects deleted or overwritten existing context keys
- node files not present in `index.json` are invisible

### Fixtures

Recommended pytest fixtures:

- `tmp_registry_path`
- `registry`
- `sample_node_spec`
- `sample_node_summary`
- `fake_interactor`
- `mock_baml_identify_goal`
- `mock_baml_extend_chain`
- `mock_baml_clarify_node`
- `mock_baml_generate_code`

### Live BAML validation

Live BAML validation is optional/manual until the repository contains credentials/configuration and documented commands. Check the BAML tooling documentation and any generated project files added during implementation. If live validation is run, it should verify that the configured model is Claude Haiku 4.5 using the exact provider identifier supported by BAML/Anthropic.

## Migration / Backward Compatibility

Not applicable for existing application behavior because no calculation-agent implementation currently exists.

Compatibility constraints for the new system:

- Registry index format should be stable once introduced.
- Node files without `index.json` entries are ignored.
- Duplicate node IDs are rejected until a formal update/versioning flow is designed.
- Execution relies on registry metadata as the node contract.

## Risks and Mitigations

### Risk: BAML setup is unknown

- Why it matters: direct BAML imports require concrete generated-client paths and project configuration.
- Mitigation: keep direct BAML imports localized to `agent/planning.py`, `agent/authoring.py`, and `agent/codegen.py`; configure all BAML functions for Claude Haiku 4.5; verify the exact BAML/Anthropic model identifier during implementation; mock BAML calls in tests.
- Status: Accepted with assumptions.

### Risk: Generated complete functions can violate contracts

- Why it matters: BAML controls signature, reads, writes, and return behavior.
- Mitigation: strict AST/static validation plus mandatory engineer approval plus runtime contract checks.
- Status: Accepted.

### Risk: Dynamic node loading executes Python from disk

- Why it matters: unsafe code could run during execution.
- Mitigation: only load indexed nodes; only save after validation and approval; tests verify unindexed files are invisible.
- Status: Accepted.

### Risk: Graph model adds complexity

- Why it matters: graph linting/topological sorting is more complex than a linear list.
- Mitigation: keep execution linear; graph is only for planning/lint/review; test shared dependencies, cycles, and duplicate producers.
- Status: Accepted.

### Risk: Context keys are untyped strings

- Why it matters: key presence does not guarantee semantic/unit compatibility.
- Mitigation: runtime checks enforce key contracts now; typed/unit-aware context schemas are deferred future work.
- Status: Accepted with assumptions.

### Risk: No existing error/logging convention

- Why it matters: failures must still be understandable.
- Mitigation: define explicit exception classes per core module where needed; avoid adding logging framework unless implementation requires it.
- Status: Accepted with assumptions.

### Risk: User-input nodes could make execution interactive

- Why it matters: prompting during execution weakens deterministic execution and makes automated execution difficult.
- Mitigation: collect all `user_input` values after plan approval and before execution; execution receives pre-collected values and never prompts.
- Status: Accepted.

## Validation Checklist

Implementation checklist:

- [ ] `dinoponera/core/`, `dinoponera/agent/`, and optional `dinoponera/integrations/` packages exist.
- [ ] Pydantic models are implemented for all shared data contracts.
- [ ] `pyproject.toml` includes Pydantic, pytest, and required BAML tooling.
- [ ] Registry path is configurable and defaults to `registry/`.
- [ ] `node_id` values are lowercase snake_case Python identifiers.
- [ ] `Registry.summaries()` reads `index.json` only.
- [ ] Dynamic loading only loads indexed executable node files and rejects `user_input` nodes.
- [ ] Direct BAML calls are localized to agent modules.
- [ ] All BAML functions are configured to use Claude Haiku 4.5 with the verified BAML/Anthropic model identifier.
- [ ] User prompts go through `UserInteractor`, not direct `input()` in core logic.
- [ ] Graph lint groups shared missing inputs by key and all consumers.
- [ ] Duplicate producers and cycles fail before execution.
- [ ] Topological sort is deterministic.
- [ ] Generated code is statically validated before review.
- [ ] Generated code obeys the first-implementation AST constraints for direct literal context access and no imports/helpers/dynamic context access.
- [ ] Generated code is not saved without explicit approval.
- [ ] `user_input` values are collected before execution.
- [ ] Execution performs runtime contract checks for reads, writes, return type, undeclared extra writes, deleted keys, and overwritten existing keys.
- [ ] Automated tests use mocked BAML calls, fake interactors, and temporary registries.
- [ ] `pytest` passes.

Implementability checks against current repo:

- Existing `calc_agent_design.md` exists and supports this design.
- Existing `pyproject.toml` exists and is the correct place for dependencies.
- Existing `dinoponera/` directory exists and can contain the proposed packages.
- Existing `tests/` directory exists and can contain the proposed pytest layout.
- Proposed source files are all new except `pyproject.toml`.
- No existing source module needs migration.
- `main.py` is intentionally not referenced.

## Open Questions

### Exact BAML setup

Unknown: the repository does not currently contain BAML files, generated clients, dependency declarations, or validation commands. The model choice is decided: use Claude Haiku 4.5 for all BAML functions. The exact BAML/Anthropic model identifier must still be verified during implementation.

Why it matters: direct BAML calls require concrete imports, generated schema conventions, provider credentials, and the correct model identifier.

Conservative default: implementation agent should introduce BAML according to the BAML tooling it selects, configure all BAML functions for Claude Haiku 4.5, keep direct imports localized to agent modules, and mock calls in tests.

Status: Accepted with assumptions.

### Conditional execution

Unknown/deferred: how to represent branches such as “if data exists, fetch it; otherwise ask user.”

Why it matters: some engineering workflows are conditional at runtime.

Conservative default: do not support conditional graph execution in the first implementation; encapsulate such logic inside a single approved node only if necessary.

Status: Deferred.

### Typed and unit-aware context values

Unknown/deferred: no canonical `CalcContext` key vocabulary, value schemas, or unit system exists.

Why it matters: engineering calculations require semantic and unit correctness, not just key presence.

Conservative default: enforce declared key presence/writes now; defer type/unit schemas.

Status: Deferred.

### Node update/versioning flow

Unknown/deferred: how to correct or replace a previously registered node.

Why it matters: engineering methods may be corrected or improved over time.

Conservative default: reject duplicate node IDs and require a future explicit update/versioning design.

Status: Deferred.

### Registry scaling

Unknown/deferred: how planner selection behaves once the registry has many nodes.

Why it matters: dumping a large `index.json` into prompts may degrade selection quality.

Conservative default: pass full summaries initially; add prefiltering later if registry size requires it.

Status: Deferred.

### Report generation

Unknown/deferred: final calculation report format is undefined.

Why it matters: auditability likely requires more than a final context dictionary.

Conservative default: return final `CalcContext` in the first implementation and defer report formatting.

Status: Deferred.

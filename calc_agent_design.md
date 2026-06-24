# Calculation Agent — Architecture Design Document

## Overview

A Python + BAML system that allows a civil engineer to describe a calculation problem in natural language and receive a fully auditable, deterministic calculation graph.

**Step 1 — Planning.** The planner works against a hand-authored registry of nodes. Through a structured dialogue with the user it produces an approved, lint-clean calculation graph serialized to disk. No execution happens. If a required node is missing, the system surfaces an error and asks the engineer to add it to the registry manually before restarting.

**Step 2 — Execution.** Takes the approved graph from Step 1 and generates a concrete, self-contained Python script. Independently runnable, version-controllable, and human-readable.

**Post-MVP — Node authoring.** The system gains the ability to create new nodes and domain types through a structured LLM dialogue during a planning session. The registry grows organically rather than requiring manual authoring.

---

## Design Principles

**Planning before execution.** The full calculation graph is resolved and user-confirmed before a single number is computed. No LLM calls happen during execution.

**Clarification at the point of ambiguity.** Questions are asked when a specific ambiguity is encountered in the planning process, not upfront as a bulk questionnaire.

**Narrow LLM functions.** Each BAML function has one clearly scoped job. Goal identification and graph building are separate functions with separate prompts.

**Python-native everything.** Nodes are typed Python functions. Types are Pydantic BaseModel subclasses. The registry is a Python module. No separate type vocabulary, no JSON spec files, no string-key matching.

**All domain types are Pydantic BaseModel subclasses.** Every input and output type used by a node must be a Pydantic BaseModel. Raw primitives as I/O types are discouraged — they carry no semantic meaning.

**Single output per node.** Each node produces exactly one output type. Nodes with naturally broad outputs are split into focused single-responsibility nodes that share a common upstream input.

**Type-first matching.** Node connections are resolved by Python type — an upstream node's return type must match a downstream node's parameter type. Description and when_to_use guide selection within a type-matched candidate pool. Types are serialized as full import path strings (e.g. `myproject.calc_types.soil_profile.SoilProfile`).

**Bounded prompt growth.** A compact `StateSummary` is rewritten as part of each BAML output rather than appending raw history.

**The registry is the backbone.** All agent loops share a single registry. For Step 1 it is hand-authored. Post-MVP it grows organically during planning sessions.

**Local data assumption.** All data retrieval nodes assume data is available locally. No runtime configuration of data sources is required.

---
---

# Step 1 — Planning

---

## System Overview

```
User (natural language problem description)
  │
  ▼
Phase 1 — Goal identification loop
  │  identifies terminal node, confirms goal with user
  │  if terminal node missing → surface error, ask engineer to add manually
  ▼
Phase 2 — Graph building loop
  │  works backward from terminal node
  │  Python pre-computes next unresolved input (breadth-first)
  │  BAML resolves one gap per iteration, rewrites StateSummary in same call
  │  if no candidate exists → surface error, ask engineer to add node manually
  ▼
Dependency lint (Python)
  │  checks every node input has exactly one incoming edge
  │  checks graph is acyclic
  │  user resolves remaining gaps (data_retrieval or user_input leaf nodes only)
  ▼
Graph review + approval
  │  engineer sees complete lint-clean graph in text form
  │  Approve / Full reset
  ▼
Approved graph serialized to disk (JSON)
  └─ handed off to Step 2
```

---

## Project Structure

```
project/
  calc_types/
    soil_profile.py             # SoilProfile(BaseModel)
    compressibility_params.py
    settlement_result.py
    ...
  registry/
    index.py                    # source of truth — imports all node functions
    nodes/
      schmertmann_settlement.py
      cpt_soil_profile.py
      soil_profile_editor.py
      ...
  graphs/
    settlement_analysis.json    # approved serialized CalculationGraph
```

`calc_types/` contains all domain Pydantic models, hand-authored for Step 1. `registry/index.py` is the source of truth for nodes. `graphs/` stores approved serialized graphs — the output of Step 1 and the input to Step 2.

---

## Shared Data Types

```
NodeSummary                        # built dynamically by introspecting the node function
  id:           str                # function name, unique
  node_type:    str                # computation | data_retrieval | user_input
  description:  str                # what the node does
  when_to_use:  str                # when to prefer this node over alternatives
  assumptions:  list[str]          # key preconditions in plain language
  inputs:       list[str]          # full import paths of input types
  output:       str                # full import path of output type
  references:   list[str]

UnresolvedInput                    # pre-computed by Python, passed into baml_extend_graph
  node_id:      str                # which node has the unresolved input
  input_type:   str                # full import path of the required type

Edge(BaseModel)
  from_node:    str                # node id
  to_node:      str                # node id
  type:         str                # full import path of the type flowing along this edge

CalculationGraph(BaseModel)        # persisted via model_dump_json() / model_validate_json()
  name:               str          # snake_case, filename-safe
  terminal_node_id:   str          # sink node — return type of the execution script
  nodes:              list[str]    # node ids
  edges:              list[Edge]

  def has_edge(self, to: str, type: str) -> bool:
      return any(e.to_node == to and e.type == type for e in self.edges)

QA                                 # one clarification exchange
  question:     str
  answer:       str

StateSummary                       # compact running context, rewritten each BAML call
  goal:                         str
  decisions:                    list[str]   # e.g. "CPT-based profile, Schmertmann method"
  open_items:                   list[str]   # still unresolved
  phase1_clarification_summary: str         # condensed Phase 1 QA, carried into Phase 2
```

`Edge` and `CalculationGraph` are Pydantic `BaseModel` subclasses. Serialization and deserialization use `model.model_dump_json()` and `CalculationGraph.model_validate_json()` respectively. All fields are strings or lists of strings — no live Python type objects — so no custom serializer is needed.

---

## Phase 1 — Goal Identification Loop

**Purpose.** Understand what the engineer is trying to compute and identify the terminal node. Open-ended semantic reasoning about intent — the terminal node is the output of this phase, not an input to it.

**BAML function:** `baml_identify_goal`

```
Input
  problem:          str
  registry:         list[NodeSummary]
  clarifications:   list[QA]

Output (union)
  GoalClear
    calculation_type:     str
    terminal_node_id:     str | None    # None if terminal node missing from registry
    missing_description:  str | None    # populated if terminal_node_id is None
    state_summary:        StateSummary  # baml_identify_goal populates
                                        # state_summary.phase1_clarification_summary
                                        # as condensed prose of all Phase 1 QA exchanges

  NeedsClarification
    question:   str
    context:    str                     # why this is blocking goal identification
```

**Loop behaviour.**

```
while not goal_clear:
    result = baml_identify_goal(problem, registry, clarifications)

    if NeedsClarification:
        answer = ask_user(result.question)
        clarifications.append(QA(result.question, answer))
        # loop continues — baml_identify_goal called again with updated clarifications

    else:  # GoalClear
        if result.terminal_node_id is None:
            raise MissingNodeError(
                f"No node found for: {result.missing_description}. "
                f"Please add it to the registry manually and restart."
            )
        else:
            goal = result
            break
```

**User confirmation.** Before Phase 2 starts, the resolved `GoalClear` is shown to the user for explicit confirmation. Prevents Phase 2 from building on a misclassified goal.

**Phase 1 → Phase 2 handoff.** The `StateSummary` from Phase 1 includes `phase1_clarification_summary` — compact prose of all Phase 1 QA exchanges, carried into Phase 2 as initial context.

**Name normalisation.** `CalculationGraph.name` is derived from `goal.calculation_type` via:

```python
import re
def normalise_name(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')

# "Settlement Analysis"               → "settlement_analysis"
# "CPT-based settlement (Schmertmann)"→ "cpt_based_settlement_schmertmann"
```

Used for both `graph.name` and the `graphs/{name}.json` filename.

---

## Phase 2 — Graph Building Loop

**Purpose.** Starting from the terminal node, resolve all input dependencies by building a directed acyclic graph. Python pre-computes the next unresolved input (breadth-first) and passes it to BAML. BAML resolves that one gap and rewrites the `StateSummary` in the same call. Python checks completeness after each step and loops.

**BAML function:** `baml_extend_graph`

```
Input
  current_unresolved:   UnresolvedInput     # pre-computed by Python (breadth-first)
  state_summary:        StateSummary        # running context from Phase 1 + prior steps
  graph:                CalculationGraph
  registry:             list[NodeSummary]
  clarifications:       list[QA]

Output (union)
  ConnectExisting
    from_node_id:          str              # already in graph, produces required type
    rationale:             str
    updated_state_summary: StateSummary     # rewritten in same call

  AddFromRegistry
    node_id:               str              # node to add from registry
    rationale:             str
    updated_state_summary: StateSummary     # rewritten in same call

  ApplicabilityCheck
    candidates:            list[NodeSummary]   # all produce required type
    question:              str                 # specific to candidate ambiguity

  NoCandidate
    needed_description:    str
```

**Initialization.**

```
graph = CalculationGraph(
    name=normalise_name(goal.calculation_type),   # snake_case, filename-safe
    terminal_node_id=goal.terminal_node_id,
    nodes=[goal.terminal_node_id],
    edges=[]
)
state_summary = goal.state_summary     # handed off from Phase 1
clarifications = []
```

**Loop behaviour.**

```
while True:
    unresolved = BreadthFirstTraversal().next_unresolved(graph, registry)
    if unresolved is None:
        break    # all inputs satisfied — hand off to lint

    filtered_summaries = [
        s for s in registry_summaries
        if s.output == unresolved.input_type
    ]
    result = baml_extend_graph(unresolved, state_summary, graph, filtered_summaries, clarifications)

    if ConnectExisting:
        graph.edges.append(Edge(result.from_node_id, unresolved.node_id, unresolved.input_type))
        state_summary = result.updated_state_summary

    if AddFromRegistry:
        graph.nodes.append(result.node_id)
        graph.edges.append(Edge(result.node_id, unresolved.node_id, unresolved.input_type))
        state_summary = result.updated_state_summary

    if ApplicabilityCheck:
        response = ask_user(result.question, result.candidates)
        # Step 1: candidates list only — no CreateNew option
        # if user rejects all candidates → MissingNodeError raised on next iteration

        if node chosen:
            graph.nodes.append(chosen_node_id)
            graph.edges.append(Edge(chosen_node_id, unresolved.node_id, unresolved.input_type))

        if all rejected:
            raise MissingNodeError(
                f"No applicable node found for: {unresolved.input_type}. "
                f"Please add a suitable node to the registry manually and restart."
            )

        if Unsure:
            clarifications.append(QA(result.question, response.detail))

    if NoCandidate:
        raise MissingNodeError(
            f"No node found that produces: {unresolved.input_type}. "
            f"Needed by: {unresolved.node_id}. "
            f"Please add a suitable node to the registry manually and restart."
        )

lint(graph, registry, BreadthFirstTraversal(), state_summary)
```

**Candidate resolution.** At each step the planner receives three candidate pools for the required input type, filtered by full import path match, then disambiguated by `description` and `when_to_use`:

```
Required input type: myproject.calc_types.soil_profile.SoilProfile

Already in graph:
  B  cpt_soil_profile     "Interprets CPT data into a layered soil profile"
                           when_to_use: "Use when CPT data is available"

Available in registry:
  borehole_soil_profile   "Builds soil profile from borehole log descriptions"
                           when_to_use: "Use when only borehole logs are available"
  soil_profile_editor     "Modifies existing profile — exclude or insert layers"
                           when_to_use: "Use when the raw profile needs adjustment"
```

**Transformer nodes.** Some nodes take a type as input and produce the same type as output (e.g. `soil_profile_editor`: `SoilProfile → SoilProfile`). Selecting one opens a new dependency branch for its own input, handled as a normal unresolved input on the next iteration.

**Leaf node termination.** Nodes with `node_type` of `data_retrieval` or `user_input` have no upstream inputs. `BreadthFirstTraversal` skips them.

---

## The Registry

The registry is a Python module. Node functions are imported directly. `NodeSummary` objects are built at runtime by introspecting each function's signature and decorator metadata.

**`@node` decorator.**

```python
from dataclasses import dataclass, field

@dataclass
class NodeMetadata:
    node_type:    str
    description:  str
    when_to_use:  str
    assumptions:  list[str] = field(default_factory=list)
    references:   list[str] = field(default_factory=list)

def node(**kwargs):
    def decorator(fn):
        fn._node_metadata = NodeMetadata(**kwargs)
        return fn
    return decorator
```

`build_summary` reads `fn._node_metadata` directly. No magic — just a plain attribute set on the function object.

---

**index.py**

```python
from registry.nodes.schmertmann_settlement import schmertmann_settlement
from registry.nodes.cpt_soil_profile import cpt_soil_profile
from registry.nodes.soil_profile_editor import soil_profile_editor

NODES = [
    schmertmann_settlement,
    cpt_soil_profile,
    soil_profile_editor,
]
```

**NodeSummary from introspection.**

```python
def build_summary(fn) -> NodeSummary:
    sig = inspect.signature(fn)
    meta = fn._node_metadata
    return NodeSummary(
        id=fn.__name__,
        node_type=meta.node_type,
        description=meta.description,
        when_to_use=meta.when_to_use,
        assumptions=meta.assumptions,
        inputs=[
            f"{p.annotation.__module__}.{p.annotation.__qualname__}"
            for p in sig.parameters.values()
        ],
        output=f"{sig.return_annotation.__module__}.{sig.return_annotation.__qualname__}",
        references=meta.references
    )
```

**Registry functions.**

```python
def summaries() -> list[NodeSummary]:
    return [build_summary(fn) for fn in NODES]

def get(node_id: str) -> callable:
    return next(fn for fn in NODES if fn.__name__ == node_id)

def get_summary(node_id: str) -> NodeSummary:
    return build_summary(get(node_id))

def exists(node_id: str) -> bool:
    return any(fn.__name__ == node_id for fn in NODES)
```

---

## Dependency Lint

Pure Python. Runs after Phase 2 completes. Checks that the graph is acyclic and that every non-leaf node input has exactly one incoming edge. Remaining gaps are resolved one by one. For Step 1, only leaf node options are offered — new computation nodes cannot be created mid-lint.

```python
def lint(graph, registry, traversal: DependencyTraversal, state_summary: StateSummary):
    # 1. Cycle detection — standard DFS; can delegate to networkx.is_directed_acyclic_graph()
    if has_cycle(graph):
        raise CyclicGraphError("Graph contains a cycle — full reset required")

    # 2. Unsatisfied inputs — resolve one by one
    registry_summaries = registry.summaries()
    while gap := traversal.next_unresolved(graph, registry_summaries):
        node_id = resolve_with_user(gap, state_summary)
        graph.nodes.append(node_id)
        graph.edges.append(Edge(node_id, gap.node_id, gap.input_type))
        registry_summaries = registry.summaries()  # refresh after dynamic registration
```

`registry_summaries` is refreshed after each stub registration. Without this, the traversal would fail to find the newly registered stub in the stale list on the next iteration.

**Traversal protocol.** Allows the algorithm to be swapped without touching the lint runner or Phase 2 loop.

```python
class DependencyTraversal(Protocol):
    def next_unresolved(
        self,
        graph: CalculationGraph,
        registry: list[NodeSummary]
    ) -> UnresolvedInput | None: ...

class BreadthFirstTraversal:
    def next_unresolved(self, graph, registry):
        for node_id in graph.nodes:
            summary = next(s for s in registry if s.id == node_id)  # registry is list[NodeSummary]
            if summary.node_type in ("data_retrieval", "user_input"):
                continue
            for input_type in summary.inputs:
                if not graph.has_edge(to=node_id, type=input_type):
                    return UnresolvedInput(node_id=node_id, input_type=input_type)
        return None
```

**resolve_with_user — Step 1.** Presents two leaf node options. On selection, generates a typed stub function and registers it immediately — no LLM, no dialogue. The stub has the correct return type annotation so the graph remains type-coherent. The function body raises `NotImplementedError`, signalling to the engineer that it must be implemented before the execution script can run.

```
Unresolved: myproject.calc_types.soil_profile.SoilProfile
  needed by: D  schmertmann_settlement

Options:
  1. Fetch from external source   → generates data_retrieval stub
  2. Ask me at runtime            → generates user_input stub
```

**Stub generation.** `create_leaf_stub` is a pure Python function — approximately 20 lines of string templating. It derives the node id deterministically from the node_type prefix and output type name, writes the stub to `registry/nodes/`, and adds the import to `registry/index.py`. No review gate for Step 1.

**Node id naming rule.**

```
node_type prefix:
  data_retrieval → "reader"
  user_input     → "prompt"

node_id = "{prefix}_{snake_case_type_name}"

# examples
reader_soil_profile
prompt_soil_profile

# collision (same type + same node_type already registered): append counter
reader_soil_profile_2
```

```python
def create_leaf_stub(node_type: str, output_type_path: str) -> str:
    # derives node_id using naming rule above
    # increments counter suffix until id is unique in registry
    # writes:
    #
    # @node(
    #     node_type="data_retrieval",
    #     description="Auto-generated stub — replace with real implementation",
    #     when_to_use="Placeholder"
    # )
    # def reader_soil_profile() -> SoilProfile:
    #     raise NotImplementedError("Stub — implement before running")
    #
    # 1. writes .py file to registry/nodes/{node_id}.py
    # 2. appends import to registry/index.py (persistence for future sessions)
    # 3. loads new module via importlib.import_module, appends function to
    #    in-memory NODES list — stub available immediately, no module reload needed
    # 4. returns node_id
```

Post-MVP, `resolve_with_user` replaces `create_leaf_stub` with a full `node_authoring_loop` call for the "new_computation" option, and optionally for the leaf options as well.

---

## Graph Review and Approval

After lint is clean, the engineer sees the complete graph before approval.

```
Calculation graph:

  A  cpt_file_reader         [data_retrieval]  → CptRawData
  B  cpt_soil_profile        [computation]     → SoilProfile
  C  schmertmann_params      [computation]     → CompressibilityParams
  D  schmertmann_settlement  [computation]     → SettlementResult

Connections:

  A      → B  (CptRawData)
  B      → C  (SoilProfile)
  B+C    → D  (SoilProfile, CompressibilityParams)

  [ Approve ]   [ Full reset ]
```

On approval, `CalculationGraph` is serialized to `graphs/{name}.json`. Full reset discards the entire plan and restarts Phase 1.

---

## Implementation Milestones

Step 1 is built in five sequential milestones. Each has a clear input, a testable output, and no dependency on milestones that follow it.

**M1 — Foundation**
Pure Python, no LLM. `NodeMetadata`, `@node` decorator, `build_summary`, all registry functions, all shared data types (`CalculationGraph`, `Edge`, `NodeSummary`, `UnresolvedInput`, `StateSummary`, `QA`), `BreadthFirstTraversal`, `normalise_name`, `has_edge`, graph text renderer. Testable: construct a graph manually, run the traversal, verify correct unresolved inputs are returned in breadth-first order.

Note: `@node` decorator design is load-bearing — all downstream milestones depend on it. Finalise it in M1 before proceeding.

**M2 — Phase 1**
`baml_identify_goal` + Phase 1 loop. Phase 2 is stubbed — print the goal and stop. First LLM integration. Testable: does the planner correctly identify the goal and ask sensible clarifying questions against a real registry?

**M3 — Phase 2 happy path**
`baml_extend_graph` with `ConnectExisting` and `AddFromRegistry` outputs only. `NoCandidate` raises `MissingNodeError`. If BAML returns `ApplicabilityCheck`, raise `NotImplementedError('ApplicabilityCheck not handled until M4')` — fails loudly rather than silently. First full end-to-end: problem → approved graph (in memory, no serialization yet).

Constraint: the test registry for M3 must have exactly one node per output type to avoid triggering `ApplicabilityCheck` before M4. Design the test registry deliberately.

**M4 — Phase 2 full**
Add `ApplicabilityCheck` handling. The planner can now ask the user to choose between candidates. Test registry gains multiple nodes per output type. No structural changes to M3 code — purely additive.

**M5 — Lint + leaf stubs + approval + serialization**
`lint()`, `has_cycle()`, `create_leaf_stub()`, `resolve_with_user()`, graph review display, approve/reset flow, `model_dump_json()` serialization to `graphs/`. Complete Step 1.

```
M1  Foundation + BreadthFirstTraversal    pure Python, testable immediately
M2  Phase 1                               first BAML call
M3  Phase 2 happy path                    first full end-to-end loop
M4  Phase 2 full (ApplicabilityCheck)     additive extension
M5  Lint + stubs + approval + serialize   completes Step 1
```

---

## BAML Function Summary

| Function | Called by | Job |
|---|---|---|
| `baml_identify_goal` | Phase 1 loop | Classify goal, identify terminal node |
| `baml_extend_graph` | Phase 2 loop | Resolve one unresolved input, rewrite StateSummary |

---

## LLM vs Python Responsibilities

| LLM (BAML) | Python |
|---|---|
| Goal classification | Registry introspection and loading |
| Node selection by description | Type-based candidate prefiltering |
| Applicability assessment | Next unresolved input (breadth-first) |
| Clarifying questions | Registry pre-filter by output type |
| StateSummary rewriting | Completeness check after each step |
| | Cycle detection |
| | Dependency lint |
| | Leaf stub generation (create_leaf_stub) |
| | Graph serialization |

---

## Open Questions — Step 1

- **Conditional execution.** Some nodes depend on runtime results to decide which path to take. The DAG model cannot represent this. Deferred.
- **Registry scaling.** At large node counts a full registry dump to the planner may degrade selection quality. A type-based prefilter can narrow candidates before passing to BAML. Deferred until registry size makes it necessary.
- **Step reset.** Full reset is the only recovery option. A step reset requires storing graph state step by step. Deferred.
- **Multiple terminal nodes.** A planning session produces one terminal output. Running two independent calculations in one session is not supported. Deferred.

---
---

# Step 2 — Execution

---

## System Overview

```
Approved graph loaded from graphs/{name}.json
  │
  ▼
Execution script generation (Python)
  │  topological sort
  │  resolve imports from full type paths in graph edges
  │  generate concrete Python script
  │  no LLM calls
  ▼
runs/{name}.py
  │
  ▼
Engineer runs script independently
```

Step 2 is entirely self-contained. It requires only the serialized graph and the registry — no planning state, no BAML, no user interaction.

---

## Project Structure Additions

```
project/
  runs/
    run_settlement_analysis.py    # generated execution script
```

---

## Execution Script Generation

Python loads the approved `CalculationGraph` from `graphs/`, performs a topological sort, resolves all imports from the full type paths stored in each edge, and generates a self-contained script.

**Why topological sort gives the correct execution order.**

Even though Phase 2 builds the graph backward from the terminal node, edges are always stored in the forward direction — `Edge.from_node` is the producer, `Edge.to_node` is the consumer. This convention is established at every graph mutation in Phase 2:

```python
graph.edges.append(Edge(
    from_node  = producer_node_id,   # always the upstream node
    to_node    = unresolved.node_id, # always the downstream node needing input
    type       = unresolved.input_type
))
```

As a result:
- Leaf source nodes (`data_retrieval`, `user_input`) have in-degree 0 — no incoming edges — and sort to the front
- The terminal node has the highest in-degree — it depends on everything — and sorts to the end
- Topological sort over this forward-edge graph directly gives the correct execution order with no transformation needed

The backward construction during planning and the forward execution during Step 2 are two views of the same edge set. No graph inversion is required.

**Generated script example.**

```python
# runs/run_settlement_analysis.py
# Generated from approved calculation graph — do not edit manually

from myproject.calc_types.cpt_raw_data import CptRawData
from myproject.calc_types.soil_profile import SoilProfile
from myproject.calc_types.compressibility_params import CompressibilityParams
from myproject.calc_types.settlement_result import SettlementResult
from registry.nodes.cpt_file_reader import cpt_file_reader
from registry.nodes.cpt_soil_profile import cpt_soil_profile
from registry.nodes.schmertmann_params import schmertmann_params
from registry.nodes.schmertmann_settlement import schmertmann_settlement

def run() -> SettlementResult:
    cpt_raw_data: CptRawData           = cpt_file_reader()
    soil_profile: SoilProfile          = cpt_soil_profile(cpt_raw_data)
    params: CompressibilityParams      = schmertmann_params(soil_profile)
    return schmertmann_settlement(soil_profile, params)

if __name__ == "__main__":
    result = run()
    print(result)
```

The script is human-readable, version-controllable, and independently executable without the planning system. It serves as both the execution artifact and the primary audit trail.

**Implementation notes.**
- Import statements are derived entirely from node ids and the full import path strings in `NodeSummary`. No dynamic dispatch required.
- Variable names are derived from the output type name in snake_case (e.g. `SoilProfile` → `soil_profile`). On collision (same type produced by two nodes), suffix with the node id:

```python
# single producer of SoilProfile
soil_profile = cpt_soil_profile(cpt_raw_data)

# two producers of SoilProfile — suffix with node id
soil_profile_cpt_soil_profile  = cpt_soil_profile(cpt_raw_data)
soil_profile_borehole_profile  = borehole_soil_profile(borehole_data)
```

Downstream nodes use the variable resolved by following the graph edge for the required type.
- Call order follows topological sort order of the graph.
- The terminal node's output type is read from `graph.terminal_node_id` to generate the `run()` return annotation and final return statement.

---

## Open Questions — Step 2

- **Report generation.** The execution script prints the terminal result. A structured calculation report format is undefined. Deferred.
- **Iterative calculations.** Workflows requiring iteration do not fit the DAG model. Deferred.

---
---

# Post-MVP — Node Authoring

Node authoring extends the planning system (Step 1) to create new nodes and domain types through a structured LLM dialogue when no suitable node exists in the registry. Planning resumes after the new node is registered. The registry grows organically over time.

---

## Revised System Overview

```
Phase 1 — Goal identification loop
  │  if terminal node missing → triggers node authoring loop
  ▼
Phase 2 — Graph building loop
  │  if no candidate exists → triggers node authoring loop
  ▼
Dependency lint
  │  resolve_with_user gains a third option: create new computation node
  │  all three options route through node_authoring_loop
  ▼
Graph review + approval
  ▼
Approved graph serialized to disk
```

---

## Integration Points

**Phase 1.** Replace `MissingNodeError` with:

```python
if result.terminal_node_id is None:
    node_authoring_loop(result.missing_description, result.state_summary)
    # registers internally before returning
    # loop continues — terminal node now in registry
```

**Phase 2.** Replace `MissingNodeError` with:

```python
if NoCandidate:
    node_authoring_loop(result.needed_description, state_summary)
    # registers internally before returning
    # loop continues — same unresolved input retried
    # refresh registry_summaries after registration:
    registry_summaries = registry.summaries()
    filtered_summaries = [
        s for s in registry_summaries
        if s.output == unresolved.input_type
    ]
```

**Lint.** `resolve_with_user` gains a third option and replaces `create_leaf_stub` with `node_authoring_loop` for all three options, passing a `node_type_hint`:

```python
def resolve_with_user(gap: UnresolvedInput, state_summary: StateSummary) -> str:
    choice = ask_user(gap, options=["data_retrieval", "user_input", "new_computation"])
    intent_map = {
        "data_retrieval":  f"retrieve {gap.input_type} from a local source",
        "user_input":      f"ask the user to provide {gap.input_type}",
        "new_computation": f"compute {gap.input_type}",
    }
    return node_authoring_loop(
        intent=intent_map[choice],
        node_type_hint=choice,
        context=state_summary
    )
```

`node_type_hint` pre-fills the node type in `NodeDefinition`, removing one clarification round.

---

## Node Authoring Loop

**Nesting constraint.** Node authoring must not itself trigger node authoring. Max nesting depth: one.

**BAML function:** `baml_clarify_node`

```
Input
  intent:           str
  planning_context: StateSummary
  node_type_hint:   str | None
  clarifications:   list[QA]

Output (union)
  NodeDefinition
    name:               str
    node_type:          str            # computation | data_retrieval | user_input
    description:        str
    when_to_use:        str
    assumptions:        list[str]
    inputs:             list[str]      # full import paths
    output:             str            # full import path
    logic_description:  str
    references:         list[str]

  NeedsClarification
    question:   str
    context:    str
```

**Loop behaviour.**

```
while not definition_complete:
    result = baml_clarify_node(intent, planning_context, node_type_hint, clarifications)
    if NeedsClarification:
        answer = ask_user(result.question)
        clarifications.append(QA(result.question, answer))
    else:
        definition = result
        break

type_assessment(definition)
node_id = code_generation_pipeline(definition)
return node_id
```

---

## Type Assessment Step

Python attempts to import each type in `definition.inputs` and `definition.output` via `importlib.import_module`. Types that resolve (from `calc_types/` or installed packages) are accepted. For each unresolvable type, `baml_generate_type` is called.

**BAML function:** `baml_generate_type`

```
Input
  type_name:    str         # intended class name
  description:  str         # what it represents
  context:      str         # why this type is needed
  known_types:  list[str]   # full import paths already available

Output
  TypeDefinition
    class_name:   str        # PascalCase
    file_name:    str        # snake_case → calc_types/{file_name}.py
    source_code:  str        # complete Pydantic BaseModel definition
```

Each generated type has its own user review gate before being written to `calc_types/`.

**Constraints.**
- All generated types must subclass Pydantic `BaseModel`.
- Field types must be primitives, installed package types, or existing `calc_types/` types.
- File names: snake_case. Class names: PascalCase.
- A type already importable from any source must not be regenerated.

---

## Code Generation Pipeline

```
NodeDefinition (all types confirmed importable)
  │
  ▼
baml_generate_code
  │  generates internal logic only
  │  signature, decorator, type hints injected from NodeDefinition
  ▼
Static validation (Python)
  │  syntax check, parameter/return types match NodeDefinition
  │  auto-retry up to 3 times on failure
  ▼
Dependency check (Python)
  │  importlib.util.find_spec for each import
  │  prompt user to pip install if missing
  ▼
User review gate
  │  Approve / Edit / Reject and re-describe
  ▼
Registration
  │  collision check — prompt user to rename if node id exists
  │  write registry/nodes/{name}.py
  │  add import to registry/index.py
  ▼
return node_id
```

**Generated function structure.**

```python
@node(
    node_type="computation",
    description="{description}",
    when_to_use="{when_to_use}",
    assumptions={assumptions},
    references={references}
)
def {name}({param}: {InputType}, ...) -> {OutputType}:
    """
    {logic_description}
    """
    {generated_logic}
```

---

## BAML Function Summary — Post-MVP Additions

| Function | Called by | Job |
|---|---|---|
| `baml_clarify_node` | Node authoring loop | Specify a new node through dialogue |
| `baml_generate_type` | Type assessment step | Generate a Pydantic BaseModel definition |
| `baml_generate_code` | Code generation pipeline | Generate Python implementation |

---

## LLM vs Python — Post-MVP Additions

| LLM (BAML) | Python |
|---|---|
| NodeDefinition authoring | Type importability check |
| Pydantic type generation | Static code validation |
| Node code generation | Dependency installation check |
| | Node id collision check |

---

## Design Decisions and Constraints

All of these must be respected during implementation:

- All domain types are Pydantic `BaseModel` subclasses — no dataclasses, no plain dicts.
- Types from external packages are valid I/O types without needing to be in `calc_types/`.
- `calc_types/` file names are snake_case. Class names are PascalCase.
- Node authoring cannot trigger another node authoring — max nesting depth: one.
- User review gate applies separately to generated types and generated node code.
- `node_type_hint` pre-fills node type when called from `resolve_with_user`.
- Static validation retries automatically up to 3 times before surfacing to the engineer.
- Node id collision prompts the engineer to rename — no auto-suffixing.
- Planning context (`StateSummary`) is always passed into the authoring loop.

---

## Post-MVP Open Questions

- **Node updates.** When a node's implementation is corrected, impact on existing serialized graphs and generated scripts needs a defined process.
- **Type updates.** When a Pydantic model gains or loses fields, downstream nodes may break. Migration strategy undefined.
- **Authoring quality.** Generated nodes that pass static validation and review may still be numerically incorrect. A test harness against known input/output pairs would strengthen confidence before registration.

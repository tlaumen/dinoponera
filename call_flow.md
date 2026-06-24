# Calculation Agent — Complete Call Flow

```
SHARED STATE (available throughout)
══════════════════════════════════════════════════════════════
registry module
  NODES: list[callable]                 # hand-authored node functions
  summaries() → list[NodeSummary]       # built by introspection
  get(node_id) → callable
  get_summary(node_id) → NodeSummary
  exists(node_id) → bool
══════════════════════════════════════════════════════════════


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — PLANNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ENTRY]
  user_input: str
  registry_summaries = registry.summaries()  →  list[NodeSummary]
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1 — GOAL IDENTIFICATION LOOP                          │
│                                                             │
│  init: clarifications = []                                  │
│                                                             │
│  ┌─ loop ────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │  BAML ► baml_identify_goal(                           │  │
│  │           problem          = user_input,              │  │
│  │           registry         = registry_summaries,      │  │
│  │           clarifications   = clarifications           │  │
│  │         )                                             │  │
│  │         │                                             │  │
│  │         ├── NeedsClarification                        │  │
│  │         │     .question: str                          │  │
│  │         │     .context:  str                          │  │
│  │         │     │                                       │  │
│  │         │     └► ASK USER(question)                   │  │
│  │         │           → answer: str                     │  │
│  │         │         clarifications.append(              │  │
│  │         │           QA(question, answer))             │  │
│  │         │         continue loop ↑                     │  │
│  │         │                                             │  │
│  │         └── GoalClear                                 │  │
│  │               .calculation_type:    str               │  │
│  │               .terminal_node_id:    str | None        │  │
│  │               .missing_description: str | None        │  │
│  │               .state_summary:       StateSummary      │  │
│  │                 (incl. phase1_clarification_summary)  │  │
│  │               │                                       │  │
│  │               ├── terminal_node_id is None            │  │
│  │               │     └► ✗ MissingNodeError             │  │
│  │               │         "add node manually, restart"  │  │
│  │               │                                       │  │
│  │               └── terminal_node_id found              │  │
│  │                     goal = GoalClear result           │  │
│  │                     break loop                        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ► CONFIRM WITH USER(goal.calculation_type,                 │
│                       goal.terminal_node_id)                │
│    ├── confirmed  →  proceed to Phase 2                     │
│    └── rejected   →  restart Phase 1 ↑                     │
└─────────────────────────────────────────────────────────────┘
  │
  │  goal.terminal_node_id  →  seed graph
  │  goal.state_summary     →  carry into Phase 2
  ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2 — GRAPH BUILDING LOOP                               │
│                                                             │
│  init:                                                      │
│    graph = CalculationGraph(                                │
│      name             = normalise_name(                     │
│                           goal.calculation_type),           │
│      terminal_node_id = goal.terminal_node_id,             │
│      nodes            = [goal.terminal_node_id],           │
│      edges            = []                                  │
│    )                                                        │
│    state_summary  = goal.state_summary                      │
│    clarifications = []                                      │
│                                                             │
│  ┌─ loop ────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │  Python ► BreadthFirstTraversal()                     │  │
│  │             .next_unresolved(graph, registry)         │  │
│  │               iterates graph.nodes in order           │  │
│  │               skips data_retrieval / user_input nodes │  │
│  │               finds first input_type with no          │  │
│  │               matching incoming edge                  │  │
│  │             → UnresolvedInput | None                  │  │
│  │             │                                         │  │
│  │             ├── None → break loop  (all satisfied)    │  │
│  │             │                                         │  │
│  │             └── UnresolvedInput                       │  │
│  │                   .node_id:    str  (needs this type) │  │
│  │                   .input_type: str  (full import path)│  │
│  │                   │                                   │  │
│  │  Python ► pre-filter registry by output type:        │  │
│  │    filtered = [s for s in registry_summaries          │  │
│  │                if s.output == unresolved.input_type]  │  │
│  │                                                       │  │
│  │  BAML ► baml_extend_graph(                            │  │
│  │           current_unresolved = UnresolvedInput,       │  │
│  │           state_summary      = state_summary,         │  │
│  │           graph              = graph,                 │  │
│  │           registry           = filtered_summaries,    │  │
│  │           clarifications     = clarifications         │  │
│  │         )                                             │  │
│  │         │                                             │  │
│  │         │  [BAML sees type-matched candidates only]   │  │
│  │         │    1. graph nodes producing required type   │  │
│  │         │    2. registry nodes producing required type│  │
│  │         │    3. no candidates found                   │  │
│  │         │                                             │  │
│  │         ├── ConnectExisting                           │  │
│  │         │     .from_node_id:          str             │  │
│  │         │     .rationale:             str             │  │
│  │         │     .updated_state_summary: StateSummary    │  │
│  │         │     │                                       │  │
│  │         │     └► graph.edges.append(                  │  │
│  │         │           Edge(from_node_id,                │  │
│  │         │                unresolved.node_id,          │  │
│  │         │                unresolved.input_type))      │  │
│  │         │         state_summary = updated_state_summary│  │
│  │         │         continue loop ↑                     │  │
│  │         │                                             │  │
│  │         ├── AddFromRegistry                           │  │
│  │         │     .node_id:              str              │  │
│  │         │     .rationale:            str              │  │
│  │         │     .updated_state_summary: StateSummary    │  │
│  │         │     │                                       │  │
│  │         │     └► graph.nodes.append(node_id)          │  │
│  │         │         graph.edges.append(                 │  │
│  │         │           Edge(node_id,                     │  │
│  │         │                unresolved.node_id,          │  │
│  │         │                unresolved.input_type))      │  │
│  │         │         state_summary = updated_state_summary│  │
│  │         │         continue loop ↑                     │  │
│  │         │                                             │  │
│  │         ├── ApplicabilityCheck          [M4+]         │  │
│  │         │     .candidates: list[NodeSummary]          │  │
│  │         │     .question:   str                        │  │
│  │         │     │                                       │  │
│  │         │     └► ASK USER(question, candidates)       │  │
│  │         │           │                                 │  │
│  │         │           ├── node chosen                   │  │
│  │         │           │     graph.nodes.append(id)      │  │
│  │         │           │     graph.edges.append(Edge)    │  │
│  │         │           │     continue loop ↑             │  │
│  │         │           │                                 │  │
│  │         │           ├── all rejected                  │  │
│  │         │           │     └► ✗ MissingNodeError       │  │
│  │         │           │         "add node, restart"     │  │
│  │         │           │                                 │  │
│  │         │           └── unsure                        │  │
│  │         │                 clarifications.append(QA)   │  │
│  │         │                 continue loop ↑             │  │
│  │         │                                             │  │
│  │         └── NoCandidate                               │  │
│  │               .needed_description: str                │  │
│  │               └► ✗ MissingNodeError                   │  │
│  │                   "add node manually, restart"        │  │
│  └───────────────────────────────────────────────────────┘  │
│  (loop exits when all inputs satisfied)                     │
└─────────────────────────────────────────────────────────────┘
  │
  │  graph (all computation nodes have incoming edges)
  │  state_summary
  ▼
┌─────────────────────────────────────────────────────────────┐
│ DEPENDENCY LINT                                             │
│                                                             │
│  Python ► has_cycle(graph)                                  │
│             (DFS — delegates to networkx if available)      │
│             │                                               │
│             └── cycle found → ✗ CyclicGraphError           │
│                               "full reset required"         │
│                                                             │
│  ┌─ loop ────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │  Python ► BreadthFirstTraversal()                     │  │
│  │             .next_unresolved(graph, registry)         │  │
│  │             → UnresolvedInput | None                  │  │
│  │             │                                         │  │
│  │             ├── None → break loop  (lint clean)       │  │
│  │             │                                         │  │
│  │             └── UnresolvedInput                       │  │
│  │                   (leaf node gap remaining)           │  │
│  │                   │                                   │  │
│  │  ► resolve_with_user(gap, state_summary)              │  │
│  │      │                                                │  │
│  │      └► SHOW USER:                                    │  │
│  │           Unresolved: {input_type}                    │  │
│  │           needed by:  {node_id}                       │  │
│  │           Options:                                    │  │
│  │             1. data_retrieval stub                    │  │
│  │             2. user_input stub                        │  │
│  │           │                                           │  │
│  │           └► create_leaf_stub(node_type,              │  │
│  │                               output_type_path)       │  │
│  │                │                                      │  │
│  │                ├── derive node_id                     │  │
│  │                │     prefix: reader_ / prompt_        │  │
│  │                │     + snake_case(type_name)          │  │
│  │                │     + counter if collision           │  │
│  │                │                                      │  │
│  │                ├── write registry/nodes/{id}.py       │  │
│  │                │     @node(node_type=..., ...)        │  │
│  │                │     def {id}() -> OutputType:        │  │
│  │                │         raise NotImplementedError    │  │
│  │                │                                      │  │
│  │                ├── append import to registry/index.py │  │
│  │                │     (persistence for next session)   │  │
│  │                │                                      │  │
│  │                ├── importlib.import_module → fn       │  │
│  │                │     NODES.append(fn)                 │  │
│  │                │     (available immediately)          │  │
│  │                │                                      │  │
│  │                └── return node_id                     │  │
│  │                                                       │  │
│  │         graph.nodes.append(node_id)                   │  │
│  │         graph.edges.append(                           │  │
│  │           Edge(node_id, gap.node_id, gap.input_type)) │  │
│  │         registry_summaries = registry.summaries()     │  │
│  │           (refresh — stub now in NODES, must be       │  │
│  │            visible to traversal on next iteration)    │  │
│  │         continue loop ↑                               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
  │
  │  graph  (lint-clean, all inputs satisfied)
  ▼
┌─────────────────────────────────────────────────────────────┐
│ GRAPH REVIEW + APPROVAL                                     │
│                                                             │
│  SHOW USER:                                                 │
│    Calculation graph:                                       │
│      A  node_a  [data_retrieval]  → TypeA                  │
│      B  node_b  [computation]     → TypeB                  │
│      C  node_c  [computation]     → TypeC                  │
│                                                             │
│    Connections:                                             │
│      A      → B  (TypeA)                                   │
│      A+B    → C  (TypeA, TypeB)                            │
│                                                             │
│    [ Approve ]   [ Full reset ]                             │
│    │                                                        │
│    ├── Approve                                              │
│    │     graph.model_dump_json()                            │
│    │       → write graphs/{graph.name}.json                │
│    │     proceed to Step 2                                  │
│    │                                                        │
│    └── Full reset                                           │
│          discard all planning state                         │
│          restart Phase 1 ↑                                  │
└─────────────────────────────────────────────────────────────┘
  │
  │  graphs/{name}.json  (on disk)
  │
  └──────────────────────► STEP 1 COMPLETE


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EXECUTION SCRIPT GENERATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ENTRY]
  load graphs/{name}.json
  graph = CalculationGraph.model_validate_json(json)
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ EXECUTION SCRIPT GENERATION  (pure Python, no LLM)          │
│                                                             │
│  [edge direction — why no graph inversion is needed]        │
│    edges always stored: Edge(producer, consumer)            │
│    Phase 2 builds backward but edges always point forward   │
│    leaf nodes (data_retrieval / user_input) → in-degree 0  │
│    terminal node → highest in-degree                        │
│    topological sort directly = correct execution order      │
│                                                             │
│  1. topological_sort(graph)                                 │
│       → ordered: list[str]  (leaf nodes first, terminal     │
│                               node last)                    │
│                                                             │
│  2. for each node_id in ordered:                            │
│       summary = registry.get_summary(node_id)              │
│       resolve imports from summary.inputs, summary.output  │
│       derive variable name from snake_case(output_type)    │
│         collision → suffix with node_id                     │
│       resolve upstream variables from graph edges           │
│         for each input_type: find edge where               │
│           edge.to_node == node_id                           │
│           edge.type    == input_type                        │
│           → upstream variable name                          │
│                                                             │
│  3. terminal node = registry.get_summary(                   │
│                       graph.terminal_node_id)               │
│       → return type for run()                               │
│                                                             │
│  4. write runs/{name}.py:                                   │
│                                                             │
│       # generated — do not edit manually                    │
│       from {module} import {Type}  ...  (all types)         │
│       from registry.nodes.{id} import {fn}  ...  (all fns) │
│                                                             │
│       def run() -> {TerminalOutputType}:                    │
│           {var_a} = {node_a}()                              │
│           {var_b} = {node_b}({var_a})                       │
│           {var_c} = {node_c}({var_a}, {var_b})              │
│           return {terminal_result}                          │
│                                                             │
│       if __name__ == "__main__":                            │
│           result = run()                                    │
│           print(result)                                     │
└─────────────────────────────────────────────────────────────┘
  │
  │  runs/{name}.py  (independently executable)
  └──────────────────────► STEP 2 COMPLETE


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POST-MVP — NODE AUTHORING  (called from Phase 1, Phase 2, Lint)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ENTRY: called when a required node is missing]
  intent:          str   (what the node must do)
  planning_context: StateSummary
  node_type_hint:   str | None   (pre-filled from caller)
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ NODE AUTHORING LOOP                                         │
│ (max nesting depth: 1 — cannot call itself recursively)     │
│                                                             │
│  init: clarifications = []                                  │
│                                                             │
│  ┌─ loop ────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │  BAML ► baml_clarify_node(                            │  │
│  │           intent           = intent,                  │  │
│  │           planning_context = planning_context,        │  │
│  │           node_type_hint   = node_type_hint,          │  │
│  │           clarifications   = clarifications           │  │
│  │         )                                             │  │
│  │         │                                             │  │
│  │         ├── NeedsClarification                        │  │
│  │         │     .question, .context                     │  │
│  │         │     └► ASK USER(question) → answer          │  │
│  │         │         clarifications.append(QA)           │  │
│  │         │         continue loop ↑                     │  │
│  │         │                                             │  │
│  │         └── NodeDefinition                            │  │
│  │               .name, .node_type                       │  │
│  │               .description, .when_to_use              │  │
│  │               .assumptions, .references               │  │
│  │               .inputs: list[str]  (import paths)      │  │
│  │               .output: str        (import path)       │  │
│  │               .logic_description: str                 │  │
│  │               break loop                              │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
  │
  │  definition: NodeDefinition
  ▼
┌─────────────────────────────────────────────────────────────┐
│ TYPE ASSESSMENT                                             │
│                                                             │
│  for each type in definition.inputs + [definition.output]: │
│    importlib.import_module(module_path)                     │
│    │                                                        │
│    ├── resolves  →  accept (from calc_types/ or package)    │
│    │                                                        │
│    └── fails     →                                          │
│          BAML ► baml_generate_type(                         │
│                   type_name    = name,                      │
│                   description  = ...,                       │
│                   context      = planning_context.goal,     │
│                   known_types  = [already resolved]         │
│                 )                                           │
│                 → TypeDefinition                            │
│                     .class_name: str  (PascalCase)          │
│                     .file_name:  str  (snake_case)          │
│                     .source_code: str (Pydantic BaseModel)  │
│                 │                                           │
│                 └► SHOW USER generated type for review      │
│                       Approve / Edit / Reject               │
│                     write calc_types/{file_name}.py         │
│                     type now importable                     │
└─────────────────────────────────────────────────────────────┘
  │
  │  all types confirmed importable
  ▼
┌─────────────────────────────────────────────────────────────┐
│ CODE GENERATION PIPELINE                                    │
│                                                             │
│  BAML ► baml_generate_code(definition)                      │
│           generates internal logic only                     │
│           signature + decorator injected from definition    │
│           → source_code: str                                │
│           │                                                 │
│  Python ► static_validation(source_code, definition)        │
│             syntax check                                    │
│             param types match definition.inputs             │
│             return type matches definition.output           │
│             │                                               │
│             ├── pass  →  proceed                            │
│             └── fail  →  retry baml_generate_code           │
│                           (auto, max 3 attempts)            │
│                           if 3 failures → ask user to       │
│                             re-describe logic               │
│                                                             │
│  Python ► dependency_check(source_code)                     │
│             importlib.util.find_spec for each import        │
│             │                                               │
│             ├── all found  →  proceed                       │
│             └── missing    →  ASK USER to pip install       │
│                               install → recheck             │
│                                                             │
│  ► SHOW USER generated function for review                  │
│      Approve / Edit / Reject and re-describe                │
│      │                                                      │
│      ├── Approve / Edit                                     │
│      │     registry.exists(definition.name)?               │
│      │     ├── exists  →  ASK USER to rename               │
│      │     └── unique  →  proceed                           │
│      │     write registry/nodes/{name}.py                   │
│      │     append import to registry/index.py               │
│      │     importlib.import_module → fn                     │
│      │     NODES.append(fn)     (available immediately)     │
│      │     return node_id                                   │
│      │                                                      │
│      └── Reject and re-describe                             │
│            restart node authoring loop ↑                    │
└─────────────────────────────────────────────────────────────┘
  │
  │  node_id: str  (registered, immediately available)
  └──────────────────────► return to caller
                            (Phase 1 / Phase 2 / Lint resumes)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERROR PATHS SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase 1 — GoalClear with terminal_node_id = None
  └► MissingNodeError  →  engineer adds node manually, restart

Phase 2 — NoCandidate
  └► MissingNodeError  →  engineer adds node manually, restart

Phase 2 — ApplicabilityCheck, all candidates rejected
  └► MissingNodeError  →  engineer adds node manually, restart

Lint — has_cycle
  └► CyclicGraphError  →  full reset, restart Phase 1

Graph review — Full reset
  └► discard all state  →  restart Phase 1

Code gen — static validation fails 3 times
  └► ask user to re-describe node logic

Registry — node_id collision
  └► ask user to rename before registration


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA TYPES SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Flows between components:

  user_input: str
    └► Phase 1

  registry_summaries: list[NodeSummary]
    └► Phase 1, Phase 2, BreadthFirstTraversal, Lint

  clarifications: list[QA]
    └► Phase 1 (own list), Phase 2 (own list), Node authoring (own list)

  goal: GoalClear
    └► seeds graph.terminal_node_id + graph.name + state_summary

  state_summary: StateSummary
    └► Phase 1 → Phase 2 → Lint → Node authoring
       rewritten by each baml_extend_graph call

  unresolved: UnresolvedInput
    └► BreadthFirstTraversal → baml_extend_graph (Phase 2)
       BreadthFirstTraversal → resolve_with_user (Lint)

  filtered_summaries: list[NodeSummary]
    └► derived from registry_summaries filtered by unresolved.input_type
       passed to baml_extend_graph instead of full registry

  graph: CalculationGraph
    └► built in Phase 2, validated in Lint,
       reviewed by user, serialized to graphs/{name}.json,
       loaded in Step 2 for script generation

  node_id: str
    └► returned by Node authoring → appended to graph.nodes
       returned by create_leaf_stub → appended to graph.nodes
```

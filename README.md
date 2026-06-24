   # Dinoponera

   Dinoponera is an experimental Python + BAML calculation-agent framework for building auditable engineering
 calculation workflows.

   The goal is to let an engineer describe a calculation problem in natural language, have the system plan a typed
 calculation graph from a hand-authored node registry, review and approve that graph, and then generate a standalone
 Python script that performs the calculation deterministically.

   ## Project Status

   This project is currently in the design/planning stage.

   The implementation plan is documented in:

   - [DESIGN.md](./DESIGN.md)

   ## MVP Scope

   The planned MVP includes:

   1. **Planning**
      - BAML-assisted goal identification.
      - BAML-assisted graph construction.
      - Python registry introspection.
      - Dependency linting.
      - User review and approval.
      - Approved graph serialization.

   2. **Execution Script Generation**
      - Load an approved graph.
      - Topologically sort dependencies.
      - Generate a standalone Python script.
      - Execute without any LLM/BAML calls.

   ## Core Concepts

   - **Nodes** are typed Python functions.
   - **Domain types** are Pydantic BaseModel classes.
   - **Registry** is a Python module that imports and lists available node functions.
   - **Graphs** are explicit producer-to-consumer dependency graphs.
   - **BAML** is used only during planning, not execution.
   - **Generated scripts** are intended to be human-readable, auditable, and version-controllable.

   ## Planned Repository Layout

   ```text
   dinoponera/
     core/          # deterministic graph, registry, lint, and script-generation logic
     agent/         # planning orchestration, BAML calls, and user interaction

   calc_types/      # domain Pydantic models
   registry/        # hand-authored calculation node registry
   graphs/          # approved calculation graph JSON files
   runs/            # generated standalone Python scripts
   tests/           # Python tests
   ```

   ## Testing Plan

   The project will use:

   - pytest for deterministic Python tests.
   - BAML-native tests inside .baml files for every BAML function.

   Python tests should cover registry introspection, graph traversal, linting, serialization, and script generation.

   BAML tests should validate planning functions such as:

   - baml_identify_goal
   - baml_extend_graph

   ## Development

   Implementation has not started yet. See [DESIGN.md](./DESIGN.md) for the implementation-ready plan.

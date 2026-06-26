# Design: Geotechnical Registry Nodes for Settlement and Piled-Foundation Manual Tests

## Summary

Add geotechnical calculation domain types and registry nodes so a user can manually compose two calculation cases with the existing Dinoponera framework:

1. a general soil-compressibility settlement calculation, with both manual-entry and CPT-derived source paths available;
2. a CPT-required piled-foundation capacity calculation.

This change only populates `calc_types/`, `registry/nodes/`, and `registry/index.py` with usable node definitions and supporting tests. It does not add checked-in graph JSON files or generated run scripts. After implementation, a user/tester will manually create and approve calculation paths through the existing framework.

## Goals

- Add geotechnical Pydantic domain models using codebase-native `calc_types/` modules.
- Add settlement registry nodes:
  - manual prompt source for `SoilProfile`;
  - manual prompt source for `SettlementParameters`;
  - deterministic hypothetical CPT source;
  - CPT-to-soil-profile interpreter;
  - CPT-to-settlement-parameters derivation;
  - terminal settlement calculation.
- Add piled-foundation registry nodes:
  - deterministic hypothetical CPT source reused from settlement;
  - manual pile geometry source;
  - CPT-to-pile-foundation-parameters derivation;
  - terminal pile foundation capacity calculation that consumes geometry, derived parameters, and original CPT data.
- Keep calculations simplified, deterministic where possible, and explicitly labeled as illustrative/manual-test logic.
- Register all new nodes in `registry/index.py`.
- Add focused Python tests for node execution, prompt-node behavior with patched input, formulas, and registry summaries.

## Non-Goals

- Do not add checked-in `graphs/*.json` files.
- Do not add checked-in generated `runs/run_*.py` files.
- Do not implement a runtime conditional/branching graph engine.
- Do not implement production-grade geotechnical design standards.
- Do not implement real CPT file parsing.
- Do not add new dependencies or a units library.
- Do not change BAML schemas/prompts unless later requested separately.
- Do not create a manual-only piled-foundation soil/resistance path; pile soil/resistance parameters must derive from CPT data.

## Existing Codebase Context

Repository evidence at design time:

- `calc_types/example.py` contains simple Pydantic domain models used by the walking-skeleton calculation.
- `registry/nodes/example_source_value.py`, `registry/nodes/double_value.py`, and `registry/nodes/format_result.py` demonstrate the current decorated-node pattern.
- `registry/decorators.py` provides `@node(...)` metadata with `node_type`, `description`, `when_to_use`, `assumptions`, and `references`.
- `registry/index.py` explicitly imports registered node functions and lists them in `NODES`.
- `dinoponera/core/registry_introspection.py` requires registry node inputs and outputs to be importable Pydantic `BaseModel` subclasses. Primitive node I/O annotations are rejected.
- `dinoponera/core/models.py` defines `CalculationGraph`, `NodeSummary`, `NodeInput`, and `Edge`; graph connections are exact typed edges to named downstream inputs.
- `dinoponera/core/lint.py` requires every non-leaf computation input to have exactly one incoming edge and treats `data_retrieval` and `user_input` as leaf node types.
- `dinoponera/core/script_generation.py` generates deterministic scripts from static approved DAGs.
- `dinoponera/agent/deterministic_planning.py` can start from a terminal node ID and guide manual graph composition when multiple producers are available.
- Existing validation command documented in `README.md` is:

```bash
uv run --extra dev pytest -q
```

## Relevant Files and Modules

Existing files to update:

- `registry/index.py` — add imports for new node modules and append functions to `NODES`.

New type files:

- `calc_types/soil.py`
- `calc_types/cpt.py`
- `calc_types/settlement.py`
- `calc_types/piled_foundation.py`

New node files:

- `registry/nodes/prompt_soil_profile.py`
- `registry/nodes/prompt_settlement_parameters.py`
- `registry/nodes/hypothetical_cpt_data.py`
- `registry/nodes/interpret_cpt_soil_profile.py`
- `registry/nodes/derive_settlement_parameters_from_cpt.py`
- `registry/nodes/calculate_settlement.py`
- `registry/nodes/manual_pile_geometry.py`
- `registry/nodes/derive_pile_foundation_parameters_from_cpt.py`
- `registry/nodes/calculate_pile_foundation_capacity.py`

New test file:

- `tests/core/test_geotechnical_nodes.py`

Existing framework entrypoints for manual testing after implementation:

- `calculate.py`
- `dinoponera/agent/deterministic_planning.py`
- `dinoponera/core/script_generation.py`

## Accepted Design Decisions

1. **Registry nodes only, no committed graphs/runs** — Add nodes and types only. The user/tester will manually compose calculation graphs with the existing framework. Do not commit `graphs/*.json` or `runs/run_*.py` artifacts for these cases.
2. **Split domain type modules by area** — Use `calc_types/soil.py`, `calc_types/cpt.py`, `calc_types/settlement.py`, and `calc_types/piled_foundation.py`.
3. **Settlement workflow** — Terminal settlement node consumes separate `SoilProfile` and `SettlementParameters`. Both manual and CPT-derived producer paths are available in the registry.
4. **Piled-foundation workflow** — Piled foundation requires CPT data. The terminal node consumes `PileGeometry`, CPT-derived `PileFoundationParameters`, and the original `CptData`.
5. **Hypothetical CPT source** — Model the hypothetical CPT file as a deterministic `data_retrieval` node returning `CptData`; do not parse an external file.
6. **Manual settlement source nodes** — Use interactive `user_input` prompt nodes for manual settlement soil profile and parameters.
7. **Simplified formulas** — Use illustrative manual-test formulas, not production engineering standards. Settlement is general layered soil compressibility, not pile settlement.
8. **Unit-suffixed fields** — Use simple float fields with units encoded in field names, such as `surface_load_kpa`, `thickness_m`, `diameter_m`, `total_settlement_mm`, and `design_capacity_kn`.
9. **Validation scope** — Add registry/node unit tests only. Do not add committed graph or run artifacts. The user/tester manually composes graphs after implementation.

## Proposed Architecture

### Settlement registry paths

```text
Manual settlement path:
prompt_soil_profile() -> SoilProfile
prompt_settlement_parameters() -> SettlementParameters
calculate_settlement(
  soil_profile: SoilProfile,
  parameters: SettlementParameters,
) -> SettlementResult
```

```text
CPT settlement path:
hypothetical_cpt_data() -> CptData
interpret_cpt_soil_profile(cpt: CptData) -> SoilProfile
derive_settlement_parameters_from_cpt(cpt: CptData) -> SettlementParameters
calculate_settlement(
  soil_profile: SoilProfile,
  parameters: SettlementParameters,
) -> SettlementResult
```

### Piled-foundation registry path

```text
hypothetical_cpt_data() -> CptData
manual_pile_geometry() -> PileGeometry
derive_pile_foundation_parameters_from_cpt(cpt: CptData) -> PileFoundationParameters
calculate_pile_foundation_capacity(
  geometry: PileGeometry,
  parameters: PileFoundationParameters,
  cpt: CptData,
) -> PileFoundationResult
```

There is no manual-only producer for `PileFoundationParameters`.

## Data Flow

### Settlement manual path

1. User starts manual planning from terminal node `calculate_settlement`.
2. The graph builder sees unresolved inputs:
   - `soil_profile: calc_types.soil.SoilProfile`
   - `parameters: calc_types.settlement.SettlementParameters`
3. User selects manual prompt producers:
   - `prompt_soil_profile`
   - `prompt_settlement_parameters`
4. Generated script execution calls those prompt nodes, asks for runtime values, then calls `calculate_settlement`.

### Settlement CPT path

1. User starts manual planning from terminal node `calculate_settlement`.
2. The graph builder sees the same unresolved inputs as the manual path.
3. User selects CPT-derived producers:
   - `interpret_cpt_soil_profile` for `SoilProfile`
   - `derive_settlement_parameters_from_cpt` for `SettlementParameters`
4. Both interpreter/derivation nodes require `CptData`.
5. User selects `hypothetical_cpt_data` as the producer of `CptData`.
6. Generated script execution uses deterministic CPT data, derives the settlement inputs, then calls `calculate_settlement`.

### Piled-foundation CPT path

1. User starts manual planning from terminal node `calculate_pile_foundation_capacity`.
2. The graph builder sees unresolved inputs:
   - `geometry: calc_types.piled_foundation.PileGeometry`
   - `parameters: calc_types.piled_foundation.PileFoundationParameters`
   - `cpt: calc_types.cpt.CptData`
3. User selects:
   - `manual_pile_geometry` for pile geometry;
   - `derive_pile_foundation_parameters_from_cpt` for parameters;
   - `hypothetical_cpt_data` for original CPT data.
4. The parameter derivation node also consumes `CptData`, so `hypothetical_cpt_data` can connect to both the parameter derivation node and the terminal pile calculation.
5. Generated script execution derives parameters from CPT, passes geometry, parameters, and original CPT data to `calculate_pile_foundation_capacity`.

## API / Interface Changes

### `calc_types/soil.py`

Define:

```text
SoilLayer(BaseModel)
  name: str
  top_m: float
  bottom_m: float
  compressibility_per_kpa: float

SoilProfile(BaseModel)
  layers: list[SoilLayer]
```

Conservative implementation notes:

- `bottom_m` should be greater than `top_m` for sensible sample/prompt data.
- The settlement calculation should compute layer thickness as `bottom_m - top_m` rather than requiring a separate thickness field.
- Add Pydantic validators only if implementation wants clear input errors; no new dependencies are required.

### `calc_types/cpt.py`

Define:

```text
CptPoint(BaseModel)
  depth_m: float
  cone_resistance_mpa: float
  sleeve_friction_kpa: float

CptData(BaseModel)
  source_name: str
  points: list[CptPoint]
```

`source_name` should identify the hypothetical source, for example `"hypothetical_cpt_file.csv"`.

### `calc_types/settlement.py`

Define:

```text
SettlementParameters(BaseModel)
  surface_load_kpa: float

SettlementLayerContribution(BaseModel)
  layer_name: str
  thickness_m: float
  compressibility_per_kpa: float
  settlement_mm: float

SettlementResult(BaseModel)
  total_settlement_mm: float
  contributions: list[SettlementLayerContribution]
  notes: list[str]
```

The accepted settlement formula is illustrative layered compressibility:

```text
layer_settlement_mm = surface_load_kpa * compressibility_per_kpa * thickness_m

total_settlement_mm = sum(layer_settlement_mm for each layer)
```

The field `compressibility_per_kpa` is intended to be chosen so the formula directly produces millimetres for the manual-test examples. Result notes must state that the formula is illustrative and not production-grade.

### `calc_types/piled_foundation.py`

Define:

```text
PileGeometry(BaseModel)
  diameter_m: float
  embedded_length_m: float

PileFoundationParameters(BaseModel)
  unit_shaft_resistance_kpa: float
  unit_base_resistance_kpa: float
  resistance_factor: float

PileFoundationResult(BaseModel)
  shaft_capacity_kn: float
  base_capacity_kn: float
  ultimate_capacity_kn: float
  design_capacity_kn: float
  notes: list[str]
```

Piled-foundation capacity formula:

```text
perimeter_m = pi * diameter_m
base_area_m2 = pi * diameter_m**2 / 4
shaft_capacity_kn = unit_shaft_resistance_kpa * perimeter_m * embedded_length_m
base_capacity_kn = unit_base_resistance_kpa * base_area_m2
ultimate_capacity_kn = shaft_capacity_kn + base_capacity_kn
design_capacity_kn = ultimate_capacity_kn / resistance_factor
```

Because `1 kPa * m² = 1 kN`, no extra conversion is required for these simplified formulas.

## Code Architecture Sketch

```text
Before:
calc_types/
  example.py
registry/nodes/
  example_source_value.py
  double_value.py
  format_result.py
registry/index.py

After:
calc_types/
  example.py
  soil.py
  cpt.py
  settlement.py
  piled_foundation.py

registry/nodes/
  example_source_value.py
  double_value.py
  format_result.py
  prompt_soil_profile.py
  prompt_settlement_parameters.py
  hypothetical_cpt_data.py
  interpret_cpt_soil_profile.py
  derive_settlement_parameters_from_cpt.py
  calculate_settlement.py
  manual_pile_geometry.py
  derive_pile_foundation_parameters_from_cpt.py
  calculate_pile_foundation_capacity.py

registry/index.py
  # existing explicit registry; add imports and append new functions to NODES
```

## File-by-File Implementation Plan

### `calc_types/soil.py`

- New.
- Purpose: shared soil profile models for settlement and CPT interpretation.
- Required changes:
  - Define `SoilLayer` and `SoilProfile` as Pydantic `BaseModel` classes.
- Key types/functions/classes:
  - `SoilLayer`
  - `SoilProfile`
- Dependencies:
  - `pydantic.BaseModel`
- Tests:
  - Construct a profile with at least two layers in `tests/core/test_geotechnical_nodes.py`.
  - Verify node registry summaries reference `calc_types.soil.SoilProfile`.

### `calc_types/cpt.py`

- New.
- Purpose: deterministic hypothetical CPT data contract.
- Required changes:
  - Define `CptPoint` and `CptData` as Pydantic `BaseModel` classes.
- Key types/functions/classes:
  - `CptPoint`
  - `CptData`
- Dependencies:
  - `pydantic.BaseModel`
- Tests:
  - Verify `hypothetical_cpt_data()` returns `CptData` with non-empty `points` and a `source_name` indicating a hypothetical source.

### `calc_types/settlement.py`

- New.
- Purpose: settlement calculation input/result contracts.
- Required changes:
  - Define `SettlementParameters`, `SettlementLayerContribution`, and `SettlementResult`.
- Key types/functions/classes:
  - `SettlementParameters`
  - `SettlementLayerContribution`
  - `SettlementResult`
- Dependencies:
  - `pydantic.BaseModel`
- Tests:
  - Verify `calculate_settlement()` returns deterministic total settlement and layer contributions for known inputs.

### `calc_types/piled_foundation.py`

- New.
- Purpose: pile geometry, CPT-derived pile parameters, and pile result contracts.
- Required changes:
  - Define `PileGeometry`, `PileFoundationParameters`, and `PileFoundationResult`.
- Key types/functions/classes:
  - `PileGeometry`
  - `PileFoundationParameters`
  - `PileFoundationResult`
- Dependencies:
  - `pydantic.BaseModel`
- Tests:
  - Verify pile calculation outputs stable shaft, base, ultimate, and design capacities for known inputs.

### `registry/nodes/prompt_soil_profile.py`

- New.
- Purpose: interactive manual-entry source for settlement soil profile.
- Required changes:
  - Add a `@node(node_type="user_input", ...)` zero-argument function:

```text
prompt_soil_profile() -> SoilProfile
```

  - Prompt for enough values to construct a small `SoilProfile`.
  - Conservative default interface: prompt for number of layers, then for each layer ask name, top depth, bottom depth, and compressibility.
  - Convert input strings to floats where needed.
  - Metadata assumptions must state it is interactive and intended for manual testing.
- Key types/functions/classes:
  - `prompt_soil_profile`
- Dependencies:
  - `calc_types.soil.SoilLayer`
  - `calc_types.soil.SoilProfile`
  - `registry.decorators.node`
- Tests:
  - Patch `builtins.input` with deterministic responses and assert a valid `SoilProfile` is returned.
  - Verify registry summary node type is `user_input`.

### `registry/nodes/prompt_settlement_parameters.py`

- New.
- Purpose: interactive manual-entry source for settlement load parameters.
- Required changes:
  - Add a `@node(node_type="user_input", ...)` zero-argument function:

```text
prompt_settlement_parameters() -> SettlementParameters
```

  - Prompt for `surface_load_kpa`.
  - Metadata assumptions must state it is interactive and intended for manual testing.
- Key types/functions/classes:
  - `prompt_settlement_parameters`
- Dependencies:
  - `calc_types.settlement.SettlementParameters`
  - `registry.decorators.node`
- Tests:
  - Patch `builtins.input` and assert returned `surface_load_kpa`.
  - Verify registry summary node type is `user_input`.

### `registry/nodes/hypothetical_cpt_data.py`

- New.
- Purpose: deterministic CPT source representing a hypothetical file.
- Required changes:
  - Add a `@node(node_type="data_retrieval", ...)` zero-argument function:

```text
hypothetical_cpt_data() -> CptData
```

  - Return fixed sample `CptData` with multiple `CptPoint` values.
  - Use `source_name` such as `"hypothetical_cpt_file.csv"`.
  - Metadata assumptions must state the CPT data is hard-coded and illustrative.
- Key types/functions/classes:
  - `hypothetical_cpt_data`
- Dependencies:
  - `calc_types.cpt.CptData`
  - `calc_types.cpt.CptPoint`
  - `registry.decorators.node`
- Tests:
  - Assert returned type, source name, and non-empty points.

### `registry/nodes/interpret_cpt_soil_profile.py`

- New.
- Purpose: convert CPT data into a soil profile for settlement calculation.
- Required changes:
  - Add a `@node(node_type="computation", ...)` function:

```text
interpret_cpt_soil_profile(cpt: CptData) -> SoilProfile
```

  - Use simple deterministic interpretation logic, for example grouping CPT depth ranges into layers and deriving `compressibility_per_kpa` inversely from average cone resistance.
  - Keep formulas simple and documented in metadata/assumptions.
- Key types/functions/classes:
  - `interpret_cpt_soil_profile`
- Dependencies:
  - `calc_types.cpt.CptData`
  - `calc_types.soil.SoilLayer`
  - `calc_types.soil.SoilProfile`
  - `registry.decorators.node`
- Tests:
  - Call with `hypothetical_cpt_data()` and assert a valid non-empty `SoilProfile`.

### `registry/nodes/derive_settlement_parameters_from_cpt.py`

- New.
- Purpose: derive settlement load parameters from CPT data for the CPT settlement path.
- Required changes:
  - Add a `@node(node_type="computation", ...)` function:

```text
derive_settlement_parameters_from_cpt(cpt: CptData) -> SettlementParameters
```

  - Use deterministic illustrative logic, for example selecting a representative `surface_load_kpa` from CPT strength or returning a documented fixed value based on the hypothetical CPT source.
  - Result must be valid and positive for manual testing.
- Key types/functions/classes:
  - `derive_settlement_parameters_from_cpt`
- Dependencies:
  - `calc_types.cpt.CptData`
  - `calc_types.settlement.SettlementParameters`
  - `registry.decorators.node`
- Tests:
  - Call with `hypothetical_cpt_data()` and assert a positive `surface_load_kpa`.

### `registry/nodes/calculate_settlement.py`

- New.
- Purpose: terminal settlement calculation node.
- Required changes:
  - Add a `@node(node_type="computation", ...)` function:

```text
calculate_settlement(
  soil_profile: SoilProfile,
  parameters: SettlementParameters,
) -> SettlementResult
```

  - Compute each layer contribution:

```text
thickness_m = layer.bottom_m - layer.top_m
settlement_mm = parameters.surface_load_kpa * layer.compressibility_per_kpa * thickness_m
```

  - Sum `total_settlement_mm`.
  - Include result notes stating the calculation is illustrative/manual-test only and not a design-standard settlement method.
- Key types/functions/classes:
  - `calculate_settlement`
- Dependencies:
  - `calc_types.soil.SoilProfile`
  - `calc_types.settlement.SettlementParameters`
  - `calc_types.settlement.SettlementLayerContribution`
  - `calc_types.settlement.SettlementResult`
  - `registry.decorators.node`
- Tests:
  - Directly call with known `SoilProfile` and `SettlementParameters`.
  - Assert layer contributions and total.

### `registry/nodes/manual_pile_geometry.py`

- New.
- Purpose: manual/design source node for pile geometry.
- Required changes:
  - Add a `@node(node_type="user_input", ...)` zero-argument function:

```text
manual_pile_geometry() -> PileGeometry
```

  - To keep the pile CPT manual test easier to run, this node should return deterministic sample geometry rather than prompt interactively, unless the implementation agent chooses to also patch prompt behavior in tests.
  - Metadata should clearly state it is a representative manual design input for testing.
- Key types/functions/classes:
  - `manual_pile_geometry`
- Dependencies:
  - `calc_types.piled_foundation.PileGeometry`
  - `registry.decorators.node`
- Tests:
  - Assert returned diameter and embedded length are positive.
  - Verify registry summary node type is `user_input`.
- Note:
  - The user explicitly selected interactive prompt nodes only for manual settlement sources. Pile geometry was accepted as a separate design input, but not explicitly required to be interactive. The conservative default for runnable manual tests is deterministic sample geometry.

### `registry/nodes/derive_pile_foundation_parameters_from_cpt.py`

- New.
- Purpose: derive pile resistance parameters from CPT data.
- Required changes:
  - Add a `@node(node_type="computation", ...)` function:

```text
derive_pile_foundation_parameters_from_cpt(cpt: CptData) -> PileFoundationParameters
```

  - Use simple deterministic correlations from CPT data, for example:
    - average cone resistance to derive `unit_base_resistance_kpa`;
    - average sleeve friction or a fraction of cone resistance to derive `unit_shaft_resistance_kpa`;
    - fixed `resistance_factor`, e.g. `2.0`.
  - Keep metadata and result assumptions clear that this is illustrative/manual-test logic.
- Key types/functions/classes:
  - `derive_pile_foundation_parameters_from_cpt`
- Dependencies:
  - `calc_types.cpt.CptData`
  - `calc_types.piled_foundation.PileFoundationParameters`
  - `registry.decorators.node`
- Tests:
  - Call with `hypothetical_cpt_data()` and assert positive resistance values and `resistance_factor > 0`.

### `registry/nodes/calculate_pile_foundation_capacity.py`

- New.
- Purpose: terminal piled-foundation capacity calculation node.
- Required changes:
  - Add a `@node(node_type="computation", ...)` function:

```text
calculate_pile_foundation_capacity(
  geometry: PileGeometry,
  parameters: PileFoundationParameters,
  cpt: CptData,
) -> PileFoundationResult
```

  - Use the simplified shaft + base capacity formula:

```text
perimeter_m = pi * geometry.diameter_m
base_area_m2 = pi * geometry.diameter_m**2 / 4
shaft_capacity_kn = parameters.unit_shaft_resistance_kpa * perimeter_m * geometry.embedded_length_m
base_capacity_kn = parameters.unit_base_resistance_kpa * base_area_m2
ultimate_capacity_kn = shaft_capacity_kn + base_capacity_kn
design_capacity_kn = ultimate_capacity_kn / parameters.resistance_factor
```

  - Consume `cpt` directly as required by the accepted decision. Use it in notes or a simple consistency check, such as reporting `cpt.source_name` and number of points in result notes. Do not ignore the argument entirely.
  - Include result notes stating the calculation is illustrative/manual-test only and CPT-required.
- Key types/functions/classes:
  - `calculate_pile_foundation_capacity`
- Dependencies:
  - `math.pi`
  - `calc_types.cpt.CptData`
  - `calc_types.piled_foundation.PileGeometry`
  - `calc_types.piled_foundation.PileFoundationParameters`
  - `calc_types.piled_foundation.PileFoundationResult`
  - `registry.decorators.node`
- Tests:
  - Directly call with known geometry, parameters, and CPT data.
  - Assert stable shaft, base, ultimate, and design capacity values.

### `registry/index.py`

- Existing.
- Purpose: explicit source of truth for registered nodes.
- Required changes:
  - Import all new node functions.
  - Append all new node functions to `NODES`.
  - Preserve existing example nodes and registry helper functions.
- Key types/functions/classes:
  - `NODES`
- Dependencies:
  - new `registry.nodes.*` modules.
- Tests:
  - `registry_index.summaries()` includes all new node IDs.
  - No duplicate node IDs.
  - New node summaries expose expected input/output import paths.

### `tests/core/test_geotechnical_nodes.py`

- New.
- Purpose: focused unit tests for geotechnical types, nodes, formulas, prompt behavior, and registry summaries.
- Required tests:
  - `hypothetical_cpt_data()` returns valid `CptData` with non-empty points.
  - `interpret_cpt_soil_profile(hypothetical_cpt_data())` returns a non-empty `SoilProfile`.
  - `derive_settlement_parameters_from_cpt(hypothetical_cpt_data())` returns positive `surface_load_kpa`.
  - `prompt_soil_profile()` returns a `SoilProfile` when `builtins.input` is patched with deterministic responses.
  - `prompt_settlement_parameters()` returns `SettlementParameters` when `builtins.input` is patched.
  - `calculate_settlement()` produces expected contribution and total values for known inputs.
  - `manual_pile_geometry()` returns positive geometry.
  - `derive_pile_foundation_parameters_from_cpt(hypothetical_cpt_data())` returns positive resistance parameters.
  - `calculate_pile_foundation_capacity()` produces expected capacity values for known inputs.
  - `registry_index.summaries()` contains:
    - `prompt_soil_profile`
    - `prompt_settlement_parameters`
    - `hypothetical_cpt_data`
    - `interpret_cpt_soil_profile`
    - `derive_settlement_parameters_from_cpt`
    - `calculate_settlement`
    - `manual_pile_geometry`
    - `derive_pile_foundation_parameters_from_cpt`
    - `calculate_pile_foundation_capacity`
  - Registry summary input/output types include:
    - `calc_types.soil.SoilProfile`
    - `calc_types.cpt.CptData`
    - `calc_types.settlement.SettlementParameters`
    - `calc_types.settlement.SettlementResult`
    - `calc_types.piled_foundation.PileGeometry`
    - `calc_types.piled_foundation.PileFoundationParameters`
    - `calc_types.piled_foundation.PileFoundationResult`

## Testing Strategy

### Unit tests

Add `tests/core/test_geotechnical_nodes.py` with direct node tests and registry summary tests.

Prompt nodes should be tested with patched `builtins.input`. Use an iterator of string responses, for example:

```text
prompt_soil_profile responses:
  "2"          # number of layers
  "sand"       # layer 1 name
  "0"          # top_m
  "2"          # bottom_m
  "0.05"       # compressibility_per_kpa
  "clay"       # layer 2 name
  "2"          # top_m
  "5"          # bottom_m
  "0.12"       # compressibility_per_kpa

prompt_settlement_parameters responses:
  "100"        # surface_load_kpa
```

### Formula tests

Settlement known-value example:

```text
surface_load_kpa = 100
layers:
  layer A: top=0, bottom=2, compressibility=0.05
  layer B: top=2, bottom=5, compressibility=0.12

contributions:
  A = 100 * 0.05 * 2 = 10 mm
  B = 100 * 0.12 * 3 = 36 mm
total = 46 mm
```

Pile known-value tests should use `math.pi` expectations with `pytest.approx`.

### Registry tests

Use existing registry patterns from `tests/core/test_registry.py`:

- call `registry_index.summaries()`;
- assert expected node IDs exist;
- assert expected node types and input/output type paths.

### Manual validation after implementation

Run deterministic tests:

```bash
uv run --extra dev pytest -q
```

Then manually compose calculation paths with the framework. Example terminal-node entrypoints:

```bash
uv run python -m dinoponera.agent.deterministic_planning calculate_settlement --name settlement_manual_test
```

```bash
uv run python -m dinoponera.agent.deterministic_planning calculate_pile_foundation_capacity --name piled_foundation_cpt_test
```

Because settlement has multiple producers for `SoilProfile` and `SettlementParameters`, manual planning may ask the user to choose between prompt/manual and CPT-derived producer nodes.

## Migration / Backward Compatibility

- Existing example doubling nodes and graphs remain valid.
- Existing graph JSON format is unchanged.
- Existing script generation behavior is unchanged.
- New Pydantic type import paths become graph contracts if the user later serializes manually approved graphs. Avoid renaming these new models/modules after manual graphs are created.
- Adding new registry nodes can introduce additional candidates during manual/BAML planning. Node metadata must clearly distinguish manual prompt sources from CPT-derived producers.

## Risks and Mitigations

### Risk: Settlement producer ambiguity during manual planning

- Why it matters: both `prompt_soil_profile` and `interpret_cpt_soil_profile` produce `SoilProfile`; both `prompt_settlement_parameters` and `derive_settlement_parameters_from_cpt` produce `SettlementParameters`.
- Mitigation: use clear node names, descriptions, and `when_to_use` metadata. The deterministic planner already has an applicability/user-choice path for ambiguous candidates.
- Status: Accepted.

### Risk: Interactive prompt nodes block generated-script execution

- Why it matters: `prompt_soil_profile` and `prompt_settlement_parameters` call `input()` at runtime.
- Mitigation: this was explicitly chosen for the manual settlement source path. Tests must patch `builtins.input`. CPT paths remain deterministic.
- Status: Accepted.

### Risk: Pile geometry source is deterministic despite being manual/design input

- Why it matters: the user explicitly required interactive prompt nodes for manual settlement, but did not explicitly require pile geometry to prompt. A deterministic geometry node is more convenient for manual CPT testing.
- Conservative default: implement `manual_pile_geometry()` as a deterministic `user_input` source with representative sample geometry and clear metadata. If interactive pile geometry is desired later, add a separate prompt node.
- Status: Accepted with assumptions.

### Risk: Formulas are not production-grade

- Why it matters: geotechnical calculations can be safety-critical.
- Mitigation: node metadata and result notes must state these are illustrative/manual-test calculations, not design-standard implementations.
- Status: Accepted.

### Risk: No real CPT file parsing

- Why it matters: the requested branch mentions a hypothetical file.
- Mitigation: represent the hypothetical file through `CptData.source_name` and deterministic embedded CPT points. Add real file parsing later as a separate node/type design.
- Status: Accepted.

### Risk: Direct CPT argument in pile terminal node could be unused

- Why it matters: user clarified that `calculate_pile_foundation_capacity` needs geometry, parameters, and CPT.
- Mitigation: consume `cpt` in the function by including CPT source/point-count in result notes or performing a simple consistency check. Do not leave it unused.
- Status: Accepted.

## Validation Checklist

Implementation checklist:

- [ ] `calc_types/soil.py` exists and defines `SoilLayer`, `SoilProfile`.
- [ ] `calc_types/cpt.py` exists and defines `CptPoint`, `CptData`.
- [ ] `calc_types/settlement.py` exists and defines `SettlementParameters`, `SettlementLayerContribution`, `SettlementResult`.
- [ ] `calc_types/piled_foundation.py` exists and defines `PileGeometry`, `PileFoundationParameters`, `PileFoundationResult`.
- [ ] `registry/nodes/prompt_soil_profile.py` exists and defines decorated `prompt_soil_profile() -> SoilProfile`.
- [ ] `registry/nodes/prompt_settlement_parameters.py` exists and defines decorated `prompt_settlement_parameters() -> SettlementParameters`.
- [ ] `registry/nodes/hypothetical_cpt_data.py` exists and defines decorated `hypothetical_cpt_data() -> CptData`.
- [ ] `registry/nodes/interpret_cpt_soil_profile.py` exists and defines decorated `interpret_cpt_soil_profile(cpt: CptData) -> SoilProfile`.
- [ ] `registry/nodes/derive_settlement_parameters_from_cpt.py` exists and defines decorated `derive_settlement_parameters_from_cpt(cpt: CptData) -> SettlementParameters`.
- [ ] `registry/nodes/calculate_settlement.py` exists and defines decorated `calculate_settlement(soil_profile: SoilProfile, parameters: SettlementParameters) -> SettlementResult`.
- [ ] `registry/nodes/manual_pile_geometry.py` exists and defines decorated `manual_pile_geometry() -> PileGeometry`.
- [ ] `registry/nodes/derive_pile_foundation_parameters_from_cpt.py` exists and defines decorated `derive_pile_foundation_parameters_from_cpt(cpt: CptData) -> PileFoundationParameters`.
- [ ] `registry/nodes/calculate_pile_foundation_capacity.py` exists and defines decorated `calculate_pile_foundation_capacity(geometry: PileGeometry, parameters: PileFoundationParameters, cpt: CptData) -> PileFoundationResult`.
- [ ] `registry/index.py` imports all new node functions.
- [ ] `registry/index.py` appends all new node functions to `NODES`.
- [ ] All new registry node inputs and outputs are Pydantic `BaseModel` subclasses, not primitives.
- [ ] New node metadata clearly distinguishes manual prompt sources, deterministic hypothetical CPT source, interpretation nodes, and terminal calculations.
- [ ] No checked-in `graphs/*.json` files are added for these geotechnical cases.
- [ ] No checked-in `runs/run_*.py` files are added for these geotechnical cases.
- [ ] `tests/core/test_geotechnical_nodes.py` covers node execution, prompt behavior, formulas, and registry summaries.
- [ ] `uv run --extra dev pytest -q` passes.

Implementability checks against current repo:

- [x] `calc_types/` exists and already contains importable Pydantic models in `calc_types/example.py`.
- [x] `registry/nodes/` exists and contains decorated node examples.
- [x] `registry/decorators.py` exists and provides `@node`.
- [x] `registry/index.py` exists and is the correct explicit registry file to update.
- [x] `dinoponera/core/registry_introspection.py` supports the proposed Pydantic model annotations.
- [x] `dinoponera/core/lint.py` supports multi-input computation nodes with named inputs.
- [x] `dinoponera/core/script_generation.py` supports generated scripts for multi-input nodes using `Edge.to_input`.
- [x] `tests/core/` exists and already contains registry/script-generation tests to copy.
- [x] Existing dependency set already includes Pydantic; no new dependency is required.
- [x] Validation command is discoverable from `README.md`.

## Open Questions

### Exact prompt wording for interactive settlement nodes

Unknown: the exact user-facing prompt strings for `prompt_soil_profile()` and `prompt_settlement_parameters()`.

Why it matters: tests must provide responses in the expected order.

Conservative default: keep prompts minimal and sequential: number of layers, then per-layer name/top/bottom/compressibility, then surface load.

Status: Accepted with assumptions.

### Exact hypothetical CPT values

Unknown: the exact CPT points to embed in `hypothetical_cpt_data()`.

Why it matters: derived parameter and result tests depend on deterministic values.

Conservative default: use a short, simple set of positive CPT points at increasing depths, documented as illustrative and not from a real project.

Status: Accepted with assumptions.

### Whether pile geometry should be interactive

Unknown: whether pile geometry should prompt at runtime like manual settlement sources.

Why it matters: an interactive pile geometry node would make generated pile scripts prompt; a deterministic source makes manual CPT testing easier.

Conservative default: implement `manual_pile_geometry()` as a deterministic `user_input` node returning representative sample geometry, with metadata stating it is a manual design input for testing.

Status: Accepted with assumptions.

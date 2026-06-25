// BAML-native schemas and planner functions for the calculation-agent MVP.
// Direct Python calls to these functions are localized in dinoponera.agent.planning.

class BamlNodeInput {
  name string
  type string
}

class BamlNodeSummary {
  id string
  node_type string
  description string
  when_to_use string
  assumptions string[]
  inputs BamlNodeInput[]
  output string
  references string[]
}

class BamlEdge {
  from_node string
  to_node string
  to_input string
  type string
}

class BamlCalculationGraph {
  name string
  terminal_node_id string
  nodes string[]
  edges BamlEdge[]
}

class BamlQA {
  question string
  answer string
}

class BamlStateSummary {
  goal string
  decisions string[]
  open_items string[]
  phase1_clarification_summary string
}

class BamlUnresolvedInput {
  node_id string
  input_name string
  input_type string
}

enum GoalIdentificationKind {
  GoalClear
  NeedsClarification
}

class GoalIdentificationResult {
  kind GoalIdentificationKind

  // GoalClear fields.
  calculation_type string?
  terminal_node_id string?
  missing_description string?
  state_summary BamlStateSummary?

  // NeedsClarification fields.
  question string?
  context string?
}

enum GraphExtensionKind {
  ConnectExisting
  AddFromRegistry
  ApplicabilityCheck
  NoCandidate
}

class GraphExtensionResult {
  kind GraphExtensionKind

  // ConnectExisting fields.
  from_node_id string?

  // AddFromRegistry fields.
  node_id string?

  // ApplicabilityCheck fields.
  question string?
  candidates BamlNodeSummary[]?

  // NoCandidate fields.
  needed_description string?

  // Shared fields.
  rationale string?
  updated_state_summary BamlStateSummary?
}

function IdentifyGoal(
  problem: string,
  registry: BamlNodeSummary[],
  clarifications: BamlQA[]
) -> GoalIdentificationResult {
  client ClaudeHaiku45
  prompt #"
    You are planning an auditable typed engineering calculation.

    Task:
    - Identify the terminal calculation node that best satisfies the engineer's problem.
    - Use only the provided registry. Do not invent nodes.
    - Do not ask a clarification when the registry contains a clear terminal match.
    - If the problem is underspecified, ask exactly one focused clarification.
    - If the goal is clear but no terminal registry node exists, return GoalClear with terminal_node_id null and missing_description populated.
    - If the terminal node exists, return GoalClear with calculation_type, terminal_node_id, and state_summary.

    Engineer problem:
    {{ problem }}

    Previous clarifications:
    {{ clarifications }}

    Registry summaries:
    {{ registry }}

    Output rules:
    - kind must be GoalClear or NeedsClarification.
    - For NeedsClarification, populate question and optional context.
    - For GoalClear, populate calculation_type and state_summary.
    - terminal_node_id must be one of the registry ids or null.
    - state_summary.goal should restate the calculation goal.
    - state_summary.phase1_clarification_summary should summarize prior clarifications.

    {{ ctx.output_format }}
  "#
}

test identify_goal_clear_example {
  functions [IdentifyGoal]
  args {
    problem "Calculate the final example result from the available example nodes."
    registry [
      {
        id "format_result"
        node_type "computation"
        description "Format the doubled value as the terminal calculation result."
        when_to_use "Use as the terminal node for the example doubling calculation."
        assumptions []
        inputs [
          {
            name "doubled"
            type "calc_types.example.DoubledValue"
          }
        ]
        output "calc_types.example.CalculationResult"
        references []
      }
    ]
    clarifications []
  }
}

test identify_goal_missing_terminal_example {
  functions [IdentifyGoal]
  args {
    problem "Calculate a settlement analysis report."
    registry [
      {
        id "format_result"
        node_type "computation"
        description "Format the doubled value as the terminal calculation result."
        when_to_use "Use as the terminal node for the example doubling calculation."
        assumptions []
        inputs [
          {
            name "doubled"
            type "calc_types.example.DoubledValue"
          }
        ]
        output "calc_types.example.CalculationResult"
        references []
      }
    ]
    clarifications []
  }
}

test identify_goal_clarification_example {
  functions [IdentifyGoal]
  args {
    problem "Run the calculation."
    registry [
      {
        id "format_result"
        node_type "computation"
        description "Format the doubled value as the terminal calculation result."
        when_to_use "Use as the terminal node for the example doubling calculation."
        assumptions []
        inputs [
          {
            name "doubled"
            type "calc_types.example.DoubledValue"
          }
        ]
        output "calc_types.example.CalculationResult"
        references []
      }
    ]
    clarifications []
  }
}

function ExtendGraph(
  current_unresolved: BamlUnresolvedInput,
  state_summary: BamlStateSummary,
  graph: BamlCalculationGraph,
  registry: BamlNodeSummary[],
  clarifications: BamlQA[]
) -> GraphExtensionResult {
  client ClaudeHaiku45
  prompt #"
    You are extending an auditable typed calculation graph by satisfying exactly one unresolved named input.

    Current unresolved input:
    {{ current_unresolved }}

    Current state summary:
    {{ state_summary }}

    Current graph:
    {{ graph }}

    Type-compatible registry candidates. These are pre-filtered by Python so every candidate output should match current_unresolved.input_type:
    {{ registry }}

    Prior clarification answers for this graph-building phase:
    {{ clarifications }}

    Decision rules:
    - Prefer ConnectExisting when a node already in graph.nodes clearly produces the required value.
    - Use AddFromRegistry when exactly one registry candidate clearly should be added.
    - Use ApplicabilityCheck when multiple candidates could apply and user domain judgment is needed.
    - Use NoCandidate when no provided candidate can satisfy the unresolved input.
    - Do not invent node ids.
    - All edges will be added by Python using current_unresolved.node_id, input_name, and input_type.
    - Keep updated_state_summary concise and include any decision made.

    {{ ctx.output_format }}
  "#
}

test extend_graph_add_from_registry_example {
  functions [ExtendGraph]
  args {
    current_unresolved {
      node_id "format_result"
      input_name "doubled"
      input_type "calc_types.example.DoubledValue"
    }
    state_summary {
      goal "Example doubling calculation"
      decisions []
      open_items []
      phase1_clarification_summary ""
    }
    graph {
      name "example_doubling"
      terminal_node_id "format_result"
      nodes ["format_result"]
      edges []
    }
    registry [
      {
        id "double_value"
        node_type "computation"
        description "Double an input value."
        when_to_use "Use when a BaseValue should be multiplied by two."
        assumptions []
        inputs [
          {
            name "base"
            type "calc_types.example.BaseValue"
          }
        ]
        output "calc_types.example.DoubledValue"
        references []
      }
    ]
    clarifications []
  }
}

test extend_graph_applicability_example {
  functions [ExtendGraph]
  args {
    current_unresolved {
      node_id "format_result"
      input_name "doubled"
      input_type "calc_types.example.DoubledValue"
    }
    state_summary {
      goal "Example doubling calculation"
      decisions []
      open_items []
      phase1_clarification_summary ""
    }
    graph {
      name "example_doubling"
      terminal_node_id "format_result"
      nodes ["format_result"]
      edges []
    }
    registry [
      {
        id "double_value"
        node_type "computation"
        description "Double an input value."
        when_to_use "Use when a BaseValue should be multiplied by two."
        assumptions []
        inputs [
          {
            name "base"
            type "calc_types.example.BaseValue"
          }
        ]
        output "calc_types.example.DoubledValue"
        references []
      },
      {
        id "alternate_double_value"
        node_type "computation"
        description "Alternate way to produce a doubled value."
        when_to_use "Use only when the alternate method is specified."
        assumptions ["Requires engineer confirmation."]
        inputs [
          {
            name "base"
            type "calc_types.example.BaseValue"
          }
        ]
        output "calc_types.example.DoubledValue"
        references []
      }
    ]
    clarifications []
  }
}

test extend_graph_no_candidate_example {
  functions [ExtendGraph]
  args {
    current_unresolved {
      node_id "double_value"
      input_name "base"
      input_type "calc_types.example.BaseValue"
    }
    state_summary {
      goal "Example doubling calculation"
      decisions ["Use double_value to produce calc_types.example.DoubledValue."]
      open_items []
      phase1_clarification_summary ""
    }
    graph {
      name "example_doubling"
      terminal_node_id "format_result"
      nodes ["format_result", "double_value"]
      edges [
        {
          from_node "double_value"
          to_node "format_result"
          to_input "doubled"
          type "calc_types.example.DoubledValue"
        }
      ]
    }
    registry []
    clarifications []
  }
}

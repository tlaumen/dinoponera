// Provider configuration for Dinoponera planner functions.
// Set ANTHROPIC_API_KEY before running live BAML tests or planner calls.

client<llm> ClaudeHaiku45 {
  provider anthropic
  options {
    model "claude-haiku-4-5-20251001"
    api_key env.ANTHROPIC_API_KEY
  }
}

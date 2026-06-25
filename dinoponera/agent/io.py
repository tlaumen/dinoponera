"""User interaction boundary for planning workflows."""

from __future__ import annotations

from typing import Protocol

from dinoponera.core.models import (
    ApplicabilityResponse,
    CalculationGraph,
    NodeSummary,
    SourceGapResponse,
    StateSummary,
    UnresolvedInput,
)


class UserInteractor(Protocol):
    def ask_clarification(self, question: str, context: str | None = None) -> str: ...

    def confirm_goal(self, calculation_type: str, terminal_node_id: str) -> bool: ...

    def resolve_applicability(
        self,
        question: str,
        candidates: list[NodeSummary],
    ) -> ApplicabilityResponse: ...

    def resolve_source_gap(
        self,
        gap: UnresolvedInput,
        state_summary: StateSummary,
    ) -> SourceGapResponse: ...

    def approve_graph(self, graph: CalculationGraph, rendered: str) -> bool: ...


class ConsoleInteractor:
    """Simple terminal implementation of UserInteractor."""

    def ask_clarification(self, question: str, context: str | None = None) -> str:
        if context:
            print(context)
        return input(f"{question}\n> ").strip()

    def confirm_goal(self, calculation_type: str, terminal_node_id: str) -> bool:
        print(f"Calculation type: {calculation_type}")
        print(f"Terminal node: {terminal_node_id}")
        return _prompt_yes_no("Proceed with this goal? [y/n] ")

    def resolve_applicability(
        self,
        question: str,
        candidates: list[NodeSummary],
    ) -> ApplicabilityResponse:
        print(question)
        for index, candidate in enumerate(candidates, start=1):
            print(
                f"{index}. {candidate.id} [{candidate.node_type}] -> {candidate.output}\n"
                f"   {candidate.description}"
            )
        print("r. reject all candidates")
        print("u. unsure / provide clarification")

        while True:
            choice = input("Choose a candidate, r, or u: ").strip().lower()
            if choice == "r":
                return ApplicabilityResponse(kind="rejected_all")
            if choice == "u":
                detail = input("Clarification detail: ").strip()
                return ApplicabilityResponse(kind="unsure", detail=detail)
            if choice.isdigit():
                index = int(choice)
                if 1 <= index <= len(candidates):
                    return ApplicabilityResponse(
                        kind="chosen",
                        node_id=candidates[index - 1].id,
                    )
            print("Invalid choice. Try again.")

    def resolve_source_gap(
        self,
        gap: UnresolvedInput,
        state_summary: StateSummary,
    ) -> SourceGapResponse:
        print(
            f"No computation candidate found for {gap.node_id}.{gap.input_name} "
            f"({gap.input_type})."
        )
        if state_summary.goal:
            print(f"Goal: {state_summary.goal}")
        print("1. create data retrieval leaf stub")
        print("2. create user input leaf stub")
        print("3. this requires a missing computation node")

        while True:
            choice = input("Choose 1, 2, or 3: ").strip()
            if choice == "1":
                detail = input("Optional rationale/detail: ").strip() or None
                return SourceGapResponse(kind="data_retrieval", detail=detail)
            if choice == "2":
                detail = input("Optional rationale/detail: ").strip() or None
                return SourceGapResponse(kind="user_input", detail=detail)
            if choice == "3":
                detail = input("Describe the missing computation: ").strip() or None
                return SourceGapResponse(kind="missing_computation", detail=detail)
            print("Invalid choice. Try again.")

    def approve_graph(self, graph: CalculationGraph, rendered: str) -> bool:
        print(rendered)
        return _prompt_yes_no("Approve this graph? [y/n] ")


def _prompt_yes_no(prompt: str) -> bool:
    while True:
        choice = input(prompt).strip().lower()
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no"}:
            return False
        print("Please answer y or n.")

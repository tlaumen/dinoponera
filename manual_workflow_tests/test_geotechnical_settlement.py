from __future__ import annotations

import pytest

from calc_types.settlement import SettlementParameters
from calc_types.soil import SoilLayer, SoilProfile
from registry import index as registry_index
from registry.nodes.calculate_settlement import calculate_settlement
from registry.nodes.derive_settlement_parameters_from_cpt import (
    derive_settlement_parameters_from_cpt,
)
from registry.nodes.hypothetical_cpt_data import hypothetical_cpt_data
from registry.nodes.interpret_cpt_soil_profile import interpret_cpt_soil_profile
from registry.nodes.prompt_settlement_parameters import prompt_settlement_parameters
from registry.nodes.prompt_soil_profile import prompt_soil_profile


def test_cpt_settlement_source_and_derivations_are_runnable() -> None:
    cpt = hypothetical_cpt_data()

    assert cpt.source_name == "hypothetical_cpt_file.csv"
    assert len(cpt.points) > 0

    soil_profile = interpret_cpt_soil_profile(cpt)
    assert len(soil_profile.layers) == len(cpt.points) - 1
    assert all(layer.compressibility_per_kpa > 0 for layer in soil_profile.layers)

    parameters = derive_settlement_parameters_from_cpt(cpt)
    assert parameters.surface_load_kpa > 0


def test_prompt_soil_profile_with_patched_input(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([
        "2",
        "sand",
        "0",
        "2",
        "0.05",
        "clay",
        "2",
        "5",
        "0.12",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    soil_profile = prompt_soil_profile()

    assert soil_profile == SoilProfile(
        layers=[
            SoilLayer(
                name="sand",
                top_m=0.0,
                bottom_m=2.0,
                compressibility_per_kpa=0.05,
            ),
            SoilLayer(
                name="clay",
                top_m=2.0,
                bottom_m=5.0,
                compressibility_per_kpa=0.12,
            ),
        ]
    )


def test_prompt_settlement_parameters_with_patched_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "100")

    parameters = prompt_settlement_parameters()

    assert parameters == SettlementParameters(surface_load_kpa=100.0)


def test_calculate_settlement_known_values() -> None:
    soil_profile = SoilProfile(
        layers=[
            SoilLayer(
                name="sand",
                top_m=0.0,
                bottom_m=2.0,
                compressibility_per_kpa=0.05,
            ),
            SoilLayer(
                name="clay",
                top_m=2.0,
                bottom_m=5.0,
                compressibility_per_kpa=0.12,
            ),
        ]
    )
    parameters = SettlementParameters(surface_load_kpa=100.0)

    result = calculate_settlement(soil_profile, parameters)

    assert result.total_settlement_mm == pytest.approx(46.0)
    assert [contribution.layer_name for contribution in result.contributions] == [
        "sand",
        "clay",
    ]
    assert [contribution.settlement_mm for contribution in result.contributions] == [
        pytest.approx(10.0),
        pytest.approx(36.0),
    ]
    assert any("manual workflow testing" in note for note in result.notes)


def test_registry_includes_settlement_manual_workflow_nodes() -> None:
    summaries = {summary.id: summary for summary in registry_index.summaries()}

    expected_node_ids = {
        "prompt_soil_profile",
        "prompt_settlement_parameters",
        "hypothetical_cpt_data",
        "interpret_cpt_soil_profile",
        "derive_settlement_parameters_from_cpt",
        "calculate_settlement",
    }
    assert expected_node_ids <= set(summaries)
    assert len(summaries) == len(registry_index.NODES)

    assert summaries["prompt_soil_profile"].node_type == "user_input"
    assert summaries["prompt_settlement_parameters"].node_type == "user_input"
    assert summaries["hypothetical_cpt_data"].node_type == "data_retrieval"
    assert summaries["calculate_settlement"].output == "calc_types.settlement.SettlementResult"
    assert summaries["prompt_soil_profile"].output == "calc_types.soil.SoilProfile"
    assert summaries["hypothetical_cpt_data"].output == "calc_types.cpt.CptData"
    assert summaries["calculate_settlement"].inputs[0].type == "calc_types.soil.SoilProfile"
    assert summaries["calculate_settlement"].inputs[1].type == (
        "calc_types.settlement.SettlementParameters"
    )

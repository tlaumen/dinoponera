from __future__ import annotations

from math import pi

import pytest

from calc_types.piled_foundation import PileFoundationParameters, PileGeometry
from registry import index as registry_index
from registry.nodes.calculate_pile_foundation_capacity import (
    calculate_pile_foundation_capacity,
)
from registry.nodes.derive_pile_foundation_parameters_from_cpt import (
    derive_pile_foundation_parameters_from_cpt,
)
from registry.nodes.hypothetical_cpt_data import hypothetical_cpt_data
from registry.nodes.manual_pile_geometry import manual_pile_geometry


def test_manual_pile_geometry_returns_representative_positive_geometry() -> None:
    geometry = manual_pile_geometry()

    assert geometry.diameter_m == pytest.approx(0.6)
    assert geometry.embedded_length_m == pytest.approx(12.0)
    assert geometry.diameter_m > 0
    assert geometry.embedded_length_m > 0


def test_derive_pile_foundation_parameters_from_cpt_known_values() -> None:
    cpt = hypothetical_cpt_data()

    parameters = derive_pile_foundation_parameters_from_cpt(cpt)

    assert parameters.unit_shaft_resistance_kpa == pytest.approx(48.5)
    assert parameters.unit_base_resistance_kpa == pytest.approx(1012.5)
    assert parameters.resistance_factor == pytest.approx(2.0)


def test_calculate_pile_foundation_capacity_known_values() -> None:
    cpt = hypothetical_cpt_data()
    geometry = PileGeometry(diameter_m=1.0, embedded_length_m=10.0)
    parameters = PileFoundationParameters(
        unit_shaft_resistance_kpa=50.0,
        unit_base_resistance_kpa=1000.0,
        resistance_factor=2.0,
    )

    result = calculate_pile_foundation_capacity(geometry, parameters, cpt)

    expected_shaft_capacity_kn = 50.0 * pi * 1.0 * 10.0
    expected_base_capacity_kn = 1000.0 * pi * 1.0**2 / 4
    expected_ultimate_capacity_kn = expected_shaft_capacity_kn + expected_base_capacity_kn
    assert result.shaft_capacity_kn == pytest.approx(expected_shaft_capacity_kn)
    assert result.base_capacity_kn == pytest.approx(expected_base_capacity_kn)
    assert result.ultimate_capacity_kn == pytest.approx(expected_ultimate_capacity_kn)
    assert result.design_capacity_kn == pytest.approx(expected_ultimate_capacity_kn / 2.0)
    assert any(cpt.source_name in note for note in result.notes)


def test_cpt_piled_foundation_workflow_is_runnable() -> None:
    cpt = hypothetical_cpt_data()
    geometry = manual_pile_geometry()
    parameters = derive_pile_foundation_parameters_from_cpt(cpt)

    result = calculate_pile_foundation_capacity(geometry, parameters, cpt)

    assert result.shaft_capacity_kn > 0
    assert result.base_capacity_kn > 0
    assert result.ultimate_capacity_kn == pytest.approx(
        result.shaft_capacity_kn + result.base_capacity_kn
    )
    assert result.design_capacity_kn == pytest.approx(
        result.ultimate_capacity_kn / parameters.resistance_factor
    )


def test_registry_includes_piled_foundation_manual_workflow_nodes() -> None:
    summaries = {summary.id: summary for summary in registry_index.summaries()}

    expected_node_ids = {
        "manual_pile_geometry",
        "derive_pile_foundation_parameters_from_cpt",
        "calculate_pile_foundation_capacity",
    }
    assert expected_node_ids <= set(summaries)
    assert len(summaries) == len(registry_index.NODES)

    assert summaries["manual_pile_geometry"].node_type == "user_input"
    assert summaries["manual_pile_geometry"].output == (
        "calc_types.piled_foundation.PileGeometry"
    )
    assert summaries["derive_pile_foundation_parameters_from_cpt"].inputs[0].type == (
        "calc_types.cpt.CptData"
    )
    assert summaries["derive_pile_foundation_parameters_from_cpt"].output == (
        "calc_types.piled_foundation.PileFoundationParameters"
    )
    assert summaries["calculate_pile_foundation_capacity"].output == (
        "calc_types.piled_foundation.PileFoundationResult"
    )
    assert [node_input.type for node_input in summaries["calculate_pile_foundation_capacity"].inputs] == [
        "calc_types.piled_foundation.PileGeometry",
        "calc_types.piled_foundation.PileFoundationParameters",
        "calc_types.cpt.CptData",
    ]

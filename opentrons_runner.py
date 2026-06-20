"""Opentrons machine call for the manual workflow."""

from __future__ import annotations

from typing import Any, Mapping

from polymer_indent.clients import OpentronsClient


class OpentronsFillRunner:
    name = "Opentrons Flex"

    def __init__(self, client: OpentronsClient):
        self.client = client

    def health(self) -> Mapping[str, Any]:
        payload = self.client.health()
        if payload.get("status") == "placeholder":
            return {"status": "ok", "device": "opentrons-placeholder", "skipped": True}
        return payload

    def run(self, *, well: str, params: Mapping[str, Any], run_id: str) -> dict[str, Any]:
        return self.client.run_fill(
            well=well,
            volume_ul=params.get("volume_ul", 350),
            source_well=params.get("source_well"),
            formulation=params.get("formulation"),
            run_id=run_id,
            flow_rate_ul_min=params.get("flow_rate_ul_min", 150),
            air_expulsion_ul=params.get("air_expulsion_ul", 20),
            tip_lift_height_mm=params.get("tip_lift_height_mm", 8),
            tip_rack_slot=params.get("tip_rack_slot", "A2"),
            tube_rack_slot=params.get("tube_rack_slot", "B2"),
            plate_slot=params.get("plate_slot", "D1"),
            plate_labware=params.get("plate_labware", "corning_96_wellplate_360ul_flat"),
        )

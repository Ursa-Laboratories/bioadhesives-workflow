"""Opentrons machine call for the manual workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .opentrons_client import OpentronsClient


class OpentronsFillRunner:
    name = "Opentrons Flex"

    def __init__(self, client: OpentronsClient, *, protocol_path: str | Path | None = None):
        self.client = client
        self.protocol_path = Path(protocol_path) if protocol_path is not None else None

    def health(self) -> Mapping[str, Any]:
        payload = self.client.health()
        if payload.get("status") == "placeholder":
            return {"status": "ok", "device": "opentrons-placeholder", "skipped": True}
        return payload

    def run_protocol(self, *, run_id: str) -> dict[str, Any]:
        if self.protocol_path is None:
            raise ValueError("missing Opentrons protocol path")
        return self.client.run_protocol_file(self.protocol_path, run_id=run_id)

    def run(self, *, well: str, params: Mapping[str, Any], run_id: str) -> dict[str, Any]:
        return self.client.run_fill(
            well=well,
            volume_ul=_required(params, "volume_ul"),
            source_well=_required(params, "source_well"),
            formulation=params.get("formulation"),
            run_id=run_id,
            flow_rate_ul_min=_required(params, "flow_rate_ul_min"),
            air_expulsion_ul=_required(params, "air_expulsion_ul"),
            tip_lift_height_mm=_required(params, "tip_lift_height_mm"),
            tip_rack_slot=_required(params, "tip_rack_slot"),
            tube_rack_slot=_required(params, "tube_rack_slot"),
            plate_slot=_required(params, "plate_slot"),
            plate_labware=_required(params, "plate_labware"),
        )


def _required(params: Mapping[str, Any], key: str) -> Any:
    if key not in params or params[key] is None:
        raise ValueError(f"missing required Opentrons setting: {key}")
    return params[key]

"""SHARC station machine call for the manual workflow."""

from __future__ import annotations

from typing import Any, Mapping

from .protocol_render import apply_overrides, render_protocol
from .station_client import StationBundle


class SharcCureRunner:
    name = "SHARC station"

    def __init__(self, station: StationBundle, *, mock_mode: bool = False):
        self.station = station
        self.mock_mode = mock_mode

    def health(self) -> Mapping[str, Any]:
        return self.station.client.health()

    def validate(self, *, well: str, params: Mapping[str, Any]) -> dict[str, Any]:
        protocol_yaml = render_sharc_protocol(self.station.base_protocol_yaml, well, params)
        return self.station.client.validate_protocol(protocol_yaml)

    def run(self, *, well: str, params: Mapping[str, Any], run_id: str) -> dict[str, Any]:
        protocol_yaml = render_sharc_protocol(self.station.base_protocol_yaml, well, params)
        return self.station.client.run_protocol(
            run_id=run_id,
            protocol_yaml=protocol_yaml,
            metadata={"experiment_id": _experiment_id(run_id), "well": well, "step": "sharc"},
            mock_mode=self.mock_mode,
        )


def render_sharc_protocol(base_protocol_yaml: str, well: str, params: Mapping[str, Any]) -> str:
    scalar = _mapping(params.get("sharc_scalar"))
    method_kwargs = _mapping(params.get("sharc_method_kwargs"))
    if params.get("uv_measurement_height") is not None:
        scalar["measurement_height"] = params["uv_measurement_height"]
    if params.get("uv_intensity") is not None:
        method_kwargs["intensity"] = params["uv_intensity"]
    if params.get("uv_exposure_s") is not None:
        method_kwargs["exposure_time"] = params["uv_exposure_s"]
    return render_protocol(
        apply_overrides(base_protocol_yaml, scalar=scalar, method_kwargs=method_kwargs),
        well,
    )


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"protocol override must be a mapping, got {type(value).__name__}")
    return dict(value)


def _experiment_id(run_id: str) -> str:
    return run_id.split(":", 1)[0]

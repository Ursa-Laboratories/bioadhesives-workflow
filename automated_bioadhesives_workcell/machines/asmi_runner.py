"""ASMI station machine call for the automated workflow."""

from __future__ import annotations

from typing import Any, Mapping

from .protocol_render import apply_overrides, render_protocol
from .station_client import StationBundle


class AsmiIndentationRunner:
    name = "ASMI station"

    def __init__(self, station: StationBundle, *, mock_mode: bool = False):
        self.station = station
        self.mock_mode = mock_mode

    def health(self) -> Mapping[str, Any]:
        return self.station.client.health()

    def validate(self, *, well: str, params: Mapping[str, Any]) -> dict[str, Any]:
        protocol_yaml = render_asmi_protocol(self.station.base_protocol_yaml, well, params)
        return self.station.client.validate_protocol(protocol_yaml)

    def run(self, *, well: str, params: Mapping[str, Any], run_id: str) -> dict[str, Any]:
        protocol_yaml = render_asmi_protocol(self.station.base_protocol_yaml, well, params)
        return self.station.client.run_protocol(
            run_id=run_id,
            protocol_yaml=protocol_yaml,
            metadata={"experiment_id": _experiment_id(run_id), "well": well, "step": "asmi"},
            mock_mode=self.mock_mode,
        )


def render_asmi_protocol(base_protocol_yaml: str, well: str, params: Mapping[str, Any]) -> str:
    scalar = _mapping(params.get("asmi_scalar"))
    method_kwargs = _mapping(params.get("asmi_method_kwargs"))
    for source, target in {
        "asmi_measurement_height": "measurement_height",
        "measurement_height": "measurement_height",
        "asmi_indentation_limit_height": "indentation_limit_height",
        "indentation_limit_height": "indentation_limit_height",
        "asmi_interwell_scan_height": "interwell_scan_height",
        "interwell_scan_height": "interwell_scan_height",
    }.items():
        if params.get(source) is not None:
            scalar[target] = params[source]
    for source, target in {
        "asmi_step_size": "step_size",
        "step_size": "step_size",
        "asmi_force_limit": "force_limit",
        "force_limit": "force_limit",
        "asmi_baseline_samples": "baseline_samples",
        "baseline_samples": "baseline_samples",
        "asmi_measure_with_return": "measure_with_return",
        "measure_with_return": "measure_with_return",
    }.items():
        if params.get(source) is not None:
            method_kwargs[target] = params[source]
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

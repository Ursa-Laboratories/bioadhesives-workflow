"""Data models for the manual bioadhesives workcell."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from polymer_indent.experiment import Experiment

_WELL_RE = re.compile(r"^[A-Za-z]+[0-9]+$")
_NESTED_PARAM_KEYS = (
    "sharc_scalar",
    "sharc_method_kwargs",
    "asmi_scalar",
    "asmi_method_kwargs",
)


@dataclass(frozen=True)
class WorkflowWell:
    """One target well in the manual workflow."""

    target_well: str
    source_well: str = "A1"
    uv_exposure_s: float = 11.0
    formulation: str | None = None
    opentrons: Mapping[str, Any] = field(default_factory=dict)
    sharc_scalar: Mapping[str, Any] = field(default_factory=dict)
    sharc_method_kwargs: Mapping[str, Any] = field(default_factory=dict)
    asmi_scalar: Mapping[str, Any] = field(default_factory=dict)
    asmi_method_kwargs: Mapping[str, Any] = field(default_factory=dict)
    params: Mapping[str, Any] = field(default_factory=dict)

    def to_params(self, shared_params: Mapping[str, Any]) -> dict[str, Any]:
        params = _copy_shared_params(shared_params)
        params.update(dict(self.opentrons))
        params.update(dict(self.params))
        _merge_nested(params, "sharc_scalar", self.sharc_scalar)
        _merge_nested(params, "sharc_method_kwargs", self.sharc_method_kwargs)
        _merge_nested(params, "asmi_scalar", self.asmi_scalar)
        _merge_nested(params, "asmi_method_kwargs", self.asmi_method_kwargs)
        params["source_well"] = normalize_well(self.source_well)
        params["formulation"] = self.formulation or params["source_well"]
        params["uv_exposure_s"] = self.uv_exposure_s
        return params

    def raw(self) -> dict[str, Any]:
        return {
            "target_well": normalize_well(self.target_well),
            "source_well": normalize_well(self.source_well),
            "uv_exposure_s": self.uv_exposure_s,
            "formulation": self.formulation,
            "opentrons": dict(self.opentrons),
            "sharc_scalar": dict(self.sharc_scalar),
            "sharc_method_kwargs": dict(self.sharc_method_kwargs),
            "asmi_scalar": dict(self.asmi_scalar),
            "asmi_method_kwargs": dict(self.asmi_method_kwargs),
            "params": dict(self.params),
        }


def build_experiment(
    *,
    experiment_id: str,
    wells: Sequence[WorkflowWell],
    shared_params: Mapping[str, Any],
) -> Experiment:
    """Build the Experiment object used by ResultStore and the workflow."""
    if not wells:
        raise ValueError("manual workflow needs at least one well")

    ordered_wells: list[str] = []
    params_by_well: dict[str, dict[str, Any]] = {}
    for spec in wells:
        well = normalize_well(spec.target_well)
        if well in params_by_well:
            raise ValueError(f"workflow well {well} listed twice")
        ordered_wells.append(well)
        params_by_well[well] = spec.to_params(shared_params)

    return Experiment(
        id=experiment_id,
        wells=ordered_wells,
        params=params_by_well,
        defaults=dict(shared_params),
        raw={
            "experiment_id": experiment_id,
            "workflow": "manual_bioadhesives_workcell",
            "wells": [spec.raw() for spec in wells],
            "shared_params": _json_ready(shared_params),
        },
    )


def normalize_well(well: str) -> str:
    value = str(well).strip().upper()
    if not _WELL_RE.match(value):
        raise ValueError(f"not a well id: {well!r}")
    return value


def _copy_shared_params(shared_params: Mapping[str, Any]) -> dict[str, Any]:
    params = dict(shared_params)
    for key in _NESTED_PARAM_KEYS:
        value = params.get(key)
        if value is not None:
            if not isinstance(value, Mapping):
                raise TypeError(f"{key} must be a mapping")
            params[key] = dict(value)
    return params


def _merge_nested(params: dict[str, Any], key: str, value: Mapping[str, Any]) -> None:
    if not value:
        return
    merged = dict(params.get(key) or {})
    merged.update(dict(value))
    params[key] = merged


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value

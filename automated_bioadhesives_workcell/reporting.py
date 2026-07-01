"""Joined ASMI-shaped CSV export for the automated workflow."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

EXPORT_COLUMNS = [
    "experiment_id",
    "well",
    "sample_index",
    "timestamp_s",
    "relative_time_s",
    "z_position_mm",
    "indentation_distance_mm",
    "raw_force_n",
    "corrected_force_n",
    "direction",
    "source_well",
    "formulation",
    "volume_ul",
    "flow_rate_ul_min",
    "opentrons_source_well",
    "opentrons_volume_dispensed_ul",
    "opentrons_run_id",
    "opentrons_robot_run_id",
    "opentrons_status",
    "sharc_run_id",
    "sharc_success",
    "sharc_exposure_time_s",
    "sharc_intensity",
    "sharc_result_path",
    "sharc_run_dir",
    "asmi_run_id",
    "asmi_success",
    "asmi_baseline_avg_n",
    "asmi_baseline_std_n",
    "asmi_force_exceeded",
    "asmi_result_path",
    "asmi_run_dir",
]


def export_joined_asmi_csv(db_path: str | Path, experiment_id: str, csv_path: str | Path) -> Path:
    """Export one CSV row for every ASMI force sample in an experiment."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = load_joined_asmi_rows(db_path, experiment_id)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def load_joined_asmi_rows(db_path: str | Path, experiment_id: str) -> list[dict[str, str]]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        wells = con.execute(
            "SELECT rowid, well, params_json FROM wells WHERE experiment_id=? ORDER BY rowid",
            (experiment_id,),
        ).fetchall()
        runs = con.execute(
            "SELECT * FROM runs WHERE experiment_id=? "
            "AND kind IN ('opentrons_fill', 'sharc', 'asmi') ORDER BY started_at",
            (experiment_id,),
        ).fetchall()
    finally:
        con.close()

    runs_by_well: dict[str, dict[str, sqlite3.Row]] = {}
    for run in runs:
        if run["well"]:
            runs_by_well.setdefault(run["well"], {})[run["kind"]] = run

    output_rows: list[dict[str, str]] = []
    for well_row in wells:
        output_rows.extend(_rows_for_well(experiment_id, well_row, runs_by_well.get(well_row["well"], {})))
    return output_rows


def _rows_for_well(
    experiment_id: str,
    well_row: sqlite3.Row,
    runs: Mapping[str, sqlite3.Row],
) -> list[dict[str, str]]:
    params = _loads(well_row["params_json"], {})
    opentrons = runs.get("opentrons_fill")
    sharc = runs.get("sharc")
    asmi = runs.get("asmi")

    opentrons_payload = _loads(opentrons["result_json"], {}) if opentrons else {}
    sharc_payload = _extract_station_payload(
        _loads(sharc["result_json"], None) if sharc else None,
        preferred_keys=("exposure_time", "intensity", "readings", "mean_n"),
    )
    sharc_artifacts = _loads(sharc["artifacts_json"], {}) if sharc else {}
    asmi_payload = _extract_station_payload(
        _loads(asmi["result_json"], None) if asmi else None,
        preferred_keys=("measurements", "z_positions", "raw_forces", "corrected_forces"),
    )
    asmi_artifacts = _loads(asmi["artifacts_json"], {}) if asmi else {}
    samples = _asmi_samples(asmi_payload)
    if not samples:
        return []

    first_timestamp = _first_number(sample.get("timestamp_s") for sample in samples)
    measurement_height = _number(_param_value(
        params,
        direct=("asmi_measurement_height", "measurement_height"),
        nested=("asmi_scalar", "measurement_height"),
    ))
    first_z = _first_number(sample.get("z_position_mm") for sample in samples)

    rows: list[dict[str, str]] = []
    for index, sample in enumerate(samples):
        timestamp = _number(sample.get("timestamp_s"))
        z_position = _number(sample.get("z_position_mm"))
        rows.append(
            {
                "experiment_id": experiment_id,
                "well": well_row["well"],
                "sample_index": _cell(index),
                "timestamp_s": _cell(sample.get("timestamp_s")),
                "relative_time_s": _cell(_relative_time(timestamp, first_timestamp)),
                "z_position_mm": _cell(sample.get("z_position_mm")),
                "indentation_distance_mm": _cell(_indentation_distance(
                    z_position,
                    measurement_height=measurement_height,
                    first_z=first_z,
                )),
                "raw_force_n": _cell(sample.get("raw_force_n")),
                "corrected_force_n": _cell(sample.get("corrected_force_n")),
                "direction": _cell(sample.get("direction")),
                "source_well": _cell(params.get("source_well")),
                "formulation": _cell(params.get("formulation")),
                "volume_ul": _cell(params.get("volume_ul")),
                "flow_rate_ul_min": _cell(params.get("flow_rate_ul_min")),
                "opentrons_source_well": _cell(opentrons_payload.get("source_well")),
                "opentrons_volume_dispensed_ul": _cell(opentrons_payload.get("volume_dispensed")),
                "opentrons_run_id": _run_cell(opentrons),
                "opentrons_robot_run_id": _cell(opentrons_payload.get("opentrons_run_id")),
                "opentrons_status": _cell(opentrons_payload.get("status")),
                "sharc_run_id": _run_cell(sharc),
                "sharc_success": _success_cell(sharc),
                "sharc_exposure_time_s": _cell(_station_or_param(
                    sharc_payload,
                    params,
                    station_key="exposure_time",
                    param_keys=("uv_exposure_s",),
                    nested=("sharc_method_kwargs", "exposure_time"),
                )),
                "sharc_intensity": _cell(_station_or_param(
                    sharc_payload,
                    params,
                    station_key="intensity",
                    param_keys=("uv_intensity",),
                    nested=("sharc_method_kwargs", "intensity"),
                )),
                "sharc_result_path": _cell(sharc_artifacts.get("result_path")),
                "sharc_run_dir": _cell(sharc_artifacts.get("run_dir")),
                "asmi_run_id": _run_cell(asmi),
                "asmi_success": _success_cell(asmi),
                "asmi_baseline_avg_n": _cell(_mapping_get(asmi_payload, "baseline_avg")),
                "asmi_baseline_std_n": _cell(_mapping_get(asmi_payload, "baseline_std")),
                "asmi_force_exceeded": _cell(_mapping_get(asmi_payload, "force_exceeded")),
                "asmi_result_path": _cell(asmi_artifacts.get("result_path")),
                "asmi_run_dir": _cell(asmi_artifacts.get("run_dir")),
            }
        )
    return rows


def _asmi_samples(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    measurements = payload.get("measurements")
    if isinstance(measurements, list):
        return [
            {
                "timestamp_s": sample.get("timestamp"),
                "z_position_mm": sample.get("z_mm"),
                "raw_force_n": sample.get("raw_force_n"),
                "corrected_force_n": sample.get("corrected_force_n"),
                "direction": sample.get("direction", "down"),
            }
            for sample in measurements
            if isinstance(sample, Mapping)
        ]

    z_positions = payload.get("z_positions") or []
    raw_forces = payload.get("raw_forces") or []
    corrected_forces = payload.get("corrected_forces") or []
    timestamps = payload.get("sample_timestamps") or []
    directions = payload.get("directions") or []
    count = max(len(z_positions), len(raw_forces), len(corrected_forces), len(timestamps), len(directions))
    return [
        {
            "timestamp_s": _at(timestamps, index),
            "z_position_mm": _at(z_positions, index),
            "raw_force_n": _at(raw_forces, index),
            "corrected_force_n": _at(corrected_forces, index),
            "direction": _at(directions, index),
        }
        for index in range(count)
    ]


def _extract_station_payload(value: Any, *, preferred_keys: tuple[str, ...]) -> Any:
    if isinstance(value, list):
        for item in value:
            found = _extract_station_payload(item, preferred_keys=preferred_keys)
            if isinstance(found, Mapping) and any(key in found for key in preferred_keys):
                return found
        return None
    if isinstance(value, Mapping):
        if any(key in value for key in preferred_keys):
            return value
        for child in value.values():
            found = _extract_station_payload(child, preferred_keys=preferred_keys)
            if isinstance(found, Mapping) and any(key in found for key in preferred_keys):
                return found
    return None


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _station_or_param(
    station_payload: Any,
    params: Mapping[str, Any],
    *,
    station_key: str,
    param_keys: tuple[str, ...],
    nested: tuple[str, str],
) -> Any:
    if isinstance(station_payload, Mapping) and station_payload.get(station_key) is not None:
        return station_payload[station_key]
    for key in param_keys:
        if params.get(key) is not None:
            return params[key]
    nested_value = params.get(nested[0])
    if isinstance(nested_value, Mapping):
        return nested_value.get(nested[1])
    return None


def _param_value(
    params: Mapping[str, Any],
    *,
    direct: tuple[str, ...],
    nested: tuple[str, str],
) -> Any:
    for key in direct:
        if params.get(key) is not None:
            return params[key]
    nested_value = params.get(nested[0])
    if isinstance(nested_value, Mapping):
        return nested_value.get(nested[1])
    return None


def _indentation_distance(
    z_position: float | None,
    *,
    measurement_height: float | None,
    first_z: float | None,
) -> float | None:
    if z_position is None:
        return None
    if measurement_height is not None:
        return abs(round(measurement_height - z_position, 10))
    if first_z is not None:
        return abs(round(first_z - z_position, 10))
    return None


def _relative_time(timestamp: float | None, first_timestamp: float | None) -> float | None:
    if timestamp is None or first_timestamp is None:
        return None
    return round(timestamp - first_timestamp, 10)


def _first_number(values) -> float | None:
    for value in values:
        parsed = _number(value)
        if parsed is not None:
            return parsed
    return None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _at(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def _mapping_get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, Mapping) else None


def _run_cell(row: sqlite3.Row | None) -> str:
    return "" if row is None else _cell(row["run_id"])


def _success_cell(row: sqlite3.Row | None) -> str:
    if row is None or row["success"] is None:
        return ""
    return "true" if bool(row["success"]) else "false"


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)

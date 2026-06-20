"""Editable defaults for the manual bioadhesives workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polymer_indent.clients import CubOSStationClient
from polymer_indent.clients import OpentronsClient
from polymer_indent.config import load_controller_config
from polymer_indent.loop import StationBundle

from .asmi_runner import AsmiIndentationRunner
from .models import WorkflowWell, build_experiment
from .opentrons_runner import OpentronsFillRunner
from .sharc_runner import SharcCureRunner
from .workflow import ManualBioadhesivesWorkflow, ManualRunners

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent

EXPERIMENT_ID = "bioadhesives_manual_no_arm"
CONTROLLER_CONFIG = REPO_ROOT / "configs" / "controller.yaml"
SHARC_PROTOCOL = PACKAGE_ROOT / "protocols" / "sharc_uv_one_well.yaml"
ASMI_PROTOCOL = PACKAGE_ROOT / "protocols" / "asmi_indentation_a1.yaml"

WORKFLOW_WELLS = [
    WorkflowWell(target_well="A1", source_well="A1", uv_exposure_s=11.0),
]

OPENTRONS_TIP_RACK_SLOT = "A2"
OPENTRONS_TUBE_RACK_SLOT = "B2"
OPENTRONS_PLATE_SLOT = "D1"
OPENTRONS_PLATE_LABWARE = "corning_96_wellplate_360ul_flat"
OPENTRONS_VOLUME_UL = 100
OPENTRONS_FLOW_RATE_UL_MIN = 150
OPENTRONS_AIR_EXPULSION_UL = 20
OPENTRONS_TIP_LIFT_HEIGHT_MM = 8

UV_INTENSITY = 1

ASMI_MEASUREMENT_HEIGHT = -3.0
ASMI_INDENT_LIMIT_HEIGHT = -5.0
ASMI_STEP_SIZE = 0.01
ASMI_FORCE_LIMIT = 3.0
ASMI_BASELINE_SAMPLES = 10
ASMI_MEASURE_WITH_RETURN = False

MOCK_STATIONS = False
SKIP_OPENTRONS_FILL = False


@dataclass(frozen=True)
class ManualWorkflowSettings:
    experiment_id: str = EXPERIMENT_ID
    controller_config: Path = CONTROLLER_CONFIG
    output_csv: Path | None = None
    wells: list[WorkflowWell] | None = None
    mock_stations: bool = MOCK_STATIONS
    skip_opentrons_fill: bool = SKIP_OPENTRONS_FILL


def build_workflow(
    settings: ManualWorkflowSettings,
    *,
    input_fn=input,
    output_fn=print,
) -> ManualBioadhesivesWorkflow:
    cfg = load_controller_config(settings.controller_config)
    experiment = build_experiment(
        experiment_id=settings.experiment_id,
        wells=settings.wells or WORKFLOW_WELLS,
        shared_params=shared_params(),
    )
    opentrons_client = OpentronsClient(None) if settings.skip_opentrons_fill else cfg.opentrons_client()
    runners = ManualRunners(
        opentrons=OpentronsFillRunner(opentrons_client),
        sharc=SharcCureRunner(
            _station_bundle_with_protocol(cfg, "sharc", SHARC_PROTOCOL),
            mock_mode=settings.mock_stations,
        ),
        asmi=AsmiIndentationRunner(
            _station_bundle_with_protocol(cfg, "asmi", ASMI_PROTOCOL),
            mock_mode=settings.mock_stations,
        ),
    )
    output_csv = settings.output_csv or (cfg.root / "results" / f"{settings.experiment_id}_manual_joined_asmi.csv")
    return ManualBioadhesivesWorkflow(
        experiment=experiment,
        runners=runners,
        db_path=cfg.db_path,
        output_csv=output_csv,
        input_fn=input_fn,
        output_fn=output_fn,
    )


def _station_bundle_with_protocol(cfg, station_name: str, protocol_path: Path) -> StationBundle:
    station_cfg = cfg.raw["stations"][station_name]
    gantry_yaml = cfg._abs(station_cfg["gantry_config"]).read_text()
    deck_yaml = cfg._abs(station_cfg["deck_config"]).read_text()
    client = CubOSStationClient(
        base_url=station_cfg["base_url"],
        station=station_name,
        gantry_config_yaml=gantry_yaml,
        deck_config_yaml=deck_yaml,
        timeout_s=float(station_cfg.get("timeout_s", 900.0)),
        mock_mode=cfg.mock_mode,
    )
    return StationBundle(
        client=client,
        base_protocol_yaml=protocol_path.read_text(),
    )


def shared_params() -> dict[str, Any]:
    return {
        "volume_ul": OPENTRONS_VOLUME_UL,
        "flow_rate_ul_min": OPENTRONS_FLOW_RATE_UL_MIN,
        "air_expulsion_ul": OPENTRONS_AIR_EXPULSION_UL,
        "tip_lift_height_mm": OPENTRONS_TIP_LIFT_HEIGHT_MM,
        "tip_rack_slot": OPENTRONS_TIP_RACK_SLOT,
        "tube_rack_slot": OPENTRONS_TUBE_RACK_SLOT,
        "plate_slot": OPENTRONS_PLATE_SLOT,
        "plate_labware": OPENTRONS_PLATE_LABWARE,
        "uv_intensity": UV_INTENSITY,
        "asmi_scalar": {
            "measurement_height": ASMI_MEASUREMENT_HEIGHT,
            "indentation_limit_height": ASMI_INDENT_LIMIT_HEIGHT,
        },
        "asmi_method_kwargs": {
            "step_size": ASMI_STEP_SIZE,
            "force_limit": ASMI_FORCE_LIMIT,
            "baseline_samples": ASMI_BASELINE_SAMPLES,
            "measure_with_return": ASMI_MEASURE_WITH_RETURN,
        },
    }

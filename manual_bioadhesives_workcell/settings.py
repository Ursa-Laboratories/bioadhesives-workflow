"""Editable defaults for the manual bioadhesives workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import load_controller_config
from .machines import (
    AsmiIndentationRunner,
    CubOSStationClient,
    OpentronsClient,
    OpentronsFillRunner,
    SharcCureRunner,
    StationBundle,
)
from .models import WorkflowWell, build_experiment
from .workflow import ManualBioadhesivesWorkflow, ManualRunners

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent

EXPERIMENT_ID = "bioadhesives_manual_no_arm"
CONTROLLER_CONFIG = REPO_ROOT / "configs" / "controller.yaml"
MACHINES_ROOT = PACKAGE_ROOT / "machines"
OPENTRONS_PROTOCOL = REPO_ROOT / "opentrons_pilot.py"
SHARC_PROTOCOL = MACHINES_ROOT / "protocols" / "sharc_uv_one_well.yaml"
ASMI_PROTOCOL = MACHINES_ROOT / "protocols" / "asmi_indentation_a1.yaml"

# Device endpoints used by this manual workflow. The arm worker is intentionally
# absent because plate moves are manual. Port 5004 belongs to arm_worker; SHARC
# and ASMI protocol calls go to station_worker, which serves /run-protocol.
OPENTRONS_HOST = "10.210.29.218"
OPENTRONS_PORT = 31950
OPENTRONS_BASE_URL = f"http://{OPENTRONS_HOST}:{OPENTRONS_PORT}"
OPENTRONS_TIMEOUT_S = 600.0

SHARC_HOST = "10.210.29.12"
SHARC_PORT = 8000
SHARC_BASE_URL = f"http://{SHARC_HOST}:{SHARC_PORT}"
SHARC_TIMEOUT_S = 900.0

ASMI_HOST = "10.210.29.17"
ASMI_PORT = 8000
ASMI_BASE_URL = f"http://{ASMI_HOST}:{ASMI_PORT}"
ASMI_TIMEOUT_S = 900.0

HEALTH_TIMEOUT_S = 3.0

# Define what reagent is in each source tube rack well.
REAGENT_SOURCES = {
    "pegda_a": "A1",
}

# SHARC Settings
UV_INTENSITY = 1
UV_EXPOSURE_S = 11.0

# Define what goes into the plate. Each WorkflowWell maps a reagent source tube
# to a target well on the well plate and the SHARC cure time for that well.
WORKFLOW_WELLS = [
    WorkflowWell(
        target_well="A1",
        source_well=REAGENT_SOURCES["pegda_a"],
        formulation="pegda_a",
        uv_exposure_s=UV_EXPOSURE_S,
    ),
]

# Define the Opentrons deck layout and plate labware used by the generated fill
# protocol.
OPENTRONS_TIP_RACK_SLOT = "A2"
OPENTRONS_TUBE_RACK_SLOT = "B2"
OPENTRONS_PLATE_SLOT = "D1"
OPENTRONS_PLATE_LABWARE = "corning_96_wellplate_360ul_flat"
OPENTRONS_VOLUME_UL = 100
OPENTRONS_FLOW_RATE_UL_MIN = 150 / 60
OPENTRONS_AIR_EXPULSION_UL = 20
OPENTRONS_TIP_LIFT_HEIGHT_MM = 8

# ASMI Settings
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
    opentrons_protocol: Path = OPENTRONS_PROTOCOL
    wells: list[WorkflowWell] | None = None
    opentrons_base_url: str | None = OPENTRONS_BASE_URL
    sharc_base_url: str = SHARC_BASE_URL
    asmi_base_url: str = ASMI_BASE_URL
    opentrons_timeout_s: float = OPENTRONS_TIMEOUT_S
    sharc_timeout_s: float = SHARC_TIMEOUT_S
    asmi_timeout_s: float = ASMI_TIMEOUT_S
    health_timeout_s: float = HEALTH_TIMEOUT_S
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
    opentrons_client = (
        OpentronsClient(None)
        if settings.skip_opentrons_fill
        else _opentrons_client(
            settings.opentrons_base_url,
            settings.opentrons_timeout_s,
            settings.health_timeout_s,
        )
    )
    runners = ManualRunners(
        opentrons=OpentronsFillRunner(opentrons_client, protocol_path=settings.opentrons_protocol),
        sharc=SharcCureRunner(
            _station_bundle_with_protocol(
                cfg,
                "sharc",
                SHARC_PROTOCOL,
                base_url=settings.sharc_base_url,
                timeout_s=settings.sharc_timeout_s,
                health_timeout_s=settings.health_timeout_s,
            ),
            mock_mode=settings.mock_stations,
        ),
        asmi=AsmiIndentationRunner(
            _station_bundle_with_protocol(
                cfg,
                "asmi",
                ASMI_PROTOCOL,
                base_url=settings.asmi_base_url,
                timeout_s=settings.asmi_timeout_s,
                health_timeout_s=settings.health_timeout_s,
            ),
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


def _station_bundle_with_protocol(
    cfg,
    station_name: str,
    protocol_path: Path,
    *,
    base_url: str,
    timeout_s: float,
    health_timeout_s: float,
) -> StationBundle:
    station_cfg = cfg.raw["stations"][station_name]
    gantry_yaml = cfg.abs_path(station_cfg["gantry_config"]).read_text()
    deck_yaml = cfg.abs_path(station_cfg["deck_config"]).read_text()
    client = CubOSStationClient(
        base_url=base_url,
        station=station_name,
        gantry_config_yaml=gantry_yaml,
        deck_config_yaml=deck_yaml,
        timeout_s=float(timeout_s),
        health_timeout_s=float(health_timeout_s),
        mock_mode=cfg.mock_mode,
    )
    return StationBundle(
        client=client,
        base_protocol_yaml=protocol_path.read_text(),
    )


def _opentrons_client(base_url: str | None, timeout_s: float, health_timeout_s: float) -> OpentronsClient:
    return OpentronsClient(
        base_url,
        timeout_s=float(timeout_s),
        health_timeout_s=float(health_timeout_s),
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

"""Editable defaults for the automated bioadhesives workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from manual_bioadhesives_workcell.config import load_controller_config
from manual_bioadhesives_workcell.models import WorkflowWell
from manual_bioadhesives_workcell.settings import (
    ASMI_BASE_URL,
    ASMI_TIMEOUT_S,
    CONTROLLER_CONFIG,
    HEALTH_TIMEOUT_S,
    MOCK_STATIONS,
    OPENTRONS_BASE_URL,
    OPENTRONS_TIMEOUT_S,
    SHARC_BASE_URL,
    SHARC_TIMEOUT_S,
    SKIP_ASMI,
    SKIP_OPENTRONS_FILL,
    SKIP_SHARC,
    WORKFLOW_WELLS,
    ManualWorkflowSettings,
    build_workflow as build_manual_workflow,
)

from .arm_client import ArmTransferClient
from .workflow import AutomatedBioadhesivesWorkflow, AutomatedRunners

EXPERIMENT_ID = "bioadhesives_automated_arm"
ARM_BASE_URL = "http://localhost:5004"
ARM_TIMEOUT_S = 300.0
MOCK_ARM = False


@dataclass(frozen=True)
class AutomatedWorkflowSettings:
    experiment_id: str = EXPERIMENT_ID
    controller_config: Path = CONTROLLER_CONFIG
    output_csv: Path | None = None
    wells: list[WorkflowWell] | None = None
    opentrons_base_url: str | None = OPENTRONS_BASE_URL
    sharc_base_url: str = SHARC_BASE_URL
    asmi_base_url: str = ASMI_BASE_URL
    arm_base_url: str | None = ARM_BASE_URL
    opentrons_timeout_s: float = OPENTRONS_TIMEOUT_S
    sharc_timeout_s: float = SHARC_TIMEOUT_S
    asmi_timeout_s: float = ASMI_TIMEOUT_S
    arm_timeout_s: float | None = ARM_TIMEOUT_S
    health_timeout_s: float = HEALTH_TIMEOUT_S
    mock_stations: bool = MOCK_STATIONS
    mock_arm: bool = MOCK_ARM
    skip_opentrons_fill: bool = SKIP_OPENTRONS_FILL
    skip_sharc: bool = SKIP_SHARC
    skip_asmi: bool = SKIP_ASMI


def build_workflow(
    settings: AutomatedWorkflowSettings,
    *,
    output_fn=print,
) -> AutomatedBioadhesivesWorkflow:
    cfg = load_controller_config(settings.controller_config)
    output_csv = settings.output_csv or (cfg.root / "results" / f"{settings.experiment_id}_automated_joined_asmi.csv")
    base = build_manual_workflow(
        ManualWorkflowSettings(
            experiment_id=settings.experiment_id,
            controller_config=settings.controller_config,
            output_csv=output_csv,
            wells=settings.wells,
            opentrons_base_url=settings.opentrons_base_url,
            sharc_base_url=settings.sharc_base_url,
            asmi_base_url=settings.asmi_base_url,
            opentrons_timeout_s=settings.opentrons_timeout_s,
            sharc_timeout_s=settings.sharc_timeout_s,
            asmi_timeout_s=settings.asmi_timeout_s,
            health_timeout_s=settings.health_timeout_s,
            mock_stations=settings.mock_stations,
            skip_opentrons_fill=settings.skip_opentrons_fill,
            skip_sharc=settings.skip_sharc,
            skip_asmi=settings.skip_asmi,
        ),
        output_fn=output_fn,
    )
    base.experiment.raw["workflow"] = "automated_bioadhesives_workcell"
    arm_cfg = cfg.raw.get("arm", {}) or {}
    arm_base_url = settings.arm_base_url or arm_cfg.get("base_url") or ARM_BASE_URL
    arm_timeout_s = settings.arm_timeout_s
    if arm_timeout_s is None:
        arm_timeout_s = float(arm_cfg.get("timeout_s", ARM_TIMEOUT_S))

    return AutomatedBioadhesivesWorkflow(
        experiment=base.experiment,
        runners=AutomatedRunners(
            opentrons=base.runners.opentrons,
            sharc=base.runners.sharc,
            asmi=base.runners.asmi,
            arm=ArmTransferClient(
                arm_base_url,
                timeout_s=float(arm_timeout_s),
                health_timeout_s=float(settings.health_timeout_s),
                mock_mode=settings.mock_arm,
            ),
        ),
        db_path=base.db_path,
        output_csv=output_csv,
        skip_opentrons_fill=settings.skip_opentrons_fill,
        skip_sharc=settings.skip_sharc,
        skip_asmi=settings.skip_asmi,
        mock_arm=settings.mock_arm,
        output_fn=output_fn,
    )


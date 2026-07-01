"""CLI entrypoint for the automated bioadhesives workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .settings import (
    ARM_BASE_URL,
    ARM_TIMEOUT_S,
    CONTROLLER_CONFIG,
    EXPERIMENT_ID,
    AutomatedWorkflowSettings,
    build_workflow,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m automated_bioadhesives_workcell",
        description="Run the bioadhesives workflow with robot-arm plate moves.",
    )
    parser.add_argument(
        "--config",
        default=str(CONTROLLER_CONFIG),
        help="controller config for gantry/deck paths and DB path",
    )
    parser.add_argument("--experiment-id", default=EXPERIMENT_ID)
    parser.add_argument("--output-csv", default=None, help="joined ASMI-shaped CSV path")
    parser.add_argument("--arm-url", default=ARM_BASE_URL, help="arm worker base URL")
    parser.add_argument("--arm-timeout-s", type=float, default=ARM_TIMEOUT_S, help="per-transfer arm timeout")
    parser.add_argument("--mock-stations", action="store_true", help="send mock_mode=True to SHARC and ASMI")
    parser.add_argument("--mock-arm", action="store_true", help="ask the arm worker to use logging-only stand-ins")
    parser.add_argument(
        "--skip-opentrons-fill",
        "--skip-opentrons",
        dest="skip_opentrons_fill",
        action="store_true",
        help="bypass the Opentrons fill stage",
    )
    parser.add_argument("--skip-sharc", action="store_true", help="bypass the SHARC cure stage")
    parser.add_argument("--skip-asmi", action="store_true", help="bypass the ASMI indentation stage")
    args = parser.parse_args(argv)

    workflow = build_workflow(
        AutomatedWorkflowSettings(
            experiment_id=args.experiment_id,
            controller_config=Path(args.config),
            output_csv=Path(args.output_csv) if args.output_csv else None,
            arm_base_url=args.arm_url,
            arm_timeout_s=args.arm_timeout_s,
            mock_stations=args.mock_stations,
            mock_arm=args.mock_arm,
            skip_opentrons_fill=args.skip_opentrons_fill,
            skip_sharc=args.skip_sharc,
            skip_asmi=args.skip_asmi,
        )
    )
    return workflow.run()


if __name__ == "__main__":
    sys.exit(main())


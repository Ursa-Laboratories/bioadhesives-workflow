"""CLI entrypoint for the automated bioadhesives workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .settings import (
    ARM_SERVER_HOST,
    ARM_SERVER_PORT,
    ARM_SERVER_PYTHON,
    ARM_SERVER_STARTUP_TIMEOUT_S,
    ARM_TIMEOUT_S,
    CONTROLLER_CONFIG,
    EXPERIMENT_ID,
    OT_PLATE_TYPE,
    REPO_ROOT,
    AutomatedWorkflowSettings,
    build_workflow,
)
from .arm_server_process import ArmServerSettings, ManagedArmServer


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
    parser.add_argument("--arm-python", default=ARM_SERVER_PYTHON, help="Python executable used to run the bundled arm server")
    parser.add_argument("--arm-host", default=ARM_SERVER_HOST, help="host/interface for the bundled arm server")
    parser.add_argument("--arm-port", type=int, default=ARM_SERVER_PORT, help="port for the bundled arm server")
    parser.add_argument(
        "--arm-startup-timeout-s",
        type=float,
        default=ARM_SERVER_STARTUP_TIMEOUT_S,
        help="seconds to wait for the bundled arm server /health endpoint",
    )
    parser.add_argument("--arm-timeout-s", type=float, default=ARM_TIMEOUT_S, help="per-transfer arm timeout")
    parser.add_argument("--mock-stations", action="store_true", help="send mock_mode=True to SHARC and ASMI")
    parser.add_argument("--mock-arm", action="store_true", help="run the bundled arm server with logging-only stand-ins")
    parser.add_argument(
        "--ot-plate",
        default=OT_PLATE_TYPE,
        choices=["black", "transparent"],
        help="Opentrons D1 plate variant for arm pickup poses",
    )
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

    arm_base_url = _arm_base_url(args.arm_host, args.arm_port)
    arm_server = ArmServerSettings(
        python=args.arm_python,
        host=args.arm_host,
        port=args.arm_port,
        base_url=arm_base_url,
        startup_timeout_s=args.arm_startup_timeout_s,
        mock_arm=args.mock_arm,
        ot_plate_type=args.ot_plate,
        cwd=REPO_ROOT,
    )
    with ManagedArmServer(arm_server):
        workflow = build_workflow(
            AutomatedWorkflowSettings(
                experiment_id=args.experiment_id,
                controller_config=Path(args.config),
                output_csv=Path(args.output_csv) if args.output_csv else None,
                arm_base_url=arm_base_url,
                arm_timeout_s=args.arm_timeout_s,
                mock_stations=args.mock_stations,
                mock_arm=args.mock_arm,
                skip_opentrons_fill=args.skip_opentrons_fill,
                skip_sharc=args.skip_sharc,
                skip_asmi=args.skip_asmi,
            )
        )
        return workflow.run()


def _arm_base_url(host: str, port: int) -> str:
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    return f"http://{connect_host}:{port}"


if __name__ == "__main__":
    sys.exit(main())

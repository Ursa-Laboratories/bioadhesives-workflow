"""CLI entrypoint for checking manual workflow machine health."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .settings import CONTROLLER_CONFIG, HEALTH_TIMEOUT_S, ManualWorkflowSettings, build_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m manual_bioadhesives_workcell.health_check",
        description="Check Opentrons, SHARC, and ASMI health without running the workflow.",
    )
    parser.add_argument(
        "--config",
        default=str(CONTROLLER_CONFIG),
        help="controller config for gantry/deck paths and DB path",
    )
    parser.add_argument(
        "--skip-opentrons-fill",
        "--skip-opentrons",
        dest="skip_opentrons_fill",
        action="store_true",
        help="skip the Opentrons health check",
    )
    parser.add_argument("--skip-sharc", action="store_true", help="skip the SHARC health check")
    parser.add_argument("--skip-asmi", action="store_true", help="skip the ASMI health check")
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=HEALTH_TIMEOUT_S,
        help="per-machine health request timeout in seconds",
    )
    args = parser.parse_args(argv)

    workflow = build_workflow(
        ManualWorkflowSettings(
            controller_config=Path(args.config),
            skip_opentrons_fill=args.skip_opentrons_fill,
            skip_sharc=args.skip_sharc,
            skip_asmi=args.skip_asmi,
            health_timeout_s=args.timeout_s,
        )
    )
    return 0 if workflow.health_check_all_machines() else 1


if __name__ == "__main__":
    sys.exit(main())

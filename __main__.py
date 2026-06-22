"""CLI entrypoint for the manual no-arm bioadhesives workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .settings import CONTROLLER_CONFIG, EXPERIMENT_ID, ManualWorkflowSettings, build_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the bioadhesives workflow with manual plate moves and no robot arm.",
    )
    parser.add_argument(
        "--config",
        default=str(CONTROLLER_CONFIG),
        help="controller config for gantry/deck paths and DB path",
    )
    parser.add_argument("--experiment-id", default=EXPERIMENT_ID)
    parser.add_argument("--output-csv", default=None, help="joined ASMI-shaped CSV path")
    parser.add_argument("--mock-stations", action="store_true", help="send mock_mode=True to SHARC and ASMI")
    parser.add_argument(
        "--skip-opentrons-fill",
        action="store_true",
        help="use the Opentrons placeholder client instead of touching the real Flex",
    )
    parser.add_argument("-y", "--yes", action="store_true", help="auto-confirm manual prompts")
    args = parser.parse_args(argv)

    input_fn = (lambda _prompt: "y") if args.yes else input
    workflow = build_workflow(
        ManualWorkflowSettings(
            experiment_id=args.experiment_id,
            controller_config=Path(args.config),
            output_csv=Path(args.output_csv) if args.output_csv else None,
            mock_stations=args.mock_stations,
            skip_opentrons_fill=args.skip_opentrons_fill,
        ),
        input_fn=input_fn,
    )
    return workflow.run()


if __name__ == "__main__":
    sys.exit(main())

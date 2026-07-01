"""Run the bundled xArm + Vention-rail transfer server."""

from __future__ import annotations

import argparse
import logging
import sys

from . import settings
from .arm_server_app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m automated_bioadhesives_workcell.arm_server",
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default=settings.ARM_SERVER_HOST)
    parser.add_argument("--port", type=int, default=settings.ARM_SERVER_PORT)
    parser.add_argument("--mock", action="store_true", help="default to mock_mode, with no xArm or rail hardware")
    parser.add_argument(
        "--ot-plate",
        default=settings.OT_PLATE_TYPE,
        choices=["black", "transparent"],
        help="Opentrons D1 plate variant for pickup poses",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    app = create_app(mock_mode_default=args.mock, ot_plate_type=args.ot_plate)
    logging.getLogger("automated_bioadhesives_workcell.arm_server").info(
        "arm server listening on %s:%d (mock_default=%s, ot_plate=%s)",
        args.host,
        args.port,
        args.mock,
        args.ot_plate,
    )
    app.run(host=args.host, port=args.port, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Automated bioadhesives workflow.

This keeps the manual workflow's Opentrons/SHARC/ASMI runner abstraction and
replaces the manual plate-transfer prompts with arm-worker transfer calls.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from manual_bioadhesives_workcell.health import (
    HealthTarget,
    failed_health_names,
    format_health_report,
    run_health_checks,
)
from manual_bioadhesives_workcell.result_store import ResultStore
from manual_bioadhesives_workcell.workflow import (
    MachineRunner,
    ManualBioadhesivesWorkflow,
    ManualRunners,
)

OPENTRONS_LOCATION = "opentrons"
SHARC_LOCATION = "uv_station"
ASMI_LOCATION = "asmi"


class ArmMover(Protocol):
    name: str

    def health(self) -> dict[str, Any]:
        ...

    def transfer(
        self,
        *,
        from_location: str,
        to_location: str,
        run_id: str,
        mock_mode: bool | None = None,
        skip_safe_prelude: bool = False,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class AutomatedRunners:
    opentrons: MachineRunner
    sharc: MachineRunner
    asmi: MachineRunner
    arm: ArmMover

    @property
    def manual(self) -> ManualRunners:
        return ManualRunners(opentrons=self.opentrons, sharc=self.sharc, asmi=self.asmi)


class AutomatedBioadhesivesWorkflow(ManualBioadhesivesWorkflow):
    def __init__(
        self,
        *,
        experiment,
        runners: AutomatedRunners,
        db_path: str | Path,
        output_csv: str | Path,
        skip_opentrons_fill: bool = False,
        skip_sharc: bool = False,
        skip_asmi: bool = False,
        mock_arm: bool = False,
        output_fn=print,
    ):
        super().__init__(
            experiment=experiment,
            runners=runners.manual,
            db_path=db_path,
            output_csv=output_csv,
            skip_opentrons_fill=skip_opentrons_fill,
            skip_sharc=skip_sharc,
            skip_asmi=skip_asmi,
            output_fn=output_fn,
        )
        self.runners = runners
        self.mock_arm = mock_arm

    def run(self) -> int:
        self.output_fn("1. Health check of all machines")
        if not self.health_check_all_machines():
            return 1

        self.output_fn("2. Well plate start location: Opentrons")

        status = "completed"
        exit_code = 0
        with ResultStore(self.db_path) as results:
            results.start_experiment(self.experiment)
            try:
                if self.skip_opentrons_fill:
                    self.output_fn("3. Skip Opentrons fill")
                else:
                    self.run_opentrons_code(results)

                if self._needs_sharc_location():
                    self.move_to_sharc(results)

                if self.skip_sharc:
                    self.output_fn("5. Skip SHARC")
                else:
                    self.run_sharc_code(results)

                if self.skip_asmi:
                    self.output_fn("6. Skip ASMI")
                else:
                    self.move_to_asmi(results)
                    self.run_asmi_code(results)

                self.mark_wells_done(results)
            except Exception as exc:  # noqa: BLE001 - hardware failures should close the run cleanly
                status = "failed"
                exit_code = 1
                self.output_fn(f"Failed: {type(exc).__name__}: {exc}")
            finally:
                results.finish_experiment(self.experiment.id, status)

        self.collect_data_join_and_save_csv()
        if exit_code == 0:
            self.output_fn("9. Finish")
        return exit_code

    def health_check_all_machines(self) -> bool:
        targets = [
            HealthTarget(
                "Opentrons Flex",
                _skipped_health("opentrons") if self.skip_opentrons_fill else self.runners.opentrons.health,
            ),
            HealthTarget(
                "SHARC station",
                _skipped_health("sharc")
                if self.skip_sharc
                else self._health_with_validation(self.runners.sharc),
            ),
            HealthTarget(
                "ASMI station",
                _skipped_health("asmi")
                if self.skip_asmi
                else self._health_with_validation(self.runners.asmi),
            ),
        ]
        if self._required_arm_routes():
            targets.append(HealthTarget("Robot arm", self._arm_health))

        results = run_health_checks(targets, progress_fn=self.output_fn)
        self.output_fn(format_health_report(results))

        failed = failed_health_names(results)
        if failed:
            self.output_fn(f"Aborting: offline or unready machine(s): {', '.join(failed)}")
            return False
        return True

    def move_to_sharc(self, results: ResultStore) -> None:
        self.output_fn("4. Move well plate to SHARC with robot arm")
        self._record_arm_transfer(
            results,
            run_id=f"{self.experiment.id}:move-to-sharc",
            from_location=OPENTRONS_LOCATION,
            to_location=SHARC_LOCATION,
        )

    def move_to_asmi(self, results: ResultStore) -> None:
        self.output_fn("6. Move well plate to ASMI with robot arm")
        self._record_arm_transfer(
            results,
            run_id=f"{self.experiment.id}:move-to-asmi",
            from_location=SHARC_LOCATION,
            to_location=ASMI_LOCATION,
        )

    def _record_arm_transfer(
        self,
        results: ResultStore,
        *,
        run_id: str,
        from_location: str,
        to_location: str,
    ) -> None:
        started = time.time()
        try:
            response = self.runners.arm.transfer(
                from_location=from_location,
                to_location=to_location,
                run_id=run_id,
                mock_mode=self.mock_arm,
            )
        except Exception as exc:
            results.record_run(
                run_id=run_id,
                experiment_id=self.experiment.id,
                well=None,
                kind="arm_transfer",
                station="xarm",
                success=False,
                started_at=started,
                finished_at=time.time(),
                result={"from": from_location, "to": to_location},
                error=f"{type(exc).__name__}: {exc}",
            )
            raise

        results.record_run(
            run_id=run_id,
            experiment_id=self.experiment.id,
            well=None,
            kind="arm_transfer",
            station="xarm",
            success=_require_success(response, "arm_transfer"),
            started_at=started,
            finished_at=time.time(),
            result={"from": from_location, "to": to_location, "response": response},
        )

    def _arm_health(self) -> dict[str, Any]:
        payload = self.runners.arm.health()
        missing = self._missing_arm_routes(payload)
        if missing:
            raise RuntimeError(f"missing required arm route(s): {', '.join(missing)}")
        return payload

    def _missing_arm_routes(self, payload: dict[str, Any]) -> list[str]:
        available = set(payload.get("routes") or [])
        return sorted(self._required_arm_routes() - available)

    def _required_arm_routes(self) -> set[str]:
        routes: set[str] = set()
        if self._needs_sharc_location():
            routes.add(f"{OPENTRONS_LOCATION}->{SHARC_LOCATION}")
        if not self.skip_asmi:
            routes.add(f"{SHARC_LOCATION}->{ASMI_LOCATION}")
        return routes

    def _needs_sharc_location(self) -> bool:
        return not (self.skip_sharc and self.skip_asmi)


def _require_success(response: dict[str, Any], kind: str) -> bool:
    if "success" not in response:
        raise RuntimeError(f"{kind} response missing 'success' field: {response!r}")
    return bool(response["success"])


def _skipped_health(device: str):
    return lambda: {"status": "skipped", "device": device, "skipped": True}

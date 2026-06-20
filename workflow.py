"""High-level manual bioadhesives workflow."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from polymer_indent.results import ResultStore

from .health import HealthTarget, failed_health_names, format_health_report, run_health_checks
from .reporting import export_joined_asmi_csv


class MachineRunner(Protocol):
    name: str

    def health(self) -> dict[str, Any]:
        ...

    def run(self, *, well: str, params: dict[str, Any], run_id: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ManualRunners:
    opentrons: MachineRunner
    sharc: MachineRunner
    asmi: MachineRunner


class OperatorAbort(RuntimeError):
    """Raised when the operator declines a manual-move prompt."""


class ManualBioadhesivesWorkflow:
    def __init__(
        self,
        *,
        experiment,
        runners: ManualRunners,
        db_path: str | Path,
        output_csv: str | Path,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        self.experiment = experiment
        self.runners = runners
        self.db_path = Path(db_path)
        self.output_csv = Path(output_csv)
        self.input_fn = input_fn
        self.output_fn = output_fn

    def run(self) -> int:
        self.output_fn("1. Health check of all machines")
        if not self.health_check_all_machines():
            return 1

        if not self.prompt_well_plate_in_opentrons():
            self.output_fn("Aborted before hardware workflow started.")
            return 130

        status = "completed"
        exit_code = 0
        with ResultStore(self.db_path) as results:
            results.start_experiment(self.experiment)
            try:
                self.run_opentrons_code(results)
                self.prompt_move_to_sharc()
                self.run_sharc_code(results)
                self.prompt_move_to_asmi()
                self.run_asmi_code(results)
            except OperatorAbort as exc:
                status = "aborted"
                exit_code = 130
                self.output_fn(f"Aborted: {exc}")
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
            HealthTarget("Opentrons Flex", self.runners.opentrons.health),
            HealthTarget("SHARC station", self.runners.sharc.health),
            HealthTarget("ASMI station", self.runners.asmi.health),
        ]
        results = run_health_checks(targets)
        self.output_fn(format_health_report(results))
        failed = failed_health_names(results)
        if failed:
            self.output_fn(f"Aborting: offline or unready machine(s): {', '.join(failed)}")
            return False
        return True

    def prompt_well_plate_in_opentrons(self) -> bool:
        self.output_fn("2. Prompt user to verify well plate is in the OpenTrons")
        return self._confirm("Confirm the well plate is in the Opentrons, then press y [y/N]: ")

    def run_opentrons_code(self, results: ResultStore) -> None:
        self.output_fn("3. Run Opentrons code")
        self._run_stage(results, runner=self.runners.opentrons, kind="opentrons_fill", station="opentrons", tag="fill")

    def prompt_move_to_sharc(self) -> None:
        self.output_fn("4. Prompt for manual move to SHARC")
        if not self._confirm("Manual move to SHARC complete. Press y to run SHARC [y/N]: "):
            raise OperatorAbort("operator stopped before SHARC")

    def run_sharc_code(self, results: ResultStore) -> None:
        self.output_fn("5. Run SHARC code")
        self._run_stage(results, runner=self.runners.sharc, kind="sharc", station="sharc", tag="sharc")

    def prompt_move_to_asmi(self) -> None:
        self.output_fn("6. Prompt to move to ASMI")
        if not self._confirm("Manual move to ASMI complete. Press y to run ASMI [y/N]: "):
            raise OperatorAbort("operator stopped before ASMI")

    def run_asmi_code(self, results: ResultStore) -> None:
        self.output_fn("7. Run ASMI code")
        self._run_stage(results, runner=self.runners.asmi, kind="asmi", station="asmi", tag="asmi", mark_done=True)

    def collect_data_join_and_save_csv(self) -> None:
        self.output_fn("8. Collect data, join Opentrons/SHARC/ASMI data, and save CSV")
        export_joined_asmi_csv(self.db_path, self.experiment.id, self.output_csv)
        self.output_fn(f"CSV saved: {self.output_csv}")

    def _run_stage(
        self,
        results: ResultStore,
        *,
        runner: MachineRunner,
        kind: str,
        station: str,
        tag: str,
        mark_done: bool = False,
    ) -> None:
        for well, params in self.experiment.items():
            run_id = f"{self.experiment.id}:{well}:{tag}"
            try:
                _record_step(
                    results,
                    runner=runner,
                    run_id=run_id,
                    experiment_id=self.experiment.id,
                    well=well,
                    params=params,
                    kind=kind,
                    station=station,
                )
            except Exception as exc:
                results.set_well_status(self.experiment.id, well, "failed", error=repr(exc))
                raise
            if mark_done:
                results.set_well_status(self.experiment.id, well, "done")

    def _confirm(self, prompt: str) -> bool:
        try:
            answer = self.input_fn(prompt)
        except EOFError:
            return False
        return answer.strip().lower() in ("y", "yes")


def _record_step(
    results: ResultStore,
    *,
    runner: MachineRunner,
    run_id: str,
    experiment_id: str,
    well: str,
    params: dict[str, Any],
    kind: str,
    station: str,
) -> None:
    started = time.time()
    try:
        response = runner.run(well=well, params=params, run_id=run_id)
    except Exception as exc:
        results.record_run(
            run_id=run_id,
            experiment_id=experiment_id,
            well=well,
            kind=kind,
            station=station,
            success=False,
            started_at=started,
            finished_at=time.time(),
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
    results.record_run(
        run_id=run_id,
        experiment_id=experiment_id,
        well=well,
        kind=kind,
        station=station,
        success=_require_success(response, kind),
        started_at=started,
        finished_at=time.time(),
        result=response.get("results", response),
        artifacts=response.get("artifacts"),
    )


def _require_success(response: dict[str, Any], kind: str) -> bool:
    if "success" not in response:
        raise RuntimeError(f"{kind} response missing 'success' field: {response!r}")
    return bool(response["success"])

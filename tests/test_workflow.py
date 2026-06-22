import csv

from manual_bioadhesives_workcell.models import WorkflowWell, build_experiment
from manual_bioadhesives_workcell.result_store import ResultStore
from manual_bioadhesives_workcell.workflow import ManualBioadhesivesWorkflow, ManualRunners


class FakeRunner:
    def __init__(self, name, *, fail_health=False):
        self.name = name
        self.fail_health = fail_health
        self.calls = []

    def health(self):
        if self.fail_health:
            raise RuntimeError("offline")
        return {"status": "ok", "device": self.name}

    def run(self, *, well, params, run_id):
        self.calls.append((well, run_id, dict(params)))
        if self.name == "opentrons":
            return {
                "success": True,
                "source_well": params["source_well"],
                "well": well,
                "volume_dispensed": params["volume_ul"],
            }
        if self.name == "sharc":
            return {"success": True, "results": [None, {"exposure_time": params["uv_exposure_s"]}]}
        return {
            "success": True,
            "results": [
                {
                    "measurements": [
                        {
                            "timestamp": 1.0,
                            "z_mm": -3.0,
                            "raw_force_n": 0.1,
                            "corrected_force_n": 0.05,
                            "direction": "down",
                        }
                    ]
                }
            ],
        }


def _experiment():
    return build_experiment(
        experiment_id="manual-bio",
        wells=[WorkflowWell(target_well="A1", source_well="A1", uv_exposure_s=11.0)],
        shared_params={
            "volume_ul": 100,
            "uv_intensity": 1,
            "asmi_scalar": {"measurement_height": -3.0},
        },
    )


def test_workflow_runs_stages_with_manual_prompts_and_no_arm_rows(tmp_path):
    answers = iter(["y", "y", "y"])
    printed = []
    db_path = tmp_path / "results.db"
    csv_path = tmp_path / "joined.csv"
    opentrons = FakeRunner("opentrons")
    sharc = FakeRunner("sharc")
    asmi = FakeRunner("asmi")

    workflow = ManualBioadhesivesWorkflow(
        experiment=_experiment(),
        runners=ManualRunners(opentrons=opentrons, sharc=sharc, asmi=asmi),
        db_path=db_path,
        output_csv=csv_path,
        input_fn=lambda _prompt: next(answers),
        output_fn=printed.append,
    )

    assert workflow.run() == 0

    assert [call[1] for call in opentrons.calls] == ["manual-bio:A1:fill"]
    assert [call[1] for call in sharc.calls] == ["manual-bio:A1:sharc"]
    assert [call[1] for call in asmi.calls] == ["manual-bio:A1:asmi"]
    assert any("✅ Opentrons Flex" in line for line in printed)
    assert any("manual move to SHARC" in line for line in printed)

    with ResultStore(db_path) as store:
        kinds = {row["kind"] for row in store.runs_for_well("manual-bio", "A1")}
    assert kinds == {"opentrons_fill", "sharc", "asmi"}

    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["sharc_exposure_time_s"] == "11.0"


def test_workflow_aborts_before_prompts_when_health_fails(tmp_path):
    answers = iter(["y"])
    opentrons = FakeRunner("opentrons")
    sharc = FakeRunner("sharc", fail_health=True)
    asmi = FakeRunner("asmi")

    workflow = ManualBioadhesivesWorkflow(
        experiment=_experiment(),
        runners=ManualRunners(opentrons=opentrons, sharc=sharc, asmi=asmi),
        db_path=tmp_path / "results.db",
        output_csv=tmp_path / "joined.csv",
        input_fn=lambda _prompt: next(answers),
        output_fn=lambda _line: None,
    )

    assert workflow.run() == 1
    assert opentrons.calls == []
    assert sharc.calls == []
    assert asmi.calls == []

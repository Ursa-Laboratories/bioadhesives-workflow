import csv
import sqlite3

from automated_bioadhesives_workcell.workflow import AutomatedBioadhesivesWorkflow, AutomatedRunners
from automated_bioadhesives_workcell.models import WorkflowWell, build_experiment


class FakeRunner:
    def __init__(self, name, *, fail_health=False, validation=None):
        self.name = name
        self.fail_health = fail_health
        self.validation = validation
        self.health_calls = 0
        self.validation_calls = []
        self.calls = []

    def health(self):
        self.health_calls += 1
        if self.fail_health:
            raise RuntimeError("offline")
        return {"status": "ok", "device": self.name}

    def validate(self, *, well, params):
        self.validation_calls.append((well, dict(params)))
        return self.validation or {"passed": True}

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


class FakeArm:
    name = "Robot arm"

    def __init__(self, *, routes=None):
        self.routes = routes or ["opentrons->uv_station", "uv_station->asmi"]
        self.health_calls = 0
        self.transfers = []

    def health(self):
        self.health_calls += 1
        return {"status": "ok", "device": "xarm", "routes": list(self.routes)}

    def transfer(self, *, from_location, to_location, run_id, mock_mode=None, skip_safe_prelude=False):
        self.transfers.append(
            {
                "from": from_location,
                "to": to_location,
                "run_id": run_id,
                "mock_mode": mock_mode,
                "skip_safe_prelude": skip_safe_prelude,
            }
        )
        return {"success": True, "from": from_location, "to": to_location, "run_id": run_id}


def _experiment():
    return build_experiment(
        experiment_id="automated-bio",
        wells=[WorkflowWell(target_well="A1", source_well="A1", uv_exposure_s=11.0)],
        shared_params={
            "volume_ul": 100,
            "uv_intensity": 1,
            "asmi_scalar": {"measurement_height": -3.0},
        },
    )


def _workflow(tmp_path, *, arm=None, skip_sharc=False, skip_asmi=False, output_fn=lambda _line: None):
    return _workflow_with_runners(
        tmp_path,
        sharc=FakeRunner("sharc"),
        asmi=FakeRunner("asmi"),
        arm=arm,
        skip_sharc=skip_sharc,
        skip_asmi=skip_asmi,
        output_fn=output_fn,
    )


def _workflow_with_runners(
    tmp_path,
    *,
    sharc,
    asmi,
    arm=None,
    skip_sharc=False,
    skip_asmi=False,
    output_fn=lambda _line: None,
):
    return AutomatedBioadhesivesWorkflow(
        experiment=_experiment(),
        runners=AutomatedRunners(
            opentrons=FakeRunner("opentrons"),
            sharc=sharc,
            asmi=asmi,
            arm=arm or FakeArm(),
        ),
        db_path=tmp_path / "results.db",
        output_csv=tmp_path / "joined.csv",
        skip_sharc=skip_sharc,
        skip_asmi=skip_asmi,
        output_fn=output_fn,
    )


def test_automated_workflow_replaces_manual_prompts_with_arm_transfers(tmp_path):
    printed = []
    arm = FakeArm()
    workflow = _workflow(tmp_path, arm=arm, output_fn=printed.append)

    assert workflow.run() == 0

    assert [call["run_id"] for call in arm.transfers] == [
        "automated-bio:move-to-sharc",
        "automated-bio:move-to-asmi",
    ]
    assert [(call["from"], call["to"]) for call in arm.transfers] == [
        ("opentrons", "uv_station"),
        ("uv_station", "asmi"),
    ]
    assert all(call["mock_mode"] is False for call in arm.transfers)
    assert any("robot arm" in line for line in printed)
    assert not any("manual move" in line for line in printed)

    con = sqlite3.connect(tmp_path / "results.db")
    try:
        rows = con.execute(
            "SELECT run_id, well, kind, station FROM runs ORDER BY rowid"
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        ("automated-bio:A1:fill", "A1", "opentrons_fill", "opentrons"),
        ("automated-bio:move-to-sharc", None, "arm_transfer", "xarm"),
        ("automated-bio:A1:sharc", "A1", "sharc", "sharc"),
        ("automated-bio:move-to-asmi", None, "arm_transfer", "xarm"),
        ("automated-bio:A1:asmi", "A1", "asmi", "asmi"),
    ]

    with (tmp_path / "joined.csv").open(newline="") as f:
        csv_rows = list(csv.DictReader(f))
    assert len(csv_rows) == 1
    assert csv_rows[0]["sharc_exposure_time_s"] == "11.0"


def test_automated_workflow_aborts_before_stages_when_arm_routes_are_missing(tmp_path):
    printed = []
    arm = FakeArm(routes=["opentrons->uv_station"])
    workflow = _workflow(tmp_path, arm=arm, output_fn=printed.append)

    assert workflow.run() == 1
    assert arm.transfers == []
    assert any("missing required arm route(s): uv_station->asmi" in line for line in printed)


def test_automated_workflow_aborts_before_arm_moves_when_station_validation_fails(tmp_path):
    printed = []
    arm = FakeArm()
    sharc = FakeRunner(
        "sharc",
        validation={"passed": False, "output": "RESULT: ERROR - bad sharc config"},
    )
    workflow = _workflow_with_runners(
        tmp_path,
        sharc=sharc,
        asmi=FakeRunner("asmi"),
        arm=arm,
        output_fn=printed.append,
    )

    assert workflow.run() == 1
    assert sharc.validation_calls
    assert arm.transfers == []
    assert any("❌ SHARC station" in line for line in printed)
    assert any("bad sharc config" in line for line in printed)


def test_automated_skip_sharc_still_moves_through_uv_station_before_asmi(tmp_path):
    arm = FakeArm()
    workflow = _workflow(tmp_path, arm=arm, skip_sharc=True)

    assert workflow.run() == 0

    assert [(call["from"], call["to"]) for call in arm.transfers] == [
        ("opentrons", "uv_station"),
        ("uv_station", "asmi"),
    ]


def test_automated_skip_sharc_and_asmi_does_not_require_arm(tmp_path):
    arm = FakeArm(routes=[])
    workflow = _workflow(tmp_path, arm=arm, skip_sharc=True, skip_asmi=True)

    assert workflow.run() == 0

    assert arm.health_calls == 0
    assert arm.transfers == []

import csv

from manual_bioadhesives_workcell.models import WorkflowWell, build_experiment
from manual_bioadhesives_workcell.reporting import export_joined_asmi_csv
from manual_bioadhesives_workcell.result_store import ResultStore


def _seed_experiment(db_path, *, asmi_result):
    experiment = build_experiment(
        experiment_id="manual-bio",
        wells=[WorkflowWell(target_well="A1", source_well="B1", uv_exposure_s=11.0)],
        shared_params={
            "volume_ul": 100,
            "flow_rate_ul_min": 150,
            "uv_intensity": 1,
            "asmi_scalar": {"measurement_height": -3.0, "indentation_limit_height": -5.0},
            "asmi_method_kwargs": {"force_limit": 3.0, "step_size": 0.01},
        },
    )
    with ResultStore(db_path) as store:
        store.start_experiment(experiment)
        store.set_well_status("manual-bio", "A1", "done")
        store.record_run(
            run_id="manual-bio:A1:fill",
            experiment_id="manual-bio",
            well="A1",
            kind="opentrons_fill",
            station="opentrons",
            success=True,
            result={
                "success": True,
                "source_well": "B1",
                "well": "A1",
                "volume_dispensed": 100,
                "opentrons_run_id": "robot-run-1",
                "status": "succeeded",
            },
        )
        store.record_run(
            run_id="manual-bio:A1:sharc",
            experiment_id="manual-bio",
            well="A1",
            kind="sharc",
            station="sharc",
            success=True,
            result=[None, {"exposure_time": 11.0, "intensity": 1}, None],
            artifacts={"run_dir": "/runs/sharc", "result_path": "/runs/sharc/result.json"},
        )
        store.record_run(
            run_id="manual-bio:A1:asmi",
            experiment_id="manual-bio",
            well="A1",
            kind="asmi",
            station="asmi",
            success=True,
            result=[None, asmi_result, None],
            artifacts={"run_dir": "/runs/asmi", "result_path": "/runs/asmi/result.json"},
        )


def test_export_joined_asmi_csv_writes_one_row_per_measurement(tmp_path):
    db_path = tmp_path / "results.db"
    _seed_experiment(
        db_path,
        asmi_result={
            "baseline_avg": 0.01,
            "baseline_std": 0.02,
            "force_exceeded": False,
            "measurements": [
                {
                    "timestamp": 10.0,
                    "z_mm": -3.0,
                    "raw_force_n": 0.10,
                    "corrected_force_n": 0.03,
                    "direction": "down",
                },
                {
                    "timestamp": 10.5,
                    "z_mm": -3.25,
                    "raw_force_n": 0.20,
                    "corrected_force_n": 0.13,
                    "direction": "down",
                },
            ],
        },
    )

    out = export_joined_asmi_csv(db_path, "manual-bio", tmp_path / "joined.csv")

    with out.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["experiment_id"] == "manual-bio"
    assert rows[0]["well"] == "A1"
    assert rows[0]["source_well"] == "B1"
    assert rows[0]["volume_ul"] == "100"
    assert rows[0]["sharc_exposure_time_s"] == "11.0"
    assert rows[0]["z_position_mm"] == "-3.0"
    assert rows[0]["indentation_distance_mm"] == "0.0"
    assert rows[1]["indentation_distance_mm"] == "0.25"
    assert rows[1]["corrected_force_n"] == "0.13"
    assert rows[1]["asmi_result_path"] == "/runs/asmi/result.json"


def test_export_joined_asmi_csv_supports_array_style_asmi_results(tmp_path):
    db_path = tmp_path / "results.db"
    _seed_experiment(
        db_path,
        asmi_result={
            "z_positions": [-3.0, -3.1],
            "raw_forces": [0.1, 0.2],
            "corrected_forces": [0.04, 0.12],
            "sample_timestamps": [20.0, 20.4],
            "directions": ["down", "up"],
        },
    )

    out = export_joined_asmi_csv(db_path, "manual-bio", tmp_path / "joined.csv")

    with out.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["raw_force_n"] == "0.1"
    assert rows[1]["direction"] == "up"
    assert rows[1]["relative_time_s"] == "0.4"

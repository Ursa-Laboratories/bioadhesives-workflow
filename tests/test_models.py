from manual_bioadhesives_workcell.models import WorkflowWell, build_experiment


def test_build_experiment_merges_shared_and_per_well_settings():
    experiment = build_experiment(
        experiment_id="manual-bio",
        wells=[
            WorkflowWell(
                target_well="a1",
                source_well="b1",
                uv_exposure_s=12.5,
                formulation="pegda",
                opentrons={"volume_ul": 80},
                sharc_method_kwargs={"intensity": 2},
                asmi_scalar={"indentation_limit_height": -4.0},
                asmi_method_kwargs={"force_limit": 4.0},
            )
        ],
        shared_params={
            "volume_ul": 100,
            "uv_intensity": 1,
            "asmi_scalar": {"measurement_height": -3.0, "indentation_limit_height": -5.0},
            "asmi_method_kwargs": {"force_limit": 3.0, "step_size": 0.01},
        },
    )

    assert experiment.wells == ["A1"]
    params = experiment.well_params("A1")
    assert params["source_well"] == "B1"
    assert params["formulation"] == "pegda"
    assert params["uv_exposure_s"] == 12.5
    assert params["volume_ul"] == 80
    assert params["sharc_method_kwargs"] == {"intensity": 2}
    assert params["asmi_scalar"] == {"measurement_height": -3.0, "indentation_limit_height": -4.0}
    assert params["asmi_method_kwargs"] == {"force_limit": 4.0, "step_size": 0.01}


def test_build_experiment_rejects_duplicate_wells():
    try:
        build_experiment(
            experiment_id="manual-bio",
            wells=[WorkflowWell("A1"), WorkflowWell("a1")],
            shared_params={},
        )
    except ValueError as exc:
        assert "listed twice" in str(exc)
    else:
        raise AssertionError("expected duplicate well to fail")

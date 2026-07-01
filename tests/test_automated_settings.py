from automated_bioadhesives_workcell.settings import (
    ARM_SERVER_BASE_URL,
    AutomatedWorkflowSettings,
    build_workflow,
)


def test_default_automated_workflow_builds_from_manual_machine_settings():
    workflow = build_workflow(
        AutomatedWorkflowSettings(
            skip_opentrons_fill=True,
            skip_sharc=True,
            skip_asmi=True,
            mock_stations=True,
            mock_arm=True,
        )
    )

    assert workflow.skip_opentrons_fill is True
    assert workflow.skip_sharc is True
    assert workflow.skip_asmi is True
    assert workflow.mock_arm is True
    assert workflow.runners.arm.base_url == ARM_SERVER_BASE_URL
    assert workflow.runners.arm.mock_mode is True
    assert workflow.output_csv.name == "bioadhesives_automated_arm_automated_joined_asmi.csv"
    assert workflow.experiment.raw["workflow"] == "automated_bioadhesives_workcell"
    assert workflow.runners.sharc.station.client.gantry_config_yaml
    assert workflow.runners.asmi.station.client.deck_config_yaml

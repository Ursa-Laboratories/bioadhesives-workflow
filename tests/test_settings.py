import yaml

from manual_bioadhesives_workcell.settings import (
    ASMI_PROTOCOL,
    SHARC_PROTOCOL,
    ManualWorkflowSettings,
    build_workflow,
)


def test_build_workflow_uses_package_protocols_not_controller_base_protocol(tmp_path):
    gantry = tmp_path / "gantry.yaml"
    deck = tmp_path / "deck.yaml"
    gantry.write_text("serial_port: /dev/null\n")
    deck.write_text("labware: []\n")
    missing_base_protocol = tmp_path / "missing-base-protocol.yaml"
    config = tmp_path / "controller.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "stations": {
                    "sharc": {
                        "base_url": "http://sharc.example",
                        "gantry_config": str(gantry),
                        "deck_config": str(deck),
                        "base_protocol": str(missing_base_protocol),
                    },
                    "asmi": {
                        "base_url": "http://asmi.example",
                        "gantry_config": str(gantry),
                        "deck_config": str(deck),
                        "base_protocol": str(missing_base_protocol),
                    },
                },
                "opentrons": {"base_url": None},
                "results": {"db_path": str(tmp_path / "results.db")},
            }
        )
    )

    workflow = build_workflow(
        ManualWorkflowSettings(
            controller_config=config,
            skip_opentrons_fill=True,
        )
    )

    assert workflow.runners.sharc.station.base_protocol_yaml == SHARC_PROTOCOL.read_text()
    assert workflow.runners.asmi.station.base_protocol_yaml == ASMI_PROTOCOL.read_text()

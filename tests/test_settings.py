import yaml

from manual_bioadhesives_workcell.settings import (
    ASMI_PORT,
    ASMI_PROTOCOL,
    CONTROLLER_CONFIG,
    OPENTRONS_FLOW_RATE_UL_MIN,
    OPENTRONS_PROTOCOL,
    OPENTRONS_PORT,
    SHARC_PORT,
    SHARC_PROTOCOL,
    ManualWorkflowSettings,
    build_workflow,
)


def test_default_ports_are_defined_in_settings_and_match_station_worker_configs():
    assert OPENTRONS_PORT == 31950
    assert SHARC_PORT == 8000
    assert ASMI_PORT == 8000


def test_default_opentrons_flow_rate_matches_pilot_protocol():
    assert OPENTRONS_FLOW_RATE_UL_MIN == 2.5


def test_default_workflow_builds_from_repo_root_config():
    workflow = build_workflow(ManualWorkflowSettings(skip_opentrons_fill=True, mock_stations=True))

    assert CONTROLLER_CONFIG.exists()
    assert workflow.db_path.name == "polymer_indent.db"
    assert workflow.runners.sharc.station.client.gantry_config_yaml
    assert workflow.runners.asmi.station.client.deck_config_yaml
    assert workflow.runners.opentrons.protocol_path == OPENTRONS_PROTOCOL


def test_build_workflow_uses_package_settings_not_controller_endpoint_values(tmp_path):
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
                        "base_url": "http://wrong-sharc.example",
                        "gantry_config": str(gantry),
                        "deck_config": str(deck),
                        "base_protocol": str(missing_base_protocol),
                        "timeout_s": 1,
                    },
                    "asmi": {
                        "base_url": "http://wrong-asmi.example",
                        "gantry_config": str(gantry),
                        "deck_config": str(deck),
                        "base_protocol": str(missing_base_protocol),
                        "timeout_s": 1,
                    },
                },
                "opentrons": {"base_url": "http://wrong-opentrons.example", "timeout_s": 1},
                "results": {"db_path": str(tmp_path / "results.db")},
            }
        )
    )

    workflow = build_workflow(
        ManualWorkflowSettings(
            controller_config=config,
            opentrons_base_url="http://settings-opentrons.example:31950",
            sharc_base_url="http://settings-sharc.example:8000",
            asmi_base_url="http://settings-asmi.example:8000",
            opentrons_timeout_s=12,
            sharc_timeout_s=34,
            asmi_timeout_s=56,
            health_timeout_s=2,
        )
    )

    assert workflow.runners.sharc.station.base_protocol_yaml == SHARC_PROTOCOL.read_text()
    assert workflow.runners.asmi.station.base_protocol_yaml == ASMI_PROTOCOL.read_text()
    assert workflow.runners.opentrons.client.base_url == "http://settings-opentrons.example:31950"
    assert workflow.runners.opentrons.client.timeout_s == 12
    assert workflow.runners.opentrons.client.health_timeout_s == 2
    assert workflow.runners.sharc.station.client.base_url == "http://settings-sharc.example:8000"
    assert workflow.runners.sharc.station.client.timeout_s == 34
    assert workflow.runners.sharc.station.client.health_timeout_s == 2
    assert workflow.runners.asmi.station.client.base_url == "http://settings-asmi.example:8000"
    assert workflow.runners.asmi.station.client.timeout_s == 56
    assert workflow.runners.asmi.station.client.health_timeout_s == 2

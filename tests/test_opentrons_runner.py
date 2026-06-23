import pytest
import requests

from manual_bioadhesives_workcell.http_client import HttpError
from manual_bioadhesives_workcell.machines.opentrons_client import OpentronsClient, render_viscous_fill_protocol
from manual_bioadhesives_workcell.machines.opentrons_runner import OpentronsFillRunner


class FakeOpentronsClient:
    def __init__(self):
        self.calls = []

    def health(self):
        return {"status": "ok"}

    def run_fill(self, **kwargs):
        self.calls.append(kwargs)
        return {"success": True}

class TimeoutSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        raise requests.exceptions.ConnectTimeout("timed out")


def test_opentrons_runner_requires_settings_in_params():
    runner = OpentronsFillRunner(FakeOpentronsClient())

    with pytest.raises(ValueError, match="plate_labware"):
        runner.run(
            well="A1",
            run_id="run-1",
            params={
                "volume_ul": 100,
                "source_well": "A1",
                "flow_rate_ul_min": 150,
                "air_expulsion_ul": 20,
                "tip_lift_height_mm": 8,
                "tip_rack_slot": "A2",
                "tube_rack_slot": "B2",
                "plate_slot": "D1",
            },
        )


def test_opentrons_runner_passes_settings_without_fallbacks():
    client = FakeOpentronsClient()
    runner = OpentronsFillRunner(client)

    runner.run(
        well="A1",
        run_id="run-1",
        params={
            "volume_ul": 100,
            "source_well": "A1",
            "formulation": "pegda_a",
            "flow_rate_ul_min": 150,
            "air_expulsion_ul": 20,
            "tip_lift_height_mm": 8,
            "tip_rack_slot": "A2",
            "tube_rack_slot": "B2",
            "plate_slot": "D1",
            "plate_labware": "corning_96_wellplate_360ul_flat",
        },
    )

    assert client.calls == [
        {
            "well": "A1",
            "volume_ul": 100,
            "source_well": "A1",
            "formulation": "pegda_a",
            "run_id": "run-1",
            "flow_rate_ul_min": 150,
            "air_expulsion_ul": 20,
            "tip_lift_height_mm": 8,
            "tip_rack_slot": "A2",
            "tube_rack_slot": "B2",
            "plate_slot": "D1",
            "plate_labware": "corning_96_wellplate_360ul_flat",
        }
    ]


def test_generated_fill_protocol_uses_current_custom_tube_rack_geometry():
    protocol = render_viscous_fill_protocol(
        source_well="A1",
        target_well="A1",
        volume_ul=100,
        flow_rate_ul_min=2.5,
        air_expulsion_ul=20,
        tip_lift_height_mm=8,
        tip_rack_slot="A2",
        tube_rack_slot="B2",
        plate_slot="D1",
        plate_labware="corning_96_wellplate_360ul_flat",
    )

    assert '"zDimension": 130' in protocol
    assert protocol.count('"depth": 50') == 6
    assert protocol.count('"z": 75') == 6
    assert "p1000.flow_rate.aspirate = 2.5" in protocol


def test_opentrons_health_transport_failure_does_not_try_fallback():
    session = TimeoutSession()
    client = OpentronsClient("http://opentrons.example", health_timeout_s=0.25, session=session)

    with pytest.raises(HttpError, match="/health"):
        client.health()

    assert session.calls == [
        ("http://opentrons.example/health", {"timeout": 0.25}),
    ]

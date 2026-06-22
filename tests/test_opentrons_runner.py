import pytest

from manual_bioadhesives_workcell.machines.opentrons_runner import OpentronsFillRunner


class FakeOpentronsClient:
    def __init__(self):
        self.calls = []

    def health(self):
        return {"status": "ok"}

    def run_fill(self, **kwargs):
        self.calls.append(kwargs)
        return {"success": True}


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

# Manual Bioadhesives Workcell

Runs the bioadhesives Opentrons -> SHARC -> ASMI flow without the robot arm.
The operator moves the well plate by hand between machines and confirms each
move in the CLI before the next hardware step starts.

## Run

From the repo root on the controller machine:

```bash
python -m manual_bioadhesives_workcell
```

The workflow reads device URLs from `manual_bioadhesives_workcell/settings.py`:

- Opentrons Flex: `OPENTRONS_BASE_URL`, default `http://10.210.29.218:31950`
- SHARC station worker: `SHARC_BASE_URL`, default `http://10.210.29.12:8000`
- ASMI station worker: `ASMI_BASE_URL`, default `http://10.210.29.17:8000`

The arm worker is not health-checked and is never called. The
`scripts/test_arm_loop_with_asmi_pause.py` script only talks to the arm worker
through `arm.base_url`, which is `http://localhost:5004` by default. That port
serves the arm worker's `/run` route, not the station worker's `/run-protocol`
route used for SHARC and ASMI.

The SHARC and ASMI protocol YAMLs live inside this package:

```text
manual_bioadhesives_workcell/machines/protocols/sharc_uv_one_well.yaml
manual_bioadhesives_workcell/machines/protocols/asmi_indentation_a1.yaml
```

`configs/controller.yaml` is still used for gantry/deck YAML paths and the
controller DB path. Its station URLs, Opentrons URL, timeouts, and station
`base_protocol` entries are not used by this manual workflow.

Useful options:

```bash
python -m manual_bioadhesives_workcell --mock-stations
python -m manual_bioadhesives_workcell --skip-opentrons-fill
python -m manual_bioadhesives_workcell --experiment-id my_run_001
python -m manual_bioadhesives_workcell --output-csv results/my_run_001.csv
```

`--mock-stations` sends `mock_mode=True` to SHARC and ASMI. The station workers
must still be reachable, but CubOS should not move hardware.

`--skip-opentrons-fill` uses the existing Opentrons placeholder client and marks
the Opentrons health line as an intentional placeholder.

## Layout

Machine-specific code lives under `manual_bioadhesives_workcell/machines/`:

- Opentrons client and runner
- SHARC runner
- ASMI runner
- shared station worker client
- shared protocol rendering helper
- SHARC and ASMI protocol YAMLs

Top-level files hold workflow orchestration, settings, data models, health
checks, result storage, and CSV reporting.

## Operator Sequence

1. Health check Opentrons, SHARC, and ASMI. Each reachable machine prints `✅`.
2. Confirm the well plate is in the Opentrons.
3. Run Opentrons fills for all configured wells.
4. Move the plate to SHARC and press `y`.
5. Run SHARC UV cure protocols for all configured wells.
6. Move the plate to ASMI and press `y`.
7. Run ASMI indentation protocols for all configured wells.
8. Export the joined CSV from the controller SQLite DB.
9. Finish.

Any prompt response other than `y` or `yes` aborts before the next hardware step.

## Configure Wells

Edit `manual_bioadhesives_workcell/settings.py`.

Define the source tube rack first:

```python
REAGENT_SOURCES = {
    "pegda_a": "A1",
}
```

Then define what reagent goes into each well plate well:

```python
WORKFLOW_WELLS = [
    WorkflowWell(
        target_well="A1",
        source_well=REAGENT_SOURCES["pegda_a"],
        formulation="pegda_a",
        uv_exposure_s=11.0,
    ),
]
```

The well plate and Opentrons deck layout are defined in the same file:

```python
OPENTRONS_BASE_URL = "http://10.210.29.218:31950"
SHARC_BASE_URL = "http://10.210.29.12:8000"
ASMI_BASE_URL = "http://10.210.29.17:8000"

OPENTRONS_TIP_RACK_SLOT = "A2"
OPENTRONS_TUBE_RACK_SLOT = "B2"
OPENTRONS_PLATE_SLOT = "D1"
OPENTRONS_PLATE_LABWARE = "corning_96_wellplate_360ul_flat"
```

Per-well Opentrons, SHARC, and ASMI overrides live on `WorkflowWell`, so the
main workflow does not need to change when settings vary by well.

Edit `manual_bioadhesives_workcell/machines/protocols/` when the base SHARC or
ASMI protocol itself changes.

## Data And Report

The station workers run CubOS and return result payloads to this controller.
This workflow stores those payloads in the controller SQLite DB configured in
`configs/controller.yaml`, defaulting to `results/polymer_indent.db`, using
these run kinds:

- `opentrons_fill`
- `sharc`
- `asmi`

The CSV exporter reads that controller DB, joins rows by `experiment_id + well`,
and writes one CSV row per ASMI force sample. Each ASMI row includes z position,
indentation distance, raw force, corrected force, direction, SHARC cure settings,
Opentrons fill metadata, run IDs, and artifact paths.

Default CSV path:

```text
results/<experiment_id>_manual_joined_asmi.csv
```

## Tests

```bash
python -m pytest manual_bioadhesives_workcell/tests -q
python -m py_compile manual_bioadhesives_workcell/*.py
```

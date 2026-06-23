# Manual Bioadhesives Workcell

Runs the bioadhesives Opentrons -> SHARC -> ASMI flow without the robot arm.
The operator moves the well plate by hand between machines and confirms each
move in the CLI before the next hardware step starts.


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

## Install

From the repo root, install the Python dependencies with pip. If you just
cloned the repo, enter the checkout first:

```bash
cd manual_bioadhesives_workcell
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Runtime dependencies are `requests` and `PyYAML`. `pytest` is included for the
local test suite.

## Run

Run commands from the repo root, meaning the directory that contains this
`README.md`:

```bash
python -m manual_bioadhesives_workcell
```

The `-m` command runs `manual_bioadhesives_workcell/__main__.py`, which builds
the workflow from settings and calls `ManualBioadhesivesWorkflow.run()`. Do not
run `workflow.py` directly.

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

## Health Check

To check Opentrons, SHARC, and ASMI without running the workflow:

```bash
python -m manual_bioadhesives_workcell.health_check
```

The command exits `0` when all machines pass health checks and `1` if any check
fails. It uses a `3` second per-machine timeout by default; adjust that with
`--timeout-s`. Use `--skip-opentrons-fill` to use the Opentrons placeholder
health path.

## Configuration

The workflow reads device URLs from `manual_bioadhesives_workcell/settings.py`:

- Opentrons Flex: `OPENTRONS_BASE_URL`, default `http://10.210.29.218:31950`
- SHARC station worker: `SHARC_BASE_URL`, default `http://10.210.29.12:8000`
- ASMI station worker: `ASMI_BASE_URL`, default `http://10.210.29.17:8000`

The arm worker is not health-checked and is never called. This manual workflow
talks to Opentrons and to the SHARC/ASMI station-worker `/run-protocol` routes.
Port `5004` is the arm worker's `/run` route and is not used here.

`configs/controller.yaml` is used for the gantry/deck YAML paths sent to the
station workers and for the controller DB path. The default local config points
at:

```text
configs/gantry/sharc_gantry.yaml
configs/gantry/asmi_gantry.yaml
configs/deck/sharc_deck.yaml
configs/deck/asmi_deck.yaml
```

The SHARC and ASMI protocol YAMLs live inside the Python package:

```text
manual_bioadhesives_workcell/machines/protocols/sharc_uv_one_well.yaml
manual_bioadhesives_workcell/machines/protocols/asmi_indentation_a1.yaml
```

The station URLs, Opentrons URL, timeouts, and `base_protocol` values inside
`configs/controller.yaml` are kept as config metadata, but this manual workflow
uses the values in `settings.py` for those runtime decisions.

## Layout

Repo-level files and directories:

- `manual_bioadhesives_workcell/` - importable Python package and `-m` entrypoint
- `configs/` - local controller, gantry, and deck YAMLs
- `tests/` - pytest suite
- `README.md` - operator and developer notes

Machine-specific code lives under `manual_bioadhesives_workcell/machines/`:

- Opentrons client and runner
- SHARC runner
- ASMI runner
- shared station worker client
- shared protocol rendering helper
- SHARC and ASMI protocol YAMLs

The package top-level holds workflow orchestration, settings, data models,
health checks, result storage, and CSV reporting.

## Configure Settings

Edit `manual_bioadhesives_workcell/settings.py`.

This file owns the editable runtime defaults for the manual workflow:

- `EXPERIMENT_ID`
- Opentrons URL, timeout, deck slots, labware, fill volume, and pipetting settings
- SHARC station URL, timeout, UV cure protocol settings, and cure-time defaults
- ASMI station URL, timeout, indentation heights, step size, force limit, and measurement settings
- the per-well `WORKFLOW_WELLS` plan

Define the source tube rack first:

```python
REAGENT_SOURCES = {
    "pegda_a": "A1",
}
```

Then define what reagent goes into each well plate well:

```python
UV_INTENSITY = 1
UV_EXPOSURE_S = 11.0

WORKFLOW_WELLS = [
    WorkflowWell(
        target_well="A1",
        source_well=REAGENT_SOURCES["pegda_a"],
        formulation="pegda_a",
        uv_exposure_s=UV_EXPOSURE_S,
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
python -m manual_bioadhesives_workcell --help
python -m manual_bioadhesives_workcell.health_check --help
python -m pytest tests -q
python -m py_compile manual_bioadhesives_workcell/*.py
```

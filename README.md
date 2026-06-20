# Manual Bioadhesives Workcell

Runs the bioadhesives Opentrons -> SHARC -> ASMI flow without the robot arm.
The operator moves the well plate by hand between machines and confirms each
move in the CLI before the next hardware step starts.

## Run

From the repo root on the controller machine:

```bash
python -m manual_bioadhesives_workcell
```

The workflow reads current device URLs from `configs/controller.yaml`:

- Opentrons Flex: `http://10.210.29.218:31950`
- SHARC station worker: `http://10.210.29.12:8000`
- ASMI station worker: `http://10.210.29.17:8000`

The arm worker is not health-checked and is never called.

The SHARC and ASMI protocol YAMLs live inside this package:

```text
manual_bioadhesives_workcell/protocols/sharc_uv_one_well.yaml
manual_bioadhesives_workcell/protocols/asmi_indentation_a1.yaml
```

`configs/controller.yaml` is still used for station URLs, timeouts, gantry/deck
YAML paths, and the controller DB path. Its station `base_protocol` entries are
not used by this manual workflow.

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

The default run is one well:

```python
WORKFLOW_WELLS = [
    WorkflowWell(target_well="A1", source_well="A1", uv_exposure_s=11.0),
]
```

Per-well Opentrons, SHARC, and ASMI overrides live on `WorkflowWell`, so the
main workflow does not need to change when settings vary by well.

Edit `manual_bioadhesives_workcell/protocols/` when the base SHARC or ASMI
protocol itself changes.

## Data And Report

The station workers run CubOS and return result payloads to this controller.
This workflow stores those payloads in `results/polymer_indent.db` using the
existing `ResultStore` tables:

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

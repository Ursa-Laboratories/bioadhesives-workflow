from pathlib import Path


def test_manual_package_source_does_not_import_polymer_indent():
    package_root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in package_root.rglob("*.py"):
        if "tests" in path.relative_to(package_root).parts:
            continue
        text = path.read_text()
        if "from polymer_indent" in text or "import polymer_indent" in text:
            offenders.append(path.name)
    assert offenders == []


def test_machine_specific_files_live_under_machines():
    package_root = Path(__file__).resolve().parents[1]
    machine_files = [
        "asmi_runner.py",
        "opentrons_client.py",
        "opentrons_runner.py",
        "protocol_render.py",
        "sharc_runner.py",
        "station_client.py",
    ]

    assert all(not (package_root / filename).exists() for filename in machine_files)
    assert all((package_root / "machines" / filename).exists() for filename in machine_files)
    assert (package_root / "machines" / "protocols" / "sharc_uv_one_well.yaml").exists()
    assert (package_root / "machines" / "protocols" / "asmi_indentation_a1.yaml").exists()

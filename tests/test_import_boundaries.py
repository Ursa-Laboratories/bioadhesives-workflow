import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "manual_bioadhesives_workcell"
AUTOMATED_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "automated_bioadhesives_workcell"
REPO_ROOT = PACKAGE_ROOT.parent


def test_manual_package_source_does_not_import_polymer_indent():
    offenders = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        text = path.read_text()
        if "from polymer_indent" in text or "import polymer_indent" in text:
            offenders.append(path.name)
    assert offenders == []


def test_automated_package_source_does_not_import_polymer_indent():
    offenders = []
    for path in AUTOMATED_PACKAGE_ROOT.rglob("*.py"):
        text = path.read_text()
        if "from polymer_indent" in text or "import polymer_indent" in text:
            offenders.append(path.name)
    assert offenders == []


def test_machine_specific_files_live_under_machines():
    machine_files = [
        "asmi_runner.py",
        "opentrons_client.py",
        "opentrons_runner.py",
        "protocol_render.py",
        "sharc_runner.py",
        "station_client.py",
    ]

    assert all(not (PACKAGE_ROOT / filename).exists() for filename in machine_files)
    assert all((PACKAGE_ROOT / "machines" / filename).exists() for filename in machine_files)
    assert (PACKAGE_ROOT / "machines" / "protocols" / "sharc_uv_one_well.yaml").exists()
    assert (PACKAGE_ROOT / "machines" / "protocols" / "asmi_indentation_a1.yaml").exists()


def test_module_entrypoint_runs_from_repo_root():
    result = subprocess.run(
        [sys.executable, "-m", "manual_bioadhesives_workcell", "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Run the bioadhesives workflow" in result.stdout


def test_automated_module_entrypoint_runs_from_repo_root():
    result = subprocess.run(
        [sys.executable, "-m", "automated_bioadhesives_workcell", "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "robot-arm plate moves" in result.stdout


def test_health_check_entrypoint_runs_from_repo_root():
    result = subprocess.run(
        [sys.executable, "-m", "manual_bioadhesives_workcell.health_check", "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Check Opentrons, SHARC, and ASMI health" in result.stdout

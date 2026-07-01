"""Load controller endpoints for the automated package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ControllerConfig:
    raw: dict[str, Any]
    root: Path
    db_path: Path
    mock_mode: bool

    def abs_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.root / path


def load_controller_config(path: str | Path) -> ControllerConfig:
    path = Path(path).resolve()
    with path.open() as f:
        raw = yaml.safe_load(f) or {}
    if "stations" not in raw or not isinstance(raw["stations"], dict):
        raise ValueError(f"{path}: missing 'stations:' mapping")
    for name in ("sharc", "asmi"):
        if name not in raw["stations"]:
            raise ValueError(f"{path}: stations.{name} is required")
    db_path = Path(str(raw.get("results", {}).get("db_path", "results/polymer_indent.db"))).expanduser()
    if not db_path.is_absolute():
        db_path = _REPO_ROOT / db_path
    return ControllerConfig(
        raw=raw,
        root=_REPO_ROOT,
        db_path=db_path,
        mock_mode=bool(raw.get("mock_mode", False)),
    )

"""SQLite result store for the automated workcell."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    created_at    REAL NOT NULL,
    status        TEXT NOT NULL,
    config_json   TEXT
);
CREATE TABLE IF NOT EXISTS wells (
    experiment_id TEXT NOT NULL,
    well          TEXT NOT NULL,
    status        TEXT NOT NULL,
    params_json   TEXT,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL,
    error         TEXT,
    PRIMARY KEY (experiment_id, well)
);
CREATE TABLE IF NOT EXISTS runs (
    run_id         TEXT PRIMARY KEY,
    experiment_id  TEXT NOT NULL,
    well           TEXT,
    kind           TEXT NOT NULL,
    station        TEXT,
    started_at     REAL NOT NULL,
    finished_at    REAL,
    success        INTEGER,
    protocol_yaml  TEXT,
    result_json    TEXT,
    artifacts_json TEXT,
    error          TEXT
);
CREATE INDEX IF NOT EXISTS ix_runs_exp_well ON runs (experiment_id, well);
"""


class ResultStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if self.db_path.parent:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def __enter__(self) -> "ResultStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def start_experiment(self, experiment) -> None:
        now = _now()
        with self._conn:
            self._conn.execute(
                """INSERT INTO experiments (experiment_id, created_at, status, config_json)
                   VALUES (?, ?, 'running', ?)
                   ON CONFLICT(experiment_id) DO UPDATE SET status='running'""",
                (experiment.id, now, _dump(getattr(experiment, "raw", None))),
            )
            for well in experiment.wells:
                self._conn.execute(
                    """INSERT INTO wells (experiment_id, well, status, params_json, created_at, updated_at)
                       VALUES (?, ?, 'pending', ?, ?, ?)
                       ON CONFLICT(experiment_id, well) DO NOTHING""",
                    (experiment.id, well, _dump(experiment.params[well]), now, now),
                )

    def set_well_status(self, experiment_id: str, well: str, status: str, *, error: str | None = None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE wells SET status=?, error=?, updated_at=? WHERE experiment_id=? AND well=?",
                (status, error, _now(), experiment_id, well),
            )

    def finish_experiment(self, experiment_id: str, status: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE experiments SET status=? WHERE experiment_id=?", (status, experiment_id))

    def record_run(
        self,
        *,
        run_id: str,
        experiment_id: str,
        well: str | None,
        kind: str,
        station: str | None = None,
        success: bool | None = None,
        started_at: float | None = None,
        finished_at: float | None = None,
        protocol_yaml: str | None = None,
        result: Any = None,
        artifacts: Any = None,
        error: str | None = None,
    ) -> None:
        started = _now() if started_at is None else started_at
        with self._conn:
            self._conn.execute(
                """INSERT INTO runs (run_id, experiment_id, well, kind, station, started_at, finished_at,
                        success, protocol_yaml, result_json, artifacts_json, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(run_id) DO UPDATE SET
                        finished_at=excluded.finished_at,
                        success=excluded.success,
                        result_json=excluded.result_json,
                        artifacts_json=excluded.artifacts_json,
                        error=excluded.error""",
                (
                    run_id,
                    experiment_id,
                    well,
                    kind,
                    station,
                    started,
                    finished_at,
                    None if success is None else int(bool(success)),
                    protocol_yaml,
                    _dump(result),
                    _dump(artifacts),
                    error,
                ),
            )

    def runs_for_well(self, experiment_id: str, well: str):
        return self._conn.execute(
            "SELECT * FROM runs WHERE experiment_id=? AND well=? ORDER BY started_at",
            (experiment_id, well),
        ).fetchall()


def _now() -> float:
    return time.time()


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str, sort_keys=True)

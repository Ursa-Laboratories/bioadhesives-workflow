"""Start and stop the bundled arm server for one automated workflow run."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .arm_client import ArmTransferClient


@dataclass(frozen=True)
class ArmServerSettings:
    python: str
    host: str
    port: int
    base_url: str
    startup_timeout_s: float
    mock_arm: bool
    ot_plate_type: str
    cwd: Path


class ManagedArmServer:
    def __init__(
        self,
        settings: ArmServerSettings,
        *,
        output_fn: Callable[[str], None] = print,
        popen=subprocess.Popen,
    ):
        self.settings = settings
        self.output_fn = output_fn
        self._popen = popen
        self.process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    def command(self) -> list[str]:
        cmd = [
            self.settings.python,
            "-m",
            "automated_bioadhesives_workcell.arm_server",
            "--host",
            self.settings.host,
            "--port",
            str(self.settings.port),
            "--ot-plate",
            self.settings.ot_plate_type,
        ]
        if self.settings.mock_arm:
            cmd.append("--mock")
        return cmd

    def start(self) -> None:
        if self.process is not None:
            return
        cmd = self.command()
        self.output_fn(f"Starting arm server: {' '.join(cmd)}")
        self.process = self._popen(cmd, cwd=self.settings.cwd)
        self._wait_until_ready()

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                ArmTransferClient(
                    self.settings.base_url,
                    timeout_s=5.0,
                    health_timeout_s=2.0,
                    mock_mode=self.settings.mock_arm,
                ).stop()
            except Exception as exc:  # noqa: BLE001 - terminate even if /stop fails
                self.output_fn(f"Arm server /stop failed: {type(exc).__name__}: {exc}")
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5.0)
        self.output_fn("Arm server stopped")
        self.process = None

    def _wait_until_ready(self) -> None:
        assert self.process is not None
        client = ArmTransferClient(
            self.settings.base_url,
            timeout_s=5.0,
            health_timeout_s=1.0,
            mock_mode=self.settings.mock_arm,
        )
        deadline = time.monotonic() + self.settings.startup_timeout_s
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"arm server exited during startup with code {self.process.returncode}")
            try:
                client.health()
                return
            except Exception as exc:  # noqa: BLE001 - keep polling until timeout
                last_error = exc
                time.sleep(0.2)
        raise RuntimeError(f"arm server did not become ready: {last_error}")


def command_for_display(command: Sequence[str]) -> str:
    return " ".join(command)

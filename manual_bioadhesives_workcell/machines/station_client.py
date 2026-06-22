"""Client for SHARC and ASMI station workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from ..http_client import get_json, new_session, post_json


class StationRunError(RuntimeError):
    """A station accepted a request but the CubOS protocol failed."""

    def __init__(self, station: str, run_id: str, payload: dict[str, Any]):
        self.station = station
        self.run_id = run_id
        self.payload = payload
        super().__init__(
            f"[{station}] run {run_id!r} failed: {payload.get('error') or 'run failed'}"
        )


@dataclass
class StationBundle:
    client: "CubOSStationClient"
    base_protocol_yaml: str


class CubOSStationClient:
    def __init__(
        self,
        base_url: str,
        station: str,
        *,
        gantry_config_yaml: str,
        deck_config_yaml: str,
        timeout_s: float = 900.0,
        mock_mode: bool = False,
        session: Any | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.station = station
        self.gantry_config_yaml = gantry_config_yaml
        self.deck_config_yaml = deck_config_yaml
        self.timeout_s = timeout_s
        self.mock_mode = mock_mode
        self._session = session or new_session()

    def health(self) -> dict[str, Any]:
        return get_json(self._session, f"{self.base_url}/health", timeout=15.0)

    def validate_protocol(self, protocol_yaml: str) -> dict[str, Any]:
        return post_json(
            self._session,
            f"{self.base_url}/validate-protocol",
            {
                "protocol_yaml": protocol_yaml,
                "gantry_config": self.gantry_config_yaml,
                "deck_config": self.deck_config_yaml,
            },
            timeout=60.0,
        )

    def run_protocol(
        self,
        *,
        run_id: str,
        protocol_yaml: str,
        metadata: dict[str, Any] | None = None,
        mock_mode: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": run_id,
            "gantry_config": self.gantry_config_yaml,
            "deck_config": self.deck_config_yaml,
            "protocol_yaml": protocol_yaml,
            "mock_mode": self.mock_mode if mock_mode is None else mock_mode,
        }
        if metadata:
            payload["metadata"] = metadata
        response = post_json(
            self._session,
            f"{self.base_url}/run-protocol",
            payload,
            timeout=self.timeout_s,
        )
        if not response.get("success", False):
            raise StationRunError(self.station, run_id, response)
        return response

    def get_run(self, run_id: str) -> dict[str, Any]:
        return get_json(
            self._session,
            f"{self.base_url}/runs/{quote(run_id, safe='')}",
            timeout=15.0,
        )

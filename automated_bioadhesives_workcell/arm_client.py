"""Client for the bundled xArm + Vention-rail transfer server."""

from __future__ import annotations

from typing import Any

from .http_client import get_json, new_session, post_json


class ArmTransferError(RuntimeError):
    """The arm worker returned a JSON failure payload for a transfer."""

    def __init__(self, from_location: str, to_location: str, payload: dict[str, Any]):
        self.from_location = from_location
        self.to_location = to_location
        self.payload = payload
        message = payload.get("error") or "transfer failed"
        super().__init__(f"arm transfer {from_location} -> {to_location} failed: {message}")


class ArmTransferClient:
    name = "Robot arm"

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 300.0,
        health_timeout_s: float = 3.0,
        mock_mode: bool = False,
        session: Any | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.health_timeout_s = health_timeout_s
        self.mock_mode = mock_mode
        self._session = session or new_session()

    def health(self) -> dict[str, Any]:
        return get_json(self._session, f"{self.base_url}/health", timeout=self.health_timeout_s)

    def transfer(
        self,
        *,
        from_location: str,
        to_location: str,
        run_id: str,
        mock_mode: bool | None = None,
        skip_safe_prelude: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "from": from_location,
            "to": to_location,
            "run_id": run_id,
            "mock_mode": self.mock_mode if mock_mode is None else mock_mode,
        }
        if skip_safe_prelude:
            payload["skip_safe_prelude"] = True

        response = post_json(self._session, f"{self.base_url}/run", payload, timeout=self.timeout_s)
        if not response.get("success", False):
            raise ArmTransferError(from_location, to_location, response)
        return response

    def stop(self) -> dict[str, Any]:
        return post_json(self._session, f"{self.base_url}/stop", {}, timeout=self.health_timeout_s)

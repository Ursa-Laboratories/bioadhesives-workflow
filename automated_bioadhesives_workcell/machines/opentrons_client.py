"""Opentrons Flex client for generated one-well bioadhesives fills."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..http_client import HttpError, get_json, new_session

_TERMINAL_STATUSES = {
    "succeeded",
    "failed",
    "stopped",
    "canceled",
    "cancelled",
    "blocked-by-open-door",
}


class OpentronsRunError(RuntimeError):
    def __init__(self, run_id: str | None, payload: dict[str, Any]):
        self.run_id = run_id
        self.payload = payload
        super().__init__(
            f"opentrons run {run_id or '<unknown>'} ended with status "
            f"{_run_status(payload) or 'unknown'}: {payload!r}"
        )


class OpentronsClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_s: float = 600.0,
        poll_interval_s: float = 2.0,
        health_timeout_s: float = 3.0,
        api_version: str = "*",
        session: Any | None = None,
    ):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.health_timeout_s = health_timeout_s
        self.api_version = api_version
        self._session = session or new_session()

    def health(self) -> dict[str, Any]:
        if not self.base_url:
            return {"status": "placeholder", "device": "opentrons", "base_url": self.base_url}
        try:
            return get_json(self._session, f"{self.base_url}/health", timeout=self.health_timeout_s)
        except HttpError as exc:
            if _is_transport_error(exc):
                raise
            return self._get_json("/networking/status", timeout=self.health_timeout_s)

    def run_fill(
        self,
        *,
        well: str,
        volume_ul: float,
        flow_rate_ul_min: float,
        air_expulsion_ul: float,
        tip_lift_height_mm: float,
        tip_rack_slot: str,
        tube_rack_slot: str,
        plate_slot: str,
        plate_labware: str,
        source_well: str | None = None,
        formulation: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        well = _normalize_well(well)
        source_well = _normalize_well(source_well or formulation or "A1")
        if self.base_url:
            return self._run_flex_fill(
                well=well,
                source_well=source_well,
                volume_ul=volume_ul,
                formulation=formulation,
                run_id=run_id,
                flow_rate_ul_min=flow_rate_ul_min,
                air_expulsion_ul=air_expulsion_ul,
                tip_lift_height_mm=tip_lift_height_mm,
                tip_rack_slot=tip_rack_slot,
                tube_rack_slot=tube_rack_slot,
                plate_slot=plate_slot,
                plate_labware=plate_labware,
            )
        return {
            "success": True,
            "placeholder": True,
            "source_well": source_well,
            "well": well,
            "volume_dispensed": volume_ul,
            "formulation": formulation,
            "run_id": run_id,
            "timestamp": time.time(),
        }

    def run_protocol_file(self, protocol_path: str | Path, *, run_id: str | None = None) -> dict[str, Any]:
        path = Path(protocol_path)
        protocol_text = path.read_text()
        if self.base_url:
            return self._run_uploaded_protocol(
                protocol_text,
                run_id=run_id,
                protocol_filename=path.name,
                protocol_path=str(path),
            )
        return {
            "success": True,
            "placeholder": True,
            "run_id": run_id,
            "protocol_filename": path.name,
            "protocol_path": str(path),
            "protocol_size_bytes": len(protocol_text.encode("utf-8")),
            "timestamp": time.time(),
        }

    def _run_flex_fill(
        self,
        *,
        well: str,
        source_well: str,
        volume_ul: float,
        formulation: str | None,
        run_id: str | None,
        flow_rate_ul_min: float,
        air_expulsion_ul: float,
        tip_lift_height_mm: float,
        tip_rack_slot: str,
        tube_rack_slot: str,
        plate_slot: str,
        plate_labware: str,
    ) -> dict[str, Any]:
        protocol_text = render_viscous_fill_protocol(
            source_well=source_well,
            target_well=well,
            volume_ul=volume_ul,
            flow_rate_ul_min=flow_rate_ul_min,
            air_expulsion_ul=air_expulsion_ul,
            tip_lift_height_mm=tip_lift_height_mm,
            tip_rack_slot=tip_rack_slot,
            tube_rack_slot=tube_rack_slot,
            plate_slot=plate_slot,
            plate_labware=plate_labware,
        )
        payload = self._run_uploaded_protocol(
            protocol_text,
            run_id=run_id,
            protocol_filename="bioadhesives_one_well.py",
        )
        payload.update({
            "source_well": source_well,
            "well": well,
            "volume_dispensed": volume_ul,
            "formulation": formulation,
        })
        return payload

    def _run_uploaded_protocol(
        self,
        protocol_text: str,
        *,
        run_id: str | None,
        protocol_filename: str,
        protocol_path: str | None = None,
    ) -> dict[str, Any]:
        protocol_id = self._upload_protocol(protocol_text, key=run_id, filename=protocol_filename)
        robot_run_id = self._create_run(protocol_id)
        self._play_run(robot_run_id)
        final = self._poll_run(robot_run_id)
        success = _run_status(final) == "succeeded"
        payload = {
            "success": success,
            "placeholder": False,
            "run_id": run_id,
            "protocol_filename": protocol_filename,
            "opentrons_protocol_id": protocol_id,
            "opentrons_run_id": robot_run_id,
            "status": _run_status(final),
            "final_run": final,
            "timestamp": time.time(),
        }
        if protocol_path is not None:
            payload["protocol_path"] = protocol_path
        if not success:
            raise OpentronsRunError(robot_run_id, final)
        return payload

    def _upload_protocol(self, protocol_text: str, *, key: str | None, filename: str) -> str:
        files = {"files": (filename, protocol_text.encode("utf-8"), "text/x-python")}
        data = {"key": key} if key else None
        try:
            response = self._session.post(
                f"{self.base_url}/protocols",
                headers=self._headers(),
                files=files,
                data=data,
                timeout=self.timeout_s,
            )
        except Exception as exc:
            raise HttpError(f"POST {self.base_url}/protocols failed: {exc}") from exc
        protocol_id = _data_id(_decode_response(response, f"{self.base_url}/protocols"))
        if not protocol_id:
            raise HttpError("protocol upload response missing data.id")
        return protocol_id

    def _create_run(self, protocol_id: str) -> str:
        robot_run_id = _data_id(self._post_json("/runs", {"data": {"protocolId": protocol_id}}, timeout=30.0))
        if not robot_run_id:
            raise HttpError("run creation response missing data.id")
        return robot_run_id

    def _play_run(self, robot_run_id: str) -> None:
        self._post_json(f"/runs/{robot_run_id}/actions", {"data": {"actionType": "play"}}, timeout=30.0)

    def _poll_run(self, robot_run_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout_s
        last: dict[str, Any] = {}
        while time.time() < deadline:
            last = self._get_json(f"/runs/{robot_run_id}", timeout=30.0)
            if _run_status(last) in _TERMINAL_STATUSES:
                return last
            time.sleep(self.poll_interval_s)
        raise TimeoutError(f"Opentrons run {robot_run_id} did not finish within {self.timeout_s}s; last={last!r}")

    def _post_json(self, path: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.post(url, json=payload, headers=self._headers(), timeout=timeout)
        except Exception as exc:
            raise HttpError(f"POST {url} failed: {exc}") from exc
        return _decode_response(response, url)

    def _get_json(self, path: str, *, timeout: float) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.get(url, headers=self._headers(), timeout=timeout)
        except Exception as exc:
            raise HttpError(f"GET {url} failed: {exc}") from exc
        return _decode_response(response, url)

    def _headers(self) -> dict[str, str]:
        return {"opentrons-version": self.api_version}


def render_viscous_fill_protocol(
    *,
    source_well: str,
    target_well: str,
    volume_ul: float,
    flow_rate_ul_min: float,
    air_expulsion_ul: float,
    tip_lift_height_mm: float,
    tip_rack_slot: str,
    tube_rack_slot: str,
    plate_slot: str,
    plate_labware: str,
) -> str:
    source_well = _normalize_well(source_well)
    target_well = _normalize_well(target_well)
    return f'''from opentrons import protocol_api

metadata = {{
    "apiLevel": "2.15",
    "protocolName": "Automated bioadhesives viscous one-well dispense",
}}

requirements = {{"robotType": "Flex"}}

custom_tube_rack = {{
    "ordering": [["A1", "B1"], ["A2", "B2"], ["A3", "B3"]],
    "brand": {{"brand": "Custom", "brandId": []}},
    "metadata": {{"displayName": "Custom 6 Tube Rack with Generic 20 mL", "displayCategory": "tubeRack", "displayVolumeUnits": "µL", "tags": []}},
    "dimensions": {{"xDimension": 127, "yDimension": 85, "zDimension": 130}},
    "wells": {{
        "A1": {{"depth": 50, "totalLiquidVolume": 20000, "shape": "circular", "diameter": 30, "x": 25, "y": 62, "z": 75}},
        "B1": {{"depth": 50, "totalLiquidVolume": 20000, "shape": "circular", "diameter": 30, "x": 25, "y": 22, "z": 75}},
        "A2": {{"depth": 50, "totalLiquidVolume": 20000, "shape": "circular", "diameter": 30, "x": 65, "y": 62, "z": 75}},
        "B2": {{"depth": 50, "totalLiquidVolume": 20000, "shape": "circular", "diameter": 30, "x": 65, "y": 22, "z": 75}},
        "A3": {{"depth": 50, "totalLiquidVolume": 20000, "shape": "circular", "diameter": 30, "x": 105, "y": 62, "z": 75}},
        "B3": {{"depth": 50, "totalLiquidVolume": 20000, "shape": "circular", "diameter": 30, "x": 105, "y": 22, "z": 75}}
    }},
    "groups": [{{"brand": {{"brand": "Generic", "brandId": []}}, "metadata": {{"wellBottomShape": "flat", "displayCategory": "tubeRack"}}, "wells": ["A1", "B1", "A2", "B2", "A3", "B3"]}}],
    "parameters": {{"format": "irregular", "quirks": [], "isTiprack": "False", "isMagneticModuleCompatible": "False", "loadName": "jeremy_custom_6_tube_rack_20ml"}},
    "namespace": "custom_beta",
    "version": 1,
    "schemaVersion": 2,
    "cornerOffsetFromSlot": {{"x": 0, "y": 0, "z": 0}}
}}

def run(protocol: protocol_api.ProtocolContext):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_1000ul", "{tip_rack_slot}")
    stock_rack = protocol.load_labware_from_definition(custom_tube_rack, "{tube_rack_slot}")
    plate = protocol.load_labware("{plate_labware}", "{plate_slot}")
    p1000 = protocol.load_instrument("flex_1channel_1000", "right", tip_racks=[tips])
    p1000.flow_rate.aspirate = {float(flow_rate_ul_min)!r}
    p1000.flow_rate.dispense = {float(flow_rate_ul_min)!r}
    p1000.pick_up_tip()
    p1000.aspirate({float(volume_ul)!r}, stock_rack["{source_well}"].bottom(z=5))
    p1000.dispense({float(volume_ul)!r}, plate["{target_well}"].bottom(z=5))
    p1000.move_to(plate["{target_well}"].bottom(z={float(tip_lift_height_mm)!r}))
    p1000.dispense({float(air_expulsion_ul)!r})
    p1000.drop_tip()
'''


def _normalize_well(well: str) -> str:
    value = str(well).strip().upper()
    if not value or not value[0].isalpha() or not value[1:].isdigit():
        raise ValueError(f"not a well id: {well!r}")
    return value


def _decode_response(resp, url: str) -> dict[str, Any]:
    if resp.status_code >= 400:
        raise HttpError(f"{url} -> HTTP {resp.status_code}: {getattr(resp, 'text', '')[:300]}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise HttpError(f"{url} -> non-JSON response: {getattr(resp, 'text', '')[:200]!r}") from exc
    if not isinstance(data, dict):
        raise HttpError(f"{url} -> JSON response is not an object: {data!r}")
    return data


def _data_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    return None


def _run_status(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, dict) and data.get("status"):
        return str(data["status"])
    if payload.get("status"):
        return str(payload["status"])
    return None


def _is_transport_error(exc: HttpError) -> bool:
    return " failed:" in str(exc)

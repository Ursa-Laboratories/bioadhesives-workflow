"""Operator-facing health checks for the manual workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class HealthTarget:
    name: str
    call: Callable[[], Mapping[str, Any]]


@dataclass(frozen=True)
class HealthResult:
    name: str
    ok: bool
    detail: str
    payload: Mapping[str, Any] | None = None
    error: str | None = None


def run_health_checks(
    targets: Sequence[HealthTarget],
    *,
    progress_fn: Callable[[str], None] | None = None,
) -> list[HealthResult]:
    results: list[HealthResult] = []
    for target in targets:
        if progress_fn:
            progress_fn(f"Checking {target.name}...")
        try:
            payload = target.call()
        except Exception as exc:  # noqa: BLE001 - report every machine, not just first failure
            results.append(
                HealthResult(
                    name=target.name,
                    ok=False,
                    detail=f"offline: {type(exc).__name__}: {exc}",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        ok, detail = _payload_status(payload)
        results.append(HealthResult(name=target.name, ok=ok, detail=detail, payload=payload))
    return results


def format_health_report(results: Sequence[HealthResult]) -> str:
    lines = ["Health check:"]
    for result in results:
        mark = "✅" if result.ok else "❌"
        lines.append(f"  {mark} {result.name:<14} {result.detail}")
    return "\n".join(lines)


def failed_health_names(results: Sequence[HealthResult]) -> list[str]:
    return [result.name for result in results if not result.ok]


def _payload_status(payload: Mapping[str, Any]) -> tuple[bool, str]:
    if not isinstance(payload, Mapping):
        return False, f"unexpected response: {payload!r}"
    if payload.get("busy"):
        return False, f"online but busy with {payload.get('current_run_id') or 'unknown run'}"
    status = str(payload.get("status") or "").lower()
    ok = status in ("", "ok", "running", "healthy", "full", "skipped")
    return ok, _health_detail(payload)


def _health_detail(payload: Mapping[str, Any]) -> str:
    pieces = []
    status = payload.get("status")
    if status:
        pieces.append(f"status={status}")
    device = payload.get("station_id") or payload.get("device")
    if device:
        pieces.append(f"id={device}")
    cubos_version = payload.get("cubos_version")
    if cubos_version:
        pieces.append(f"cubos={cubos_version}")
    return " ".join(pieces) or "reachable"

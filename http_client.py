"""Small HTTP helpers used by the manual workcell clients."""

from __future__ import annotations

from typing import Any

import requests


class HttpError(RuntimeError):
    """A device endpoint returned a transport error or a non-2xx status."""


def post_json(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    try:
        resp = session.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise HttpError(f"POST {url} failed: {exc}") from exc
    return _decode(resp, url)


def get_json(session: requests.Session, url: str, *, timeout: float) -> dict[str, Any]:
    try:
        resp = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise HttpError(f"GET {url} failed: {exc}") from exc
    return _decode(resp, url)


def new_session() -> requests.Session:
    return requests.Session()


def _decode(resp: requests.Response, url: str) -> dict[str, Any]:
    if resp.status_code >= 400:
        raise HttpError(f"{url} -> HTTP {resp.status_code}: {_safe_body(resp)}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise HttpError(f"{url} -> non-JSON response: {resp.text[:200]!r}") from exc
    if not isinstance(data, dict):
        raise HttpError(f"{url} -> JSON response is not an object: {data!r}")
    return data


def _safe_body(resp: requests.Response) -> str:
    try:
        return str(resp.json())
    except ValueError:
        return resp.text[:300]

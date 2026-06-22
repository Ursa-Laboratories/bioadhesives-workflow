"""Render per-well CubOS protocol YAMLs."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_WELL_RE = re.compile(r"^[A-Za-z]+[0-9]+$")
_REF_LINE_RE = re.compile(
    r"(?P<head>^[ \t]*(?:position|plate)[ \t]*:[ \t]*[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*\.)"
    r"(?P<well>[A-Za-z]+[0-9]+)"
    r"(?P<tail>[ \t]*(?:#.*)?)$",
    re.MULTILINE,
)
_PLACEHOLDER = "{{WELL}}"


def render_protocol(base_protocol: str | Path, well: str) -> str:
    well = _normalize_well(well)
    text = Path(base_protocol).read_text() if isinstance(base_protocol, Path) else str(base_protocol)
    if _PLACEHOLDER in text:
        return text.replace(_PLACEHOLDER, well)
    matches = list(_REF_LINE_RE.finditer(text))
    if not matches:
        raise ValueError("base protocol has no rewritable well reference")
    return _REF_LINE_RE.sub(lambda match: f"{match.group('head')}{well}{match.group('tail')}", text)


def apply_overrides(
    protocol_yaml: str,
    *,
    scalar: dict | None = None,
    method_kwargs: dict | None = None,
) -> str:
    if not scalar and not method_kwargs:
        return protocol_yaml
    doc = yaml.safe_load(protocol_yaml) or {}
    for step in doc.get("protocol") or []:
        if not isinstance(step, dict):
            continue
        for command, body in step.items():
            if command not in ("measure", "scan") or not isinstance(body, dict):
                continue
            if scalar:
                body.update(scalar)
            if method_kwargs:
                if not isinstance(body.get("method_kwargs"), dict):
                    body["method_kwargs"] = {}
                body["method_kwargs"].update(method_kwargs)
    return yaml.safe_dump(doc, sort_keys=False)


def _normalize_well(well: str) -> str:
    value = str(well).strip().upper()
    if not _WELL_RE.match(value):
        raise ValueError(f"not a well id: {well!r}")
    return value

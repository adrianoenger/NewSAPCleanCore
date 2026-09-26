"""Versioned prompt/schema registry (ADR-012).

Each persistable AI capability registers one or more `PromptSchemaVersion`s keyed by
`capability` -> `version`. Domain code resolves a version explicitly (or the latest) and
persists the resolved `(capability, version)` alongside its result, so a later prompt/schema
change never silently reinterprets an already-persisted output.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromptSchemaVersion:
    capability: str
    version: str
    system_prompt: str
    json_schema: dict[str, Any]
    schema_name: str


_REGISTRY: dict[str, dict[str, PromptSchemaVersion]] = {}


def register(entry: PromptSchemaVersion) -> None:
    _REGISTRY.setdefault(entry.capability, {})[entry.version] = entry


def get_version(capability: str, version: str | None = None) -> PromptSchemaVersion:
    versions = _REGISTRY.get(capability)
    if not versions:
        raise KeyError(f"No prompt/schema versions registered for capability={capability!r}")
    resolved = version or latest_version(capability)
    if resolved not in versions:
        raise KeyError(f"Unknown version {resolved!r} for capability={capability!r}")
    return versions[resolved]


def latest_version(capability: str) -> str:
    versions = _REGISTRY.get(capability)
    if not versions:
        raise KeyError(f"No prompt/schema versions registered for capability={capability!r}")
    return sorted(versions, key=lambda v: int(v.lstrip("v")))[-1]

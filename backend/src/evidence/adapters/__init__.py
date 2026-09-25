"""Registry mapping `dataset_type` to its adapter module (ADR-017).

Downstream code (pipeline stage, API routes) dispatches through this registry
instead of importing `panaya`/`signavio`/etc directly, so adding a new
provider means adding one entry here — nothing else branches on provider identity.

FUE User Validation was dropped (see ADR-017): the real export's `.bin` payloads are a
proprietary, high-entropy compressed format (confirmed ~7.9 bits/byte Shannon entropy, no
match against zlib/gzip/bz2/lzma) with no available specification or decoder — decoding it
would mean guessing the binary schema, which ADR-017 explicitly prohibits.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType

from evidence.adapters import hana_sizing, panaya, readiness_check, signavio

ADAPTERS: dict[str, ModuleType] = {
    panaya.DATASET_TYPE: panaya,
    signavio.DATASET_TYPE: signavio,
    hana_sizing.DATASET_TYPE: hana_sizing,
    readiness_check.DATASET_TYPE: readiness_check,
}


def detect_adapter(filename: str, file_path: Path) -> ModuleType | None:
    """Return the first adapter whose `detect(filename, file_path)` matches, or None.

    `file_path` must already contain the uploaded bytes — detection sniffs actual
    ZIP/XML/JSON structure, not just the filename (see `evidence.adapters.base`).
    """
    for adapter in ADAPTERS.values():
        if adapter.detect(filename, file_path):
            return adapter
    return None


def get_adapter(dataset_type: str) -> ModuleType | None:
    return ADAPTERS.get(dataset_type)

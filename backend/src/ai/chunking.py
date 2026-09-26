"""Structural ABAP chunking for large objects (ADR-012 — bounded prompt/context size).

Splits on ABAP block-end statements (ENDMETHOD/ENDFORM/ENDMODULE/ENDFUNCTION) so a chunk never
cuts through the middle of a routine. Content with no recognized boundary (e.g. a DDIC listing,
or a single routine larger than the budget) falls back to returning it as one chunk — callers
decide how many chunks to actually send (see `ai.object_understanding.evidence_package`).
"""
from __future__ import annotations

import re

_BOUNDARY_RE = re.compile(r"^\s*END(METHOD|FORM|MODULE|FUNCTION)\b", re.IGNORECASE)

DEFAULT_MAX_CHUNK_CHARS = 6000


def chunk_source(content: str, max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> list[str]:
    """Split `content` into structurally-bounded chunks of at most ~`max_chunk_chars` each."""
    if len(content) <= max_chunk_chars:
        return [content]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in content.splitlines(keepends=True):
        current.append(line)
        current_len += len(line)
        if current_len >= max_chunk_chars and _BOUNDARY_RE.match(line):
            chunks.append("".join(current))
            current = []
            current_len = 0

    if current:
        chunks.append("".join(current))

    return chunks or [content]

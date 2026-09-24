"""Parsed object data structures returned by parsers before DB persistence."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedObject:
    """A SAP object extracted from a source file."""

    object_type: str  # class | function_module | report | program | ddic_table | ddic_domain
    object_name: str
    description: str = ""
    line_start: int = 1
    line_end: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

"""Detect deterministic ABAP dependencies from source content.

Detects CALL FUNCTION, INCLUDE, class inheritance, and TABLES usage.
Returns a list of DetectedDependency objects for persistence.
"""
import re
from dataclasses import dataclass

_CALL_FUNC = re.compile(r"^\s*CALL\s+FUNCTION\s+'(\w+)'", re.IGNORECASE | re.MULTILINE)
_INCLUDE = re.compile(r"^\s*INCLUDE\s+(\w+)\s*\.", re.IGNORECASE | re.MULTILINE)
_INHERITS = re.compile(r"INHERITING\s+FROM\s+(\w+)", re.IGNORECASE)
_TABLES_LINE = re.compile(r"^\s*TABLES\s*:\s*(.+?)\.", re.IGNORECASE | re.MULTILINE | re.DOTALL)


@dataclass
class DetectedDependency:
    target_name: str
    target_type: str | None
    dep_type: str
    source_line: int | None
    confidence: str = "CERTAIN"


def detect_dependencies(content: str, object_type: str, attributes: dict) -> list[DetectedDependency]:
    """Detect all deterministic dependencies for a single SAP object."""
    deps: list[DetectedDependency] = []
    lines = content.splitlines()

    # CALL FUNCTION dependencies
    for m in _CALL_FUNC.finditer(content):
        line_num = content[: m.start()].count("\n") + 1
        target = m.group(1).upper()
        deps.append(DetectedDependency(
            target_name=target,
            target_type="function_module",
            dep_type="CALL_FUNCTION",
            source_line=line_num,
        ))

    # INCLUDE dependencies
    for m in _INCLUDE.finditer(content):
        line_num = content[: m.start()].count("\n") + 1
        target = m.group(1).upper()
        deps.append(DetectedDependency(
            target_name=target,
            target_type=None,
            dep_type="INCLUDE",
            source_line=line_num,
        ))

    # Inheritance (class only) — from parsed attributes
    if object_type == "class" and attributes.get("superclass"):
        deps.append(DetectedDependency(
            target_name=str(attributes["superclass"]).upper(),
            target_type="class",
            dep_type="INHERITS_FROM",
            source_line=None,
        ))

    # TABLES usage (program/report) — from parsed attributes
    for table in attributes.get("tables", []):
        deps.append(DetectedDependency(
            target_name=str(table).upper(),
            target_type="ddic_table",
            dep_type="USES_TABLE",
            source_line=None,
        ))

    return _deduplicate(deps)


def _deduplicate(deps: list[DetectedDependency]) -> list[DetectedDependency]:
    seen: set[tuple] = set()
    result: list[DetectedDependency] = []
    for d in deps:
        key = (d.target_name, d.dep_type)
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result

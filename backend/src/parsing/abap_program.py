"""Parser for ABAP report/program source files."""
import re
from parsing.models import ParsedObject

_REPORT = re.compile(r"^\s*REPORT\s+(\w+)", re.IGNORECASE)
_PROGRAM = re.compile(r"^\s*PROGRAM\s+(\w+)", re.IGNORECASE)
_TABLES = re.compile(r"^\s*TABLES\s*:\s*(.+)\.", re.IGNORECASE)
_SELECT_OPT = re.compile(r"\bso_(\w+)\b", re.IGNORECASE)
_PARAM = re.compile(r"\bp_(\w+)\b", re.IGNORECASE)


def parse_abap_program(content: str) -> list[ParsedObject]:
    lines = content.splitlines()

    prog_name: str | None = None
    prog_line = 1
    tables: list[str] = []
    select_options: list[str] = []
    parameters: list[str] = []

    for i, line in enumerate(lines, start=1):
        if prog_name is None:
            for pattern in (_REPORT, _PROGRAM):
                m = pattern.match(line)
                if m:
                    prog_name = m.group(1).upper()
                    prog_line = i
                    break
            continue

        t = _TABLES.match(line)
        if t:
            tables.extend([s.strip().upper() for s in t.group(1).split(",")])

        for so in _SELECT_OPT.finditer(line):
            name = f"SO_{so.group(1).upper()}"
            if name not in select_options:
                select_options.append(name)

        for p in _PARAM.finditer(line):
            name = f"P_{p.group(1).upper()}"
            if name not in parameters:
                parameters.append(name)

    if prog_name is None:
        return []

    attrs: dict = {}
    if tables:
        attrs["tables"] = tables
    if select_options:
        attrs["select_options"] = select_options
    if parameters:
        attrs["parameters"] = parameters

    return [
        ParsedObject(
            object_type="report",
            object_name=prog_name,
            line_start=prog_line,
            line_end=len(lines),
            attributes=attrs,
        )
    ]

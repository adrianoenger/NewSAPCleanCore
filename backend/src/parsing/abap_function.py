"""Parser for ABAP function module source files (.abap containing FUNCTION)."""
import re
from parsing.models import ParsedObject

_FUNC_START = re.compile(r"^\s*FUNCTION\s+(\w+)\s*\.", re.IGNORECASE)
_ENDFUNC = re.compile(r"^\s*ENDFUNCTION\s*\.", re.IGNORECASE)
_IMPORTING = re.compile(r"^\*\"\s+VALUE\((\w+)\)\s+TYPE\s+(\S+)", re.IGNORECASE)
_EXPORTING = re.compile(r"^\*\"\s+EXPORTING", re.IGNORECASE)
_IMPORTING_SECTION = re.compile(r"^\*\"\s+IMPORTING", re.IGNORECASE)


def parse_abap_function(content: str) -> list[ParsedObject]:
    lines = content.splitlines()
    results: list[ParsedObject] = []

    func_start: int | None = None
    func_name: str | None = None
    importing: list[str] = []
    exporting: list[str] = []
    in_importing = False
    in_exporting = False

    _param = re.compile(r"^\*\"\s+VALUE\((\w+)\)\s+TYPE\s+(\S+)", re.IGNORECASE)
    _sec_import = re.compile(r"^\*\"\s+IMPORTING", re.IGNORECASE)
    _sec_export = re.compile(r"^\*\"\s+EXPORTING", re.IGNORECASE)

    for i, line in enumerate(lines, start=1):
        if func_start is None:
            m = _FUNC_START.match(line)
            if m:
                func_name = m.group(1).upper()
                func_start = i
                importing = []
                exporting = []
                in_importing = False
                in_exporting = False
            continue

        if _sec_import.match(line):
            in_importing = True
            in_exporting = False
            continue
        if _sec_export.match(line):
            in_exporting = True
            in_importing = False
            continue

        pm = _param.match(line)
        if pm:
            pname = f"{pm.group(1)}:{pm.group(2)}"
            if in_importing:
                importing.append(pname)
            elif in_exporting:
                exporting.append(pname)

        if _ENDFUNC.match(line):
            attrs: dict = {}
            if importing:
                attrs["importing"] = importing
            if exporting:
                attrs["exporting"] = exporting
            results.append(
                ParsedObject(
                    object_type="function_module",
                    object_name=func_name or "",
                    line_start=func_start,
                    line_end=i,
                    attributes=attrs,
                )
            )
            func_start = None
            func_name = None

    return results

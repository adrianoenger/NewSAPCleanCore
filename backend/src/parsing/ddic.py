"""Parser for DDIC source files (.tabl, .doma, etc.)."""
import re
from parsing.models import ParsedObject

_TABLE_NAME = re.compile(r"DDIC Table Definition:\s*(\w+)", re.IGNORECASE)
_DOMAIN_NAME = re.compile(r"DDIC Domain:\s*(\w+)", re.IGNORECASE)
_TABLE_TYPE = re.compile(r"Table Type:\s*(.+)", re.IGNORECASE)
_DELIVERY = re.compile(r"Delivery Class:\s*(\w+)", re.IGNORECASE)
_FIELD = re.compile(r"^\s+(\w+)\s+\w+\s+\d+\s+(.+)$")
_FIXED_VAL = re.compile(r"^\s+(\w+)\s+(.+)$")
_DATA_TYPE = re.compile(r"Data Type:\s*(\w+)", re.IGNORECASE)
_LENGTH = re.compile(r"Length:\s*(\d+)", re.IGNORECASE)


def parse_ddic(content: str, filename: str = "") -> list[ParsedObject]:
    lines = content.splitlines()

    # Determine type from header or extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Try table first
    m_table = None
    m_domain = None
    for i, line in enumerate(lines, start=1):
        if m_table is None:
            m_table = _TABLE_NAME.search(line)
        if m_domain is None:
            m_domain = _DOMAIN_NAME.search(line)

    if m_table:
        return _parse_table(lines, m_table)
    if m_domain:
        return _parse_domain(lines, m_domain)

    # Fallback: use filename stem
    stem = filename.split("/")[-1].split("\\")[-1].rsplit(".", 1)[0].upper()
    if ext in ("tabl",):
        return [ParsedObject(object_type="ddic_table", object_name=stem, line_start=1)]
    if ext in ("doma",):
        return [ParsedObject(object_type="ddic_domain", object_name=stem, line_start=1)]

    return []


def _parse_table(lines: list[str], name_match: re.Match) -> list[ParsedObject]:
    name = name_match.group(1).upper()
    table_type = ""
    delivery = ""
    fields: list[str] = []
    in_fields = False

    for line in lines:
        tt = _TABLE_TYPE.search(line)
        if tt:
            table_type = tt.group(1).strip()
        dc = _DELIVERY.search(line)
        if dc:
            delivery = dc.group(1).strip()
        if line.strip().startswith("Fields:"):
            in_fields = True
            continue
        if in_fields:
            fm = _FIELD.match(line)
            if fm:
                fields.append(f"{fm.group(1).strip()}:{fm.group(2).strip()}")

    attrs: dict = {}
    if table_type:
        attrs["table_type"] = table_type
    if delivery:
        attrs["delivery_class"] = delivery
    if fields:
        attrs["fields"] = fields

    return [
        ParsedObject(
            object_type="ddic_table",
            object_name=name,
            line_start=1,
            line_end=None,
            attributes=attrs,
        )
    ]


def _parse_domain(lines: list[str], name_match: re.Match) -> list[ParsedObject]:
    name = name_match.group(1).upper()
    data_type = ""
    length = ""
    fixed_vals: list[str] = []
    in_fixed = False

    for line in lines:
        dt = _DATA_TYPE.search(line)
        if dt:
            data_type = dt.group(1).strip()
        ln = _LENGTH.search(line)
        if ln:
            length = ln.group(1).strip()
        if "Fixed Values" in line:
            in_fixed = True
            continue
        if in_fixed:
            fv = _FIXED_VAL.match(line)
            if fv:
                fixed_vals.append(f"{fv.group(1).strip()}:{fv.group(2).strip()}")

    attrs: dict = {}
    if data_type:
        attrs["data_type"] = data_type
    if length:
        attrs["length"] = length
    if fixed_vals:
        attrs["fixed_values"] = fixed_vals

    return [
        ParsedObject(
            object_type="ddic_domain",
            object_name=name,
            line_start=1,
            line_end=None,
            attributes=attrs,
        )
    ]

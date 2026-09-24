"""Dispatches a source file to the appropriate parser based on category/extension."""
from parsing.abap_class import parse_abap_class
from parsing.abap_function import parse_abap_function
from parsing.abap_program import parse_abap_program
from parsing.ddic import parse_ddic
from parsing.models import ParsedObject


def parse_file(content: str, filename: str, category: str) -> list[ParsedObject]:
    """Return parsed SAP objects from a source file.

    Dispatches based on category (from ingestion classifier) and falls back
    to extension-based heuristics.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if category in ("ddic",) or ext in ("tabl", "doma", "dtel", "stru", "type"):
        return parse_ddic(content, filename)

    if category in ("abap_source",):
        return _dispatch_abap(content, filename)

    if category in ("cds",):
        return []  # CDS parsing deferred to SPRINT-04+

    return []


def _dispatch_abap(content: str, filename: str) -> list[ParsedObject]:
    """Detect ABAP object type from content and dispatch to correct parser."""
    upper = content.upper()

    if "CLASS" in upper and "DEFINITION" in upper:
        objects = parse_abap_class(content)
        if objects:
            return objects

    if upper.lstrip().startswith("FUNCTION "):
        objects = parse_abap_function(content)
        if objects:
            return objects

    if upper.lstrip().startswith("REPORT ") or upper.lstrip().startswith("PROGRAM "):
        return parse_abap_program(content)

    # Last resort: try all parsers
    for parser in (parse_abap_class, parse_abap_function, parse_abap_program):
        result = parser(content)
        if result:
            return result

    return []

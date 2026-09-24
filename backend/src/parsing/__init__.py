"""SAP object parsing — extracts SAPObject entities from classified source files."""
from parsing.abap_class import parse_abap_class
from parsing.abap_function import parse_abap_function
from parsing.abap_program import parse_abap_program
from parsing.ddic import parse_ddic
from parsing.dispatcher import parse_file

__all__ = [
    "parse_abap_class",
    "parse_abap_function",
    "parse_abap_program",
    "parse_ddic",
    "parse_file",
]

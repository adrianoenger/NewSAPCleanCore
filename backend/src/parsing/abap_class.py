"""Parser for ABAP class source files (.abap containing CLASS DEFINITION)."""
import re
from parsing.models import ParsedObject

_CLASS_DEF = re.compile(r"^\s*CLASS\s+(\w+)\s+DEFINITION", re.IGNORECASE)
_CLASS_IMPL = re.compile(r"^\s*CLASS\s+(\w+)\s+IMPLEMENTATION", re.IGNORECASE)
_ENDCLASS = re.compile(r"^\s*ENDCLASS\s*\.", re.IGNORECASE)
_METHOD_DEF = re.compile(r"^\s*METHODS?\s*:\s*(\w+)", re.IGNORECASE)
_INHERITING = re.compile(r"INHERITING\s+FROM\s+(\w+)", re.IGNORECASE)
_SUPERCLASS = re.compile(r"INHERITING\s+FROM\s+(\w+)", re.IGNORECASE)


def parse_abap_class(content: str) -> list[ParsedObject]:
    lines = content.splitlines()
    results: list[ParsedObject] = []

    def_start: int | None = None
    class_name: str | None = None
    methods: list[str] = []
    superclass: str | None = None

    for i, line in enumerate(lines, start=1):
        if def_start is None:
            m = _CLASS_DEF.match(line)
            if m:
                class_name = m.group(1).upper()
                def_start = i
                methods = []
                inh = _INHERITING.search(line)
                superclass = inh.group(1).upper() if inh else None
                continue

        if def_start is not None and class_name:
            inh = _INHERITING.search(line)
            if inh and superclass is None:
                superclass = inh.group(1).upper()

            mm = _METHOD_DEF.search(line)
            if mm:
                methods.append(mm.group(1).upper())

            if _ENDCLASS.match(line):
                attrs: dict = {"methods": methods}
                if superclass:
                    attrs["superclass"] = superclass
                results.append(
                    ParsedObject(
                        object_type="class",
                        object_name=class_name,
                        line_start=def_start,
                        line_end=i,
                        attributes=attrs,
                    )
                )
                def_start = None
                class_name = None
                methods = []
                superclass = None

    return results

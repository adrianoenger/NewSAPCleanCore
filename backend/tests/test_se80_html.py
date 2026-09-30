"""Unit tests for `parsing.se80_html` — recognizing and reassembling SE80 "Code listing" HTML
exports (real-world format confirmed against a customer export; see module docstring)."""
from __future__ import annotations

from parsing.abap_class import parse_abap_class
from parsing.se80_html import assemble_class_source, sniff_se80_fragment

_CLASS_HTML = """\
<!DOCTYPE html>
<html><head><title>ZCALL_WS</title></head>
<body>
<h2>Code listing for class: ZCALL_WS</h2>
<div class="codeComment">
**********************<br />
*   Class attributes. *<br />
**********************<br />
</div>
<div class="code">
class ZCALL_WS definition<br />
&nbsp;&nbsp;public<br />
&nbsp;&nbsp;final<br />
&nbsp;&nbsp;create&nbsp;public&nbsp;.<br />
<br />
public section.<br />
</div>
<div class="code">
&nbsp;&nbsp;methods&nbsp;<a&nbsp;href="public_methods/execute.html">EXECUTE</a><br />
&nbsp;&nbsp;&nbsp;&nbsp;importing<br />
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;INPUT&nbsp;type&nbsp;DATA&nbsp;.<br />
</div>
</body></html>
"""

_METHOD_HTML = """\
<!DOCTYPE html>
<html><head><title>EXECUTE</title></head>
<body>
<h2>Code listing for: EXECUTE</h2>
<div class="code">
METHOD execute.<br />
&nbsp;&nbsp;DATA:&nbsp;l_result&nbsp;TYPE&nbsp;string.<br />
ENDMETHOD.<br />
</div>
</body></html>
"""

_UNRELATED_HTML = "<html><body><h1>Not an SE80 export</h1></body></html>"


def test_sniff_recognizes_class_fragment() -> None:
    frag = sniff_se80_fragment(_CLASS_HTML)
    assert frag is not None
    assert frag.kind == "class"
    assert frag.name == "ZCALL_WS"
    assert "class ZCALL_WS definition" in frag.body
    assert "public section." in frag.body
    assert "methods EXECUTE" in frag.body
    # tags and entities are gone
    assert "<a" not in frag.body
    assert "&nbsp;" not in frag.body
    assert "<br" not in frag.body


def test_sniff_recognizes_method_fragment() -> None:
    frag = sniff_se80_fragment(_METHOD_HTML)
    assert frag is not None
    assert frag.kind == "method"
    assert frag.name == "EXECUTE"
    assert "METHOD execute." in frag.body
    assert "ENDMETHOD." in frag.body


def test_sniff_returns_none_for_unrelated_html() -> None:
    assert sniff_se80_fragment(_UNRELATED_HTML) is None


def test_assemble_appends_missing_endclass_and_wraps_methods() -> None:
    class_frag = sniff_se80_fragment(_CLASS_HTML)
    method_frag = sniff_se80_fragment(_METHOD_HTML)
    assembled = assemble_class_source(class_frag.name, class_frag.body, [method_frag.body])

    assert assembled.count("ENDCLASS.") == 2  # definition + implementation
    assert "CLASS ZCALL_WS IMPLEMENTATION." in assembled
    assert "METHOD execute." in assembled


def test_assemble_does_not_duplicate_existing_endclass() -> None:
    assembled = assemble_class_source("ZCL_X", "CLASS zcl_x DEFINITION.\nENDCLASS.", [])
    assert assembled.count("ENDCLASS.") == 1


def test_assembled_class_is_parseable_by_existing_class_parser() -> None:
    """The whole point: no changes needed to parse_abap_class itself once HTML is stripped and
    the definition is closed — this is what makes the fix low-risk for everything downstream."""
    class_frag = sniff_se80_fragment(_CLASS_HTML)
    method_frag = sniff_se80_fragment(_METHOD_HTML)
    assembled = assemble_class_source(class_frag.name, class_frag.body, [method_frag.body])

    objects = parse_abap_class(assembled)
    assert len(objects) == 1
    obj = objects[0]
    assert obj.object_type == "class"
    assert obj.object_name == "ZCALL_WS"
    assert "EXECUTE" in obj.attributes["methods"]

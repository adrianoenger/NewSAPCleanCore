"""Recognizes and reassembles SE80 "Code listing" HTML exports.

A real-world SAP export tool (confirmed against a customer's actual ~3469-file export, never
seen or tested before this fix) writes one HTML file per class definition and one HTML file per
method, with the real ABAP source embedded inside `<div class="code">`/`<div class="codeComment">`
blocks (`<br />` per line, `&nbsp;`-padded indentation). Neither file is valid standalone ABAP on
its own: the class-definition file never emits its own closing `ENDCLASS.` (it is a documentation
listing, not a compiler-ready file), and a method file has no enclosing `CLASS`/`METHOD` context
of its own module beyond `METHOD x. ... ENDMETHOD.`.

Rather than writing a new parser for this format, `assemble_class_source` combines a class's
definition fragment with its methods' bodies into one real, complete ABAP class listing that the
existing `parsing.abap_class.parse_abap_class` (unchanged) can already parse — so everything
downstream (SourceViewer, dependency detection, AI evidence packages) keeps working unmodified,
because the result is a genuine file written to disk and parsed through the normal path
(`pipeline.stages._assemble_se80_class_exports`).

ADR-016's "do not hard-code the reviewed sample as the only valid schema" applies here too: only
the two `<h2>` markers below are load-bearing signatures; everything else about the surrounding
HTML/CSS is ignored, so cosmetic export-tool differences (styling, footer text) do not matter.
"""
from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass

_DIV_BLOCK_RE = re.compile(r'<div class="(?:code|codeComment)">(.*?)</div>', re.IGNORECASE | re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_CLASS_TITLE_RE = re.compile(r"<h2>\s*Code listing for class:\s*([\w/]+)\s*</h2>", re.IGNORECASE)
_METHOD_TITLE_RE = re.compile(r"<h2>\s*Code listing for:\s*([\w/]+)\s*</h2>", re.IGNORECASE)
_ENDCLASS_RE = re.compile(r"ENDCLASS\s*\.\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Se80Fragment:
    kind: str  # "class" | "method"
    name: str
    body: str  # HTML-stripped, ABAP-looking text


def _extract_code_text(raw_html: str) -> str:
    """Pull the real content out of every code/codeComment block, in document order, decoding
    HTML entities and dropping any remaining tags (e.g. the `<a href="...">NAME</a>` method-name
    links in a class-definition file become plain `NAME` text)."""
    blocks = _DIV_BLOCK_RE.findall(raw_html)
    lines = []
    for block in blocks:
        block = _BR_RE.sub("\n", block)
        block = _TAG_RE.sub("", block)
        block = html_lib.unescape(block).replace("\xa0", " ")  # &nbsp; -> plain space, not NBSP
        lines.append(block.strip("\n"))
    return "\n".join(lines).strip()


def sniff_se80_fragment(content: str) -> Se80Fragment | None:
    """Return the parsed fragment if `content` is a recognized SE80 HTML code listing, else None
    (any other `.html`/`.htm` file under the `abap_source` category is left untouched — no
    behavior change for it)."""
    m = _CLASS_TITLE_RE.search(content)
    if m:
        return Se80Fragment(kind="class", name=m.group(1).upper(), body=_extract_code_text(content))
    m = _METHOD_TITLE_RE.search(content)
    if m:
        return Se80Fragment(kind="method", name=m.group(1).upper(), body=_extract_code_text(content))
    return None


def assemble_class_source(class_name: str, class_def_body: str, method_bodies: list[str]) -> str:
    """Combine a class-definition fragment (missing its own `ENDCLASS.`) with its methods'
    already-complete `METHOD ... ENDMETHOD.` bodies into one real, parseable ABAP class listing."""
    definition = class_def_body.rstrip()
    if not _ENDCLASS_RE.search(definition):
        definition += "\nENDCLASS."

    if not method_bodies:
        return definition + "\n"

    implementation = "\n\n".join(b.strip() for b in method_bodies)
    return f"{definition}\n\nCLASS {class_name} IMPLEMENTATION.\n\n{implementation}\n\nENDCLASS.\n"

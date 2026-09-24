"""Classifies files into artifact categories based on extension. No content parsing."""

from pathlib import Path

from persistence.models import ArtifactCategory

_EXT_MAP: dict[str, str] = {
    ".abap": ArtifactCategory.ABAP_SOURCE.value,
    ".prog": ArtifactCategory.ABAP_SOURCE.value,
    ".fugr": ArtifactCategory.ABAP_SOURCE.value,
    ".clas": ArtifactCategory.ABAP_SOURCE.value,
    ".intf": ArtifactCategory.ABAP_SOURCE.value,
    ".meth": ArtifactCategory.ABAP_SOURCE.value,
    # SAP HTML exports (ABAPDoc / SAP documentation export) embed ABAP source
    ".html": ArtifactCategory.ABAP_SOURCE.value,
    ".htm": ArtifactCategory.ABAP_SOURCE.value,
    ".xml": ArtifactCategory.XML_METADATA.value,
    ".xslt": ArtifactCategory.XML_METADATA.value,
    ".cds": ArtifactCategory.CDS.value,
    ".tabl": ArtifactCategory.DDIC.value,
    ".dtel": ArtifactCategory.DDIC.value,
    ".doma": ArtifactCategory.DDIC.value,
    ".ttyp": ArtifactCategory.DDIC.value,
    ".msag": ArtifactCategory.DDIC.value,
    ".yaml": ArtifactCategory.CONFIGURATION.value,
    ".yml": ArtifactCategory.CONFIGURATION.value,
    ".json": ArtifactCategory.CONFIGURATION.value,
    ".ini": ArtifactCategory.CONFIGURATION.value,
    ".cfg": ArtifactCategory.CONFIGURATION.value,
    ".properties": ArtifactCategory.CONFIGURATION.value,
    ".md": ArtifactCategory.DOCUMENTATION.value,
    ".txt": ArtifactCategory.DOCUMENTATION.value,
    ".pdf": ArtifactCategory.DOCUMENTATION.value,
    ".rst": ArtifactCategory.DOCUMENTATION.value,
}

# Multi-extension patterns (.clas.xml → abap_source takes priority over xml_metadata)
_SUFFIX_PAIRS: dict[str, str] = {
    ".clas.xml": ArtifactCategory.ABAP_SOURCE.value,
    ".intf.xml": ArtifactCategory.ABAP_SOURCE.value,
    ".prog.xml": ArtifactCategory.ABAP_SOURCE.value,
    ".fugr.xml": ArtifactCategory.ABAP_SOURCE.value,
}


def classify(path: str) -> str:
    """Return the ArtifactCategory value for the given file path."""
    name = Path(path).name.lower()
    for suffix, cat in _SUFFIX_PAIRS.items():
        if name.endswith(suffix):
            return cat
    ext = Path(path).suffix.lower()
    return _EXT_MAP.get(ext, ArtifactCategory.OTHER.value)

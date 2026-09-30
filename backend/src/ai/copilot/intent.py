"""Deterministic question-intent routing for the Copilot context (SPRINT-18 CAP-004).

No LLM involved: plain keyword matching (pt-BR/en, accent-insensitive) decides which assessment
catalog items `ai.copilot.context` adds, so a question like "Quais objetos o clean core
categorizou como Remediar?" gets the objects/applications of that category as citable context
instead of only aggregate counts.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# ADR-018 taxonomy — pt-BR display labels (mirrors frontend cleanCoreDisplay.tsx).
RECOMMENDATION_LABELS: dict[str, str] = {
    "MODERNIZAR": "Modernizar",
    "MANTER_AS_IS": "Manter as-is",
    "REMEDIAR": "Remediar",
    "DESCONTINUAR": "Descontinuar",
    "REIMPLEMENTAR_EXTENSAO": "Reimplementar como extensão",
    "SUBSTITUIR_STANDARD": "Substituir por standard",
    "ATUALIZAR_OSS": "Atualizar via nota OSS",
}
UNCLASSIFIED_LABEL = "Não classificado"

# Word stems matched against the normalized question (lowercase, no accents).
_CATEGORY_STEMS: dict[str, tuple[str, ...]] = {
    "MODERNIZAR": ("moderniz", "modernis"),
    "MANTER_AS_IS": ("manter", "mantid", "as-is", "as is", "retain"),
    "REMEDIAR": ("remedi", "remediat"),
    "DESCONTINUAR": ("descontinu", "retire", "retir", "obsolet"),
    "REIMPLEMENTAR_EXTENSAO": ("reimplement", "extens", "side-by-side", "btp", "replatform"),
    "SUBSTITUIR_STANDARD": ("substitu", "standard", "padrao"),
    "ATUALIZAR_OSS": ("oss", "nota sap", "sap note"),
}
_OBJECT_STEMS = ("objeto", "object", "classe", "class", "programa", "report", "funcao", "function", "modulo", "listar", "liste", "lista", "list ")
_APPLICATION_STEMS = ("aplicac", "application", "app ", "apps", "customizac", "clean core", "categor", "classific", "recomend", "recommend")
_ATC_STEMS = ("atc", "finding", "achado", "prioridade", "priority", "check", "erro", "critic")
_UNCLASSIFIED_STEMS = ("nao classific", "sem classific", "unclassif")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"\s+", " ", "".join(c for c in decomposed if not unicodedata.combining(c))) + " "


@dataclass(frozen=True)
class CopilotIntent:
    wants_objects: bool = False
    wants_applications: bool = False
    wants_atc: bool = False
    categories: frozenset[str] = field(default_factory=frozenset)
    wants_unclassified: bool = False


def detect_intent(question: str) -> CopilotIntent:
    q = _normalize(question)
    categories = frozenset(cat for cat, stems in _CATEGORY_STEMS.items() if any(s in q for s in stems))
    wants_unclassified = any(s in q for s in _UNCLASSIFIED_STEMS)
    return CopilotIntent(
        wants_objects=any(s in q for s in _OBJECT_STEMS),
        wants_applications=any(s in q for s in _APPLICATION_STEMS) or bool(categories) or wants_unclassified,
        wants_atc=any(s in q for s in _ATC_STEMS),
        categories=categories,
        wants_unclassified=wants_unclassified,
    )

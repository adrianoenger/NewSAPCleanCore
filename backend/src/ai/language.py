"""Output-language rule shared by every AI capability's prompt (SPRINT-18 CAP-001)."""
from __future__ import annotations

PT_BR_OUTPUT_RULE = """
Output language:
- Write every free-text field (purposes, descriptions, names, domains, conditions, actions, \
rationales, answers, summaries, concept labels) in Brazilian Portuguese (pt-BR), with correct \
accents and SAP-consultant vocabulary.
- Never translate enum values, ref_id values, SAP object names/identifiers, table/field names, \
ABAP keywords or code — copy them verbatim.
"""

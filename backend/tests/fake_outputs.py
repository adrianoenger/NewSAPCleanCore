"""Canned AI outputs shared by the per-file fake providers (SPRINT-18).

Every full pipeline run now reaches the `executive_summary` stage; fakes that do not care about it
fall back to this INSUFFICIENT_CONTEXT output instead of a KeyError.
"""
EXECUTIVE_SUMMARY_SCHEMA = "executive_summary_result"
INSUFFICIENT_EXECUTIVE_SUMMARY_OUTPUT = {"status": "INSUFFICIENT_CONTEXT", "markdown": "", "evidence_refs": []}

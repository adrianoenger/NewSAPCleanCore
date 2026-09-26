"""Embeddings and semantic retrieval (ADR-004, Baseline core rule 14, SPRINT-14).

Unlike the other `ai.*` capabilities, embeddings are not a structured/validated interpretive
conclusion (ADR-012 applies to persistable AI *interpretations* like Object Understanding or
Clean Core Analysis) — they are a derived index artifact. No prompt/schema registration here;
`ai.embeddings.source_builder` builds embeddable text/metadata and `ai.embeddings.search` ranks
persisted vectors, both consumed by the `embeddings` pipeline stage (`pipeline/stages.py`).
"""

"""SAP knowledge guidance service (ADR-007) — builds a contextual query from a finding/
application, then queries or reuses cached guidance across the configured `SAPKnowledgeProvider`s.

Query-only-when-relevant is enforced two ways: (1) callers only trigger `fetch_guidance` from a
finding/application detail view, never a background/bulk job; (2) a target that already has a
persisted reference for a given provider is never re-queried — the persisted rows are the cache.
Reuse across *different* targets is still possible via `query_fingerprint` (ADR-007: "cache/reuse
semantically equivalent guidance when safe") since SAP/ABAP documentation is generic, not
customer evidence.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.knowledge_provider import KnowledgeQuery, SAPKnowledgeProvider, SAPKnowledgeProviderError
from persistence.models import Application, BusinessRule, SapKnowledgeReference, SapKnowledgeTargetType

_WHITESPACE = re.compile(r"\s+")


class SapKnowledgeTargetNotFound(Exception):
    """The referenced Application/BusinessRule does not exist under this assessment."""


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text.strip().lower())


def _fingerprint(provider_name: str, query_text: str) -> str:
    return hashlib.sha256(f"{provider_name}:{_normalize(query_text)}".encode("utf-8")).hexdigest()


def build_query_text(session: Session, assessment_id: int, target_type: str, target_id: int) -> str:
    """Derive the contextual query from the target's own content — never a free-text query
    supplied by the caller, so a guidance request always stays bound to a real finding/
    application (ADR-007)."""
    if target_type == SapKnowledgeTargetType.APPLICATION.value:
        app = session.get(Application, target_id)
        if app is None or app.assessment_id != assessment_id:
            raise SapKnowledgeTargetNotFound(f"Application {target_id} not found")
        text = f"{app.name}. {app.description}".strip(". ")
        return text or app.domain or f"Application {target_id}"
    if target_type == SapKnowledgeTargetType.BUSINESS_RULE.value:
        rule = session.get(BusinessRule, target_id)
        if rule is None or rule.assessment_id != assessment_id:
            raise SapKnowledgeTargetNotFound(f"BusinessRule {target_id} not found")
        return f"{rule.condition} {rule.action}".strip()
    raise ValueError(f"Unknown sap_knowledge target_type={target_type!r}")


def list_guidance(
    session: Session, assessment_id: int, target_type: str, target_id: int
) -> list[SapKnowledgeReference]:
    return list(
        session.scalars(
            select(SapKnowledgeReference)
            .where(
                SapKnowledgeReference.assessment_id == assessment_id,
                SapKnowledgeReference.target_type == target_type,
                SapKnowledgeReference.target_id == target_id,
            )
            .order_by(SapKnowledgeReference.created_at.desc())
        )
    )


def fetch_guidance(
    session: Session,
    assessment_id: int,
    target_type: str,
    target_id: int,
    providers: list[SAPKnowledgeProvider],
) -> list[SapKnowledgeReference]:
    """Ensure guidance exists for this target from every configured provider, then return the
    full persisted list. A provider that already has a reference for this exact target is
    skipped (already relevant, no repeat call); a provider error is skipped, not fatal — guidance
    is enrichment, never a blocking dependency of the demonstrable flow."""
    query_text = build_query_text(session, assessment_id, target_type, target_id)

    for provider in providers:
        already_present = session.scalars(
            select(SapKnowledgeReference.id).where(
                SapKnowledgeReference.target_type == target_type,
                SapKnowledgeReference.target_id == target_id,
                SapKnowledgeReference.provider == provider.name,
            )
        ).first()
        if already_present is not None:
            continue

        fingerprint = _fingerprint(provider.name, query_text)
        cached = session.scalars(
            select(SapKnowledgeReference)
            .where(
                SapKnowledgeReference.provider == provider.name,
                SapKnowledgeReference.query_fingerprint == fingerprint,
            )
            .order_by(SapKnowledgeReference.retrieved_at.desc())
        ).first()

        if cached is not None:
            session.add(
                SapKnowledgeReference(
                    assessment_id=assessment_id,
                    target_type=target_type,
                    target_id=target_id,
                    provider=provider.name,
                    query=query_text,
                    query_fingerprint=fingerprint,
                    title=cached.title,
                    reference=cached.reference,
                    summary=cached.summary,
                    retrieved_at=cached.retrieved_at,
                    reused_from_id=cached.id,
                )
            )
            continue

        try:
            result = provider.query(KnowledgeQuery(text=query_text))
        except SAPKnowledgeProviderError:
            continue

        retrieved_at = datetime.now(timezone.utc)
        for ref in result.references:
            session.add(
                SapKnowledgeReference(
                    assessment_id=assessment_id,
                    target_type=target_type,
                    target_id=target_id,
                    provider=provider.name,
                    query=query_text,
                    query_fingerprint=fingerprint,
                    title=ref.title,
                    reference=ref.reference,
                    summary=ref.summary,
                    retrieved_at=retrieved_at,
                )
            )

    session.commit()
    return list_guidance(session, assessment_id, target_type, target_id)

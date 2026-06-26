"""
Celery async task pipeline.
Orchestrates: ingest → extract → score → persist → alert.
"""
from __future__ import annotations

import os
from typing import Any

try:
    from celery import Celery
    celery_app = Celery(
        "horison_esg",
        broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    )
    celery_app.conf.task_serializer = "json"
    celery_app.conf.result_serializer = "json"
    CELERY_AVAILABLE = True
except ImportError:
    celery_app = None  # type: ignore
    CELERY_AVAILABLE = False


def _task(fn):
    """Decorator: registers as Celery task if available, else plain function."""
    if CELERY_AVAILABLE and celery_app:
        return celery_app.task(name=fn.__name__)(fn)
    return fn


@_task
def ingest_questionnaire(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Ingest a DDQ / questionnaire submission and trigger scoring."""
    from src.ingestion.extractor import QuestionnaireExtractor
    from src.ontology.esg_ontology import ESGOntology
    from src.scoring.engine import ScoringEngine
    from src.audit.ledger import AuditLedger

    ontology = ESGOntology()
    extractor = QuestionnaireExtractor(ontology=ontology)
    evidence = extractor.extract({"company_id": company_id, **payload})

    engine = ScoringEngine(ontology)
    score, alerts = engine.score(
        company_id=company_id,
        sector=payload.get("sector", "*"),
        evidence=evidence,
    )

    ledger = AuditLedger()
    audit_id = ledger.append(
        event_type="questionnaire_ingested",
        company_id=company_id,
        score_id=score.id,
        score_value=score.composite_score,
        confidence=score.confidence,
        evidence_count=score.evidence_count,
        greenwash_risk=score.greenwash_risk,
        payload={
            "score": score.model_dump(),
            "alerts": [a.model_dump() for a in alerts],
            "source": "questionnaire",
        },
    )
    return {"score_id": score.id, "audit_id": audit_id, "alert_count": len(alerts)}


@_task
def ingest_document(company_id: str, text: str, source_url: str = "",
                    sector: str = "*") -> dict[str, Any]:
    """Extract ESG evidence from a document and trigger scoring."""
    from src.ingestion.extractor import DocumentExtractor
    from src.ontology.esg_ontology import ESGOntology
    from src.scoring.engine import ScoringEngine
    from src.audit.ledger import AuditLedger

    ontology = ESGOntology()
    extractor = DocumentExtractor(ontology=ontology)
    evidence = extractor.extract_from_text(company_id, text, source_url or None)

    engine = ScoringEngine(ontology)
    score, alerts = engine.score(company_id=company_id, sector=sector, evidence=evidence)

    ledger = AuditLedger()
    audit_id = ledger.append(
        event_type="document_ingested",
        company_id=company_id,
        score_id=score.id,
        score_value=score.composite_score,
        confidence=score.confidence,
        evidence_count=score.evidence_count,
        greenwash_risk=score.greenwash_risk,
        payload={"score": score.model_dump(), "source_url": source_url},
    )
    return {"score_id": score.id, "audit_id": audit_id, "alert_count": len(alerts)}

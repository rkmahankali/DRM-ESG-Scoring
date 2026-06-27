"""FastAPI routes for the ESG Scoring Service."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from src.audit.ledger import AuditLedger
from src.graph.graph_service import GraphService
from src.ingestion.extractor import APIFeedExtractor, DocumentExtractor, QuestionnaireExtractor
from src.models.domain import Company, ESGScore, EvidenceItem, GreenwashAlert
from src.ontology.esg_ontology import ESGOntology
from src.scoring.engine import ScoringConfig, ScoringEngine
from src.scoring.peer_benchmarks import PeerBenchmarker

router = APIRouter()


# --- Shared singletons (injected via dependency) -----------------------

def get_ontology() -> ESGOntology:
    return ESGOntology()

def get_ledger() -> AuditLedger:
    return AuditLedger()

def get_engine(ontology: Annotated[ESGOntology, Depends(get_ontology)]) -> ScoringEngine:
    return ScoringEngine(ontology)

def get_graph() -> GraphService:
    from src.api.provenance import get_graph as _get_graph
    return _get_graph()

def get_benchmarker() -> PeerBenchmarker:
    return PeerBenchmarker.default_benchmarks()


# --- Request / Response schemas ----------------------------------------

class ScoreRequest(BaseModel):
    company: Company
    evidence: list[EvidenceItem]
    config: Optional[ScoringConfig] = None


class ScoreResponse(BaseModel):
    score: ESGScore
    alerts: list[GreenwashAlert]
    audit_id: str


class DocumentIngestRequest(BaseModel):
    company_id: str
    sector: str = "*"
    text: str
    source_url: Optional[str] = None


class QuestionnaireIngestRequest(BaseModel):
    company_id: str
    sector: str = "*"
    responses: dict


class APIFeedIngestRequest(BaseModel):
    company_id: str
    sector: str = "*"
    records: list[dict]


# --- Scoring endpoints --------------------------------------------------

@router.post("/score", response_model=ScoreResponse, summary="Score a company from pre-extracted evidence")
async def score_company(
    req: ScoreRequest,
    engine: Annotated[ScoringEngine, Depends(get_engine)],
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
    benchmarker: Annotated[PeerBenchmarker, Depends(get_benchmarker)],
    graph: Annotated[GraphService, Depends(get_graph)],
):
    if req.config:
        engine = ScoringEngine(engine.ontology, req.config)

    esg_score, alerts = engine.score(
        company_id=req.company.id,
        sector=req.company.sector,
        evidence=req.evidence,
    )
    esg_score = benchmarker.annotate(esg_score, req.company.sector)

    audit_id = ledger.append(
        event_type="score_computed",
        company_id=req.company.id,
        score_id=esg_score.id,
        score_value=esg_score.composite_score,
        confidence=esg_score.confidence,
        evidence_count=esg_score.evidence_count,
        greenwash_risk=esg_score.greenwash_risk,
        payload={
            "company": req.company.model_dump(),
            "score": esg_score.model_dump(),
            "alerts": [a.model_dump() for a in alerts],
        },
    )
    esg_score.audit_log_id = audit_id

    # Populate knowledge graph (in-memory or Neo4j)
    try:
        graph.store_company(req.company.id, req.company.name,
                            req.company.sector, req.company.jurisdiction,
                            req.company.is_listed)
        graph.store_evidence_items(req.evidence)
        graph.store_score(req.company.id, esg_score, req.evidence)
    except Exception:
        pass  # graph is best-effort; score is already persisted in audit ledger

    return ScoreResponse(score=esg_score, alerts=alerts, audit_id=audit_id)


@router.post("/ingest/document", summary="Extract ESG evidence from text/PDF and score")
async def ingest_document(
    req: DocumentIngestRequest,
    ontology: Annotated[ESGOntology, Depends(get_ontology)],
    engine: Annotated[ScoringEngine, Depends(get_engine)],
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
    benchmarker: Annotated[PeerBenchmarker, Depends(get_benchmarker)],
):
    extractor = DocumentExtractor(ontology=ontology)
    evidence = extractor.extract_from_text(req.company_id, req.text, req.source_url)
    score, alerts = engine.score(req.company_id, req.sector, evidence)
    score = benchmarker.annotate(score, req.sector)
    audit_id = ledger.append(
        event_type="document_ingested",
        company_id=req.company_id,
        score_id=score.id,
        score_value=score.composite_score,
        confidence=score.confidence,
        evidence_count=score.evidence_count,
        greenwash_risk=score.greenwash_risk,
        payload={"score": score.model_dump(), "source_url": req.source_url},
    )
    return {"score_id": score.id, "audit_id": audit_id,
            "composite_score": score.composite_score,
            "alert_count": len(alerts), "evidence_extracted": len(evidence)}


@router.post("/ingest/questionnaire", summary="Ingest DDQ / portfolio company questionnaire")
async def ingest_questionnaire(
    req: QuestionnaireIngestRequest,
    ontology: Annotated[ESGOntology, Depends(get_ontology)],
    engine: Annotated[ScoringEngine, Depends(get_engine)],
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
):
    extractor = QuestionnaireExtractor(ontology=ontology)
    evidence = extractor.extract({
        "company_id": req.company_id,
        "responses": req.responses,
    })
    score, alerts = engine.score(req.company_id, req.sector, evidence)
    audit_id = ledger.append(
        event_type="questionnaire_ingested",
        company_id=req.company_id,
        score_id=score.id,
        score_value=score.composite_score,
        confidence=score.confidence,
        evidence_count=score.evidence_count,
        greenwash_risk=score.greenwash_risk,
        payload={"score": score.model_dump()},
    )
    return {"score_id": score.id, "audit_id": audit_id,
            "composite_score": score.composite_score, "alert_count": len(alerts)}


@router.post("/ingest/feed", summary="Ingest numeric data from API feed or IoT")
async def ingest_feed(
    req: APIFeedIngestRequest,
    ontology: Annotated[ESGOntology, Depends(get_ontology)],
    engine: Annotated[ScoringEngine, Depends(get_engine)],
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
):
    extractor = APIFeedExtractor(ontology=ontology)
    evidence = extractor.extract(req.company_id, req.records)
    score, alerts = engine.score(req.company_id, req.sector, evidence)
    audit_id = ledger.append(
        event_type="feed_ingested",
        company_id=req.company_id,
        score_id=score.id,
        score_value=score.composite_score,
        confidence=score.confidence,
        evidence_count=score.evidence_count,
        greenwash_risk=score.greenwash_risk,
        payload={"score": score.model_dump()},
    )
    return {"score_id": score.id, "audit_id": audit_id,
            "composite_score": score.composite_score, "alert_count": len(alerts)}


# --- History & audit endpoints ------------------------------------------

@router.get("/score/{company_id}/history", summary="Score history with full lineage")
async def score_history(
    company_id: str,
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
):
    history = ledger.get_history(company_id)
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No scores found")
    return {"company_id": company_id, "history": history}


@router.get("/audit/{score_id}", summary="Full audit trail for a score")
async def audit_trail(
    score_id: str,
    ledger: Annotated[AuditLedger, Depends(get_ledger)],
):
    trail = ledger.get_score_audit(score_id)
    if not trail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Score not found")
    return {"score_id": score_id, "audit_trail": trail}


@router.get("/graph/evidence-chain/{score_id}", summary="Knowledge graph evidence chain")
async def evidence_chain(
    score_id: str,
    graph: Annotated[GraphClient, Depends(get_graph)],
):
    chain = graph.get_evidence_chain(score_id)
    return {"score_id": score_id, "evidence_chain": chain}


@router.get("/graph/supply-chain/{company_id}", summary="Supply chain ESG risk")
async def supply_chain_risk(
    company_id: str,
    graph: Annotated[GraphClient, Depends(get_graph)],
):
    return graph.supply_chain_esg_risk(company_id)


# --- Ontology endpoints -------------------------------------------------

@router.get("/metrics", summary="List metrics for a sector")
async def list_metrics(
    sector: str = "*",
    ontology: Annotated[ESGOntology, Depends(get_ontology)] = None,
):
    metrics = ontology.metrics_for_sector(sector)
    return {
        "sector": sector,
        "count": len(metrics),
        "metrics": [
            {
                "id": m.id, "name": m.name, "pillar": m.pillar,
                "category": m.category, "unit": m.unit,
                "outcome_based": m.outcome_based,
                "gri": m.gri_reference,
                "sfdr_pai": m.sfdr_pai_reference,
                "csrd": m.csrd_reference,
            }
            for m in metrics
        ],
    }


@router.get("/ontology/pillars", summary="ESG ontology structure")
async def ontology_pillars(
    ontology: Annotated[ESGOntology, Depends(get_ontology)] = None,
):
    return {
        pillar_id: {
            "name": p.name, "weight": p.weight,
            "categories": [
                {"id": c.id, "name": c.name, "weight": c.weight,
                 "metric_count": len(c.metrics)}
                for c in p.categories
            ],
        }
        for pillar_id, p in ontology.pillars.items()
    }

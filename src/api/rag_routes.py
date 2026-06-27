"""
GraphRAG API endpoints — semantic layer + context graph + AI explanations.
"""
from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.graph.graph_service import GraphService
from src.rag.graph_retriever import GraphRetriever
from src.rag.synthesizer import Synthesizer
from src.semantic.concept_layer import ConceptLayer
from src.semantic.regulatory_crosswalk import RegulatoryCrosswalk

router = APIRouter(prefix="/semantic", tags=["graphrag"])

_concept_layer = ConceptLayer()
_crosswalk     = RegulatoryCrosswalk()
_synthesizer   = Synthesizer()


def get_graph() -> GraphService:
    from src.api.provenance import get_graph as _get
    return _get()


# ── Semantic / Concept Layer ─────────────────────────────────────────────────

@router.get("/metric/{metric_id}/concept")
async def metric_concept(metric_id: str):
    """Semantic metadata for a metric: tags, SDG goals, TCFD pillar, data availability."""
    c = _concept_layer.get_concept(metric_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not in concept layer")
    return {
        "metric_id": c.metric_id,
        "concept_tags": c.concept_tags,
        "sdg_goals": c.sdg_goals,
        "tcfd_pillar": c.tcfd_pillar,
        "double_materiality": c.double_materiality,
        "data_availability": c.data_availability,
        "typical_evidence_type": c.typical_evidence_type,
    }


@router.get("/metric/{metric_id}/related")
async def metric_related(metric_id: str,
                          rel_types: Optional[List[str]] = Query(None)):
    """All semantic relationships from this metric (SIMILAR_TO, REINFORCES, CONFLICTS_WITH…)."""
    related = _concept_layer.get_related(metric_id, rel_types)
    return {
        "metric_id": metric_id,
        "relationships": [
            {"target": t, "rel_type": r, "weight": w, "description": d}
            for t,r,w,d in related
        ],
    }


@router.get("/metric/{metric_id}/regulatory")
async def metric_regulatory(metric_id: str):
    """Full regulatory cross-walk: GRI, SFDR PAI, CSRD ESRS, ISSB, SASB."""
    data = _crosswalk.as_dict(metric_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"No regulatory mapping for {metric_id}")
    return data


@router.get("/metric/{metric_id}/graph")
async def metric_semantic_graph(metric_id: str):
    """SVG-ready nodes + edges for the semantic relationship graph of a metric."""
    return _concept_layer.semantic_graph_json(metric_id)


@router.get("/sector/{sector}/materiality")
async def sector_materiality(sector: str, top: int = 10):
    """Top-N most material metrics for this sector (SFDR double-materiality lens)."""
    top_metrics = _concept_layer.top_material_metrics(sector, n=top)
    regs = []
    for mid, weight in top_metrics:
        ref = _crosswalk.as_dict(mid)
        concept = _concept_layer.get_concept(mid)
        regs.append({
            "metric_id": mid,
            "materiality": weight,
            "tags": concept.concept_tags if concept else [],
            "sfdr_pai": ref.get("sfdr_pai",[]) if ref else [],
            "csrd_esrs": ref.get("csrd_esrs",[]) if ref else [],
            "sdg": ref.get("sdg",[]) if ref else [],
        })
    return {"sector": sector, "metrics": regs}


@router.get("/sfdr-pai/{pai_number}/metrics")
async def sfdr_pai_metrics(pai_number: str):
    """Which metrics cover a given SFDR PAI indicator."""
    metrics = _crosswalk.metrics_for_sfdr_pai(pai_number)
    return {"sfdr_pai": pai_number, "metrics": metrics}


@router.get("/compliance/{company_id}/score/{score_id}")
async def compliance_coverage(company_id: str, score_id: str,
                               graph: Annotated[GraphService, Depends(get_graph)]):
    """SFDR / CSRD compliance gap analysis for a scored company."""
    prov = graph.get_provenance(company_id, score_id)
    scored_metrics = list({r["metric_id"] for r in prov if r.get("metric_id")})
    report = _crosswalk.coverage_report(scored_metrics)
    return {
        "company_id": company_id,
        "score_id": score_id,
        "scored_metrics": scored_metrics,
        "coverage": report,
    }


# ── GraphRAG Explanations ────────────────────────────────────────────────────

@router.get("/explain/{company_id}/score/{score_id}/metric/{metric_id}")
async def explain_metric(
    company_id: str, score_id: str, metric_id: str,
    use_llm: bool = Query(True, description="Use LLM if API key available"),
    graph: Annotated[GraphService, Depends(get_graph)] = None,
):
    """
    GraphRAG explanation for a single metric score.
    Retrieves multi-hop context from the knowledge graph, then synthesises
    a structured narrative (template or LLM-enhanced).
    """
    retriever = GraphRetriever(graph._mem, _concept_layer, _crosswalk)
    ctx = retriever.retrieve(company_id, score_id, metric_id)
    if not ctx:
        raise HTTPException(status_code=404,
                            detail=f"No graph data for {company_id}/{score_id}/{metric_id}")
    result = _synthesizer.explain(ctx, use_llm=use_llm)
    return {
        "metric_id": result.metric_id,
        "metric_name": result.metric_name,
        "score": result.score,
        "grade": result.grade,
        "headline": result.headline,
        "narrative": result.narrative,
        "evidence_quality": result.evidence_quality,
        "evidence_summary": result.evidence_summary,
        "peer_insight": result.peer_insight,
        "regulatory_insight": result.regulatory_insight,
        "risk_flags": result.risk_flags,
        "opportunities": result.opportunities,
        "confidence_note": result.confidence_note,
        "generated_by": result.generated_by,
        "context": {
            "evidence_count": len(ctx.evidence_items),
            "peer_count": len(ctx.peer_scores),
            "materiality": ctx.materiality,
            "greenwash_conflict": ctx.greenwash_conflict,
            "related_metrics": ctx.related_metrics,
            "regulatory": ctx.regulatory,
        },
    }


@router.get("/explain/{company_id}/score/{score_id}/full")
async def explain_full_score(
    company_id: str, score_id: str,
    use_llm: bool = Query(False),
    graph: Annotated[GraphService, Depends(get_graph)] = None,
):
    """GraphRAG explanation for all metrics in a score — returns array."""
    retriever = GraphRetriever(graph._mem, _concept_layer, _crosswalk)
    contexts  = retriever.retrieve_all_metrics(company_id, score_id)
    results   = []
    for ctx in contexts:
        result = _synthesizer.explain(ctx, use_llm=False)  # template for bulk
        results.append({
            "metric_id": result.metric_id,
            "score": result.score,
            "grade": result.grade,
            "headline": result.headline,
            "evidence_quality": result.evidence_quality,
            "risk_flags": result.risk_flags,
            "opportunities": result.opportunities,
            "materiality": ctx.materiality,
            "peer_percentile": ctx.peer_percentile,
        })
    return {"company_id": company_id, "score_id": score_id, "explanations": results}

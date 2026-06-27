"""
Provenance API routes — expose the knowledge graph to the frontend.
"""
from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from src.graph.graph_service import GraphService
from src.ontology.esg_ontology import ESGOntology

router = APIRouter(prefix="/provenance", tags=["provenance"])

_graph: GraphService | None = None


def get_graph() -> GraphService:
    global _graph
    if _graph is None:
        _graph = GraphService()
        # Seed ontology metrics into graph on first access
        try:
            _graph.ingest_ontology(ESGOntology())
        except Exception:
            pass
    return _graph


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/status")
async def graph_status(graph: Annotated[GraphService, Depends(get_graph)]):
    return {"backend": graph.backend, "status": "ok"}


@router.get("/{company_id}/score/{score_id}/graph")
async def score_graph(
    company_id: str, score_id: str,
    graph: Annotated[GraphService, Depends(get_graph)],
):
    """
    Returns nodes + edges for the evidence provenance graph of a score.
    Used by the frontend force-directed SVG visualiser.
    """
    data = graph.get_graph_json(company_id, score_id)
    if not data["nodes"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No graph data found — score this company first")
    return data


@router.get("/{company_id}/score/{score_id}/trail")
async def provenance_trail(
    company_id: str, score_id: str,
    graph: Annotated[GraphService, Depends(get_graph)],
):
    """Full row-level provenance: every metric score linked to every evidence item."""
    rows = graph.get_provenance(company_id, score_id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No provenance data found")
    return {"company_id": company_id, "score_id": score_id,
            "row_count": len(rows), "rows": rows}


@router.get("/{company_id}/evidence-summary")
async def evidence_summary(
    company_id: str,
    graph: Annotated[GraphService, Depends(get_graph)],
):
    return {"company_id": company_id,
            "summary": graph.get_evidence_summary(company_id)}


@router.get("/{company_id}/metric/{metric_id}/trail")
async def metric_trail(
    company_id: str, metric_id: str,
    graph: Annotated[GraphService, Depends(get_graph)],
):
    """All evidence items that support a specific metric for this company."""
    trail = graph.get_metric_trail(company_id, metric_id)
    return {"company_id": company_id, "metric_id": metric_id,
            "evidence": trail}


@router.get("/{company_id}/history")
async def score_history(
    company_id: str,
    graph: Annotated[GraphService, Depends(get_graph)],
):
    return {"company_id": company_id,
            "history": graph.get_score_history(company_id)}

"""
GraphRAG Retriever — multi-hop traversal of the knowledge graph to assemble
rich context for LLM-based explanation synthesis.

Retrieval strategy per metric:
  1. Company evidence items (BACKED_BY chain)
  2. Peer company scores for same metric (HAS_SCORE traversal)
  3. Semantic related metrics from ConceptLayer
  4. Regulatory references from RegulatoryCrosswalk
  5. Greenwash conflict signals
  6. Score history / trend
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.graph.in_memory_graph import InMemoryGraph
from src.semantic.concept_layer import ConceptLayer, CONFLICTS_WITH, REINFORCES, SIMILAR_TO
from src.semantic.regulatory_crosswalk import RegulatoryCrosswalk


@dataclass
class RetrievedContext:
    company_id: str
    company_name: str
    company_sector: str
    metric_id: str
    metric_name: str
    metric_score: float
    metric_confidence: float
    outcome_based: bool
    pillar: str

    # Evidence chain
    evidence_items: List[Dict] = field(default_factory=list)
    greenwash_conflict: Optional[Dict] = None   # divergence detail if detected

    # Peer benchmarking
    peer_scores: List[Dict] = field(default_factory=list)   # [{company, score, sector}]
    peer_percentile: Optional[float] = None

    # Semantic context
    related_metrics: List[Dict] = field(default_factory=list)   # [{metric_id, rel_type, score_if_known}]
    materiality: float = 0.7

    # Regulatory
    regulatory: Dict = field(default_factory=dict)
    compliance_gaps: List[str] = field(default_factory=list)

    # Trend
    score_history: List[Dict] = field(default_factory=list)


class GraphRetriever:

    def __init__(self, graph: InMemoryGraph,
                 concept_layer: Optional[ConceptLayer] = None,
                 crosswalk: Optional[RegulatoryCrosswalk] = None):
        self._g  = graph
        self._cl = concept_layer or ConceptLayer()
        self._rw = crosswalk or RegulatoryCrosswalk()

    def retrieve(self, company_id: str, score_id: str, metric_id: str) -> Optional[RetrievedContext]:
        """
        Full multi-hop retrieval for a single (company, score, metric) triple.
        Returns None if company or score not found in graph.
        """
        company = self._g.get_node("Company", company_id)
        score   = self._g.get_node("ESGScore", score_id)
        if not company or not score:
            return None

        # ── 1. Find MetricScore node ───────────────────────────────────────
        ms_node = self._find_metric_score(score_id, metric_id)
        if not ms_node:
            return None

        ctx = RetrievedContext(
            company_id=company_id,
            company_name=company.get("name",""),
            company_sector=company.get("sector",""),
            metric_id=metric_id,
            metric_name=ms_node.get("metric_name",""),
            metric_score=round(ms_node.get("score",0),1),
            metric_confidence=ms_node.get("confidence",0),
            outcome_based=ms_node.get("outcome_based",True),
            pillar=ms_node.get("pillar",""),
        )

        # ── 2. Evidence items ─────────────────────────────────────────────
        ms_id = ms_node["id"]
        for (ev, eprops) in self._g.out_neighbors("MetricScore", ms_id, "BACKED_BY", "EvidenceItem"):
            ctx.evidence_items.append({
                "id": ev["id"],
                "source": ev.get("source",""),
                "type": ev.get("evidence_type",""),
                "value": ev.get("normalized_value"),
                "raw": ev.get("raw_value"),
                "confidence": ev.get("confidence",0),
                "verified": ev.get("verified",False),
                "claim": ev.get("claim_text",""),
                "contribution": eprops.get("contribution",0),
            })

        # ── 3. Greenwash conflict detection ──────────────────────────────
        ctx.greenwash_conflict = self._detect_conflict(ctx.evidence_items, metric_id)

        # ── 4. Peer scores for same metric ───────────────────────────────
        ctx.peer_scores = self._get_peer_scores(company_id, metric_id)
        if ctx.peer_scores:
            all_scores = [p["score"] for p in ctx.peer_scores] + [ctx.metric_score]
            rank = sum(1 for s in all_scores if s <= ctx.metric_score)
            ctx.peer_percentile = round(rank / len(all_scores) * 100)

        # ── 5. Semantic related metrics (with their scores if available) ──
        related = self._cl.get_related(metric_id)
        for (target_id, rel_type, weight, desc) in related[:6]:
            target_ms = self._find_metric_score(score_id, target_id)
            ctx.related_metrics.append({
                "metric_id": target_id,
                "rel_type": rel_type,
                "weight": weight,
                "description": desc,
                "score": round(target_ms.get("score",0),1) if target_ms else None,
            })
        ctx.materiality = self._cl.materiality(metric_id, company.get("sector",""))

        # ── 6. Regulatory references ─────────────────────────────────────
        ctx.regulatory = self._rw.as_dict(metric_id)

        # ── 7. Score history ─────────────────────────────────────────────
        ctx.score_history = self._g.get_score_history(company_id, limit=5)

        return ctx

    def retrieve_all_metrics(self, company_id: str, score_id: str) -> List[RetrievedContext]:
        """Retrieve context for every metric in a score (used for full narrative)."""
        results = []
        score = self._g.get_node("ESGScore", score_id)
        if not score:
            return results
        for (ps, _) in self._g.out_neighbors("ESGScore", score_id, "HAS_PILLAR", "PillarScore"):
            for (ms, _) in self._g.out_neighbors("PillarScore", ps["id"], "HAS_METRIC", "MetricScore"):
                if ms.get("score",0) > 0:
                    ctx = self.retrieve(company_id, score_id, ms.get("metric_id",""))
                    if ctx:
                        results.append(ctx)
        return results

    # ── helpers ───────────────────────────────────────────────────────────────

    def _find_metric_score(self, score_id: str, metric_id: str) -> Optional[dict]:
        for (ps, _) in self._g.out_neighbors("ESGScore", score_id, "HAS_PILLAR", "PillarScore"):
            for (ms, _) in self._g.out_neighbors("PillarScore", ps["id"], "HAS_METRIC", "MetricScore"):
                if ms.get("metric_id") == metric_id:
                    return ms
        return None

    def _detect_conflict(self, evidence_items: List[dict], metric_id: str) -> Optional[dict]:
        self_rep = [e for e in evidence_items if e["type"] == "self_reported" and e["value"] is not None]
        measured = [e for e in evidence_items if e["type"] in ("quantitative","certified") and e["value"] is not None]
        if not self_rep or not measured:
            return None
        avg_sr = sum(e["value"] for e in self_rep) / len(self_rep)
        avg_meas = sum(e["value"] for e in measured) / len(measured)
        divergence = abs(avg_sr - avg_meas)
        if divergence >= 0.10:  # lower threshold for RAG context (vs 0.35 for greenwash alert)
            return {
                "self_reported_avg": round(avg_sr,3),
                "measured_avg": round(avg_meas,3),
                "divergence_pct": round(divergence*100,1),
                "is_greenwash_alert": divergence >= 0.35,
            }
        return None

    def _get_peer_scores(self, exclude_company_id: str, metric_id: str) -> List[dict]:
        results = []
        for company_node in self._g._nodes["Company"].values():
            cid = company_node["id"]
            if cid == exclude_company_id:
                continue
            # Find latest ESGScore for this peer
            peer_scores = [s for s in self._g._nodes["ESGScore"].values()
                           if any(fi == cid and r == "HAS_SCORE"
                                  for fl, fi, r in self._g._in_edges.get(s["id"], []))]
            if not peer_scores:
                continue
            latest = max(peer_scores, key=lambda s: s.get("scored_at",""))
            ms = self._find_metric_score(latest["id"], metric_id)
            if ms and ms.get("score",0) > 0:
                results.append({
                    "company": company_node.get("name",""),
                    "company_id": cid,
                    "sector": company_node.get("sector",""),
                    "score": round(ms.get("score",0),1),
                    "confidence": ms.get("confidence",0),
                })
        return results

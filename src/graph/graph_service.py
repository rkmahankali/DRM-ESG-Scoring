"""
GraphService — unified API over Neo4j (production) or InMemoryGraph (dev/fallback).
All callers use GraphService; the backend is transparent.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Optional

from src.graph.in_memory_graph import InMemoryGraph
from src.models.domain import ESGScore, EvidenceItem, GreenwashAlert
from src.ontology.esg_ontology import ESGOntology

NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "horison123")

# Module-level shared in-memory graph (persists across requests in the same process)
_IN_MEMORY: InMemoryGraph = InMemoryGraph()


class GraphService:
    """
    Wraps Neo4j or InMemoryGraph with a single clean API.
    Falls back to InMemoryGraph automatically if Neo4j is unavailable.
    """

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER,
                 password: str = NEO4J_PASSWORD):
        self._neo4j = None
        self._mem   = _IN_MEMORY
        self._use_neo4j = False
        self._try_connect(uri, user, password)

    def _try_connect(self, uri, user, password):
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
            self._neo4j = driver
            self._use_neo4j = True
            self._init_schema()
        except Exception:
            self._use_neo4j = False

    @property
    def backend(self) -> str:
        return "neo4j" if self._use_neo4j else "in_memory"

    def close(self):
        if self._neo4j:
            self._neo4j.close()

    # ── Schema ────────────────────────────────────────────────────────────

    def _init_schema(self):
        if not self._use_neo4j:
            return
        from src.graph.schema import CONSTRAINTS, INDEXES
        with self._neo4j.session() as s:
            for q in CONSTRAINTS + INDEXES:
                try:
                    s.run(q)
                except Exception:
                    pass

    # ── Ingest ontology metrics ───────────────────────────────────────────

    def ingest_ontology(self, ontology: ESGOntology) -> int:
        count = 0
        for metric in ontology.all_metrics():
            props = {
                "id": metric.id, "name": metric.name,
                "pillar": metric.pillar, "category": metric.category,
                "unit": metric.unit, "outcome_based": metric.outcome_based,
                "gri": metric.gri_reference or "",
                "sfdr_pai": metric.sfdr_pai_reference or "",
                "csrd": metric.csrd_reference or "",
            }
            if self._use_neo4j:
                from src.graph.schema import UPSERT_METRIC
                with self._neo4j.session() as s:
                    s.run(UPSERT_METRIC, **props)
            else:
                self._mem.upsert_metric(props)
            count += 1
        return count

    # ── Store company + evidence + score ─────────────────────────────────

    def store_company(self, company_id: str, name: str, sector: str,
                      jurisdiction: str, is_listed: bool = False):
        props = {"id": company_id, "name": name, "sector": sector,
                 "jurisdiction": jurisdiction, "is_listed": is_listed}
        if self._use_neo4j:
            from src.graph.schema import UPSERT_COMPANY, UPSERT_DATASOURCE
            with self._neo4j.session() as s:
                s.run(UPSERT_COMPANY, **props)
                for src in ["api_feed","questionnaire","document","regulatory_filing","third_party","satellite"]:
                    s.run(UPSERT_DATASOURCE, name=src, type=src)
        else:
            self._mem.upsert_company(props)
            for src in ["api_feed","questionnaire","document","regulatory_filing","third_party","satellite"]:
                self._mem.upsert_datasource(src, src)

    def store_evidence_items(self, evidence: list[EvidenceItem]):
        for ev in evidence:
            props = {
                "id": ev.id, "company_id": ev.company_id,
                "metric_id": ev.metric_id,
                "source": ev.source.value, "evidence_type": ev.evidence_type.value,
                "normalized_value": ev.normalized_value,
                "raw_value": str(ev.raw_value) if ev.raw_value is not None else None,
                "confidence": ev.confidence, "verified": ev.verified,
                "claim_text": ev.claim_text or "",
                "source_url": ev.source_url or "",
                "extracted_at": ev.extracted_at.isoformat(),
            }
            if self._use_neo4j:
                from src.graph.schema import UPSERT_EVIDENCE
                with self._neo4j.session() as s:
                    s.run(UPSERT_EVIDENCE, **props)
            else:
                self._mem.store_evidence(props)

    def store_score(self, company_id: str, esg_score: ESGScore,
                    evidence: list[EvidenceItem]):
        """Persist the full score tree: ESGScore → PillarScore → MetricScore → EvidenceItem."""
        score_props = {
            "id": esg_score.id,
            "composite_score": esg_score.composite_score,
            "confidence": esg_score.confidence,
            "greenwash_risk": esg_score.greenwash_risk,
            "data_coverage": esg_score.data_coverage,
            "evidence_count": esg_score.evidence_count,
            "scored_at": esg_score.scored_at.isoformat(),
            "scoring_version": esg_score.scoring_version,
            "audit_log_id": esg_score.audit_log_id or "",
        }

        pillar_nodes = []
        metric_nodes_by_pillar: dict[str, list] = {}
        ev_by_metric: dict[str, list[str]] = {}

        for ev in evidence:
            ev_by_metric.setdefault(ev.metric_id, []).append(ev.id)

        for pillar_enum, ps in esg_score.pillar_scores.items():
            pk = pillar_enum.value
            ps_id = str(uuid.uuid4())
            ps_props = {
                "id": ps_id, "pillar": pk,
                "score": ps.score, "confidence": ps.confidence,
                "greenwash_risk": ps.greenwash_risk,
                "score_id": esg_score.id,
            }
            pillar_nodes.append(ps_props)
            metric_nodes_by_pillar[pk] = []

            for ms in ps.metric_scores:
                ms_id = str(uuid.uuid4())
                ms_props = {
                    "id": ms_id,
                    "metric_id": ms.metric_id,
                    "metric_name": ms.metric_name,
                    "pillar": pk,
                    "category": ms.category,
                    "score": ms.score,
                    "confidence": ms.confidence,
                    "data_coverage": ms.data_coverage,
                    "outcome_based": ms.outcome_based,
                    "peer_percentile": ms.peer_percentile,
                    "pillar_score_id": ps_id,
                }
                metric_nodes_by_pillar[pk].append(ms_props)

        if self._use_neo4j:
            self._neo4j_store_tree(company_id, score_props, pillar_nodes,
                                   metric_nodes_by_pillar, ev_by_metric)
        else:
            self._mem.store_score_tree(company_id, score_props, pillar_nodes,
                                       metric_nodes_by_pillar, ev_by_metric)

    def _neo4j_store_tree(self, company_id, score_props, pillar_nodes,
                           metric_nodes_by_pillar, ev_by_metric):
        from src.graph.schema import (STORE_SCORE_TREE, STORE_PILLAR,
                                       STORE_METRIC_SCORE, LINK_EVIDENCE_TO_METRIC_SCORE)
        with self._neo4j.session() as s:
            s.run(STORE_SCORE_TREE, company_id=company_id, **score_props)
            for ps in pillar_nodes:
                s.run(STORE_PILLAR, **ps)
                for ms in metric_nodes_by_pillar.get(ps["pillar"], []):
                    s.run(STORE_METRIC_SCORE, **ms)
                    for ev_id in ev_by_metric.get(ms["metric_id"], []):
                        s.run(LINK_EVIDENCE_TO_METRIC_SCORE,
                              metric_score_id=ms["id"], evidence_id=ev_id,
                              weight=1.0, contribution=ms["score"]/100)

    # ── Provenance queries ────────────────────────────────────────────────

    def get_provenance(self, company_id: str, score_id: str) -> list[dict]:
        if self._use_neo4j:
            from src.graph.schema import PROVENANCE_FULL
            with self._neo4j.session() as s:
                result = s.run(PROVENANCE_FULL, company_id=company_id, score_id=score_id)
                return [dict(r) for r in result]
        return self._mem.get_provenance(company_id, score_id)

    def get_graph_json(self, company_id: str, score_id: str) -> dict:
        """Nodes + edges for frontend visualisation."""
        if self._use_neo4j:
            return self._neo4j_graph_json(company_id, score_id)
        return self._mem.build_graph_json(company_id, score_id)

    def _neo4j_graph_json(self, company_id: str, score_id: str) -> dict:
        from src.graph.schema import PROVENANCE_FULL
        rows = self.get_provenance(company_id, score_id)
        nodes, edges = {}, []
        for r in rows:
            nodes[r["company_id"]] = {"id": r["company_id"], "label": "Company", "name": r["company_name"]}
            nodes[r["score_id"]]   = {"id": r["score_id"], "label": "ESGScore", "score": r["composite_score"]}
            nodes[r["metric_score_id"]] = {"id": r["metric_score_id"], "label": "MetricScore",
                                            "metric_id": r["metric_id"], "score": r["metric_score"],
                                            "outcome_based": r["outcome_based"]}
            if r.get("evidence_id"):
                nodes[r["evidence_id"]] = {"id": r["evidence_id"], "label": "EvidenceItem",
                                            "source": r["source_name"], "type": r["evidence_type"],
                                            "value": r["norm_value"], "confidence": r["ev_confidence"],
                                            "verified": r["verified"]}
                edges.append({"source": r["metric_score_id"], "target": r["evidence_id"], "rel": "BACKED_BY"})
        return {"nodes": list(nodes.values()), "edges": edges,
                "meta": {"company": rows[0]["company_name"] if rows else "", "score_id": score_id,
                         "composite": rows[0]["composite_score"] if rows else 0}}

    def get_score_history(self, company_id: str, limit: int = 10) -> list[dict]:
        if self._use_neo4j:
            from src.graph.schema import SCORE_HISTORY
            with self._neo4j.session() as s:
                return [dict(r) for r in s.run(SCORE_HISTORY, company_id=company_id, limit=limit)]
        return self._mem.get_score_history(company_id, limit)

    def get_evidence_summary(self, company_id: str) -> list[dict]:
        if self._use_neo4j:
            from src.graph.schema import EVIDENCE_SUMMARY
            with self._neo4j.session() as s:
                return [dict(r) for r in s.run(EVIDENCE_SUMMARY, company_id=company_id)]
        return self._mem.get_evidence_summary(company_id)

    def get_metric_trail(self, company_id: str, metric_id: str) -> list[dict]:
        if self._use_neo4j:
            from src.graph.schema import METRIC_EVIDENCE_TRAIL
            with self._neo4j.session() as s:
                return [dict(r) for r in s.run(METRIC_EVIDENCE_TRAIL,
                                                company_id=company_id, metric_id=metric_id)]
        return self._mem.get_metric_evidence_trail(company_id, metric_id)

    def link_supply_chain(self, buyer_id: str, supplier_id: str, tier: int = 1):
        if self._use_neo4j:
            with self._neo4j.session() as s:
                s.run("""
                    MATCH (b:Company {id:$buyer_id})
                    MATCH (s:Company {id:$supplier_id})
                    MERGE (b)-[r:SUPPLIES_TO {tier:$tier}]->(s)
                """, buyer_id=buyer_id, supplier_id=supplier_id, tier=tier)
        else:
            self._mem.merge_edge("Company", buyer_id, "SUPPLIES_TO", "Company", supplier_id, {"tier": tier})

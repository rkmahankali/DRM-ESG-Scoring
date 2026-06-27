"""
In-memory graph store — exact mirror of the Neo4j schema.
Uses Python dicts + adjacency lists. Provides the same query API as
GraphService so the rest of the code needs zero changes when Neo4j is unavailable.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional


class InMemoryGraph:
    """
    Adjacency-list graph store.
    Nodes are identified by (label, id).
    Relationships are stored as directed edges with properties.
    """

    def __init__(self):
        # nodes: label -> {id -> props}
        self._nodes: dict[str, dict[str, dict]] = defaultdict(dict)
        # edges: (from_label, from_id, rel_type, to_label, to_id) -> props
        self._edges: dict[tuple, dict] = {}
        # reverse index: to_id -> list of (from_label, from_id, rel_type)
        self._in_edges: dict[str, list] = defaultdict(list)

    # ── node operations ──────────────────────────────────────────────────

    def merge_node(self, label: str, node_id: str, props: dict) -> None:
        existing = self._nodes[label].get(node_id, {})
        self._nodes[label][node_id] = {**existing, **props, "id": node_id}

    def get_node(self, label: str, node_id: str) -> Optional[dict]:
        return self._nodes[label].get(node_id)

    def find_nodes(self, label: str, **filters) -> list[dict]:
        result = []
        for n in self._nodes[label].values():
            if all(n.get(k) == v for k, v in filters.items()):
                result.append(n)
        return result

    # ── edge operations ──────────────────────────────────────────────────

    def merge_edge(self, from_label: str, from_id: str, rel: str,
                   to_label: str, to_id: str, props: dict | None = None) -> None:
        key = (from_label, from_id, rel, to_label, to_id)
        existing = self._edges.get(key, {})
        self._edges[key] = {**existing, **(props or {})}
        if (from_label, from_id, rel) not in self._in_edges[to_id]:
            self._in_edges[to_id].append((from_label, from_id, rel))

    def out_neighbors(self, label: str, node_id: str, rel: str,
                      target_label: str) -> list[tuple[dict, dict]]:
        """Returns [(target_node, edge_props), ...]"""
        result = []
        for (fl, fi, r, tl, ti), eprops in self._edges.items():
            if fl == label and fi == node_id and r == rel and tl == target_label:
                target = self._nodes[target_label].get(ti)
                if target:
                    result.append((target, eprops))
        return result

    # ── domain operations ─────────────────────────────────────────────────

    def upsert_company(self, props: dict) -> None:
        self.merge_node("Company", props["id"], props)

    def upsert_metric(self, props: dict) -> None:
        self.merge_node("Metric", props["id"], props)

    def upsert_datasource(self, name: str, source_type: str) -> None:
        self.merge_node("DataSource", name, {"name": name, "type": source_type})

    def store_evidence(self, ev: dict) -> None:
        self.merge_node("EvidenceItem", ev["id"], ev)
        self.merge_edge("Company", ev["company_id"], "HAS_EVIDENCE", "EvidenceItem", ev["id"])
        self.merge_edge("EvidenceItem", ev["id"], "FROM_SOURCE", "DataSource", ev["source"])
        self.merge_edge("EvidenceItem", ev["id"], "SUPPORTS", "Metric", ev["metric_id"])

    def store_score_tree(self, company_id: str, score: dict,
                         pillar_scores: list[dict],
                         metric_scores_by_pillar: dict[str, list[dict]],
                         evidence_by_metric: dict[str, list[str]]) -> None:

        # ESGScore node
        self.merge_node("ESGScore", score["id"], score)
        self.merge_edge("Company", company_id, "HAS_SCORE", "ESGScore", score["id"])

        for ps in pillar_scores:
            ps_id = ps["id"]
            self.merge_node("PillarScore", ps_id, ps)
            self.merge_edge("ESGScore", score["id"], "HAS_PILLAR", "PillarScore", ps_id)

            for ms in metric_scores_by_pillar.get(ps["pillar"], []):
                ms_id = ms["id"]
                self.merge_node("MetricScore", ms_id, ms)
                self.merge_edge("PillarScore", ps_id, "HAS_METRIC", "MetricScore", ms_id)

                for ev_id in evidence_by_metric.get(ms["metric_id"], []):
                    self.merge_edge("MetricScore", ms_id, "BACKED_BY", "EvidenceItem", ev_id,
                                    {"weight": 1.0, "contribution": ms.get("score", 0) / 100})

    # ── provenance queries ────────────────────────────────────────────────

    def get_provenance(self, company_id: str, score_id: str) -> list[dict]:
        rows = []
        company = self.get_node("Company", company_id)
        score   = self.get_node("ESGScore", score_id)
        if not company or not score:
            return []

        for (ps_node, _) in self.out_neighbors("ESGScore", score_id, "HAS_PILLAR", "PillarScore"):
            for (ms_node, _) in self.out_neighbors("PillarScore", ps_node["id"], "HAS_METRIC", "MetricScore"):
                ev_pairs = self.out_neighbors("MetricScore", ms_node["id"], "BACKED_BY", "EvidenceItem")
                if not ev_pairs:
                    rows.append(self._prov_row(company, score, ps_node, ms_node, None, None, None))
                else:
                    for (ev_node, edge_props) in ev_pairs:
                        ds_list = self.out_neighbors("EvidenceItem", ev_node["id"], "FROM_SOURCE", "DataSource")
                        ds_node = ds_list[0][0] if ds_list else None
                        metric  = self.get_node("Metric", ms_node.get("metric_id",""))
                        rows.append(self._prov_row(company, score, ps_node, ms_node, ev_node, ds_node, metric, edge_props))
        return rows

    def _prov_row(self, company, score, ps, ms, ev, ds, metric, edge=None) -> dict:
        return {
            "company_id":    company["id"],
            "company_name":  company.get("name",""),
            "score_id":      score["id"],
            "composite_score": score.get("composite_score",0),
            "score_confidence": score.get("confidence",0),
            "scored_at":     score.get("scored_at",""),
            "pillar":        ps.get("pillar",""),
            "pillar_score":  ps.get("score",0),
            "metric_score_id": ms.get("id",""),
            "metric_id":     ms.get("metric_id",""),
            "metric_name":   ms.get("metric_name",""),
            "metric_score":  ms.get("score",0),
            "outcome_based": ms.get("outcome_based",True),
            "evidence_id":   ev["id"] if ev else None,
            "norm_value":    ev.get("normalized_value") if ev else None,
            "raw_value":     ev.get("raw_value") if ev else None,
            "ev_confidence": ev.get("confidence") if ev else None,
            "verified":      ev.get("verified") if ev else None,
            "evidence_type": ev.get("evidence_type") if ev else None,
            "claim_text":    ev.get("claim_text") if ev else None,
            "source_url":    ev.get("source_url") if ev else None,
            "source_name":   ds.get("name") if ds else None,
            "unit":          metric.get("unit","") if metric else "",
            "weight":        edge.get("weight",1.0) if edge else 1.0,
            "contribution":  edge.get("contribution",0.0) if edge else 0.0,
        }

    def get_score_history(self, company_id: str, limit: int = 10) -> list[dict]:
        scores = [s for s in self._nodes["ESGScore"].values()
                  if any(fi == company_id and r == "HAS_SCORE"
                         for fl, fi, r in self._in_edges.get(s["id"], []))]
        scores.sort(key=lambda s: s.get("scored_at",""), reverse=True)
        return scores[:limit]

    def get_evidence_summary(self, company_id: str) -> list[dict]:
        ev_list = [n for n in self._nodes["EvidenceItem"].values()
                   if any(fi == company_id and r == "HAS_EVIDENCE"
                          for fl, fi, r in self._in_edges.get(n["id"], []))]
        summary: dict[tuple, dict] = {}
        for ev in ev_list:
            key = (ev.get("source",""), ev.get("evidence_type",""), ev.get("verified",False))
            if key not in summary:
                summary[key] = {"source":key[0],"evidence_type":key[1],"verified":key[2],"count":0,"total_conf":0}
            summary[key]["count"] += 1
            summary[key]["total_conf"] += ev.get("confidence",0)
        result = []
        for k, v in summary.items():
            result.append({**v, "avg_confidence": v["total_conf"]/v["count"] if v["count"] else 0})
        return sorted(result, key=lambda x: -x["count"])

    def get_metric_evidence_trail(self, company_id: str, metric_id: str) -> list[dict]:
        ev_list = [n for n in self._nodes["EvidenceItem"].values()
                   if n.get("metric_id") == metric_id and
                   any(fi == company_id and r == "HAS_EVIDENCE"
                       for fl, fi, r in self._in_edges.get(n["id"], []))]
        return sorted(ev_list, key=lambda e: -e.get("confidence", 0))

    def build_graph_json(self, company_id: str, score_id: str) -> dict:
        """Return {nodes, edges} for frontend D3/SVG visualisation."""
        nodes, edges = [], []
        seen_nodes: set[str] = set()

        def add_node(nid, label, props):
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({"id": nid, "label": label, **props})

        def add_edge(src, tgt, rel, props=None):
            edges.append({"source": src, "target": tgt, "rel": rel, **(props or {})})

        company = self.get_node("Company", company_id)
        score   = self.get_node("ESGScore", score_id)
        if not company or not score:
            return {"nodes": [], "edges": []}

        add_node(company_id, "Company", {"name": company.get("name",""), "sector": company.get("sector","")})
        add_node(score_id, "ESGScore", {"score": round(score.get("composite_score",0),1), "confidence": score.get("confidence",0)})
        add_edge(company_id, score_id, "HAS_SCORE")

        for (ps, _) in self.out_neighbors("ESGScore", score_id, "HAS_PILLAR", "PillarScore"):
            add_node(ps["id"], "PillarScore", {"pillar": ps.get("pillar",""), "score": round(ps.get("score",0),1)})
            add_edge(score_id, ps["id"], "HAS_PILLAR")

            for (ms, _) in self.out_neighbors("PillarScore", ps["id"], "HAS_METRIC", "MetricScore"):
                if ms.get("score",0) == 0:
                    continue
                add_node(ms["id"], "MetricScore", {"metric_id": ms.get("metric_id",""), "score": round(ms.get("score",0),1), "outcome_based": ms.get("outcome_based",True)})
                add_edge(ps["id"], ms["id"], "HAS_METRIC")

                for (ev, eprops) in self.out_neighbors("MetricScore", ms["id"], "BACKED_BY", "EvidenceItem"):
                    ev_label = f"{ev.get('source','')}\n{ev.get('evidence_type','')}"
                    add_node(ev["id"], "EvidenceItem", {
                        "source": ev.get("source",""),
                        "type": ev.get("evidence_type",""),
                        "value": round(ev.get("normalized_value",0)*100,1) if ev.get("normalized_value") is not None else None,
                        "confidence": ev.get("confidence",0),
                        "verified": ev.get("verified",False),
                    })
                    add_edge(ms["id"], ev["id"], "BACKED_BY", {"contribution": eprops.get("contribution",0)})

        return {"nodes": nodes, "edges": edges,
                "meta": {"company": company.get("name",""), "score_id": score_id,
                         "composite": round(score.get("composite_score",0),1)}}

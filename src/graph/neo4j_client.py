"""
Neo4j knowledge graph client.
Nodes: Company, Metric, EvidenceItem, DataSource, Sector, SupplyChainRelation
Relationships encode the full evidence chain for every score.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "horison123")


class GraphClient:
    """
    Thin wrapper around the Neo4j driver.
    Falls back to a no-op stub when the driver isn't installed,
    so the rest of the service stays importable without Neo4j.
    """

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
    ):
        try:
            from neo4j import GraphDatabase  # type: ignore
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            self._available = True
        except ImportError:
            self._driver = None
            self._available = False

    def close(self):
        if self._driver:
            self._driver.close()

    # ------------------------------------------------------------------
    # Schema / constraints
    # ------------------------------------------------------------------

    def create_constraints(self):
        if not self._available:
            return
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Metric) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Evidence) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:ESGScore) REQUIRE s.id IS UNIQUE",
        ]
        with self._driver.session() as session:
            for q in queries:
                session.run(q)

    # ------------------------------------------------------------------
    # Company nodes
    # ------------------------------------------------------------------

    def upsert_company(self, company_id: str, props: dict[str, Any]):
        if not self._available:
            return
        query = """
        MERGE (c:Company {id: $id})
        SET c += $props
        RETURN c.id
        """
        with self._driver.session() as session:
            session.run(query, id=company_id, props=props)

    def link_supply_chain(self, buyer_id: str, supplier_id: str, tier: int = 1):
        if not self._available:
            return
        query = """
        MATCH (buyer:Company {id: $buyer_id})
        MATCH (supplier:Company {id: $supplier_id})
        MERGE (buyer)-[r:SUPPLIES_TO {tier: $tier}]->(supplier)
        RETURN r
        """
        with self._driver.session() as session:
            session.run(query, buyer_id=buyer_id, supplier_id=supplier_id, tier=tier)

    # ------------------------------------------------------------------
    # Evidence → Score lineage
    # ------------------------------------------------------------------

    def store_evidence(self, ev_id: str, company_id: str, metric_id: str, props: dict[str, Any]):
        if not self._available:
            return
        query = """
        MERGE (e:Evidence {id: $ev_id})
        SET e += $props
        WITH e
        MATCH (c:Company {id: $company_id})
        MERGE (c)-[:HAS_EVIDENCE]->(e)
        WITH e
        MERGE (m:Metric {id: $metric_id})
        MERGE (e)-[:SUPPORTS]->(m)
        """
        with self._driver.session() as session:
            session.run(query, ev_id=ev_id, company_id=company_id,
                        metric_id=metric_id, props=props)

    def store_score(self, score_id: str, company_id: str, score_props: dict[str, Any],
                    evidence_ids: list[str]):
        if not self._available:
            return
        # Create the score node
        with self._driver.session() as session:
            session.run("""
                MERGE (s:ESGScore {id: $score_id})
                SET s += $props
                WITH s
                MATCH (c:Company {id: $company_id})
                MERGE (c)-[:HAS_SCORE]->(s)
            """, score_id=score_id, company_id=company_id, props=score_props)

            # Link each evidence item to the score
            for ev_id in evidence_ids:
                session.run("""
                    MATCH (s:ESGScore {id: $score_id})
                    MATCH (e:Evidence {id: $ev_id})
                    MERGE (s)-[:BACKED_BY]->(e)
                """, score_id=score_id, ev_id=ev_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_evidence_chain(self, score_id: str) -> list[dict[str, Any]]:
        if not self._available:
            return []
        query = """
        MATCH (s:ESGScore {id: $score_id})-[:BACKED_BY]->(e:Evidence)-[:SUPPORTS]->(m:Metric)
        RETURN e.id AS evidence_id, e.metric_id AS metric_id, m.id AS metric,
               e.normalized_value AS value, e.confidence AS confidence,
               e.source AS source, e.source_url AS url
        ORDER BY m.id
        """
        with self._driver.session() as session:
            result = session.run(query, score_id=score_id)
            return [dict(r) for r in result]

    def peer_companies(self, company_id: str, sector: str, limit: int = 20) -> list[str]:
        if not self._available:
            return []
        query = """
        MATCH (c:Company {sector: $sector})
        WHERE c.id <> $company_id
        RETURN c.id AS id LIMIT $limit
        """
        with self._driver.session() as session:
            result = session.run(query, sector=sector, company_id=company_id, limit=limit)
            return [r["id"] for r in result]

    def supply_chain_esg_risk(self, company_id: str) -> dict[str, Any]:
        """Aggregate ESG risk across the supply chain graph."""
        if not self._available:
            return {}
        query = """
        MATCH (buyer:Company {id: $company_id})-[:SUPPLIES_TO*1..3]->(supplier:Company)
        MATCH (supplier)-[:HAS_SCORE]->(s:ESGScore)
        WITH supplier, s ORDER BY s.scored_at DESC
        WITH supplier, COLLECT(s)[0] AS latest
        RETURN supplier.id AS supplier_id, supplier.name AS name,
               latest.composite_score AS score,
               latest.greenwash_risk AS greenwash_risk
        ORDER BY latest.composite_score ASC
        """
        with self._driver.session() as session:
            result = session.run(query, company_id=company_id)
            rows = [dict(r) for r in result]
        return {"company_id": company_id, "supply_chain_risks": rows}

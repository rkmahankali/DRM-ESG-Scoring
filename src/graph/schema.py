"""
Neo4j graph schema for ESG provenance.

Node labels:
  Company       — the private company being scored
  ESGScore      — a composite score snapshot at a point in time
  PillarScore   — E / S / G pillar sub-score
  MetricScore   — individual metric score
  EvidenceItem  — atomic piece of evidence (a claim + value + source)
  Metric        — ontology definition of a metric
  DataSource    — origin of evidence (API, document, questionnaire…)

Relationships:
  (Company)     -[:HAS_SCORE]->     (ESGScore)
  (ESGScore)    -[:HAS_PILLAR]->    (PillarScore)
  (PillarScore) -[:HAS_METRIC]->    (MetricScore)
  (MetricScore) -[:BACKED_BY]->     (EvidenceItem)   {weight, contribution}
  (EvidenceItem)-[:FROM_SOURCE]->   (DataSource)
  (EvidenceItem)-[:SUPPORTS]->      (Metric)
  (Company)     -[:HAS_EVIDENCE]->  (EvidenceItem)
  (Company)     -[:SUPPLIES_TO]->   (Company)        {tier}   # supply chain
"""

CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Company)     REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ESGScore)    REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:PillarScore) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:MetricScore) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:EvidenceItem)REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Metric)      REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:DataSource)  REQUIRE n.name IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS FOR (n:Company)     ON (n.sector)",
    "CREATE INDEX IF NOT EXISTS FOR (n:ESGScore)    ON (n.scored_at)",
    "CREATE INDEX IF NOT EXISTS FOR (n:EvidenceItem)ON (n.metric_id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:EvidenceItem)ON (n.verified)",
]

# ── Cypher queries ────────────────────────────────────────────────────────────

UPSERT_COMPANY = """
MERGE (c:Company {id: $id})
SET c += {name:$name, sector:$sector, jurisdiction:$jurisdiction,
          is_listed:$is_listed, updated_at:datetime()}
RETURN c.id AS id
"""

UPSERT_METRIC = """
MERGE (m:Metric {id: $id})
SET m += {name:$name, pillar:$pillar, category:$category,
          unit:$unit, outcome_based:$outcome_based}
RETURN m.id AS id
"""

UPSERT_DATASOURCE = """
MERGE (ds:DataSource {name: $name})
SET ds.type = $type
RETURN ds.name AS name
"""

UPSERT_EVIDENCE = """
MERGE (e:EvidenceItem {id: $id})
SET e += {metric_id:$metric_id, source:$source, evidence_type:$evidence_type,
          normalized_value:$normalized_value, raw_value:$raw_value,
          confidence:$confidence, verified:$verified,
          claim_text:$claim_text, source_url:$source_url,
          extracted_at:$extracted_at}
WITH e
MATCH (c:Company {id: $company_id})
MERGE (c)-[:HAS_EVIDENCE]->(e)
WITH e
MATCH (ds:DataSource {name: $source})
MERGE (e)-[:FROM_SOURCE]->(ds)
WITH e
MATCH (m:Metric {id: $metric_id})
MERGE (e)-[:SUPPORTS]->(m)
RETURN e.id AS id
"""

STORE_SCORE_TREE = """
// ESGScore node
MERGE (s:ESGScore {id: $score_id})
SET s += {composite_score:$composite_score, confidence:$confidence,
          greenwash_risk:$greenwash_risk, data_coverage:$data_coverage,
          evidence_count:$evidence_count, scored_at:$scored_at,
          scoring_version:$scoring_version, audit_log_id:$audit_log_id}
WITH s
MATCH (c:Company {id: $company_id})
MERGE (c)-[:HAS_SCORE]->(s)
RETURN s.id AS id
"""

STORE_PILLAR = """
MERGE (p:PillarScore {id: $id})
SET p += {pillar:$pillar, score:$score, confidence:$confidence,
          greenwash_risk:$greenwash_risk, score_id:$score_id}
WITH p
MATCH (s:ESGScore {id: $score_id})
MERGE (s)-[:HAS_PILLAR]->(p)
RETURN p.id AS id
"""

STORE_METRIC_SCORE = """
MERGE (ms:MetricScore {id: $id})
SET ms += {metric_id:$metric_id, metric_name:$metric_name,
           pillar:$pillar, category:$category,
           score:$score, confidence:$confidence,
           data_coverage:$data_coverage, outcome_based:$outcome_based,
           peer_percentile:$peer_percentile, pillar_score_id:$pillar_score_id}
WITH ms
MATCH (ps:PillarScore {id: $pillar_score_id})
MERGE (ps)-[:HAS_METRIC]->(ms)
RETURN ms.id AS id
"""

LINK_EVIDENCE_TO_METRIC_SCORE = """
MATCH (ms:MetricScore {id: $metric_score_id})
MATCH (e:EvidenceItem {id: $evidence_id})
MERGE (ms)-[r:BACKED_BY]->(e)
SET r.weight = $weight, r.contribution = $contribution
"""

# ── Provenance queries ────────────────────────────────────────────────────────

PROVENANCE_FULL = """
MATCH (c:Company {id: $company_id})-[:HAS_SCORE]->(s:ESGScore {id: $score_id})
MATCH (s)-[:HAS_PILLAR]->(ps:PillarScore)
MATCH (ps)-[:HAS_METRIC]->(ms:MetricScore)
OPTIONAL MATCH (ms)-[r:BACKED_BY]->(e:EvidenceItem)
OPTIONAL MATCH (e)-[:FROM_SOURCE]->(ds:DataSource)
OPTIONAL MATCH (e)-[:SUPPORTS]->(m:Metric)
RETURN
  c.id AS company_id, c.name AS company_name,
  s.id AS score_id, s.composite_score AS composite_score,
  s.confidence AS score_confidence, s.scored_at AS scored_at,
  ps.pillar AS pillar, ps.score AS pillar_score,
  ms.id AS metric_score_id, ms.metric_id AS metric_id,
  ms.metric_name AS metric_name, ms.score AS metric_score,
  ms.outcome_based AS outcome_based,
  e.id AS evidence_id, e.normalized_value AS norm_value,
  e.raw_value AS raw_value, e.confidence AS ev_confidence,
  e.verified AS verified, e.evidence_type AS evidence_type,
  e.claim_text AS claim_text, e.source_url AS source_url,
  ds.name AS source_name, m.unit AS unit,
  r.weight AS weight, r.contribution AS contribution
ORDER BY ps.pillar, ms.metric_id, e.confidence DESC
"""

SCORE_HISTORY = """
MATCH (c:Company {id: $company_id})-[:HAS_SCORE]->(s:ESGScore)
RETURN s.id AS score_id, s.composite_score AS composite_score,
       s.confidence AS confidence, s.greenwash_risk AS greenwash_risk,
       s.data_coverage AS data_coverage, s.scored_at AS scored_at,
       s.evidence_count AS evidence_count
ORDER BY s.scored_at DESC
LIMIT $limit
"""

SUPPLY_CHAIN_RISK = """
MATCH (buyer:Company {id: $company_id})-[:SUPPLIES_TO*1..3]->(supplier:Company)
MATCH (supplier)-[:HAS_SCORE]->(s:ESGScore)
WITH supplier, s ORDER BY s.scored_at DESC
WITH supplier, COLLECT(s)[0] AS latest
RETURN supplier.id AS id, supplier.name AS name,
       supplier.sector AS sector,
       latest.composite_score AS score,
       latest.greenwash_risk AS greenwash_risk,
       latest.confidence AS confidence
ORDER BY latest.composite_score ASC
"""

EVIDENCE_SUMMARY = """
MATCH (c:Company {id: $company_id})-[:HAS_EVIDENCE]->(e:EvidenceItem)
RETURN e.source AS source, e.evidence_type AS evidence_type,
       e.verified AS verified,
       COUNT(e) AS count,
       AVG(e.confidence) AS avg_confidence
ORDER BY count DESC
"""

METRIC_EVIDENCE_TRAIL = """
MATCH (c:Company {id: $company_id})-[:HAS_EVIDENCE]->(e:EvidenceItem {metric_id: $metric_id})
OPTIONAL MATCH (e)-[:FROM_SOURCE]->(ds:DataSource)
RETURN e.id AS id, e.evidence_type AS type, e.normalized_value AS value,
       e.raw_value AS raw, e.confidence AS confidence, e.verified AS verified,
       e.claim_text AS claim, e.source_url AS url, ds.name AS source,
       e.extracted_at AS extracted_at
ORDER BY e.confidence DESC
"""

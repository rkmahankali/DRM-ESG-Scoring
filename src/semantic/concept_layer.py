"""
Semantic layer — assigns meaning, relationships and materiality to ESG metrics.

The concept graph enriches the knowledge graph with:
  - SIMILAR_TO: metrics measuring the same underlying phenomenon
  - REINFORCES: metric A's high score should push metric B higher
  - CONFLICTS_WITH: divergence here is a greenwash signal
  - PROXIED_BY: B is a cheaper/easier proxy for A
  - AGGREGATED_BY: pillar composition relationships

Plus sector-specific materiality weights (SFDR PAI double-materiality lens).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Semantic relationship types ────────────────────────────────────────────────

SIMILAR_TO    = "SIMILAR_TO"
REINFORCES    = "REINFORCES"
CONFLICTS_WITH= "CONFLICTS_WITH"
PROXIED_BY    = "PROXIED_BY"
AGGREGATED_BY = "AGGREGATED_BY"
COMPLEMENTS   = "COMPLEMENTS"


@dataclass
class MetricRelationship:
    source: str
    target: str
    rel_type: str
    weight: float = 1.0          # 0–1 semantic similarity or strength
    description: str = ""
    bidirectional: bool = False


@dataclass
class MetricConcept:
    metric_id: str
    concept_tags: List[str]      # e.g. ["climate", "scope1", "absolute_emissions"]
    sdg_goals: List[int]         # UN SDG numbers
    tcfd_pillar: Optional[str]   # Strategy / Risk Management / Metrics & Targets
    double_materiality: str      # "financial" | "impact" | "both"
    data_availability: str       # "high" | "medium" | "low"
    typical_evidence_type: str   # "quantitative" | "self_reported" | "certified"


# ── Metric concept definitions ─────────────────────────────────────────────────

METRIC_CONCEPTS: Dict[str, MetricConcept] = {
    "E1.1": MetricConcept("E1.1", ["climate","scope1","scope2","absolute_ghg","carbon"],
                          sdg_goals=[13], tcfd_pillar="Metrics & Targets",
                          double_materiality="both", data_availability="high",
                          typical_evidence_type="quantitative"),
    "E1.2": MetricConcept("E1.2", ["climate","scope3","value_chain_emissions","carbon_intensity"],
                          sdg_goals=[13, 12], tcfd_pillar="Metrics & Targets",
                          double_materiality="both", data_availability="medium",
                          typical_evidence_type="quantitative"),
    "E1.3": MetricConcept("E1.3", ["climate","renewable_energy","decarbonisation","energy_transition"],
                          sdg_goals=[7, 13], tcfd_pillar="Strategy",
                          double_materiality="impact", data_availability="high",
                          typical_evidence_type="certified"),
    "E1.4": MetricConcept("E1.4", ["climate","net_zero","carbon_target","science_based_target"],
                          sdg_goals=[13], tcfd_pillar="Strategy",
                          double_materiality="both", data_availability="medium",
                          typical_evidence_type="self_reported"),
    "E2.1": MetricConcept("E2.1", ["energy","efficiency","kwh_per_revenue","energy_intensity"],
                          sdg_goals=[7], tcfd_pillar="Metrics & Targets",
                          double_materiality="financial", data_availability="high",
                          typical_evidence_type="quantitative"),
    "E2.2": MetricConcept("E2.2", ["energy","renewable_heat","heat_pump","fossil_fuel_heating"],
                          sdg_goals=[7, 13], tcfd_pillar="Strategy",
                          double_materiality="impact", data_availability="low",
                          typical_evidence_type="self_reported"),
    "E3.1": MetricConcept("E3.1", ["water","consumption","freshwater_stress","water_stewardship"],
                          sdg_goals=[6], tcfd_pillar="Risk Management",
                          double_materiality="both", data_availability="medium",
                          typical_evidence_type="quantitative"),
    "E3.2": MetricConcept("E3.2", ["waste","circular_economy","landfill_diversion","food_waste"],
                          sdg_goals=[12], tcfd_pillar="Metrics & Targets",
                          double_materiality="impact", data_availability="medium",
                          typical_evidence_type="quantitative"),
    "E4.1": MetricConcept("E4.1", ["biodiversity","nature","deforestation","land_use","ecosystems"],
                          sdg_goals=[15, 14], tcfd_pillar="Risk Management",
                          double_materiality="both", data_availability="low",
                          typical_evidence_type="self_reported"),
    "S1.1": MetricConcept("S1.1", ["workforce","gender_pay","pay_equity","fair_pay"],
                          sdg_goals=[10, 5], tcfd_pillar=None,
                          double_materiality="impact", data_availability="high",
                          typical_evidence_type="certified"),
    "S1.2": MetricConcept("S1.2", ["workforce","health_safety","injury_rate","riddor"],
                          sdg_goals=[3, 8], tcfd_pillar=None,
                          double_materiality="financial", data_availability="high",
                          typical_evidence_type="quantitative"),
    "S1.3": MetricConcept("S1.3", ["workforce","training","upskilling","human_capital"],
                          sdg_goals=[4, 8], tcfd_pillar=None,
                          double_materiality="financial", data_availability="medium",
                          typical_evidence_type="self_reported"),
    "S2.1": MetricConcept("S2.1", ["supply_chain","ethical_sourcing","tier1","due_diligence"],
                          sdg_goals=[12, 8], tcfd_pillar="Risk Management",
                          double_materiality="both", data_availability="medium",
                          typical_evidence_type="certified"),
    "S3.1": MetricConcept("S3.1", ["community","social_impact","products","customers"],
                          sdg_goals=[11, 17], tcfd_pillar=None,
                          double_materiality="impact", data_availability="low",
                          typical_evidence_type="self_reported"),
    "G1.1": MetricConcept("G1.1", ["governance","board","independence","oversight"],
                          sdg_goals=[16], tcfd_pillar="Governance",
                          double_materiality="financial", data_availability="high",
                          typical_evidence_type="certified"),
    "G1.2": MetricConcept("G1.2", ["governance","diversity","board_gender","inclusion"],
                          sdg_goals=[5, 16], tcfd_pillar="Governance",
                          double_materiality="financial", data_availability="high",
                          typical_evidence_type="certified"),
    "G2.1": MetricConcept("G2.1", ["ethics","anti_corruption","code_of_conduct","whistleblower"],
                          sdg_goals=[16], tcfd_pillar="Governance",
                          double_materiality="financial", data_availability="medium",
                          typical_evidence_type="self_reported"),
    "G2.2": MetricConcept("G2.2", ["ethics","bribery","violations","enforcement"],
                          sdg_goals=[16], tcfd_pillar="Governance",
                          double_materiality="financial", data_availability="medium",
                          typical_evidence_type="quantitative"),
    "G3.1": MetricConcept("G3.1", ["tax","transparency","cbcr","country_reporting"],
                          sdg_goals=[17, 16], tcfd_pillar=None,
                          double_materiality="both", data_availability="medium",
                          typical_evidence_type="certified"),
}


# ── Semantic relationships ─────────────────────────────────────────────────────

METRIC_RELATIONSHIPS: List[MetricRelationship] = [
    # E1.x — emissions cluster
    MetricRelationship("E1.1","E1.2", SIMILAR_TO, 0.88,
                       "Both measure GHG footprint; E1.2 adds value-chain scope 3", True),
    MetricRelationship("E1.3","E1.1", REINFORCES, 0.82,
                       "Higher renewable energy % directly reduces Scope 1+2 emissions"),
    MetricRelationship("E2.1","E1.1", REINFORCES, 0.75,
                       "Improved energy efficiency reduces absolute emissions"),
    MetricRelationship("E1.4","E1.1", REINFORCES, 0.70,
                       "Net-zero target ownership drives emission reduction outcomes"),
    MetricRelationship("E1.4","E1.3", REINFORCES, 0.65,
                       "Net-zero commitment typically includes renewable transition plan"),

    # Greenwash conflict pairs — divergence here triggers alert
    MetricRelationship("E1.3","E1.1", CONFLICTS_WITH, 0.80,
                       "High renewable % claim should reduce absolute emissions; divergence = greenwash signal"),
    MetricRelationship("S1.1","S1.2", CONFLICTS_WITH, 0.60,
                       "Pay equity claims vs safety outcomes — both reflect workforce treatment"),

    # E2.x — energy cluster
    MetricRelationship("E2.1","E2.2", SIMILAR_TO, 0.72,
                       "Both measure energy system characteristics", True),
    MetricRelationship("E2.2","E1.3", COMPLEMENTS, 0.68,
                       "Renewable heat and renewable electricity together = full energy decarbonisation"),

    # E3.x — resource cluster
    MetricRelationship("E3.1","E3.2", SIMILAR_TO, 0.65,
                       "Both measure resource stewardship — water and waste", True),
    MetricRelationship("S2.1","E3.2", REINFORCES, 0.55,
                       "Strong supply chain due diligence reduces upstream waste and water risk"),

    # E4.x — nature cluster
    MetricRelationship("E4.1","E3.1", COMPLEMENTS, 0.60,
                       "Biodiversity and water stewardship are co-located ecosystem risks"),
    MetricRelationship("E4.1","S2.1", REINFORCES, 0.65,
                       "No-deforestation policy requires supply chain traceability"),

    # S1.x — workforce cluster
    MetricRelationship("S1.1","S1.2", SIMILAR_TO, 0.70,
                       "Both workforce welfare outcomes; pay + safety", True),
    MetricRelationship("S1.1","S1.3", COMPLEMENTS, 0.55,
                       "Pay equity and training investment together signal human capital quality"),
    MetricRelationship("G1.2","S1.1", REINFORCES, 0.60,
                       "Board gender diversity sets tone for workforce pay equity"),

    # S2.x / S3.x
    MetricRelationship("S2.1","S1.2", REINFORCES, 0.50,
                       "Supplier safety standards cascade from buyer ethical sourcing programmes"),

    # G1.x — governance cluster
    MetricRelationship("G1.1","G1.2", SIMILAR_TO, 0.80,
                       "Board independence and diversity are complementary governance pillars", True),
    MetricRelationship("G1.1","G2.1", REINFORCES, 0.78,
                       "Independent board oversight strengthens ethics and anti-corruption frameworks"),
    MetricRelationship("G1.1","E1.4", REINFORCES, 0.65,
                       "Board oversight of climate risk drives net-zero target-setting"),

    # G2.x — ethics cluster
    MetricRelationship("G2.1","G2.2", SIMILAR_TO, 0.85,
                       "Anti-corruption policy and bribery violations are two sides of ethics", True),
    MetricRelationship("G2.1","S2.1", REINFORCES, 0.60,
                       "Anti-corruption frameworks extend into supply chain due diligence"),
    MetricRelationship("G3.1","G2.1", REINFORCES, 0.65,
                       "Tax transparency is an expression of ethics and anti-corruption culture"),

    # Cross-pillar
    MetricRelationship("G1.1","E1.1", REINFORCES, 0.55,
                       "Independent board oversight of Scope 1+2 emissions targets"),
    MetricRelationship("S2.1","E1.2", REINFORCES, 0.70,
                       "Supply chain management directly affects Scope 3 / value-chain emissions"),
]


# ── Sector materiality weights ─────────────────────────────────────────────────
# Weight 1.0 = highly material; 0.5 = moderately; 0.2 = less material

SECTOR_MATERIALITY: Dict[str, Dict[str, float]] = {
    "Industrials": {
        "E1.1":1.0,"E1.2":0.9,"E1.3":0.9,"E1.4":0.8,"E2.1":0.9,"E2.2":0.6,
        "E3.1":0.7,"E3.2":0.8,"E4.1":0.5,
        "S1.1":0.7,"S1.2":1.0,"S1.3":0.6,"S2.1":0.7,"S3.1":0.5,
        "G1.1":0.8,"G1.2":0.7,"G2.1":0.9,"G2.2":0.9,"G3.1":0.7,
    },
    "FMCG / Retail": {
        "E1.1":0.8,"E1.2":0.9,"E1.3":0.8,"E1.4":0.7,"E2.1":0.7,"E2.2":0.5,
        "E3.1":0.7,"E3.2":1.0,"E4.1":0.9,
        "S1.1":0.9,"S1.2":0.8,"S1.3":0.7,"S2.1":1.0,"S3.1":0.9,
        "G1.1":0.8,"G1.2":0.8,"G2.1":0.9,"G2.2":0.8,"G3.1":0.8,
    },
    "Logistics": {
        "E1.1":1.0,"E1.2":0.9,"E1.3":1.0,"E1.4":0.9,"E2.1":1.0,"E2.2":0.6,
        "E3.1":0.4,"E3.2":0.6,"E4.1":0.5,
        "S1.1":0.7,"S1.2":1.0,"S1.3":0.6,"S2.1":0.7,"S3.1":0.5,
        "G1.1":0.8,"G1.2":0.7,"G2.1":0.8,"G2.2":0.8,"G3.1":0.7,
    },
    "Manufacturing": {
        "E1.1":1.0,"E1.2":0.9,"E1.3":0.9,"E1.4":0.8,"E2.1":0.9,"E2.2":0.7,
        "E3.1":0.8,"E3.2":0.9,"E4.1":0.6,
        "S1.1":0.8,"S1.2":1.0,"S1.3":0.7,"S2.1":0.8,"S3.1":0.6,
        "G1.1":0.8,"G1.2":0.7,"G2.1":0.9,"G2.2":0.9,"G3.1":0.7,
    },
    "default": {k:0.7 for k in METRIC_CONCEPTS},
}


# ── Query API ──────────────────────────────────────────────────────────────────

class ConceptLayer:

    def get_concept(self, metric_id: str) -> Optional[MetricConcept]:
        return METRIC_CONCEPTS.get(metric_id)

    def get_related(self, metric_id: str,
                    rel_types: Optional[List[str]] = None
                    ) -> List[Tuple[str, str, float, str]]:
        """Return [(target_id, rel_type, weight, description), ...]"""
        results = []
        for r in METRIC_RELATIONSHIPS:
            if r.source == metric_id and (rel_types is None or r.rel_type in rel_types):
                results.append((r.target, r.rel_type, r.weight, r.description))
            if r.bidirectional and r.target == metric_id and (rel_types is None or r.rel_type in rel_types):
                results.append((r.source, r.rel_type, r.weight, r.description))
        return sorted(results, key=lambda x: -x[2])

    def get_conflict_pairs(self, metric_ids: List[str]) -> List[Tuple[str,str,str]]:
        """Return all (a, b, description) conflict pairs among given metric_ids."""
        result = []
        for r in METRIC_RELATIONSHIPS:
            if r.rel_type == CONFLICTS_WITH and r.source in metric_ids and r.target in metric_ids:
                result.append((r.source, r.target, r.description))
        return result

    def materiality(self, metric_id: str, sector: str) -> float:
        norm_sector = self._normalise_sector(sector)
        mat = SECTOR_MATERIALITY.get(norm_sector, SECTOR_MATERIALITY["default"])
        return mat.get(metric_id, 0.7)

    def top_material_metrics(self, sector: str, n: int = 8) -> List[Tuple[str, float]]:
        norm_sector = self._normalise_sector(sector)
        mat = SECTOR_MATERIALITY.get(norm_sector, SECTOR_MATERIALITY["default"])
        return sorted(mat.items(), key=lambda x: -x[1])[:n]

    def semantic_graph_json(self, metric_id: str) -> dict:
        """Returns {nodes, edges} for the frontend semantic graph visualiser."""
        nodes, edges = [], []
        centre = METRIC_CONCEPTS.get(metric_id)
        if not centre:
            return {"nodes":[], "edges":[]}

        nodes.append({"id": metric_id, "label": metric_id, "group":"centre",
                      "tags": centre.concept_tags, "sdg": centre.sdg_goals,
                      "tcfd": centre.tcfd_pillar, "dm": centre.double_materiality})

        for (target, rel_type, weight, desc) in self.get_related(metric_id):
            tgt_concept = METRIC_CONCEPTS.get(target)
            if tgt_concept and target not in [n["id"] for n in nodes]:
                nodes.append({"id": target, "label": target, "group": rel_type,
                               "tags": tgt_concept.concept_tags})
            edges.append({"source": metric_id, "target": target,
                          "rel": rel_type, "weight": weight, "description": desc})
        return {"nodes": nodes, "edges": edges}

    def _normalise_sector(self, sector: str) -> str:
        s = sector.lower()
        if "fmcg" in s or "retail" in s or "food" in s or "consumer" in s:
            return "FMCG / Retail"
        if "logistic" in s or "transport" in s or "freight" in s:
            return "Logistics"
        if "manufactur" in s or "industrial" in s:
            return "Industrials"
        return "default"

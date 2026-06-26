"""
ESG ontology: pillars → categories → metrics.
Private-market focused, SASB-sector-aware.
Supports GRI, SFDR PAI, CSRD and ISSB cross-mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class MetricDefinition:
    id: str
    name: str
    pillar: str           # E / S / G
    category: str
    description: str
    unit: str
    outcome_based: bool   # True = real-world outcome; False = policy/disclosure
    sasb_sectors: list[str]          # applicable SASB sectors ("*" = all)
    gri_reference: str | None = None
    sfdr_pai_reference: str | None = None
    csrd_reference: str | None = None
    weight_default: float = 1.0      # relative weight within category


@dataclass
class CategoryDefinition:
    id: str
    name: str
    pillar: str
    weight: float         # weight within pillar
    metrics: list[MetricDefinition] = field(default_factory=list)


@dataclass
class PillarDefinition:
    id: str
    name: str
    weight: float         # default composite weight
    categories: list[CategoryDefinition] = field(default_factory=list)


class ESGOntology:
    """
    Private-market ESG ontology.
    Emphasises outcome-based, auditable metrics over disclosure scores.
    """

    PILLARS: ClassVar[dict[str, PillarDefinition]] = {}

    def __init__(self):
        self._build()

    def _build(self):
        env = PillarDefinition("E", "Environmental", weight=0.40, categories=[
            CategoryDefinition("E1", "Climate & Emissions", pillar="E", weight=0.40, metrics=[
                MetricDefinition(
                    "E1.1", "Scope 1 GHG Emissions", "E", "Climate & Emissions",
                    "Direct GHG emissions (tonnes CO2e)", "tCO2e", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 305-1",
                    sfdr_pai_reference="PAI 1", csrd_reference="E1-6",
                ),
                MetricDefinition(
                    "E1.2", "Scope 2 GHG Emissions", "E", "Climate & Emissions",
                    "Indirect energy-related GHG emissions", "tCO2e", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 305-2",
                    sfdr_pai_reference="PAI 1",
                ),
                MetricDefinition(
                    "E1.3", "Carbon Intensity", "E", "Climate & Emissions",
                    "GHG emissions per unit revenue", "tCO2e/M USD", outcome_based=True,
                    sasb_sectors=["*"], sfdr_pai_reference="PAI 3",
                ),
                MetricDefinition(
                    "E1.4", "Net-Zero Target Credibility", "E", "Climate & Emissions",
                    "Alignment of stated targets with measured trajectory", "score 0–1",
                    outcome_based=False, sasb_sectors=["*"],
                ),
            ]),
            CategoryDefinition("E2", "Energy", pillar="E", weight=0.25, metrics=[
                MetricDefinition(
                    "E2.1", "Renewable Energy Share", "E", "Energy",
                    "% total energy from renewable sources", "%", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 302-1",
                ),
                MetricDefinition(
                    "E2.2", "Energy Intensity", "E", "Energy",
                    "Energy consumption per unit revenue", "MWh/M USD", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 302-3",
                ),
            ]),
            CategoryDefinition("E3", "Water & Waste", pillar="E", weight=0.20, metrics=[
                MetricDefinition(
                    "E3.1", "Water Consumption", "E", "Water & Waste",
                    "Total water withdrawal (m³)", "m³", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 303-5",
                ),
                MetricDefinition(
                    "E3.2", "Hazardous Waste", "E", "Water & Waste",
                    "Hazardous waste generated (tonnes)", "tonnes", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 306-3",
                    sfdr_pai_reference="PAI 9",
                ),
            ]),
            CategoryDefinition("E4", "Biodiversity & Land", pillar="E", weight=0.15, metrics=[
                MetricDefinition(
                    "E4.1", "Land Use in Sensitive Areas", "E", "Biodiversity & Land",
                    "Operations in or near protected areas", "boolean/ha",
                    outcome_based=True, sasb_sectors=["*"],
                    sfdr_pai_reference="PAI 7", csrd_reference="E4",
                ),
            ]),
        ])

        soc = PillarDefinition("S", "Social", weight=0.35, categories=[
            CategoryDefinition("S1", "Workforce", pillar="S", weight=0.40, metrics=[
                MetricDefinition(
                    "S1.1", "LTIFR", "S", "Workforce",
                    "Lost-time injury frequency rate", "per 200k hours",
                    outcome_based=True, sasb_sectors=["*"],
                    gri_reference="GRI 403-9", sfdr_pai_reference="PAI 11",
                ),
                MetricDefinition(
                    "S1.2", "Gender Pay Gap", "S", "Workforce",
                    "Mean gender pay gap (%)", "%", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 405-2",
                    sfdr_pai_reference="PAI 12",
                ),
                MetricDefinition(
                    "S1.3", "Employee Turnover Rate", "S", "Workforce",
                    "Annual voluntary turnover %", "%", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 401-1",
                ),
            ]),
            CategoryDefinition("S2", "Supply Chain", pillar="S", weight=0.30, metrics=[
                MetricDefinition(
                    "S2.1", "Supply Chain Human Rights Audits", "S", "Supply Chain",
                    "% tier-1 suppliers audited for human rights", "%",
                    outcome_based=True, sasb_sectors=["*"],
                    gri_reference="GRI 414-1", sfdr_pai_reference="PAI 10",
                ),
            ]),
            CategoryDefinition("S3", "Community & Products", pillar="S", weight=0.30, metrics=[
                MetricDefinition(
                    "S3.1", "Product Safety Incidents", "S", "Community & Products",
                    "Confirmed product safety incidents", "count", outcome_based=True,
                    sasb_sectors=["*"],
                ),
            ]),
        ])

        gov = PillarDefinition("G", "Governance", weight=0.25, categories=[
            CategoryDefinition("G1", "Board & Oversight", pillar="G", weight=0.40, metrics=[
                MetricDefinition(
                    "G1.1", "Board Independence", "G", "Board & Oversight",
                    "% independent directors", "%", outcome_based=False,
                    sasb_sectors=["*"], gri_reference="GRI 2-9",
                ),
                MetricDefinition(
                    "G1.2", "Board Gender Diversity", "G", "Board & Oversight",
                    "% women on board", "%", outcome_based=True,
                    sasb_sectors=["*"], gri_reference="GRI 405-1",
                    sfdr_pai_reference="PAI 13",
                ),
            ]),
            CategoryDefinition("G2", "Business Ethics", pillar="G", weight=0.35, metrics=[
                MetricDefinition(
                    "G2.1", "Anti-Corruption Policy", "G", "Business Ethics",
                    "Existence & enforcement of anti-corruption controls", "boolean",
                    outcome_based=False, sasb_sectors=["*"],
                    gri_reference="GRI 205-2",
                ),
                MetricDefinition(
                    "G2.2", "Confirmed Corruption Incidents", "G", "Business Ethics",
                    "Legal/regulatory actions for corruption", "count",
                    outcome_based=True, sasb_sectors=["*"],
                    sfdr_pai_reference="PAI 17",
                ),
            ]),
            CategoryDefinition("G3", "Tax Transparency", pillar="G", weight=0.25, metrics=[
                MetricDefinition(
                    "G3.1", "Effective Tax Rate", "G", "Tax Transparency",
                    "Effective tax rate vs. statutory rate", "%",
                    outcome_based=True, sasb_sectors=["*"],
                    sfdr_pai_reference="PAI 16",
                ),
            ]),
        ])

        self.pillars = {"E": env, "S": soc, "G": gov}

    def get_metric(self, metric_id: str) -> MetricDefinition | None:
        for pillar in self.pillars.values():
            for cat in pillar.categories:
                for m in cat.metrics:
                    if m.id == metric_id:
                        return m
        return None

    def metrics_for_sector(self, sasb_sector: str) -> list[MetricDefinition]:
        result = []
        for pillar in self.pillars.values():
            for cat in pillar.categories:
                for m in cat.metrics:
                    if "*" in m.sasb_sectors or sasb_sector in m.sasb_sectors:
                        result.append(m)
        return result

    def all_metrics(self) -> list[MetricDefinition]:
        return self.metrics_for_sector("*")

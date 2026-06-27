"""
Regulatory cross-walk — maps every ESG metric to its counterparts across
GRI, SFDR PAI, CSRD ESRS, ISSB IFRS S2, SASB, UN SDG, and TCFD.

This is the "Rosetta Stone" of the semantic layer: a fund manager using
SFDR Article 8 can ask "which metrics cover PAI indicator 1?" and get
the canonical answer from the graph.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RegulatoryRef:
    metric_id: str
    gri: List[str] = field(default_factory=list)
    sfdr_pai: List[str] = field(default_factory=list)     # Principal Adverse Impact indicator numbers
    csrd_esrs: List[str] = field(default_factory=list)    # ESRS standard + disclosure requirement
    issb_ifrs: List[str] = field(default_factory=list)    # IFRS S1/S2 paragraphs
    sasb: Dict[str, str] = field(default_factory=dict)    # {industry_code: metric_code}
    sdg: List[int] = field(default_factory=list)
    tcfd: List[str] = field(default_factory=list)
    description: str = ""
    mandatory_jurisdictions: List[str] = field(default_factory=list)  # ISO codes where mandatory


REGULATORY_CROSSWALK: Dict[str, RegulatoryRef] = {
    "E1.1": RegulatoryRef(
        metric_id="E1.1",
        gri=["305-1", "305-2"],
        sfdr_pai=["1", "2"],
        csrd_esrs=["ESRS E1-6", "ESRS E1-7"],
        issb_ifrs=["IFRS S2 para 29a", "IFRS S2 para 29b"],
        sasb={"IF-EU": "IF-EU-110a.1", "TR-RO": "TR-RO-110a.1", "RR": "RR-110a.1"},
        sdg=[13, 9],
        tcfd=["Metrics & Targets — GHG emissions (a)"],
        description="Absolute Scope 1 & Scope 2 GHG emissions (tCO2e)",
        mandatory_jurisdictions=["GB","EU","FR","DE","NL"],
    ),
    "E1.2": RegulatoryRef(
        metric_id="E1.2",
        gri=["305-3"],
        sfdr_pai=["1", "3"],
        csrd_esrs=["ESRS E1-6", "ESRS E1-9"],
        issb_ifrs=["IFRS S2 para 29c"],
        sasb={"IF-EU": "IF-EU-110a.2"},
        sdg=[13, 12],
        tcfd=["Metrics & Targets — GHG emissions (a)"],
        description="Scope 3 / carbon intensity per unit revenue (tCO2e / £M)",
        mandatory_jurisdictions=["EU","GB"],
    ),
    "E1.3": RegulatoryRef(
        metric_id="E1.3",
        gri=["302-1", "302-2"],
        sfdr_pai=["5"],
        csrd_esrs=["ESRS E1-5", "ESRS E2-4"],
        issb_ifrs=["IFRS S2 para 29e"],
        sasb={"IF-EU": "IF-EU-000.B", "CN-CE": "CN-CE-130a.1"},
        sdg=[7, 13],
        tcfd=["Metrics & Targets — transition risks"],
        description="% of electricity/energy from renewable sources",
        mandatory_jurisdictions=["EU","GB","DE"],
    ),
    "E1.4": RegulatoryRef(
        metric_id="E1.4",
        gri=["305-5"],
        sfdr_pai=["4"],
        csrd_esrs=["ESRS E1-4"],
        issb_ifrs=["IFRS S2 para 22"],
        sasb={},
        sdg=[13],
        tcfd=["Strategy — transition plan"],
        description="Net-zero or SBTi-aligned carbon reduction target",
        mandatory_jurisdictions=["EU"],
    ),
    "E2.1": RegulatoryRef(
        metric_id="E2.1",
        gri=["302-3"],
        sfdr_pai=["5"],
        csrd_esrs=["ESRS E1-5"],
        issb_ifrs=["IFRS S2 para 29e"],
        sasb={"IF-EU": "IF-EU-000.A"},
        sdg=[7],
        tcfd=["Metrics & Targets — energy use"],
        description="Energy intensity (kWh per £M revenue)",
        mandatory_jurisdictions=["GB","EU"],
    ),
    "E2.2": RegulatoryRef(
        metric_id="E2.2",
        gri=["302-1"],
        sfdr_pai=["5"],
        csrd_esrs=["ESRS E1-5"],
        issb_ifrs=[],
        sasb={},
        sdg=[7, 13],
        tcfd=[],
        description="% heating from low-carbon / renewable sources",
        mandatory_jurisdictions=[],
    ),
    "E3.1": RegulatoryRef(
        metric_id="E3.1",
        gri=["303-3", "303-4", "303-5"],
        sfdr_pai=["7"],
        csrd_esrs=["ESRS E3-4", "ESRS E3-5"],
        issb_ifrs=[],
        sasb={"IF-EU": "IF-EU-140a.1", "FB-AG": "FB-AG-140a.1"},
        sdg=[6],
        tcfd=["Risk Management — physical risks"],
        description="Water consumption (m³) and % in water-stressed areas",
        mandatory_jurisdictions=["EU"],
    ),
    "E3.2": RegulatoryRef(
        metric_id="E3.2",
        gri=["306-3", "306-4"],
        sfdr_pai=["8"],
        csrd_esrs=["ESRS E5-4", "ESRS E5-5"],
        issb_ifrs=[],
        sasb={"FB-FR": "FB-FR-150a.1"},
        sdg=[12],
        tcfd=[],
        description="% waste diverted from landfill / food surplus redistributed",
        mandatory_jurisdictions=["EU","GB"],
    ),
    "E4.1": RegulatoryRef(
        metric_id="E4.1",
        gri=["304-2"],
        sfdr_pai=["7", "10", "14"],
        csrd_esrs=["ESRS E4-1", "ESRS E4-2", "ESRS E4-5"],
        issb_ifrs=[],
        sasb={"FB-AG": "FB-AG-160a.1"},
        sdg=[15, 14],
        tcfd=["Risk Management — nature-related risks"],
        description="No-deforestation / biodiversity protection policy in place",
        mandatory_jurisdictions=["EU"],
    ),
    "S1.1": RegulatoryRef(
        metric_id="S1.1",
        gri=["405-2"],
        sfdr_pai=["12"],
        csrd_esrs=["ESRS S1-16"],
        issb_ifrs=["IFRS S1 para 29"],
        sasb={"HC-DY": "HC-DY-330a.1"},
        sdg=[10, 5],
        tcfd=[],
        description="Gender pay gap — mean % difference in pay",
        mandatory_jurisdictions=["GB","FR","DE"],
    ),
    "S1.2": RegulatoryRef(
        metric_id="S1.2",
        gri=["403-9"],
        sfdr_pai=["3"],
        csrd_esrs=["ESRS S1-14"],
        issb_ifrs=[],
        sasb={"IF-EU": "IF-EU-320a.1", "TR-RO": "TR-RO-320a.1"},
        sdg=[3, 8],
        tcfd=[],
        description="Reportable injury rate (RIDDOR / TRIR per 200,000 hrs)",
        mandatory_jurisdictions=["GB","EU"],
    ),
    "S1.3": RegulatoryRef(
        metric_id="S1.3",
        gri=["404-1"],
        sfdr_pai=[],
        csrd_esrs=["ESRS S1-13"],
        issb_ifrs=[],
        sasb={"HC-DY": "HC-DY-330a.2"},
        sdg=[4, 8],
        tcfd=[],
        description="Average hours of training per employee per year",
        mandatory_jurisdictions=["EU"],
    ),
    "S2.1": RegulatoryRef(
        metric_id="S2.1",
        gri=["308-1", "414-1"],
        sfdr_pai=["9", "10", "11"],
        csrd_esrs=["ESRS S2-1", "ESRS S2-4"],
        issb_ifrs=[],
        sasb={"FB-AG": "FB-AG-430a.1"},
        sdg=[12, 8],
        tcfd=[],
        description="% suppliers screened for environmental and social standards",
        mandatory_jurisdictions=["EU","DE","GB"],
    ),
    "S3.1": RegulatoryRef(
        metric_id="S3.1",
        gri=["203-1", "413-1"],
        sfdr_pai=[],
        csrd_esrs=["ESRS S3-1", "ESRS S4-1"],
        issb_ifrs=[],
        sasb={},
        sdg=[11, 17],
        tcfd=[],
        description="Community investment, product safety, customer impact",
        mandatory_jurisdictions=[],
    ),
    "G1.1": RegulatoryRef(
        metric_id="G1.1",
        gri=["405-1"],
        sfdr_pai=["3"],
        csrd_esrs=["ESRS G1-1", "ESRS 2 GOV-1"],
        issb_ifrs=["IFRS S1 para 5"],
        sasb={"FN-IB": "FN-IB-510a.1"},
        sdg=[16],
        tcfd=["Governance — board oversight"],
        description="% board members who are independent non-executives",
        mandatory_jurisdictions=["GB","EU","US"],
    ),
    "G1.2": RegulatoryRef(
        metric_id="G1.2",
        gri=["405-1"],
        sfdr_pai=[],
        csrd_esrs=["ESRS 2 GOV-1"],
        issb_ifrs=[],
        sasb={},
        sdg=[5, 16],
        tcfd=["Governance — board composition"],
        description="% women on board of directors",
        mandatory_jurisdictions=["GB","EU","FR","DE"],
    ),
    "G2.1": RegulatoryRef(
        metric_id="G2.1",
        gri=["205-1", "205-2"],
        sfdr_pai=["13"],
        csrd_esrs=["ESRS G1-3"],
        issb_ifrs=[],
        sasb={"FN-IB": "FN-IB-510a.2"},
        sdg=[16],
        tcfd=[],
        description="Anti-corruption and code-of-conduct policy in place",
        mandatory_jurisdictions=["GB","EU"],
    ),
    "G2.2": RegulatoryRef(
        metric_id="G2.2",
        gri=["205-3"],
        sfdr_pai=["13"],
        csrd_esrs=["ESRS G1-4"],
        issb_ifrs=[],
        sasb={},
        sdg=[16],
        tcfd=[],
        description="Number of confirmed bribery / corruption incidents",
        mandatory_jurisdictions=["GB","EU"],
    ),
    "G3.1": RegulatoryRef(
        metric_id="G3.1",
        gri=["207-3", "207-4"],
        sfdr_pai=["15"],
        csrd_esrs=["ESRS G1-6"],
        issb_ifrs=[],
        sasb={},
        sdg=[17, 16],
        tcfd=[],
        description="Country-by-country tax transparency reporting",
        mandatory_jurisdictions=["EU","GB"],
    ),
}


class RegulatoryCrosswalk:

    def get(self, metric_id: str) -> Optional[RegulatoryRef]:
        return REGULATORY_CROSSWALK.get(metric_id)

    def metrics_for_sfdr_pai(self, pai_number: str) -> List[str]:
        return [mid for mid, ref in REGULATORY_CROSSWALK.items()
                if pai_number in ref.sfdr_pai]

    def metrics_for_csrd(self, esrs_code: str) -> List[str]:
        return [mid for mid, ref in REGULATORY_CROSSWALK.items()
                if any(esrs_code in e for e in ref.csrd_esrs)]

    def coverage_report(self, scored_metric_ids: List[str]) -> dict:
        """Returns compliance gap analysis for SFDR/CSRD/ISSB."""
        all_sfdr = set()
        all_csrd = set()
        covered_sfdr = set()
        covered_csrd = set()

        for mid, ref in REGULATORY_CROSSWALK.items():
            all_sfdr.update(ref.sfdr_pai)
            all_csrd.update(ref.csrd_esrs)
            if mid in scored_metric_ids:
                covered_sfdr.update(ref.sfdr_pai)
                covered_csrd.update(ref.csrd_esrs)

        return {
            "sfdr_pai": {
                "total": len(all_sfdr),
                "covered": len(covered_sfdr),
                "pct": round(len(covered_sfdr)/len(all_sfdr)*100 if all_sfdr else 0),
                "missing": sorted(all_sfdr - covered_sfdr),
            },
            "csrd_esrs": {
                "total": len(all_csrd),
                "covered": len(covered_csrd),
                "pct": round(len(covered_csrd)/len(all_csrd)*100 if all_csrd else 0),
                "missing": sorted(all_csrd - covered_csrd),
            },
        }

    def as_dict(self, metric_id: str) -> dict:
        ref = REGULATORY_CROSSWALK.get(metric_id)
        if not ref:
            return {}
        return {
            "metric_id": ref.metric_id,
            "description": ref.description,
            "gri": ref.gri,
            "sfdr_pai": ref.sfdr_pai,
            "csrd_esrs": ref.csrd_esrs,
            "issb_ifrs": ref.issb_ifrs,
            "sasb": ref.sasb,
            "sdg": ref.sdg,
            "tcfd": ref.tcfd,
            "mandatory_jurisdictions": ref.mandatory_jurisdictions,
        }

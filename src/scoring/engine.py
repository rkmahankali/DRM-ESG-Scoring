"""
ESG Scoring Engine.
Outcome-based, confidence-weighted, fully auditable.
Every score references the evidence items that produced it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from src.models.domain import (
    ESGPillar,
    ESGScore,
    EvidenceItem,
    MetricScore,
    PillarScore,
    GreenwashAlert,
)
from src.ontology.esg_ontology import ESGOntology, MetricDefinition


@dataclass
class ScoringConfig:
    """Overridable weights and thresholds."""
    pillar_weights: dict[str, float] = None  # E/S/G → weight
    outcome_premium: float = 1.2             # outcome-based metrics score 20% higher weight
    min_data_coverage: float = 0.30          # below this, score is marked unreliable
    greenwash_threshold: float = 0.35        # delta between stated and measured triggers alert
    peer_adjust: bool = True                 # normalise vs. sector peers

    def __post_init__(self):
        if self.pillar_weights is None:
            self.pillar_weights = {"E": 0.40, "S": 0.35, "G": 0.25}


class ScoringEngine:
    """
    Core scoring engine.
    Input:  evidence items for a company (already normalised to 0–1)
    Output: ESGScore with full lineage
    """

    def __init__(self, ontology: ESGOntology, config: Optional[ScoringConfig] = None):
        self.ontology = ontology
        self.config = config or ScoringConfig()

    def score(
        self,
        company_id: str,
        sector: str,
        evidence: list[EvidenceItem],
        peer_evidence: Optional[dict[str, list[EvidenceItem]]] = None,
    ) -> tuple[ESGScore, list[GreenwashAlert]]:
        metrics = self.ontology.metrics_for_sector(sector)
        evidence_by_metric: dict[str, list[EvidenceItem]] = {}
        for ev in evidence:
            evidence_by_metric.setdefault(ev.metric_id, []).append(ev)

        metric_scores: list[MetricScore] = []
        for metric_def in metrics:
            ms = self._score_metric(metric_def, evidence_by_metric.get(metric_def.id, []))
            metric_scores.append(ms)

        pillar_scores: dict[ESGPillar, PillarScore] = {}
        for pillar_enum in ESGPillar:
            pkey = pillar_enum.value
            p_metrics = [ms for ms in metric_scores if ms.pillar == pillar_enum]
            ps = self._aggregate_pillar(pillar_enum, p_metrics, self.ontology.pillars[pkey])
            pillar_scores[pillar_enum] = ps

        composite = self._composite(pillar_scores)
        alerts = self._detect_greenwash(company_id, metric_scores, evidence_by_metric)

        total_evidence = sum(len(v) for v in evidence_by_metric.values())
        covered = sum(1 for ms in metric_scores if ms.data_coverage > 0)
        data_coverage = covered / max(len(metrics), 1)
        overall_confidence = _weighted_mean(
            [(ps.confidence, self.config.pillar_weights.get(p.value, 0.33))
             for p, ps in pillar_scores.items()]
        )
        greenwash_risk = max((a.divergence_score for a in alerts), default=0.0)

        esg = ESGScore(
            company_id=company_id,
            composite_score=composite,
            pillar_scores=pillar_scores,
            confidence=overall_confidence,
            data_coverage=data_coverage,
            greenwash_risk=greenwash_risk,
            evidence_count=total_evidence,
        )
        return esg, alerts

    # ------------------------------------------------------------------

    def _score_metric(
        self, metric_def: MetricDefinition, evidence: list[EvidenceItem]
    ) -> MetricScore:
        if not evidence:
            return MetricScore(
                metric_id=metric_def.id,
                metric_name=metric_def.name,
                pillar=ESGPillar(metric_def.pillar),
                category=metric_def.category,
                score=0.0,
                confidence=0.0,
                data_coverage=0.0,
                outcome_based=metric_def.outcome_based,
            )

        # Confidence-weighted average of normalised values
        weighted_values = [
            (ev.normalized_value, ev.confidence)
            for ev in evidence
            if ev.normalized_value is not None
        ]
        if not weighted_values:
            score_raw = 0.0
            confidence = 0.0
        else:
            score_raw = _weighted_mean(weighted_values)
            confidence = _weighted_mean([(ev.confidence, 1.0) for ev in evidence])

        # Convert 0-1 → 0-100, apply outcome premium
        weight_mult = self.config.outcome_premium if metric_def.outcome_based else 1.0
        score = min(score_raw * 100 * weight_mult, 100.0)

        coverage = min(len(evidence) / 3.0, 1.0)  # expect ~3 evidence points per metric

        return MetricScore(
            metric_id=metric_def.id,
            metric_name=metric_def.name,
            pillar=ESGPillar(metric_def.pillar),
            category=metric_def.category,
            score=score,
            confidence=confidence,
            data_coverage=coverage,
            evidence_ids=[ev.id for ev in evidence],
            outcome_based=metric_def.outcome_based,
        )

    def _aggregate_pillar(
        self, pillar_enum: ESGPillar, metric_scores: list[MetricScore], pillar_def
    ) -> PillarScore:
        if not metric_scores:
            return PillarScore(pillar=pillar_enum, score=0.0, confidence=0.0)

        # Build category weight map
        cat_weights = {cat.id: cat.weight for cat in pillar_def.categories}
        cat_metric_map: dict[str, list[MetricScore]] = {}
        for ms in metric_scores:
            cat_key = ms.metric_id[:2]   # "E1", "S2", etc.
            cat_metric_map.setdefault(cat_key, []).append(ms)

        cat_scores: list[tuple[float, float]] = []  # (score, weight)
        for cat_id, cat_ms in cat_metric_map.items():
            w = cat_weights.get(cat_id, 1.0)
            avg = _weighted_mean([(m.score, m.confidence or 0.01) for m in cat_ms])
            cat_scores.append((avg, w))

        score = _weighted_mean(cat_scores) if cat_scores else 0.0
        confidence = _weighted_mean(
            [(ms.confidence, 1.0) for ms in metric_scores]
        )
        return PillarScore(
            pillar=pillar_enum,
            score=score,
            confidence=confidence,
            metric_scores=metric_scores,
        )

    def _composite(self, pillar_scores: dict[ESGPillar, PillarScore]) -> float:
        pairs = [
            (ps.score, self.config.pillar_weights.get(p.value, 0.33))
            for p, ps in pillar_scores.items()
        ]
        return _weighted_mean(pairs) if pairs else 0.0

    def _detect_greenwash(
        self,
        company_id: str,
        metric_scores: list[MetricScore],
        evidence_by_metric: dict[str, list[EvidenceItem]],
    ) -> list[GreenwashAlert]:
        alerts = []
        for ms in metric_scores:
            evidence = evidence_by_metric.get(ms.metric_id, [])
            policy_ev = [e for e in evidence if not e.verified and e.evidence_type.value == "self_reported"]
            outcome_ev = [e for e in evidence if e.evidence_type.value == "quantitative" and e.verified]
            if not (policy_ev and outcome_ev):
                continue
            policy_score = _weighted_mean([(e.normalized_value or 0, e.confidence) for e in policy_ev])
            outcome_score = _weighted_mean([(e.normalized_value or 0, e.confidence) for e in outcome_ev])
            divergence = abs(policy_score - outcome_score)
            if divergence >= self.config.greenwash_threshold:
                alerts.append(GreenwashAlert(
                    company_id=company_id,
                    pillar=ms.pillar,
                    metric_id=ms.metric_id,
                    claim=f"Self-reported score: {policy_score:.2f}",
                    counter_evidence=f"Measured outcome score: {outcome_score:.2f}",
                    divergence_score=divergence,
                ))
        return alerts


def _weighted_mean(pairs: list[tuple[float, float]]) -> float:
    total_w = sum(w for _, w in pairs)
    if total_w == 0 or not pairs:
        return 0.0
    return sum(v * w for v, w in pairs) / total_w

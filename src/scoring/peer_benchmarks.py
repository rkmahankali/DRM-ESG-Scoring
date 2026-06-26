"""
Peer benchmarking — normalise scores against sector cohort.
Computes percentile rank and updates peer_percentile on MetricScore.
In production this queries the graph DB for peer company evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import math

from src.models.domain import ESGScore, MetricScore


@dataclass
class SectorBenchmark:
    """
    Holds sector-level statistics per metric for normalisation.
    Populated from the knowledge graph or a static reference table.
    """
    sector: str
    # metric_id → (p10, p50, p90) across peer companies
    percentiles: dict[str, tuple[float, float, float]] = field(default_factory=dict)

    def peer_percentile(self, metric_id: str, score: float) -> Optional[float]:
        if metric_id not in self.percentiles:
            return None
        p10, p50, p90 = self.percentiles[metric_id]
        # Approximate normal CDF from the three percentiles
        if p90 == p10:
            return 0.5
        sigma = (p90 - p10) / (2 * 1.282)   # ~80th–20th percentile span
        mu = p50
        z = (score - mu) / max(sigma, 0.001)
        return _normal_cdf(z)


class PeerBenchmarker:
    def __init__(self, benchmarks: dict[str, SectorBenchmark]):
        self._benchmarks = benchmarks  # sector → SectorBenchmark

    def annotate(self, score: ESGScore, sector: str) -> ESGScore:
        """Add peer_percentile to each MetricScore in-place."""
        bench = self._benchmarks.get(sector) or self._benchmarks.get("*")
        if not bench:
            return score
        for pillar_score in score.pillar_scores.values():
            for ms in pillar_score.metric_scores:
                ms.peer_percentile = bench.peer_percentile(ms.metric_id, ms.score)
        return score

    @staticmethod
    def default_benchmarks() -> "PeerBenchmarker":
        """
        Synthetic sector-agnostic benchmarks for bootstrapping.
        Replace with real peer data once the graph is populated.
        """
        generic = SectorBenchmark(
            sector="*",
            percentiles={
                "E1.1": (20.0, 50.0, 80.0),
                "E1.2": (25.0, 55.0, 78.0),
                "E1.3": (15.0, 48.0, 75.0),
                "E2.1": (30.0, 60.0, 85.0),
                "E2.2": (20.0, 50.0, 78.0),
                "S1.1": (40.0, 65.0, 85.0),
                "S1.2": (25.0, 55.0, 80.0),
                "G1.2": (20.0, 50.0, 75.0),
                "G2.2": (55.0, 72.0, 90.0),
            },
        )
        return PeerBenchmarker({"*": generic})


def _normal_cdf(z: float) -> float:
    """Approximation of Φ(z) using Abramowitz & Stegun."""
    p = 0.2316419
    b = (0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429)
    t = 1.0 / (1.0 + p * abs(z))
    poly = sum(b[i] * t ** (i + 1) for i in range(5))
    cdf = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z * z) * poly
    return cdf if z >= 0 else 1.0 - cdf

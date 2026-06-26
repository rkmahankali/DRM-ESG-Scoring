"""Tests for peer benchmarking."""
import pytest

from src.scoring.peer_benchmarks import PeerBenchmarker, SectorBenchmark, _normal_cdf


def test_normal_cdf_midpoint():
    assert abs(_normal_cdf(0.0) - 0.5) < 0.01

def test_normal_cdf_positive():
    assert _normal_cdf(1.96) > 0.97

def test_normal_cdf_negative():
    assert _normal_cdf(-1.96) < 0.03


def test_peer_percentile_above_median():
    bench = SectorBenchmark(
        sector="*",
        percentiles={"E1.1": (20.0, 50.0, 80.0)},
    )
    pct = bench.peer_percentile("E1.1", 70.0)
    assert pct is not None
    assert pct > 0.5


def test_peer_percentile_unknown_metric():
    bench = SectorBenchmark(sector="*", percentiles={})
    assert bench.peer_percentile("ZZ.0", 50.0) is None


def test_default_benchmarker_instantiates():
    bm = PeerBenchmarker.default_benchmarks()
    assert bm is not None

"""Unit tests for the ESG scoring engine."""
import pytest

from src.models.domain import DataSource, EvidenceItem, EvidenceType
from src.ontology.esg_ontology import ESGOntology
from src.scoring.engine import ScoringEngine, ScoringConfig


@pytest.fixture
def ontology():
    return ESGOntology()


@pytest.fixture
def engine(ontology):
    return ScoringEngine(ontology)


def make_evidence(metric_id: str, value: float, evidence_type=EvidenceType.QUANTITATIVE,
                  verified=True, confidence=0.9) -> EvidenceItem:
    return EvidenceItem(
        company_id="test-co",
        metric_id=metric_id,
        source=DataSource.API_FEED,
        evidence_type=evidence_type,
        normalized_value=value,
        confidence=confidence,
        verified=verified,
    )


def test_full_evidence_produces_high_score(engine):
    evidence = [
        make_evidence("E1.1", 0.85),
        make_evidence("E1.2", 0.80),
        make_evidence("E2.1", 0.90),
        make_evidence("S1.1", 0.88),
        make_evidence("G1.2", 0.75),
    ]
    score, alerts = engine.score("test-co", "*", evidence)
    assert score.composite_score > 0
    assert 0 <= score.composite_score <= 100
    assert score.confidence > 0


def test_no_evidence_produces_zero_score(engine):
    score, alerts = engine.score("test-co", "*", [])
    assert score.composite_score == 0.0
    assert score.evidence_count == 0


def test_greenwash_detection(engine):
    evidence = [
        make_evidence("E1.1", 0.95, EvidenceType.SELF_REPORTED, verified=False, confidence=0.7),
        make_evidence("E1.1", 0.20, EvidenceType.QUANTITATIVE, verified=True, confidence=0.95),
    ]
    score, alerts = engine.score("test-co", "*", evidence)
    assert len(alerts) >= 1
    assert alerts[0].metric_id == "E1.1"
    assert alerts[0].divergence_score >= 0.35


def test_outcome_premium_applied(engine, ontology):
    ev_outcome = make_evidence("E1.1", 0.5)  # outcome_based=True in ontology
    score_out, _ = engine.score("test-co", "*", [ev_outcome])

    # Disable outcome premium
    engine_flat = ScoringEngine(ontology, ScoringConfig(outcome_premium=1.0))
    score_flat, _ = engine_flat.score("test-co", "*", [ev_outcome])

    assert score_out.composite_score >= score_flat.composite_score


def test_ontology_sector_filter(ontology):
    all_metrics = ontology.metrics_for_sector("*")
    assert len(all_metrics) > 10
    for m in all_metrics:
        assert m.pillar in ("E", "S", "G")


def test_pillar_weights_sum_to_one(engine):
    total = sum(engine.config.pillar_weights.values())
    assert abs(total - 1.0) < 0.001

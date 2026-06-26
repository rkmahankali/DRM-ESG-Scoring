"""Tests for data ingestion extractors."""
import pytest

from src.ingestion.extractor import (
    QuestionnaireExtractor,
    APIFeedExtractor,
    DocumentExtractor,
    normalise_lower_is_better,
    normalise_higher_is_better,
)
from src.models.domain import DataSource, EvidenceType
from src.ontology.esg_ontology import ESGOntology


@pytest.fixture
def ontology():
    return ESGOntology()


# --- Normalisation ---

def test_lower_is_better_at_max():
    assert normalise_lower_is_better(100.0, 100.0) == 0.0

def test_lower_is_better_at_min():
    assert normalise_lower_is_better(0.0, 100.0) == 1.0

def test_higher_is_better_midpoint():
    result = normalise_higher_is_better(50.0, 100.0)
    assert abs(result - 0.5) < 0.01


# --- Questionnaire extractor ---

def test_questionnaire_extracts_known_metric(ontology):
    extractor = QuestionnaireExtractor(
        ontology=ontology,
        sector_benchmarks={"E2.1": (0.0, 100.0)},
    )
    evidence = extractor.extract({
        "company_id": "test-co",
        "responses": {
            "E2.1": {"value": 75.0, "unit": "%", "verified": False},
        },
    })
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.metric_id == "E2.1"
    assert ev.source == DataSource.QUESTIONNAIRE
    assert ev.evidence_type == EvidenceType.SELF_REPORTED
    assert ev.normalized_value is not None
    assert 0.0 <= ev.normalized_value <= 1.0
    assert ev.confidence == pytest.approx(0.60)
    assert ev.verified is False


def test_questionnaire_ignores_unknown_metric(ontology):
    extractor = QuestionnaireExtractor(ontology=ontology)
    evidence = extractor.extract({
        "company_id": "test-co",
        "responses": {"XX.99": {"value": 10}},
    })
    assert evidence == []


def test_questionnaire_skips_missing_value(ontology):
    extractor = QuestionnaireExtractor(ontology=ontology)
    evidence = extractor.extract({
        "company_id": "test-co",
        "responses": {"E1.1": {"value": None}},
    })
    assert evidence == []


# --- API feed extractor ---

def test_api_feed_extracts_records(ontology):
    extractor = APIFeedExtractor(
        ontology=ontology,
        sector_benchmarks={"S1.1": (0.0, 5.0)},
    )
    records = [
        {"metric_id": "S1.1", "value": 1.2, "unit": "per 200k hours",
         "confidence": 0.92, "verified": True},
    ]
    evidence = extractor.extract("test-co", records)
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.source == DataSource.API_FEED
    assert ev.evidence_type == EvidenceType.QUANTITATIVE
    assert ev.verified is True
    assert ev.confidence == pytest.approx(0.92)


def test_api_feed_skips_unknown_metric(ontology):
    extractor = APIFeedExtractor(ontology=ontology)
    evidence = extractor.extract("test-co", [{"metric_id": "ZZ.0", "value": 5.0}])
    assert evidence == []


# --- Document extractor (regex mode) ---

def test_document_extracts_emissions(ontology):
    extractor = DocumentExtractor(ontology=ontology, llm_enabled=False)
    text = "The company emitted 12,500 tonnes CO2e in 2023, down 8% from prior year."
    items = extractor.extract_from_text("test-co", text)
    metric_ids = [i.metric_id for i in items]
    assert "E1.1" in metric_ids
    ev = next(i for i in items if i.metric_id == "E1.1")
    assert ev.source == DataSource.DOCUMENT
    assert ev.confidence < 0.80   # lower confidence for document extraction


def test_document_extracts_renewable_share(ontology):
    extractor = DocumentExtractor(ontology=ontology, llm_enabled=False)
    text = "We source 68% renewable energy across all facilities."
    items = extractor.extract_from_text("test-co", text)
    metric_ids = [i.metric_id for i in items]
    assert "E2.1" in metric_ids


def test_document_no_match_returns_empty(ontology):
    extractor = DocumentExtractor(ontology=ontology, llm_enabled=False)
    items = extractor.extract_from_text("test-co", "No ESG data here, just boilerplate text.")
    assert items == []

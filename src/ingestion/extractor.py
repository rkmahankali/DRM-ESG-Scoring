"""
Data ingestion & evidence extraction pipeline.

Sources supported:
  - PDF / text documents (LLM-assisted extraction)
  - Structured questionnaire JSON (DDQ / portfolio company submission)
  - API feeds (numeric time-series)
  - Regulatory filings (SFDR, CSRD templates)

Each extractor normalises raw values to [0, 1] and emits EvidenceItems
with source provenance and confidence scores.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from src.models.domain import DataSource, EvidenceItem, EvidenceType
from src.ontology.esg_ontology import ESGOntology, MetricDefinition


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalise_lower_is_better(value: float, peer_max: float, peer_min: float = 0.0) -> float:
    """Metrics where lower = better (emissions, injury rate, pay gap)."""
    if peer_max <= peer_min:
        return 0.5
    return 1.0 - max(0.0, min(1.0, (value - peer_min) / (peer_max - peer_min)))


def normalise_higher_is_better(value: float, peer_max: float, peer_min: float = 0.0) -> float:
    """Metrics where higher = better (renewable share, board diversity)."""
    if peer_max <= peer_min:
        return 0.5
    return max(0.0, min(1.0, (value - peer_min) / (peer_max - peer_min)))


def normalise_boolean(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, str):
        return 1.0 if value.lower() in ("yes", "true", "1", "exists") else 0.0
    return float(bool(value))


# Metrics where lower raw value → better normalised score
LOWER_IS_BETTER = {
    "E1.1", "E1.2", "E1.3",  # emissions
    "E3.2",                   # hazardous waste
    "S1.1",                   # injury rate
    "S1.2",                   # pay gap (absolute)
    "G2.2",                   # corruption incidents
}

BOOLEAN_METRICS = {"G2.1", "E4.1"}


def normalise(metric_id: str, raw_value: float, sector_max: float, sector_min: float = 0.0) -> float:
    if metric_id in BOOLEAN_METRICS:
        return normalise_boolean(raw_value)
    if metric_id in LOWER_IS_BETTER:
        return normalise_lower_is_better(raw_value, sector_max, sector_min)
    return normalise_higher_is_better(raw_value, sector_max, sector_min)


# ---------------------------------------------------------------------------
# Questionnaire extractor (DDQ / portfolio company form)
# ---------------------------------------------------------------------------

@dataclass
class QuestionnaireExtractor:
    """
    Parses a structured JSON questionnaire submission from a portfolio company.

    Expected format:
    {
      "company_id": "...",
      "responses": {
        "E1.1": {"value": 12500, "unit": "tCO2e", "verified": false},
        "S1.1": {"value": 0.8, "unit": "per 200k hours", "verified": false},
        ...
      }
    }
    """
    ontology: ESGOntology
    sector_benchmarks: dict[str, tuple[float, float]] = field(default_factory=dict)

    def extract(self, payload: dict[str, Any]) -> list[EvidenceItem]:
        company_id = payload["company_id"]
        items: list[EvidenceItem] = []
        for metric_id, resp in payload.get("responses", {}).items():
            metric_def = self.ontology.get_metric(metric_id)
            if not metric_def:
                continue
            raw = resp.get("value")
            if raw is None:
                continue
            s_min, s_max = self.sector_benchmarks.get(metric_id, (0.0, 100.0))
            norm = normalise(metric_id, float(raw), s_max, s_min)
            items.append(EvidenceItem(
                company_id=company_id,
                metric_id=metric_id,
                source=DataSource.QUESTIONNAIRE,
                evidence_type=EvidenceType.SELF_REPORTED,
                raw_value=raw,
                normalized_value=norm,
                unit=resp.get("unit"),
                confidence=0.60,   # self-reported, unverified
                verified=resp.get("verified", False),
            ))
        return items


# ---------------------------------------------------------------------------
# Structured API feed extractor (numeric time-series)
# ---------------------------------------------------------------------------

@dataclass
class APIFeedExtractor:
    """
    Ingests numeric data from an external feed (satellite, IoT, public registry).
    Expects list of {metric_id, value, unit, confidence, source_url}.
    """
    ontology: ESGOntology
    sector_benchmarks: dict[str, tuple[float, float]] = field(default_factory=dict)

    def extract(self, company_id: str, records: list[dict[str, Any]]) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for rec in records:
            metric_id = rec.get("metric_id")
            if not metric_id or not self.ontology.get_metric(metric_id):
                continue
            raw = rec.get("value")
            s_min, s_max = self.sector_benchmarks.get(metric_id, (0.0, 100.0))
            norm = normalise(metric_id, float(raw), s_max, s_min)
            items.append(EvidenceItem(
                company_id=company_id,
                metric_id=metric_id,
                source=DataSource.API_FEED,
                evidence_type=EvidenceType.QUANTITATIVE,
                raw_value=raw,
                normalized_value=norm,
                unit=rec.get("unit"),
                source_url=rec.get("source_url"),
                confidence=rec.get("confidence", 0.85),
                verified=rec.get("verified", True),
            ))
        return items


# ---------------------------------------------------------------------------
# LLM-based document extractor (PDF / filings / news)
# ---------------------------------------------------------------------------

@dataclass
class DocumentExtractor:
    """
    Uses an LLM to extract ESG claims from unstructured text.
    Returns EvidenceItems with lower confidence (qualitative, unverified).

    In production this calls the Anthropic Claude API with a structured
    extraction prompt. The stub below parses simple regex patterns for demo.
    """
    ontology: ESGOntology
    llm_enabled: bool = False   # set True when Anthropic API key is configured

    # Regex patterns for quick demo extraction
    PATTERNS: dict[str, re.Pattern] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self.PATTERNS = {
            "E1.1": re.compile(r"(\d[\d,\.]+)\s*(?:tonnes?|tCO2e|t CO2)", re.I),
            "E2.1": re.compile(r"(\d[\d\.]+)\s*%\s*renewable", re.I),
            "S1.2": re.compile(r"gender\s+pay\s+gap[^\d]*(\d[\d\.]+)\s*%", re.I),
            "G1.2": re.compile(r"(\d[\d\.]+)\s*%\s*women\s+on\s+(?:the\s+)?board", re.I),
        }

    def extract_from_text(self, company_id: str, text: str,
                          source_url: Optional[str] = None) -> list[EvidenceItem]:
        if self.llm_enabled:
            return self._llm_extract(company_id, text, source_url)
        return self._regex_extract(company_id, text, source_url)

    def _regex_extract(self, company_id: str, text: str,
                       source_url: Optional[str]) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for metric_id, pattern in self.PATTERNS.items():
            match = pattern.search(text)
            if not match:
                continue
            raw_str = match.group(1).replace(",", "")
            try:
                raw_val = float(raw_str)
            except ValueError:
                continue
            items.append(EvidenceItem(
                company_id=company_id,
                metric_id=metric_id,
                source=DataSource.DOCUMENT,
                evidence_type=EvidenceType.QUALITATIVE,
                raw_value=raw_val,
                normalized_value=None,  # requires sector benchmark to normalise
                claim_text=match.group(0),
                source_url=source_url,
                confidence=0.55,        # regex extraction, lower confidence
                verified=False,
            ))
        return items

    def _llm_extract(self, company_id: str, text: str,
                     source_url: Optional[str]) -> list[EvidenceItem]:
        """
        Production path: call Anthropic Claude with a structured JSON extraction prompt.
        Returns EvidenceItems parsed from the model's JSON output.
        """
        try:
            import anthropic
        except ImportError:
            return self._regex_extract(company_id, text, source_url)

        client = anthropic.Anthropic()
        metric_list = "\n".join(
            f"  {m.id}: {m.name} ({m.unit})"
            for m in self.ontology.all_metrics()
        )
        prompt = f"""Extract ESG metrics from the following text.
Return a JSON array of objects with keys: metric_id, value (numeric), unit, claim_text.
Only include metrics you can find explicit numeric evidence for.

Available metrics:
{metric_list}

Text:
{text[:8000]}

Return only valid JSON array, no markdown fences."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            extracted = json.loads(message.content[0].text)
        except (json.JSONDecodeError, IndexError):
            return []

        items: list[EvidenceItem] = []
        for rec in extracted:
            metric_id = rec.get("metric_id")
            if not metric_id or not self.ontology.get_metric(metric_id):
                continue
            items.append(EvidenceItem(
                company_id=company_id,
                metric_id=metric_id,
                source=DataSource.DOCUMENT,
                evidence_type=EvidenceType.QUALITATIVE,
                raw_value=rec.get("value"),
                normalized_value=None,
                unit=rec.get("unit"),
                claim_text=rec.get("claim_text"),
                source_url=source_url,
                confidence=0.72,
                verified=False,
            ))
        return items

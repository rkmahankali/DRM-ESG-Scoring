"""Core domain models for ESG scoring service."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ESGPillar(str, Enum):
    ENVIRONMENTAL = "E"
    SOCIAL = "S"
    GOVERNANCE = "G"


class DataSource(str, Enum):
    DOCUMENT = "document"
    API_FEED = "api_feed"
    QUESTIONNAIRE = "questionnaire"
    REGULATORY_FILING = "regulatory_filing"
    THIRD_PARTY = "third_party"
    SATELLITE = "satellite"


class EvidenceType(str, Enum):
    QUANTITATIVE = "quantitative"
    QUALITATIVE = "qualitative"
    CERTIFIED = "certified"  # third-party verified
    SELF_REPORTED = "self_reported"


class Company(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    legal_entity_identifier: Optional[str] = None
    jurisdiction: str
    sector: str                # SASB sector
    sub_sector: Optional[str] = None
    employee_count: Optional[int] = None
    revenue_usd: Optional[float] = None
    is_listed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    """Atomic unit of evidence backing a metric claim."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    metric_id: str
    source: DataSource
    evidence_type: EvidenceType
    raw_value: Optional[Any] = None
    normalized_value: Optional[float] = None   # 0–1 scale
    unit: Optional[str] = None
    claim_text: Optional[str] = None           # extracted assertion
    source_url: Optional[str] = None
    source_page: Optional[int] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(ge=0.0, le=1.0)  # extraction confidence
    verified: bool = False


class MetricScore(BaseModel):
    """Score for a single ESG metric, fully traceable."""
    metric_id: str
    metric_name: str
    pillar: ESGPillar
    category: str
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    data_coverage: float = Field(ge=0.0, le=1.0)  # % of expected data points present
    evidence_ids: list[str] = Field(default_factory=list)
    peer_percentile: Optional[float] = None    # vs. sector peers
    outcome_based: bool = True              # True = real-world signal, False = disclosure only


class PillarScore(BaseModel):
    pillar: ESGPillar
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    metric_scores: list[MetricScore] = Field(default_factory=list)
    greenwash_risk: float = Field(ge=0.0, le=1.0, default=0.0)


class ESGScore(BaseModel):
    """Top-level ESG score for a company at a point in time."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    composite_score: float = Field(ge=0.0, le=100.0)
    pillar_scores: dict[ESGPillar, PillarScore] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    data_coverage: float = Field(ge=0.0, le=1.0)
    greenwash_risk: float = Field(ge=0.0, le=1.0)
    scored_at: datetime = Field(default_factory=datetime.utcnow)
    scoring_version: str = "1.0"
    # Lineage — every score references its full evidence chain
    evidence_count: int = 0
    audit_log_id: Optional[str] = None


class GreenwashAlert(BaseModel):
    """Raised when stated policy diverges from measured outcome."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    pillar: ESGPillar
    metric_id: str
    claim: str
    counter_evidence: str
    divergence_score: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

"""
Immutable audit ledger.
Every score event is appended; nothing is ever updated or deleted.
Provides regulators a full evidence chain for any score at any point in time.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text, Boolean,
    create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


class AuditEntry(Base):
    __tablename__ = "esg_audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(64), nullable=False)
    company_id = Column(String(36), nullable=False, index=True)
    score_id = Column(String(36), nullable=True, index=True)
    metric_id = Column(String(32), nullable=True)
    pillar = Column(String(1), nullable=True)
    score_value = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    evidence_count = Column(Integer, nullable=True)
    greenwash_risk = Column(Float, nullable=True)
    payload = Column(Text, nullable=False)   # full JSON snapshot
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    scoring_version = Column(String(16), nullable=False, default="1.0")
    immutable = Column(Boolean, nullable=False, default=True)


class AuditLedger:
    """Append-only audit store. Raises on any attempt to mutate existing rows."""

    def __init__(self, db_url: str = "sqlite:///./esg_audit.db"):
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self._guard_mutations()

    def _guard_mutations(self):
        @event.listens_for(self.engine, "before_execute")
        def block_updates(conn, clauseelement, multiparams, params, execution_options):
            sql = str(clauseelement).upper().strip()
            if sql.startswith("UPDATE") or sql.startswith("DELETE"):
                raise PermissionError("Audit ledger is append-only. Updates/deletes are forbidden.")

    def append(self, event_type: str, company_id: str, payload: dict[str, Any], **kwargs) -> str:
        entry_id = str(uuid.uuid4())
        entry = AuditEntry(
            id=entry_id,
            event_type=event_type,
            company_id=company_id,
            payload=json.dumps(payload, default=str),
            **kwargs,
        )
        with Session(self.engine) as session:
            session.add(entry)
            session.commit()
        return entry_id

    def get_history(self, company_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = (
                session.query(AuditEntry)
                .filter(AuditEntry.company_id == company_id)
                .order_by(AuditEntry.created_at)
                .all()
            )
        return [self._row_to_dict(r) for r in rows]

    def get_score_audit(self, score_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = (
                session.query(AuditEntry)
                .filter(AuditEntry.score_id == score_id)
                .order_by(AuditEntry.created_at)
                .all()
            )
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: AuditEntry) -> dict[str, Any]:
        return {
            "id": row.id,
            "event_type": row.event_type,
            "company_id": row.company_id,
            "score_id": row.score_id,
            "metric_id": row.metric_id,
            "pillar": row.pillar,
            "score_value": row.score_value,
            "confidence": row.confidence,
            "evidence_count": row.evidence_count,
            "greenwash_risk": row.greenwash_risk,
            "payload": json.loads(row.payload),
            "created_at": row.created_at.isoformat(),
            "scoring_version": row.scoring_version,
        }

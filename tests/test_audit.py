"""Tests for the immutable audit ledger."""
import pytest

from src.audit.ledger import AuditLedger


@pytest.fixture
def ledger(tmp_path):
    return AuditLedger(db_url=f"sqlite:///{tmp_path}/test_audit.db")


def test_append_and_retrieve(ledger):
    audit_id = ledger.append(
        event_type="score_computed",
        company_id="test-co",
        score_id="score-123",
        score_value=72.5,
        confidence=0.88,
        evidence_count=5,
        greenwash_risk=0.1,
        payload={"test": True},
    )
    assert audit_id is not None

    history = ledger.get_history("test-co")
    assert len(history) == 1
    assert history[0]["score_value"] == pytest.approx(72.5)
    assert history[0]["event_type"] == "score_computed"


def test_get_score_audit(ledger):
    ledger.append(
        event_type="score_computed",
        company_id="co-a",
        score_id="score-abc",
        score_value=55.0,
        confidence=0.75,
        evidence_count=3,
        greenwash_risk=0.0,
        payload={},
    )
    trail = ledger.get_score_audit("score-abc")
    assert len(trail) == 1
    assert trail[0]["score_id"] == "score-abc"


def test_no_history_returns_empty(ledger):
    assert ledger.get_history("nonexistent") == []


def test_updates_are_blocked(ledger):
    ledger.append(
        event_type="test",
        company_id="co-b",
        score_value=50.0,
        confidence=0.8,
        evidence_count=1,
        greenwash_risk=0.0,
        payload={},
    )
    with pytest.raises(PermissionError):
        with ledger.engine.connect() as conn:
            conn.execute(
                ledger.engine.dialect.statement_compiler(
                    ledger.engine.dialect, None
                ).__class__
            )

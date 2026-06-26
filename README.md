# Horison ESG Scoring Service

> Trustworthy, outcome-based, auditable ESG scoring for private markets.

**Problem:** Investors don't lack ESG scores — they lack ones they can trust, trace and act on.  
- Only ~17% of ESG metrics measure real performance (OECD 2025)  
- Major providers' ratings correlate just 0.54 vs. ~0.99 for credit ratings  
- Private companies are invisible: no Bloomberg/MSCI, self-reported data  
- No audit trail: scores can't be traced to source evidence

**Solution:** An ontology + knowledge-graph approach that delivers outcome-based, auditable ESG scores with full lineage — every score traceable to its source evidence.

---

## Architecture

```
Data Ingestion  →  Ontology + Knowledge Graph  →  Scoring Engine  →  REST API
(PDF, DDQ, API     (Neo4j evidence chain,          (outcome-based,    (FastAPI,
 satellite, IoT)    SASB/GRI/SFDR mapping)          greenwash detect)  audit trail)
```

## Regulatory coverage

| Standard | Coverage |
|---|---|
| SFDR PAI | 17 Principal Adverse Indicators mapped |
| CSRD | E1–E5, S1–S4, G1 disclosure requirements |
| ISSB S1/S2 | Climate risk & general sustainability |
| GRI | GRI 302, 303, 305, 306, 401, 403, 405, 414 |
| SASB | Sector-aware metric weighting |

## Quickstart

```bash
# Backend
pip install -e ".[dev]"
uvicorn src.api.main:app --reload
# → http://localhost:8000/docs

# Frontend
cd frontend && npm install && npm run dev
# → http://localhost:5173

# Full stack
docker-compose up
```

## Run tests

```bash
pytest tests/ -v
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/score` | Score from pre-extracted evidence |
| `POST` | `/api/v1/ingest/document` | Extract from PDF/text and score |
| `POST` | `/api/v1/ingest/questionnaire` | Ingest DDQ/portfolio company form |
| `POST` | `/api/v1/ingest/feed` | Ingest numeric API/IoT feed |
| `GET` | `/api/v1/score/{id}/history` | Score history with full lineage |
| `GET` | `/api/v1/audit/{score_id}` | Complete audit trail for a score |
| `GET` | `/api/v1/graph/evidence-chain/{id}` | Knowledge graph evidence chain |
| `GET` | `/api/v1/graph/supply-chain/{id}` | Supply chain ESG risk |
| `GET` | `/api/v1/metrics?sector=*` | List all metrics (SASB sector filter) |
| `GET` | `/api/v1/ontology/pillars` | Full E/S/G ontology structure |

## Project structure

```
src/
  api/          FastAPI routes + app
  audit/        Append-only immutable audit ledger (SQLAlchemy)
  graph/        Neo4j knowledge graph client
  ingestion/    Evidence extractors (document, questionnaire, API feed)
  models/       Pydantic domain models
  ontology/     ESG ontology (E/S/G pillars → categories → 18+ metrics)
  scoring/      Scoring engine + greenwash detector + peer benchmarker
  tasks/        Celery async pipeline
frontend/       React + Recharts + TailwindCSS dashboard
config/         Scoring weight profiles (default, climate-focus, SFDR PAI)
tests/          Pytest test suite
```

## Key design decisions

- **Outcome premium** — real-world metrics are weighted 1.2× vs. policy/disclosure metrics
- **Greenwash detector** — raises alerts when self-reported score diverges from measured outcome ≥35%
- **Immutable audit log** — SQLAlchemy model blocks UPDATE/DELETE at the engine level
- **Configurable scoring profiles** — swap pillar weights per investor mandate (YAML)
- **LLM extraction** — `DocumentExtractor` calls Claude claude-sonnet-4-6 for structured JSON extraction from unstructured documents when `ANTHROPIC_API_KEY` is set

---

*Horison.ai · Prepared by Rama Mahankali*

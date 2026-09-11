# Regulation OS

AI-powered Regulatory Intelligence & Compliance Platform.

See [CLAUDE.md](./CLAUDE.md) for the full project briefing, principles, and roadmap.

## Repo layout

```
apps/
  engine/   Python 3.11+ / FastAPI — OCR, AI extraction, verification, knowledge base
  api/      Node.js / Express — users, login, tasks, alerts, dashboards
  web/      Next.js / React / TypeScript — frontend (later phase)
```

## Status

Phase 0 complete: 16-table regulation data model, 2 Alembic migrations
(schema + integrity triggers), SBP-pack seed data, 7/7 integrity tests
passing.

Phase 1 core engine complete: Pydantic extraction contract, OCR
(Claude vision), structured extraction (Claude Opus 5), fuzzy-match
source verification, and a full ingestion pipeline (PDF -> DRAFT
requirements/obligations/citations in Postgres). Verified live against
realistic clause text and a real PDF end-to-end.

Next: run the pipeline against a real SBP document, build the 100-clause
gold-standard dataset, and human review of the DRAFT output.

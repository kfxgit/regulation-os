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

Next: Phase 1 -- extraction engine (Pydantic extraction contract, AI
prompt, OCR pipeline, source verification, gold-standard dataset).

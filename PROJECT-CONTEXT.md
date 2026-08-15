---
title: Project Context
type: project-context
status: active
owner: "Trading Journal"
created: 2026-08-13
updated: 2026-08-13
ai_access: internal
ai_generated: true
review_status: draft
---

# Project Context

## Objective

Build a Python web-based trading journal backed by PostgreSQL, using the Excel backtesting template as the formula and data-model reference. Users enter trades directly in the web UI (not in Excel). The system automates R-multiple calculations, streaks, drawdown, performance dashboards, and future local AI analysis via Ollama. Preserve all analytical capabilities from the Excel while making them filterable, persistent, and extensible.

## Users

- Primary: single trader owner (local, personal use)
- Future: AI assistant (Ollama) analyzing trade history for pattern detection

## Constraints

- **Delivery**: solo project, phased build
- **Technology**: Python/FastAPI, PostgreSQL, Jinja2 frontend, Ollama via local REST API
- **Privacy**: all trade data and AI processing remain local; no cloud APIs for sensitive data
- **Cost**: free/open-source stack only
- **Compatibility**: must replicate the Excel calculations exactly before adding new features
- **Credentials**: database and any secrets live only in `.env` (never in Markdown)

## Current Phase

**Phase 0 — Project Scaffold**

Exit criteria:
- KOS project docs created and reviewed
- Tech stack confirmed (Python/FastAPI/PostgreSQL/Ollama/Jinja2)
- Excel columns, formulas, and Settings mapped in `SOURCE-REFERENCE.md`

## Authorities

- Requirements: `requirements.md`
- Architecture: `architecture.md`
- Decisions: `DECISIONS.md` and `docs/decisions/`
- Durable knowledge: `memory.md`
- Execution state: `handoff.md`

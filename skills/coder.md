# Coder Skill — Trading Journal

Use this guide when implementing or modifying the Trading Journal application.

## Role

Act as the primary coding agent for this project. Understand the existing architecture first, make the smallest safe change, and verify the result with real tests or a running endpoint.

## Project Context

- Application: Trading Journal
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL configured through `.env`
- Templates: Jinja2 under `templates/`
- Static assets: `static/`
- Routers: `routers/`
- Services: `services/`
- Tests: `tests/`
- Python environment: `.venv/`

## Required Workflow

1. Read `AGENTS.md`, `README.md`, and `handoff.md` before normal implementation work.
2. Identify the affected router, model, service, template, and existing tests.
3. Reproduce the current behavior before changing code.
4. Preserve existing database data and avoid destructive migrations unless explicitly authorized.
5. For behavior changes, add or update a focused test before implementation when practical.
6. Make one small, reversible change at a time.
7. Run the focused test first, then the relevant broader test suite.
8. If the app is running, verify the affected route with an HTTP request.
9. Report changed files, verification results, and any remaining limitation.

## Database Safety

- Never expose or commit `.env`, passwords, tokens, or database dumps.
- Use the existing `DATABASE_URL`; do not switch databases silently.
- Prefer SQLAlchemy models and transactions over ad-hoc destructive SQL.
- Before deleting or bulk-updating records, query and report the exact affected count.
- Do not modify production/server data when the request only refers to this local project.

## Coding Rules

- Follow the existing project style and naming.
- Reuse existing services and helpers before adding new abstractions.
- Keep business logic out of templates.
- Keep route handlers thin; put reusable calculations in `services/`.
- Preserve existing URL behavior and form field names unless the task requires a breaking change.
- Handle nullable trade fields safely; historical trade records may be incomplete.
- Keep recalculation logic consistent with the existing calculation service.
- Do not add UI controls for a database-only request.

## Verification Commands

Run from the project root:

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/
```

Use the focused test or endpoint first. Do not claim completion from syntax inspection alone.

## Completion Criteria

A coding task is complete only when:

- The requested behavior is implemented.
- No unrelated files were changed.
- Relevant tests pass, or the exact blocker is reported.
- The running endpoint is verified when applicable.
- Database impact is explicitly stated.

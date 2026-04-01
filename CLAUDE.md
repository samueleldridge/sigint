# sigint — Agentic Alternative Data Signal Explorer

## What This Is
Multi-agent system (LangGraph) that lets users ask natural language questions
across heterogeneous financial datasets. An entity resolution layer maps messy
real-world names to canonical entities before any query executes.

## Tech Stack
- Python 3.13, managed with pyproject.toml (NOT setup.py)
- LangGraph for agent orchestration
- FastAPI for the API layer
- PostgreSQL + pgvector for storage + vector search
- Pydantic v2 for ALL models (request/response/intermediate/config)
- asyncio + httpx for async data ingestion
- rapidfuzz for fuzzy matching
- sentence-transformers for semantic matching
- pytest for testing, ruff for linting, mypy for type checking

## Code Standards
- IMPORTANT: Every function has type hints. No exceptions.
- IMPORTANT: Every public function has a docstring.
- Use Pydantic BaseModel for all data structures, never raw dicts.
- Use async def for all I/O-bound operations.
- Imports: stdlib → third-party → local, separated by blank lines.
- Use `from __future__ import annotations` in every file.
- Error handling: never bare `except:`. Always catch specific exceptions.
- Logging: use structlog, not print statements.

## Project Structure
See @docs/architecture.md for the full system design.
Source code lives in src/sigint/. Tests mirror the src structure in tests/.

## How To Verify Changes
```
make lint      # ruff check + mypy
make test      # pytest -x --tb=short
make eval      # run evaluation harness (only after eval/ exists)
```

## Git Workflow
- IMPORTANT: Never commit directly to main.
- Create a feature branch named feat/<short-description> for each task.
- Write meaningful commit messages: "Add fuzzy matching strategy" not "update files"
- Each PR should be focused on ONE concern.

## What NOT To Do
- Do NOT use LangChain. We use LangGraph directly.
- Do NOT use SQLAlchemy ORM queries — use raw SQL via asyncpg for the text-to-SQL layer.
- Do NOT create a frontend unless explicitly asked. API-first.
- Do NOT install packages without adding them to pyproject.toml dependencies.
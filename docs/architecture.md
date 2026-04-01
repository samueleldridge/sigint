# sigint Architecture

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                   Chat Interface                     │
│              (FastAPI + simple React UI)              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│               Orchestrator Agent (LangGraph)          │
│                                                       │
│  1. Intent classification                             │
│  2. Query decomposition (multi-source if needed)      │
│  3. Sub-agent routing                                 │
│  4. Result synthesis + citation                       │
└───┬──────────┬──────────┬──────────┬────────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────────────┐
│ Trade  │ │ Jobs   │ │ SEC    │ │ Macro /        │
│ Flow   │ │ Signal │ │ Filing │ │ Commodities    │
│ Agent  │ │ Agent  │ │ Agent  │ │ Agent          │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────┐
│            Entity Resolution Layer                    │
│                                                       │
│  Canonical entity graph (companies, tickers,          │
│  subsidiaries, aliases, LEIs)                         │
│                                                       │
│  - Fuzzy matching (rapidfuzz / Levenshtein)           │
│  - Embedding similarity (pgvector)                    │
│  - Rule-based overrides (known aliases)               │
│  - Cascading strategy: exact → fuzzy → semantic       │
│                                                       │
│  This is the secret sauce. It sits between every      │
│  sub-agent and its data source.                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              Data Layer (PostgreSQL + pgvector)        │
│                                                       │
│  Tables:                                              │
│  - entity_canonical  (master entity registry)         │
│  - entity_aliases    (all known name variants)        │
│  - trade_flows       (UN Comtrade / public trade)     │
│  - job_postings      (public job trend datasets)      │
│  - sec_filings       (EDGAR full-text + metadata)     │
│  - macro_indicators  (FRED API data)                  │
│  - embeddings        (pgvector for semantic search)   │
└─────────────────────────────────────────────────────┘
```

## Orchestrator

The orchestrator is a LangGraph StateGraph that manages the full query lifecycle.

### Routing Logic
The orchestrator uses an LLM classification step to determine which agents
a query needs. The classifier receives the user question plus a short
description of each registered agent's capabilities and returns one or more
agent names. This is NOT keyword matching — it's an LLM call so it handles
ambiguous or implicit routing (e.g. "how are markets reacting to the latest
jobs report?" routes to both Macro and Jobs agents).

### Multi-Source Queries
When the classifier selects multiple agents, the orchestrator:
1. Decomposes the question into per-agent sub-queries (LLM call)
2. Dispatches sub-queries to agents in parallel (asyncio.gather)
3. Passes all agent responses to a synthesis step that produces a
   unified answer with per-source citations

### Agent Registry
Agents self-register via a registry dict mapping agent name → class.
Adding a new agent means implementing BaseAgent and adding one line
to the registry. The orchestrator never imports agents directly.

## Agent Interface

Every sub-agent inherits from BaseAgent and implements:
- `plan(query: str) -> QueryPlan` — decompose the question
- `resolve_entities(plan: QueryPlan) -> QueryPlan` — call the shared entity resolution service
- `generate_sql(plan: QueryPlan) -> str` — text-to-SQL with schema context + few-shot examples
- `execute(sql: str) -> QueryResult` — run query, validate output with Pydantic
- `format(result: QueryResult) -> AgentResponse` — structure output with source citations

## Sub-Agents

### MacroAgent (FRED)
Queries US macroeconomic time-series data. Source: FRED API (free).
SQL-only — all data lives in the macro_indicators table.
Handles: GDP, inflation, rates, employment, commodity prices.
Example queries: "What was the fed funds rate trend in 2024?",
"Correlation between CPI and 10Y yield over 5 years?"
Entity resolution maps informal names → FRED series IDs
("fed rate" → FEDFUNDS, "unemployment" → UNRATE).

### SecFilingsAgent (SEC EDGAR)
Queries public company filings. Source: SEC EDGAR (free).
Hybrid: SQL for structured metadata, RAG (pgvector) for filing text.
Handles: filing lookups, risk factor analysis, cross-company comparison.
Example queries: "Which semiconductor companies mentioned tariff risk
in their latest 10-K?", "How many 10-Qs did Tesla file in 2024?"
Entity resolution maps company names → CIK numbers.

### TradeFlowAgent (UN Comtrade)
Queries international trade volumes. Source: UN Comtrade API (free).
SQL-only against the trade_flows table.
Handles: import/export volumes by country, commodity, partner.
Example: "Have Chinese semiconductor imports from Taiwan declined YoY?"
Entity resolution maps country names + commodity descriptions.

### JobsSignalAgent
Queries job posting trends as leading indicators.
Source: public dataset or realistic synthetic data.
SQL-only against the job_postings table.
Handles: hiring velocity by company, role type, location.
Example: "Is Citadel scaling quant hiring faster than Two Sigma?"
Entity resolution maps informal company/role names.

## Entity Resolution

### Architectural Position
Entity resolution is a **shared service**, not embedded in each agent.
It lives in `src/sigint/entity_resolution/` and agents call it via
`resolver.resolve(name, entity_type_hint)`. This means:
- Resolution logic is tested and improved in one place
- All agents benefit from alias/embedding improvements immediately
- The resolver is independently benchmarkable (ties into finmatch)

### Cascade Strategy
1. **Exact normalised match** — lowercase, strip legal suffixes → lookup against canonical + aliases table
2. **Rule-based match** — ticker lookup, known abbreviation map, FRED series ID map
3. **Fuzzy match** — rapidfuzz token_sort_ratio against all aliases, threshold 85
4. **Semantic match** — embed query with sentence-transformers, pgvector cosine similarity, threshold 0.82
5. **No match** — return None with explanation. Never guess.

The cascade short-circuits: the first strategy that produces a confident
match wins. This keeps latency low for easy cases (most queries hit
exact or rules) while handling messy inputs gracefully.

# ArbiCast

**Cross-Market Prediction-Market Research Platform**<br>
**跨平台预测市场套利与动态价格发现研究平台**

[中文说明](README.zh-CN.md)

ArbiCast is a local research platform for studying executable cross-market and dynamic sports prediction-market opportunities, currently focused on Chinese Super League (CSL) markets across Kalshi and Polymarket. It combines live public market data, strict contract matching, real order-book depth, VWAP, latency-aware simulated execution, and persistent research analytics.

> ArbiCast tests whether apparent opportunities survive contract-equivalence checks, liquidity, fees, spread, slippage, and execution latency. It does not claim guaranteed arbitrage.

**ArbiCast is read-only research software with paper/simulated execution. It does not place real-money orders.**

## Current Focus: CSL Dynamic Arbitrage Research

```text
Chinese Super League
        ↓
Kalshi + Polymarket
        ↓
Fixture and Outcome Matching
        ↓
Price Tick Recording
        ↓
Lead / Lag and Dynamic Signals
        ↓
Execution-Delay Simulation
        ↓
Markout and Research Performance
```

The current research question is:

> During live CSL matches, do Kalshi and Polymarket exhibit cross-market price discrepancies or lead/lag relationships that persist long enough, with enough liquidity, to remain executable after realistic latency, fees, spread, and slippage?

Static arbitrage, the general matcher, paper trading, settlement, replay, Research Test, and developer diagnostics remain available. Phase 5 adds a focused CSL research path; it does not replace the earlier platform.

## How It Works

```text
Kalshi public APIs ───────┐
                         ├─> Platform Connectors ─> Normalized Markets / Books
Polymarket public APIs ───┘                              │
                                                        ▼
                                               Strict Market Matcher
                                                        │
                                  ┌─────────────────────┴────────────────────┐
                                  ▼                                          ▼
                         Static Arbitrage                         CSL Research Pairs
                                  │                                          │
                         Paper Execution                  MatchSession / PriceTick
                                                                             │
                                                               Lead/Lag / DynamicSignal
                                                                             │
                                                           ExecutionScenario / Markout
                                                                             │
                                                                  Research Performance
```

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, Recharts
- **Backend:** FastAPI, Python, asyncio, httpx
- **Database:** PostgreSQL, SQLAlchemy 2.x, Alembic
- **Runtime:** Docker Compose

The frontend only communicates with the ArbiCast backend. Kalshi and Polymarket JSON is normalized inside platform-specific connectors before entering matching, arbitrage, or paper-execution services.

## Current Live Research Status

The following is a live validation snapshot from **2026-08-21**, not a permanent market statistic:

```text
Kalshi compatible CSL markets:     33
Polymarket compatible CSL markets: 57

Canonical fixture matches:         10
Matched outcome pairs:             30
Research pairs:                    30

Fully-compatible outcome pairs:     0
Recording sessions:                 0
```

`Recording sessions = 0` is expected before the configured recording window:

```text
Research Pair → PRE_MATCH → Recording Window → Recording Session
```

By default, recording starts 30 minutes before the scheduled research time. A Research Pair can therefore exist before high-frequency recording begins.

## Phase History

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Mock dashboard | Complete |
| 2 | Live Kalshi and Polymarket data, normalized books, health, persistence | Complete |
| 2.5 | Simplified bilingual UI | Complete |
| 3 | General matcher, resolution checks, static arbitrage, lifecycle and replay | Core complete |
| 4 | Paper account, simulated execution, positions, settlement, performance | Core complete |
| 4.5 | Isolated Research Test Console and end-to-end validation | Complete |
| 5 | CSL MatchSession, ticks, dynamic signals, latency scenarios and markout | Core complete |
| 5.1 | CSL acquisition, diagnostics, recording lifecycle and observability | Complete |
| 5.2 | Direct Kalshi CSL series verification | Complete |
| 5.3 | Live fixture-pairing audit and parser corrections | Complete |

### Phase 5.1 — Data Acquisition and Observability

- CSL discovery is independent of the general `MAX_MARKETS=500` cache.
- Bounded football/event pagination and local CSL detection prevent unlimited scans.
- `GET /api/csl/discovery` exposes each discovery stage and rejection diagnostics.
- Research Pairs and Approved Trading Pairs are separate concepts.
- A core-compatible Research Pair may record live ticks without human approval.
- Paper execution retains stricter approval and resolution requirements.
- Synthetic/test records remain isolated with `is_test=true` and are excluded from production research.
- Price ticks preserve `exchange_timestamp`, `received_timestamp`, `processed_at`, and `source_type` without inventing unavailable exchange timestamps.
- MatchSession recording has pre-start and maximum-duration boundaries.
- Collector source, interval, and lag-quality warnings are visible in Debug and Research.

Relevant configuration:

```env
CSL_DISCOVERY_MAX_PAGES=20
CSL_DISCOVERY_MAX_MARKETS=5000
CSL_DISCOVERY_REFRESH_SECONDS=300
CSL_RECORDING_PRESTART_MINUTES=30
CSL_RECORDING_MAX_HOURS=4
```

### Phase 5.2 — Kalshi CSL Discovery Verification

The earlier `Kalshi CSL = 0` result did **not** mean Kalshi lacked CSL markets. The bounded global scan reached its limit before the series appeared, and normalization did not retain `series_ticker`.

ArbiCast now directly probes `KXCHNSLGAME` and applies the deterministic league rule:

```text
series_ticker == KXCHNSLGAME → league = CSL
```

Live API verification confirmed:

```text
Series exists: YES
Title: Chinese Super League Game
Category: Sports
Tags: Soccer
```

### Phase 5.3 — Fixture Pairing Verification

A live audit confirmed all eight specified 2026-08-22/23 fixtures were present on both platforms. Three confirmed parser defects were corrected without changing matcher thresholds:

1. Negated resolution phrases such as `does not include extra time or penalties` are no longer interpreted as including those phases.
2. `Aug 22`, `August 22`, `Aug. 22`, and ISO dates normalize to a comparable `YYYY-MM-DD` date when an explicit year is available.
3. Polymarket HOME/AWAY orientation now comes from the event-level fixture; the individual market question determines only the outcome.

Regression audit:

```text
Fixtures present on both platforms: 8 / 8
HOME orientation:                    8 / 8
DRAW orientation:                    8 / 8
AWAY orientation:                    8 / 8
Core-compatible outcome pairs:      24 / 24
```

Reproduce the read-only live audit:

```bash
docker compose run --rm -e PYTHONPATH=/app \
  backend python scripts/audit_csl_fixtures.py --summary
```

## Resolution Compatibility

ArbiCast uses three explicit levels:

- **CORE_COMPATIBLE** — same fixture, date, outcome, and regulation scope: 90 minutes plus stoppage time, with extra time and penalties excluded.
- **FULLY_COMPATIBLE** — core compatibility plus confirmed-equivalent cancellation, abandonment, postponement, rescheduling, void/refund, and other edge-case rules.
- **INCOMPATIBLE** — a core fixture, outcome, date, or resolution difference exists.

Current matched CSL outcomes are:

```text
CORE_COMPATIBLE
resolution_risk = CANCELLATION_RULE_UNVERIFIED
```

They may create Research Pairs, record PriceTicks, and support lead/lag and DynamicSignal research. They are **not** described as guaranteed arbitrage, and current Paper eligibility remains disabled until the stricter requirements are met.

## Dynamic Research

Existing Phase 5 capabilities include:

- `MatchSession`, `MarketPriceTick`, `DynamicSignal`, and `DynamicExecutionScenario` persistence;
- HOME/DRAW/AWAY price recording with change detection and bounded snapshots;
- signal TTL and follower-lag observation;
- execution-delay scenarios and 250 ms through 5 s markouts;
- opportunity lifetime and collector-quality metadata;
- strict separation of `STATIC_ARB`, `DYNAMIC_LEAD_LAG`, and `is_test=true` data.

Price timestamp policy:

```text
exchange_timestamp  # null when the platform does not provide one
received_timestamp
processed_at
source_type
```

Scores, match minutes, or exchange timestamps are never fabricated. No external football event feed is connected yet.

## Collector and Latency Limitations

Current collector mode:

```text
Kalshi:     REST polling
Polymarket: REST polling
Configured interval: 1000 ms
lag_quality: LOW
```

Observed lead/lag may include collector latency. The current system does not claim reliable millisecond-level venue leadership. WebSocket or higher-quality exchange timestamps are a future data-quality improvement, not part of this checkpoint.

## User Interface

- **Overview** — current CSL research status and concise paper summary.
- **Live Match** (`/live-match`) — fixture, recording status, H/D/A prices, ticks, current signal, observed lag, and quality. Some advanced metrics remain in progress until live observations exist.
- **Research** (`/research`) — data coverage, latency survival, markout, and performance; empty datasets show insufficient live data rather than mock charts.
- **Debug** (`/debug`) — CSL discovery pipeline, series probe, normalized fixtures, resolution levels, connectors, books, requests, and Research Test access.
- **Markets, Matches, Opportunities, Paper, Performance, Research Test, Settings** — earlier research and diagnostic capabilities remain available.

The Research Test Console uses real cached markets and production services while isolating generated records with `is_test=true`.

## API

FastAPI documentation is available at <http://localhost:8000/docs>. Primary CSL endpoints include:

```text
GET /api/csl/overview
GET /api/csl/discovery
GET /api/csl/discovery/kalshi-series
GET /api/csl/matches
GET /api/csl/matches/live
GET /api/csl/matches/{id}/prices
GET /api/csl/matches/{id}/signals
GET /api/csl/research/summary
GET /api/csl/research/latency
GET /api/csl/research/performance
```

General market, order-book, matching, opportunity, paper, analytics, connector, and Research Test APIs remain available.

## Quick Start

### Requirements

- Docker Desktop
- Git

```bash
git clone https://github.com/LutaoZheng/ArbiCast.git
cd ArbiCast
cp .env.example .env
```

### Mock Mode

```bash
DATA_MODE=mock docker compose up --build
```

Mock mode is for deterministic UI/development work and remains isolated from live research.

### Live Mode

```bash
DATA_MODE=live docker compose up --build
```

Background mode:

```bash
DATA_MODE=live docker compose up -d --build
```

Open:

- <http://localhost:3000>
- <http://localhost:3000/live-match>
- <http://localhost:3000/research>
- <http://localhost:3000/debug>
- <http://localhost:8000/docs>

Running plain `docker compose up --build` may use the environment/default data mode. For live research, verify that the UI displays **LIVE MODE**.

Stop without deleting PostgreSQL data:

```bash
docker compose down
```

Do not use `docker compose down -v` unless permanent removal of the local database is intentional.

## Testing

Backend:

```bash
docker compose run --rm backend pytest -q
```

CSL fixture audit:

```bash
docker compose run --rm -e PYTHONPATH=/app \
  backend python scripts/audit_csl_fixtures.py --summary
```

Frontend:

```bash
cd frontend
npm install
npm run typecheck
npm run build
```

Compose:

```bash
docker compose config --quiet
```

The Docker frontend production build is the canonical build verification path. A macOS ARM checkout with an incomplete local optional dependency installation may report a missing Next.js SWC binary even when the Docker production build succeeds.

Phase 5.3 checkpoint validation: **43 backend tests passed**, the live eight-fixture audit returned **24/24 core-compatible outcomes**, frontend Docker production build passed, and Compose configuration validated.

## Project Structure

```text
backend/
  app/
    connectors/       # read-only platform adapters
    matching/         # general and resolution matching
    csl/              # deterministic CSL matching and dynamic research
    arbitrage/        # VWAP, fees, lifecycle, replay
    paper_trading/    # simulated execution
    services/         # scheduler, cache, persistence, research services
    models/           # SQLAlchemy models
  alembic/            # PostgreSQL migrations
  scripts/            # live smoke tests and fixture audit
  tests/
frontend/             # Next.js application
docker-compose.yml
.env.example
README.md
README.zh-CN.md
```

## Current Limitations

- Live market coverage remains bounded by explicit discovery limits.
- Resolution edge cases are not yet fully verified across platforms.
- Current CSL pairs are core-compatible, not guaranteed-arbitrage compatible.
- REST polling limits lead/lag timestamp quality.
- Recording and performance datasets remain sparse until real CSL matches enter the recording window.
- Paper execution is a simulation and cannot guarantee real fills.
- Live Match and Research advanced metrics remain in progress where real observations are insufficient.
- No live trading, account login, wallet, private-key, deposit, or withdrawal support exists.
- ArbiCast is research software, not financial advice.

## Next Experiment

The next step is not another strategy. It is to record real CSL matches and test whether observed cross-market opportunities survive realistic execution latency.

The forward test will measure PriceTicks, dynamic signals, lead/lag, opportunity lifetime, order-book depth, VWAP, fees, slippage, execution delay, markout, and paper PnL at:

```text
0 ms · 100 ms · 250 ms · 500 ms · 1 s · 2 s · 3 s · 5 s
```

Key questions:

- How many observations survive 500 ms, 1 second, and 2 seconds?
- How much executable depth exists after latency?
- How much theoretical edge is lost to spread, fees, slippage, and delay?
- What is delay-adjusted paper PnL?

## Safety and Research Scope

ArbiCast currently supports:

- public read-only market data;
- local analysis and research persistence;
- paper/simulated execution only.

It does **not** implement real-money order placement or cancellation, account login, wallet signing, private-key storage, deposits, withdrawals, or geographic-restriction bypass. No result is a guarantee of profit or financial advice.

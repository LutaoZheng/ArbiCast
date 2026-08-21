# ArbiCast

Cross-Market Prediction Market Arbitrage Research Platform<br>
跨平台预测市场套利研究平台

ArbiCast is a local research platform for comparing Kalshi and Polymarket prediction markets. It identifies potentially equivalent contracts, validates resolution compatibility, measures real order-book depth, VWAP, fees, slippage, and execution latency, then studies execution through persistent paper trading.

ArbiCast 是一个本地运行的 Kalshi × Polymarket 研究平台。它用于寻找可能等价的预测市场合约，核验结算规则，并基于真实盘口深度、VWAP、手续费、滑点和执行延迟研究跨平台套利是否具备现实可执行性。

> A research platform designed to test whether apparent arbitrage survives real execution constraints.<br>
> 它的目标不是证明“套利一定赚钱”，而是验证表面套利在真实执行约束下是否仍然成立。

**ArbiCast currently performs read-only market research and paper trading only. It does not place real-money orders.**

## Current Status / 当前状态

| Phase | Scope / 范围 | Status / 状态 |
| --- | --- | --- |
| Phase 1 | Mock Dashboard / 模拟数据仪表盘 | ✅ Complete |
| Phase 2 | Live Kalshi + Polymarket market data / 真实市场数据 | ✅ Complete |
| Phase 2.5 | Simplified bilingual UI / 简洁中英双语界面 | ✅ Complete |
| Phase 3 | Market Matcher + Arbitrage Engine / 市场匹配与套利引擎 | ✅ Core implementation |
| Phase 4 | Paper Account + Execution Simulator + Settlement / 模拟账户、执行与结算 | ✅ Core implementation |
| Phase 4.5 | Research Test Console + End-to-End Validation / 研究测试台与端到端验证 | ✅ Complete |

At the latest validation, the configured 500 × 500 live-market cache produced **0 real high-confidence matched pairs**. This is an honest research result, not a system failure: strict matching intentionally avoids presenting low-quality or non-equivalent contracts as arbitrage.

最近一次验证中，配置的 500 × 500 真实市场缓存产生了 **0 个真实高置信匹配对**。这不是被隐藏的失败，而是研究结果：系统宁愿漏掉候选，也不会把低质量或结算规则不等价的合约包装成套利。

## What ArbiCast Is Trying to Answer / ArbiCast 想回答什么？

Do apparent Kalshi × Polymarket arbitrage opportunities remain profitable after accounting for:

- contract equivalence and resolution-rule checks;
- order-book depth and VWAP;
- fees, slippage, and safety buffers;
- execution latency and partial or single-leg fills;
- capital holding time and actual settlement?

ArbiCast 想回答：在扣除以下现实约束后，Kalshi × Polymarket 的表面套利是否仍能盈利？

- 合约是否真正等价、结算规则是否一致；
- 盘口深度与真实 VWAP；
- 手续费、滑点和安全缓冲；
- 执行延迟、部分成交与单腿风险；
- 资金占用时间与最终真实结算。

## Features / 核心功能

### Live Market Data / 实时市场数据

- Kalshi and Polymarket public market ingestion / 两个平台公开市场数据接入
- Cursor/keyset pagination and configurable market limits / 分页与可配置市场上限
- Normalized YES/NO order books and watched markets / 统一 YES/NO 盘口与关注市场
- Automatic metadata and order-book refresh / 自动刷新
- Independent connector health, retry, backoff, and rate-limit tracking / 独立健康状态、重试、退避与限流记录
- PostgreSQL market and order-book snapshots / PostgreSQL 行情快照

### Market Matching / 市场匹配

- Title normalization and token similarity / 标题标准化与相似度
- Entity, date, category, and numeric-threshold matching / 实体、日期、类别与数字阈值匹配
- Event-scope and resolution-compatibility checks / 事件范围与结算兼容性检查
- Manual Approve, Reject, and Needs Review workflow / 人工审核流程

### Arbitrage Engine / 套利引擎

- Both directions: Kalshi YES + Polymarket NO, and Kalshi NO + Polymarket YES
- Multi-level order-book depth and VWAP / 多档盘口与 VWAP
- Configurable fee models, slippage, and safety buffer / 可配置手续费、滑点与安全缓冲
- Multiple trade-size calculations / 多仓位规模计算
- Opportunity lifecycle, edge history, and replay / 机会生命周期、Edge 历史与重放

### Paper Trading / 模拟交易

- Persistent paper account / 持久化模拟账户
- Execution latency and refreshed-book simulation / 延迟后重新读取盘口模拟
- Full fill, partial fill, single-leg, and failed states / 完全成交、部分成交、单腿与失败状态
- Paper orders, trades, positions, settlement, and realized PnL / 模拟订单、交易、仓位、结算与已实现盈亏

### Research Test Console / 研究测试台

- Manually select live Kalshi and Polymarket markets / 手动选择真实市场
- Explain matcher scores and rejection stages / 解释评分与筛选失败阶段
- Find top-N nearest cross-platform markets / 查找最接近候选
- Create isolated `TEST_APPROVED` pairs / 创建隔离测试 Pair
- Inspect real order books and run sanity checks / 检查真实盘口
- Calculate both arbitrage directions at multiple sizes / 计算两个方向与不同仓位
- Trigger the production paper-execution path with test parameters / 使用正式服务链路触发模拟执行
- Keep all test records isolated with `is_test=true` / 测试数据不进入正式 Performance

## Architecture / 架构

```text
Kalshi API ───────┐
                  ├──> Connectors ──> Normalized Markets
Polymarket API ───┘                         │
                                           ▼
                                    Market Matcher
                                           │
                                    Approved Pairs
                                           │
                                           ▼
                                    Arbitrage Engine
                                           │
                                     Opportunities
                                           │
                                           ▼
                                    Paper Execution
                                           │
                                        Positions
                                           │
                                           ▼
                                       Settlement
                                           │
                                           ▼
                                      Performance
```

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, Recharts
- **Backend:** FastAPI, Python, asyncio, httpx
- **Database:** PostgreSQL, SQLAlchemy 2.x, Alembic
- **Runtime:** Docker Compose

The frontend only talks to the ArbiCast backend. External platform JSON is normalized inside platform-specific connectors before reaching matching, arbitrage, or paper-trading logic.

前端只访问 ArbiCast Backend；平台原始 JSON 在 Connector 内完成归一化，业务层不直接依赖 Kalshi 或 Polymarket 的原始结构。

## User Interface / 页面

- **Overview / 概览** — system and research summary / 系统与研究摘要
- **Markets / 市场** — live markets, watch controls, and books / 市场、关注与盘口
- **Matches / 匹配** — candidate review and resolution comparison / 候选审核
- **Opportunities / 套利机会** — live and historical opportunities / 实时与历史机会
- **Paper Trading / 模拟交易** — account, positions, and simulated trades / 账户、仓位与交易
- **Performance / 表现** — execution and realized performance / 执行与已实现表现
- **Research Test / 研究测试** — end-to-end production-path validation / 端到端链路验证
- **Developer Debug / 开发调试** — connectors, raw books, and request health / Connector 与原始盘口调试
- **Settings / 设置** — research assumptions and intervals / 研究参数

Normal research work focuses on Overview, Matches, Opportunities, Paper Trading, and Performance. Markets and Developer Debug are primarily diagnostic surfaces.

日常研究主要关注概览、匹配、套利机会、模拟交易和表现；Markets 与 Developer Debug 更多用于数据核验和故障排查。

## Setup / 启动

### Requirements / 环境要求

- Docker Desktop
- Git

Docker Compose is the recommended and reproducible runtime. No platform trading credentials are required because ArbiCast only reads public market data.

推荐使用 Docker Compose。项目只读取公开行情，不需要平台交易凭据。

### Environment / 环境变量

```bash
cp .env.example .env
```

Important settings / 主要配置：

```env
DATA_MODE=live
KALSHI_MAX_MARKETS=500
POLYMARKET_MAX_MARKETS=500

MARKET_REFRESH_SECONDS=60
ORDERBOOK_REFRESH_SECONDS=3

MIN_NET_EDGE=0.005
ARBITRAGE_SAFETY_BUFFER=0.0025

PAPER_STARTING_BALANCE=10000
PAPER_TRADE_SIZE=25
PAPER_EXECUTION_LATENCY_MS=250
```

`.env.example` contains development defaults only. The Compose PostgreSQL username/password are local container defaults and must not be reused for an exposed or production database.

`.env.example` 只包含开发默认值。Compose 中的 PostgreSQL 用户名和密码仅用于本地容器，不能复用于公网或生产数据库。

### Mock Mode / 模拟数据模式

```bash
DATA_MODE=mock docker compose up --build
```

Mock Mode provides deterministic data for UI development and demonstrations. It must not be mixed with live research results.

Mock Mode 用于 UI 开发和演示，不应与真实研究结果混合。

### Live Mode / 真实数据模式

```bash
DATA_MODE=live docker compose up --build
```

Run in the background / 后台运行：

```bash
DATA_MODE=live docker compose up -d
```

Open / 访问：

- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>
- FastAPI Docs: <http://localhost:8000/docs>
- Research Test: <http://localhost:3000/research-test>

Live Mode reads public market data and simulates execution. It never places orders or accesses real accounts.

Live Mode 读取公开市场数据并模拟执行，不会下单或访问真实账户。

### Stop / 停止

```bash
docker compose down
```

Avoid `docker compose down -v` unless you intentionally want to delete the PostgreSQL volume and all persisted local research data.

除非确定要删除全部本地研究数据，否则不要使用 `docker compose down -v`。

### Logs / 日志

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## Tests and Validation / 测试与验证

Backend tests in Docker / Docker 中运行后端测试：

```bash
docker compose run --rm backend pytest -q
```

Frontend type check and production build / 前端类型检查与生产构建：

```bash
cd frontend
npm install
npm run typecheck
npm run build
```

Compose configuration validation / Compose 配置验证：

```bash
docker compose config --quiet
```

Optional read-only live connector smoke test / 可选真实只读 Connector 测试：

```bash
docker compose run --rm backend python scripts/test_live_connectors.py
```

Latest checkpoint validation: **26 backend tests passed**. Update this count if the test suite changes.

最近 checkpoint 验证结果：**26 个后端测试通过**。测试数量变化后应同步更新。

## Research Workflow / 研究流程

1. Run ArbiCast in Live Mode. / 使用 Live Mode 启动。
2. Collect real Kalshi and Polymarket markets. / 获取两个平台真实市场。
3. Review candidate matches and resolution rules. / 审核候选匹配与结算规则。
4. Approve only genuinely equivalent contracts. / 只批准真正等价的合约。
5. Observe depth-aware executable opportunities. / 观察基于盘口深度的可执行机会。
6. Let Paper Trading simulate delayed two-leg execution. / 模拟延迟后的双腿执行。
7. Wait for real market resolution. / 等待真实市场结算。
8. Review realized PnL and execution performance. / 复盘已实现盈亏和执行表现。

## Research Test Console / 研究测试台

Open <http://localhost:3000/research-test> in Live Mode to inspect the full production research path without using the terminal.

在 Live Mode 中打开 <http://localhost:3000/research-test>，可不依赖终端检查完整正式研究链路：

- search and manually pair live markets / 搜索并手动配对真实市场；
- see why Matcher passes, reviews, or rejects a pair / 查看 Matcher 的具体判断依据；
- check top-10 retrieval recall / 检查 Top-10 召回；
- inspect normalized live order books / 检查标准化真实盘口；
- calculate positive or negative Edge without hiding results / 显示正负 Edge；
- trigger simulated execution with isolated test thresholds / 使用隔离测试阈值触发模拟执行。

Research Test records use `is_test=true`, a separate test paper account, and `approval_source=test`. Normal Performance queries exclude them, and the console can delete only test records.

研究测试记录使用 `is_test=true`、独立测试账户和 `approval_source=test`；正式 Performance 默认排除测试记录，清理按钮也只删除测试数据。

## Important Metrics / 重要指标

- **Net Edge / 净优势** — gross payout margin after fees, slippage, and safety buffer / 扣除手续费、滑点与安全缓冲后的空间。
- **VWAP / 成交量加权均价** — expected average price after consuming multiple book levels / 吃入多档盘口后的平均成交价。
- **Dual Fill Rate / 双腿成交率** — share of attempted paper trades that complete both legs / 两条腿均完成目标成交的比例。
- **Expected Edge / 预期优势** — Edge observed when an opportunity is detected / 发现机会时的理论 Edge。
- **Realized Entry Edge / 实现入场优势** — Edge calculated from simulated post-latency fills / 延迟后模拟成交价对应的 Edge。
- **Edge Capture Ratio / Edge 捕获率** — realized entry Edge divided by expected Edge / 实现 Edge 与预期 Edge 的比率。
- **Holding Time / 资金占用时间** — time between opening and settlement / 开仓至结算的时间。
- **Paper PnL / 模拟盈亏** — payout minus simulated cost and fees after settlement / 结算收益减模拟成本与费用。
- **ROI / 收益率** — paper-account return relative to starting balance / 相对模拟初始资金的收益率。

## Project Structure / 项目结构

```text
backend/
  app/
    connectors/      # Kalshi and Polymarket read-only adapters
    matching/        # candidate and resolution compatibility logic
    arbitrage/       # VWAP, fees, opportunities, and replay
    paper_trading/   # simulated execution
    services/        # runtime, cache, persistence, research test
    models/          # SQLAlchemy records
  alembic/           # database migrations
  tests/             # unit tests and API fixtures
frontend/            # Next.js dashboard
docker-compose.yml
.env.example
README.md
```

## Safety / 安全边界

The current version provides:

- read-only public market data;
- analysis and paper trading only;
- no real-money order execution or cancellation;
- no deposits or withdrawals;
- no wallet signing, private-key, or real-account login logic;
- no geographic-restriction bypass.

当前版本只读取公开市场数据并进行研究与模拟交易，不包含真钱下单、撤单、充值、提现、钱包签名、私钥、真实账户登录或地域限制绕过能力。

## Known Limitations / 已知限制

- The live market universe is limited by configured market counts. / 真实市场范围受配置上限影响。
- Cross-platform market overlap may be sparse. / 两个平台同时存在的等价市场可能很少。
- The Matcher may have false negatives. / Matcher 可能漏掉真实对应市场。
- Not every resolution-rule difference can be verified automatically. / 结算规则差异无法全部自动判断。
- Paper execution is a simulation and cannot guarantee real fills. / 模拟成交不等于真实成交。
- Public polling and snapshot granularity limit latency analysis. / Polling 与快照粒度限制延迟分析精度。
- Live trading is not supported. / 不支持真实交易。
- ArbiCast is research software, not financial advice. / 本项目是研究软件，不构成财务建议。

## Roadmap / 下一阶段

### Phase 5 — Long-running Forward Test / 长期前向测试

- improve market-universe coverage / 提升市场覆盖；
- validate Matcher recall / 验证 Matcher 召回率；
- collect live opportunities and edge decay / 收集真实机会与 Edge 衰减；
- measure dual-fill and execution success / 测量双腿成交率；
- collect settled paper PnL / 收集结算后的模拟盈亏；
- measure capital efficiency / 测量资金效率。

Real-money execution may only be considered after sufficient forward-test evidence and a separate safety review. It is **not currently implemented**.

只有积累足够长期验证数据并进行独立安全评审后，才可能讨论真实执行；当前**没有实现**。

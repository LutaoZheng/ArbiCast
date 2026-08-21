# ArbiCast

**跨平台预测市场套利与动态价格发现研究平台**

[English README](README.md)

ArbiCast 是一个本地运行的预测市场研究平台，目前重点研究 Kalshi 与 Polymarket 上的中超（Chinese Super League，CSL）市场。系统结合真实公开行情、严格合约匹配、真实盘口深度、VWAP、延迟敏感的模拟执行与持久化研究分析，用于判断表面机会在现实执行约束下是否仍然成立。

> ArbiCast 不宣传“稳赚套利”。它研究的是：经过合约等价性、流动性、手续费、价差、滑点和执行延迟后，机会是否仍然可执行。

**当前项目只读取公开市场数据并进行 Paper/模拟执行，不会提交真钱订单。**

## 当前研究重点：CSL Dynamic Arbitrage

```text
Chinese Super League
        ↓
Kalshi + Polymarket
        ↓
Fixture / Outcome Matching
        ↓
Price Tick Recording
        ↓
Lead / Lag + Dynamic Signal
        ↓
Execution Delay Simulation
        ↓
Markout + Research Performance
```

核心研究问题：

> 中超比赛进行期间，Kalshi 与 Polymarket 是否存在持续时间足够长、流动性足够大，并且在扣除真实延迟、手续费、spread 和 slippage 后仍可执行的跨平台价差或 lead/lag？

Phase 1–4.5 已有的通用 Matcher、Static Arbitrage、VWAP、Paper Trading、Settlement、Replay、Research Test 与 Debug 工具全部保留。

## 当前 Live Research 状态

以下数字是 **2026-08-21** 的真实验证快照，不代表永久市场状态：

```text
Kalshi compatible CSL markets:     33
Polymarket compatible CSL markets: 57

Canonical fixture matches:         10
Matched outcome pairs:             30
Research pairs:                    30

Fully-compatible outcome pairs:     0
Recording sessions:                 0
```

`Recording sessions = 0` 目前不是错误。Research Pair 可以先进入 PRE_MATCH，默认在计划时间前 30 分钟进入 recording window：

```text
Research Pair → PRE_MATCH → Recording Window → Recording Session
```

## Phase 5.1 — CSL 数据获取与可观测性

- CSL discovery 已与普通 `MAX_MARKETS=500` cache 解耦。
- 使用有界 football/event pagination，禁止无限扫描。
- `/api/csl/discovery` 展示 discovery 各阶段数量和拒绝原因。
- Research Pair 与 Approved Trading Pair 已解耦。
- 核心规则兼容的 Research Pair 无需人工 Approve 即可记录研究数据。
- Paper execution 继续要求更严格的审批与 resolution 条件。
- synthetic/test 数据使用 `is_test=true`，不进入正式 Research Performance。
- PriceTick 保存 `exchange_timestamp`、`received_timestamp`、`processed_at` 与 `source_type`；平台未提供 exchange timestamp 时保持 `null`。
- MatchSession 具有 pre-start、停止时间和最长 recording 生命周期。
- Debug/Research 展示 collector source、interval 与 lag quality。

```env
CSL_DISCOVERY_MAX_PAGES=20
CSL_DISCOVERY_MAX_MARKETS=5000
CSL_DISCOVERY_REFRESH_SECONDS=300
CSL_RECORDING_PRESTART_MINUTES=30
CSL_RECORDING_MAX_HOURS=4
```

## Phase 5.2 — Kalshi CSL Series 验证

早期的 `Kalshi CSL = 0` 不代表 Kalshi 没有中超市场。真实原因是全平台 bounded scan 达到上限后仍未扫描到对应 series，并且 normalization 没有保留 `series_ticker`。

系统现在直接 probe：

```text
KXCHNSLGAME
```

并使用确定性规则：

```text
series_ticker == KXCHNSLGAME → league = CSL
```

真实 API 已确认：

```text
Series exists: YES
Title: Chinese Super League Game
Category: Sports
Tags: Soccer
```

## Phase 5.3 — Fixture Pairing 验证

Live audit 确认指定的 8 场 2026-08-22/23 比赛同时存在于两个平台，并修复三个已确认 parser defect，没有修改 matcher threshold：

1. `does not include extra time or penalties` 不再被错误解释为“包含点球”。
2. `Aug 22`、`August 22`、`Aug. 22` 与 ISO 日期在存在明确年份时统一为 `YYYY-MM-DD`。
3. Polymarket 的 HOME/AWAY orientation 优先来自 event-level fixture，单个 market question 只负责确定 outcome。

```text
Fixtures present on both platforms: 8 / 8
HOME orientation:                    8 / 8
DRAW orientation:                    8 / 8
AWAY orientation:                    8 / 8
Core-compatible outcome pairs:      24 / 24
```

重跑只读审计：

```bash
docker compose run --rm -e PYTHONPATH=/app \
  backend python scripts/audit_csl_fixtures.py --summary
```

## Resolution Compatibility

系统使用三级 compatibility：

- `CORE_COMPATIBLE`：同一 fixture、日期和 outcome，并且都是 90 分钟加伤停补时，不包含加时赛或点球大战。
- `FULLY_COMPATIBLE`：在核心兼容之外，取消、中止、延期、改期、void/refund 等边缘条款也明确等价。
- `INCOMPATIBLE`：核心 fixture、outcome、日期或结算范围不一致。

当前 CSL Research Pair 为：

```text
CORE_COMPATIBLE
resolution_risk = CANCELLATION_RULE_UNVERIFIED
```

因此允许创建 Research Pair、记录 PriceTick、进行 Lead/Lag 与 DynamicSignal 研究，但不能描述为 guaranteed arbitrage。Paper eligibility 继续保持禁用，直到满足更严格条件。

## Dynamic Research 已有能力

- MatchSession、MarketPriceTick、DynamicSignal、DynamicExecutionScenario；
- HOME/DRAW/AWAY 盘口记录、变化检测与有界快照；
- signal TTL 与 follower lag；
- 多档 execution latency simulation；
- 250ms–5s markout；
- opportunity lifetime 与 collector quality；
- `STATIC_ARB`、`DYNAMIC_LEAD_LAG`、`is_test=true` 严格隔离。

时间戳策略：

```text
exchange_timestamp  # 平台未提供时为 null
received_timestamp
processed_at
source_type
```

系统不会猜测比分、比赛分钟或不存在的 exchange timestamp。目前也没有接入外部足球事件 feed。

## Collector / Latency 限制

```text
Kalshi:     REST polling
Polymarket: REST polling
Configured interval: 1000 ms
lag_quality: LOW
```

当前 observed lead/lag 可能包含 collector latency，不能声称已经测得可靠的毫秒级市场领先关系。本 checkpoint 不实现 WebSocket 升级。

## 架构与保留能力

- Backend：FastAPI、Python、asyncio、httpx
- Frontend：Next.js、React、TypeScript、Tailwind CSS、Recharts
- Database：PostgreSQL、SQLAlchemy 2.x、Alembic
- Runtime：Docker Compose
- Kalshi：Live market/event ingestion、order book、CSL direct series discovery
- Polymarket：Live event/market ingestion、search discovery、CLOB order book、event-level orientation
- Research：General Matcher、Resolution Compatibility、VWAP、Static Arbitrage、Paper Trading、Settlement、Performance、Replay、Research Test、Debug

## 页面

- Overview：CSL research status 与简洁 Paper 概览。
- `/live-match`：fixture、recording status、H/D/A 价格、ticks、signal、lag 与 quality；依赖真实数据的高级指标仍在积累中。
- `/research`：data coverage、latency survival、markout 与 performance；数据不足时显示 Insufficient live data。
- `/debug`：CSL discovery、Kalshi series probe、resolution levels、connectors、order books、requests 与 Research Test。
- Markets、Matches、Opportunities、Paper、Performance、Research Test、Settings 等旧页面继续保留。

FastAPI 文档：<http://localhost:8000/docs>

## 快速启动

要求：Docker Desktop、Git。

```bash
git clone https://github.com/LutaoZheng/ArbiCast.git
cd ArbiCast
cp .env.example .env
```

Mock Mode：

```bash
DATA_MODE=mock docker compose up --build
```

Live Mode：

```bash
DATA_MODE=live docker compose up --build
```

后台运行：

```bash
DATA_MODE=live docker compose up -d --build
```

访问：

- <http://localhost:3000>
- <http://localhost:3000/live-match>
- <http://localhost:3000/research>
- <http://localhost:3000/debug>
- <http://localhost:8000/docs>

仅运行 `docker compose up --build` 时，data mode 取决于环境/default 配置。Live research 前必须确认 UI 显示 **LIVE MODE**。

停止：

```bash
docker compose down
```

除非明确希望删除 PostgreSQL 数据，否则不要使用 `docker compose down -v`。

## 测试

```bash
docker compose run --rm backend pytest -q

docker compose run --rm -e PYTHONPATH=/app \
  backend python scripts/audit_csl_fixtures.py --summary

cd frontend
npm install
npm run typecheck
npm run build

docker compose config --quiet
```

Docker frontend production build 是正式验证路径。macOS ARM 若本地 optional dependency 安装不完整，可能提示缺失 Next.js SWC binary；这不等于 Docker production build 失败。

Phase 5.3 checkpoint：**43 个 backend tests 通过**；8 场 live fixture audit 为 **24/24 core-compatible outcomes**；Docker frontend production build 与 Compose config 均通过。

## 当前限制

- CSL discovery 有明确的有界扫描上限。
- cancellation/postponement/abandonment 等边缘规则尚未完全确认。
- 当前 pairs 是 core-compatible，不是 guaranteed-arbitrage compatible。
- REST polling 限制 lead/lag 的时间精度。
- 真实比赛尚未进入 recording window，研究数据仍然稀少。
- Paper execution 是模拟，不能保证真实成交。
- 不支持真钱交易、账户登录、钱包、私钥、充值或提现。
- 本项目是研究软件，不构成财务建议。

## Next Experiment

下一阶段不是增加新策略，而是记录真实 CSL 比赛，研究 cross-market opportunity 是否能在现实延迟下存活。

重点收集 PriceTick、DynamicSignal、Lead/Lag、opportunity lifetime、order-book depth、VWAP、fees、slippage、execution delay、markout 与 paper PnL，并比较：

```text
0 ms · 100 ms · 250 ms · 500 ms · 1 s · 2 s · 3 s · 5 s
```

最终回答：

- 有多少机会能存活 500ms、1s 和 2s？
- 延迟后的真实可执行深度是多少？
- spread、手续费、滑点和延迟吃掉多少理论 edge？
- delay-adjusted paper PnL 是多少？

## 安全边界

ArbiCast 只读取公开市场数据、进行本地研究和 Paper/模拟执行。当前不存在真钱下单或撤单、账户登录、钱包签名、私钥保存、充值、提现或地域限制绕过功能，也不保证盈利。

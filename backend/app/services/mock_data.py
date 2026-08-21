from datetime import UTC, datetime, timedelta

from app.schemas.domain import (
    MarketMatch, MatchStatus, NormalizedMarket, Opportunity, PaperTrade,
    Platform, SizeQuote,
)

NOW = datetime.now(UTC)

EVENTS = [
    ("arsenal", "Will Arsenal beat Chelsea in regulation time?", "sports"),
    ("fed", "Will the Fed cut rates at the September meeting?", "economics"),
    ("btc", "Will Bitcoin trade above $120,000 by December 31?", "crypto"),
    ("senate", "Will the Senate pass the Digital Markets Act in 2026?", "politics"),
    ("cpi", "Will US CPI be above 3.0% in September?", "economics"),
    ("lakers", "Will the Lakers win their opening game?", "sports"),
]


def markets() -> list[NormalizedMarket]:
    result: list[NormalizedMarket] = []
    for i, (slug, title, category) in enumerate(EVENTS):
        for platform in (Platform.KALSHI, Platform.POLYMARKET):
            platform_title = title
            rules = f"Resolves Yes if {title[5:].rstrip('?').lower()}, using the official event result."
            if slug == "arsenal" and platform == Platform.POLYMARKET:
                platform_title = "Will Arsenal advance against Chelsea?"
                rules = "Resolves Yes if Arsenal advances, including extra time and penalties."
            result.append(NormalizedMarket(
                id=f"{platform.value}:{slug}", platform=platform, external_id=f"{platform.value[:2].upper()}-{slug.upper()}",
                title=platform_title, description=f"Research market for {title}", category=category,
                event_date=NOW + timedelta(days=i + 2), close_time=NOW + timedelta(days=i + 2),
                resolution_rules=rules, resolution_source="Official league" if category == "sports" else "Official publication",
            ))
    return result


def matches() -> list[MarketMatch]:
    statuses = [MatchStatus.NEEDS_REVIEW, MatchStatus.APPROVED, MatchStatus.APPROVED, MatchStatus.NEEDS_REVIEW, MatchStatus.APPROVED, MatchStatus.REJECTED]
    return [MarketMatch(
        id=f"match-{slug}", kalshi_market_id=f"kalshi:{slug}", polymarket_market_id=f"polymarket:{slug}",
        similarity_score=[.78, .96, .94, .82, .91, .67][i],
        resolution_compatible=slug != "arsenal", confidence=[.42, .95, .91, .74, .89, .35][i],
        warnings=["结算规则不一致：Kalshi 仅常规时间；Polymarket 包含加时赛/点球大战。不允许用于套利计算。"] if slug == "arsenal" else ([] if i not in (3, 5) else ["结算来源不同，需要人工确认"]),
        status=statuses[i],
    ) for i, (slug, _, _) in enumerate(EVENTS)]


def _quotes(edge: float, max_size: float) -> list[SizeQuote]:
    output = []
    for size in (10, 25, 50, 100, 250, 500, 1000):
        liquid = size <= max_size
        degraded = edge - (size / max_size) * .004 if liquid else None
        output.append(SizeQuote(size=size, net_edge=degraded, expected_profit=size * degraded if degraded is not None else None, liquidity_available=liquid))
    return output


def opportunities() -> list[Opportunity]:
    rows = [
        ("opp-fed", "Will the Fed cut rates in September?", "economics", "match-fed", "Kalshi YES + Polymarket NO", .431, .521, .041, 186, 23.4),
        ("opp-btc", "Bitcoin above $120,000 by December 31", "crypto", "match-btc", "Kalshi NO + Polymarket YES", .472, .493, .026, 540, 81.7),
        ("opp-cpi", "US CPI above 3.0% in September", "economics", "match-cpi", "Kalshi YES + Polymarket NO", .388, .579, .019, 94, 8.4),
        ("opp-history", "Senate passes Digital Markets Act", "politics", "match-senate", "Kalshi NO + Polymarket YES", .501, .476, .012, 250, 143.2),
    ]
    result = []
    for i, (oid, event, category, match, direction, kp, pp, edge, size, duration) in enumerate(rows):
        live = i < 3
        result.append(Opportunity(
            id=oid, event=event, category=category, match_id=match, direction=direction,
            kalshi_side="YES" if "Kalshi YES" in direction else "NO", polymarket_side="NO" if "Polymarket NO" in direction else "YES",
            kalshi_price=kp, polymarket_price=pp, kalshi_vwap=kp+.002, polymarket_vwap=pp+.002,
            gross_edge=1-kp-pp, estimated_fees=.004, slippage=.002, safety_buffer=.002,
            net_edge=edge, available_size=size, expected_profit=round(edge*min(size, 100), 2), match_confidence=.89+i*.02,
            first_seen=NOW-timedelta(seconds=duration), last_seen=NOW if live else NOW-timedelta(days=1),
            duration_seconds=duration, best_edge=edge+.006, worst_edge=max(0, edge-.005), size_quotes=_quotes(edge, size), live=live,
        ))
    return result


def paper_trades() -> list[PaperTrade]:
    rows = [
        ("paper-1", "opp-fed", "Fed September rate cut", 100, .433, .523, 3.20),
        ("paper-2", "opp-btc", "Bitcoin above $120k", 50, .475, .495, 1.05),
        ("paper-3", "opp-cpi", "US CPI above 3.0%", 75, .391, .582, .72),
        ("paper-4", "opp-history", "Digital Markets Act", 100, .505, .479, -.18),
    ]
    return [PaperTrade(
        id=pid, opportunity_id=oid, event=event, mode="realistic", entry_time=NOW-timedelta(hours=i*7+1),
        quantity=qty, kalshi_fill=kp, polymarket_fill=pp, fees=.35, slippage=.25,
        total_cost=qty-profit, locked_payout=qty, estimated_profit=profit,
        status="settled" if i > 1 else "open",
    ) for i, (pid, oid, event, qty, kp, pp, profit) in enumerate(rows)]


def analytics() -> dict:
    return {
        "summary": {"detected": 284, "above1": 73, "above2": 21, "above3": 7, "medianDuration": 2.4, "medianLiquidity": 46, "paperProfit": 37.42},
        "daily": [{"day": f"Aug {d}", "opportunities": v} for d, v in zip(range(14, 21), [31, 44, 35, 52, 38, 47, 37])],
        "edgeDistribution": [{"bucket": b, "count": c} for b, c in zip(["0–1%", "1–2%", "2–3%", "3–4%", ">4%"], [211, 52, 14, 5, 2])],
        "durations": [{"bucket": b, "count": c} for b, c in zip(["<1s", "1–3s", "3–10s", "10–30s", ">30s"], [86, 104, 57, 24, 13])],
        "categories": [{"name": n, "value": v} for n, v in zip(["Sports", "Politics", "Economics", "Crypto", "Other"], [38, 24, 22, 12, 4])],
        "profitBySize": [{"size": f"${s}", "profit": p} for s, p in zip([10,25,50,100,250,500,1000], [.38,.91,1.55,1.70,2.1,1.2,0])],
    }


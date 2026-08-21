"""Read-only Phase 5.2 audit for the known 2026-08-22/23 CSL fixtures."""
import asyncio
import json
import sys

import httpx

from app.connectors.kalshi.connector import KalshiConnector
from app.connectors.polymarket.connector import PolymarketConnector
from app.csl.matching import deterministic_csl_match, parse_csl_contract


EVENTS = [
    "KXCHNSLGAME-26AUG22WUHTTT", "KXCHNSLGAME-26AUG22CHRSHS",
    "KXCHNSLGAME-26AUG22SHEZHP", "KXCHNSLGAME-26AUG22QWCSHT",
    "KXCHNSLGAME-26AUG22BJGYUN", "KXCHNSLGAME-26AUG23LITHEN",
    "KXCHNSLGAME-26AUG23SHPQIN", "KXCHNSLGAME-26AUG23CHODAL",
]


def compact_event(raw):
    return {key: raw.get(key) for key in (
        "id", "event_ticker", "ticker", "title", "slug", "status",
        "startDate", "endDate", "strike_date", "series_ticker",
        "category", "sportsMarketType", "gameStatus",
    ) if raw.get(key) is not None}


def compact_market(raw):
    return {key: raw.get(key) for key in (
        "id", "ticker", "question", "title", "yes_sub_title", "groupItemTitle",
        "status", "active", "closed", "occurrence_datetime", "open_time",
        "close_time", "expected_expiration_time", "endDate", "event_ticker",
        "rules_primary", "description",
    ) if raw.get(key) is not None}


async def main():
    kalshi = KalshiConnector()
    poly = PolymarketConnector()
    try:
        k_events = []
        for ticker in EVENTS:
            body = (await kalshi.http.get(f"/events/{ticker}", params={"with_nested_markets": "true"})).json()
            k_events.append(body.get("event", body))

        search = (await poly.gamma.get("/public-search", params={
            "q": "Chinese Super League", "events_status": "active",
            "limit_per_type": 100, "search_profiles": "false",
        })).json()
        p_events = search.get("events") or []
        report = []
        for ke in k_events:
            kn = kalshi._normalize_event_markets(ke)
            kc = parse_csl_contract(kn[0]) if kn else None
            matches = []
            for pe in p_events:
                pn = []
                tags = " ".join(f"{x.get('label','')} {x.get('slug','')}" for x in pe.get("tags", []) if isinstance(x, dict))
                series = " ".join(f"{x.get('title','')} {x.get('slug','')} {x.get('ticker','')}" for x in pe.get("series", []) if isinstance(x, dict))
                context = " ".join(filter(None, [pe.get("title"), pe.get("description"), tags, series]))
                for raw in pe.get("markets", []):
                    enriched = {**raw, "eventTitle": pe.get("title"), "category": raw.get("category") or "sports", "description": " ".join(filter(None, [raw.get("description"), context])), "eventId": pe.get("id"), "events": [pe], "endDate": raw.get("endDate") or pe.get("endDate")}
                    try: pn.append((raw, poly._normalize_market(enriched)))
                    except (ValueError, TypeError, KeyError): pass
                contracts = [(raw, market, parse_csl_contract(market)) for raw, market in pn]
                if kc and any(pc and {pc.home_team, pc.away_team} == {kc.home_team, kc.away_team} and pc.match_date.date() == kc.match_date.date() for _, _, pc in contracts):
                    matches.append((pe, contracts))

            outcome_rows = []
            for km in kn:
                ka = parse_csl_contract(km)
                possible = []
                for pe, contracts in matches:
                    for raw, pm, pc in contracts:
                        if not pc or not ka: continue
                        decision = deterministic_csl_match(km, pm)
                        if pc.outcome == ka.outcome or {pc.home_team, pc.away_team} == {ka.home_team, ka.away_team}:
                            possible.append({
                                "polymarket_market_raw": compact_market(raw),
                                "polymarket_canonical": pc.__dict__,
                                "matcher": decision,
                            })
                outcome_rows.append({
                    "kalshi_market_raw": compact_market(next(x for x in ke.get("markets", []) if x.get("ticker") == km.external_id)),
                    "kalshi_canonical": ka.__dict__ if ka else None,
                    "polymarket_comparisons": possible,
                })
            report.append({
                "kalshi_event_raw": compact_event(ke),
                "polymarket_events_raw": [compact_event(x[0]) for x in matches],
                "outcomes": outcome_rows,
            })
        if "--summary" in sys.argv:
            summary=[]
            for fixture in report:
                decisions={}
                for outcome in fixture["outcomes"]:
                    canonical=outcome["kalshi_canonical"]
                    same=next((x for x in outcome["polymarket_comparisons"] if x["polymarket_canonical"]["home_team"]==canonical["home_team"] and x["polymarket_canonical"]["away_team"]==canonical["away_team"] and x["polymarket_canonical"]["outcome"]==canonical["outcome"]),None)
                    decisions[canonical["outcome"]]=same["matcher"] if same else {"matched":False,"reasons":["No same-orientation same-outcome Polymarket contract"]}
                summary.append({"fixture":fixture["kalshi_event_raw"]["title"],"kalshi_event":fixture["kalshi_event_raw"].get("event_ticker"),"polymarket_event":fixture["polymarket_events_raw"][0].get("id") if fixture["polymarket_events_raw"] else None,"decisions":decisions})
            print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    finally:
        await kalshi.close()
        await poly.close()


if __name__ == "__main__":
    asyncio.run(main())

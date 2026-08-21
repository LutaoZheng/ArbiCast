import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from app.matching.resolution import resolution_compatibility
from app.schemas.domain import NormalizedMarket
from app.schemas.domain import MatchStatus,Platform

TEAM_ALIASES = {
    "beijing fc": "Beijing Guoan", "beijing guoan fc": "Beijing Guoan", "beijing guoan": "Beijing Guoan",
    "shanghai port fc": "Shanghai Port", "shanghai sipg": "Shanghai Port", "shanghai port": "Shanghai Port",
    "shanghai haigang fc": "Shanghai Port", "shanghai haigang": "Shanghai Port",
    "shanghai shenhua fc": "Shanghai Shenhua", "shanghai shenhua": "Shanghai Shenhua",
    "shandong taishan fc": "Shandong Taishan", "shandong luneng": "Shandong Taishan", "shandong taishan": "Shandong Taishan",
    "chengdu rongcheng fc": "Chengdu Rongcheng", "chengdu rongcheng": "Chengdu Rongcheng",
    "tianjin jinmen tiger fc": "Tianjin Jinmen Tiger", "tianjin teda": "Tianjin Jinmen Tiger", "tianjin jinmen tiger": "Tianjin Jinmen Tiger",
    "tianjin jinmen hu fc": "Tianjin Jinmen Tiger", "tianjin jinmen hu": "Tianjin Jinmen Tiger",
    "zhejiang professional fc": "Zhejiang", "zhejiang fc": "Zhejiang", "zhejiang professional": "Zhejiang",
    "zhejiang prof": "Zhejiang",
    "zhejiang zhiye fc": "Zhejiang", "zhejiang zhiye": "Zhejiang",
    "wuhan three towns fc": "Wuhan Three Towns", "wuhan three towns": "Wuhan Three Towns",
    "wuhan san zhen fc": "Wuhan Three Towns", "wuhan san zhen": "Wuhan Three Towns",
    "henan fc": "Henan", "henan songshan longmen": "Henan", "henan": "Henan",
    "qingdao west coast fc": "Qingdao West Coast", "qingdao west coast": "Qingdao West Coast",
    "qingdao xihaian fc": "Qingdao West Coast", "qingdao xihaian": "Qingdao West Coast",
    "qingdao hainiu fc": "Qingdao Hainiu", "qingdao hainiu": "Qingdao Hainiu",
    "changchun yatai fc": "Changchun Yatai", "changchun yatai": "Changchun Yatai",
    "shenzhen peng city fc": "Shenzhen Peng City", "shenzhen peng city": "Shenzhen Peng City",
    "shenzhen xinpengcheng fc": "Shenzhen Peng City", "shenzhen xinpengcheng": "Shenzhen Peng City",
    "meizhou hakka fc": "Meizhou Hakka", "meizhou hakka": "Meizhou Hakka",
    "yunnan yukun fc": "Yunnan Yukun", "yunnan yukun": "Yunnan Yukun",
    "dalian yingbo fc": "Dalian Yingbo", "dalian yingbo": "Dalian Yingbo",
    "liaoning tieren fc": "Liaoning Tieren", "liaoning tieren": "Liaoning Tieren",
    "chongqing tonglianglong fc": "Chongqing Tonglianglong", "chongqing tonglianglong": "Chongqing Tonglianglong",
}

def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())

def canonical_team(value: str) -> str | None:
    normalized = _plain(value)
    if normalized in TEAM_ALIASES: return TEAM_ALIASES[normalized]
    for alias, canonical in sorted(TEAM_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", normalized): return canonical
    return None

def is_football_market(market: NormalizedMarket) -> bool:
    text=_plain(f"{market.category} {market.title} {market.description}")
    return any(x in text for x in ("soccer","football","match winner","chinese super league","china super league")) or bool(re.search(r"\bcsl\b",text))

def is_csl_like_market(market: NormalizedMarket) -> bool:
    if market.platform==Platform.KALSHI and market.series_ticker=="KXCHNSLGAME":return True
    text=_plain(f"{market.title} {market.description}")
    return "chinese super league" in text or "china super league" in text or bool(re.search(r"\bcsl\b",text))

def is_semantically_compatible_csl(market:NormalizedMarket)->bool:
    if not parse_csl_contract(market):return False
    # Compare against an explicit regulation-only reference so negated phrases
    # such as "does not include penalties" are interpreted correctly.
    return resolution_compatibility(market.resolution_rules,"First 90 minutes of regular play plus stoppage time; excludes extra time and penalties.").core_compatible

def inspect_csl_market(market:NormalizedMarket)->dict:
    contract=parse_csl_contract(market)
    return {"platform":market.platform.value,"market_id":market.id,"raw_title":market.title,"detected_league":"CSL" if is_csl_like_market(market) else None,"home_team":contract.home_team if contract else None,"away_team":contract.away_team if contract else None,"start_time":(contract.match_date if contract else market.event_date or market.close_time),"market_type":contract.market_type if contract else None,"outcome":contract.outcome if contract else None,"resolution_type":"90 MIN" if contract and not any(x in _plain(market.resolution_rules) for x in ("extra time","penalties","advance")) else "REVIEW","normalization_result":"OK" if contract else "REJECTED","candidate_pair":None,"match_score":None,"status":"NORMALIZED" if contract else "REJECTED","reject_reason":None if contract else "Unsupported team aliases or missing 90-minute CSL fixture semantics"}

@dataclass(frozen=True)
class CSLContract:
    home_team: str
    away_team: str
    outcome: str
    match_date: datetime
    market_type: str = "90_MINUTE_MATCH_WINNER"

def parse_csl_contract(market: NormalizedMarket) -> CSLContract | None:
    text = _plain(f"{market.title} {market.description}")
    if not (market.platform==Platform.KALSHI and market.series_ticker=="KXCHNSLGAME") and not ("chinese super league" in text or "china super league" in text or re.search(r"\bcsl\b",text)): return None
    # Event-level fixture orientation is authoritative. A single outcome title
    # often starts with the selected away team and must not reverse the fixture.
    fixture_text=_plain(market.event_title or "") or text
    hits=[]
    for alias, canonical in sorted(TEAM_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        match=re.search(rf"\b{re.escape(alias)}\b",fixture_text)
        if match and canonical not in {x[1] for x in hits}:hits.append((match.start(),canonical))
    hits.sort()
    if len(hits)<2:return None
    home,away=hits[0][1],hits[1][1]
    label=_plain(market.outcome_label or market.title)
    selected=canonical_team(label) if market.outcome_label else None
    if re.search(r"\b(draw|tie)\b",label):outcome="DRAW"
    elif selected==away:outcome="AWAY"
    elif selected==home:outcome="HOME"
    elif any(x in label for x in ("away win","away winner",f"{_plain(away)} win",f"{_plain(away)} winner")):outcome="AWAY"
    else:outcome="HOME"
    return CSLContract(home,away,outcome,market.event_date or market.close_time)

def deterministic_csl_match(left: NormalizedMarket, right: NormalizedMarket) -> dict:
    a,b=parse_csl_contract(left),parse_csl_contract(right)
    reasons=[]
    if not a or not b:return {"matched":False,"needs_review":False,"reasons":["Not a supported CSL 90-minute match-winner contract"]}
    if (a.home_team,a.away_team)!=(b.home_team,b.away_team):reasons.append("Different home/away teams")
    if a.match_date.date()!=b.match_date.date():reasons.append("Different match date")
    if a.outcome!=b.outcome:reasons.append("Different match outcome contract")
    resolution=resolution_compatibility(left.resolution_rules,right.resolution_rules)
    if not resolution.core_compatible:reasons.extend(resolution.differences or ["Core resolution semantics are not equivalent"])
    hard=bool(reasons)
    return {"matched":not hard and resolution.core_compatible,"needs_review":False,"reasons":reasons or resolution.warnings,"home_team":a.home_team,"away_team":a.away_team,"outcome":a.outcome,"scheduled_start":min(a.match_date,b.match_date),"market_type":a.market_type,"resolution_compatible":resolution.core_compatible,"core_compatible":resolution.core_compatible,"fully_compatible":resolution.fully_compatible,"compatibility_level":resolution.level,"resolution_risk":resolution.resolution_risk,"resolution_confidence":resolution.confidence}

def match_session_payload(pair:dict,left:NormalizedMarket,right:NormalizedMarket,existing:dict|None=None,now:datetime|None=None)->dict|None:
    import hashlib
    from datetime import UTC, timedelta
    match=deterministic_csl_match(left,right)
    if not (match.get("matched") or match.get("needs_review")):return None
    key=f"{match['home_team']}|{match['away_team']}|{match['scheduled_start'].date()}";sid="csl:"+hashlib.sha1(key.encode()).hexdigest()[:16]
    markets=dict((existing or {}).get("markets",{}));markets={venue:dict(outcomes) for venue,outcomes in markets.items()}
    markets.setdefault("kalshi",{})[match["outcome"]]=left.id;markets.setdefault("polymarket",{})[match["outcome"]]=right.id
    research_eligible=bool(match["core_compatible"]);approved=pair.get("status")=="approved" and bool(match["fully_compatible"]);clock=now or datetime.now(UTC);start=match["scheduled_start"]
    status="LIVE" if start<=clock<=start+timedelta(hours=3) else "FINISHED" if clock>start+timedelta(hours=3) else "PRE_MATCH"
    return {"id":sid,"season":str(start.year),"home_team":match["home_team"],"away_team":match["away_team"],"scheduled_start":start,"status":status,"pair_id":pair["id"],"markets":markets,"metadata":{"market_type":"90_MINUTE_MATCH_WINNER","pair_kind":"RESEARCH_PAIR","approval_status":pair.get("status"),"resolution_compatible":match["resolution_compatible"],"core_compatible":match["core_compatible"],"fully_compatible":match["fully_compatible"],"resolution_risk":match["resolution_risk"],"research_eligible":research_eligible,"recording_enabled":research_eligible,"paper_execution_allowed":approved,"clock_source":"market_schedule_only"}}

def csl_candidate_pairs(markets:list[NormalizedMarket])->list[dict]:
    parsed=[]
    for market in markets:
        contract=parse_csl_contract(market)
        if contract:parsed.append((market,contract))
    poly_index={}
    for market,contract in parsed:
        if market.platform==Platform.POLYMARKET:poly_index.setdefault((contract.home_team,contract.away_team,contract.match_date.date(),contract.outcome),[]).append(market)
    rows=[]
    for left,contract in parsed:
        if left.platform!=Platform.KALSHI:continue
        key=(contract.home_team,contract.away_team,contract.match_date.date(),contract.outcome)
        for right in poly_index.get(key,[]):
            match=deterministic_csl_match(left,right)
            if not (match.get("matched") or match.get("needs_review")):continue
            confidence=.99 if match["fully_compatible"] else .95 if match["core_compatible"] else .85
            rows.append({"id":f"csl-{left.external_id}-{right.external_id}","kalshi_market_id":left.id,"polymarket_market_id":right.id,"title_similarity":1.0,"entity_similarity":1.0,"date_similarity":1.0,"numeric_similarity":1.0,"category_match":True,"preliminary_score":1.0,"similarity_score":1.0,"resolution_compatible":match["core_compatible"],"core_compatible":match["core_compatible"],"fully_compatible":match["fully_compatible"],"compatibility_level":match["compatibility_level"],"resolution_risk":match["resolution_risk"],"paper_eligible":False,"resolution_confidence":match["resolution_confidence"],"differences":match["reasons"],"confidence":confidence,"warnings":match["reasons"] or ["CSL structured match; manually confirm full resolution and postponement rules"],"status":MatchStatus.NEEDS_REVIEW,"kalshi_market":left,"polymarket_market":right,"signals":{"same_league":True,"home_team_match":True,"away_team_match":True,"date_match":True,"market_type_match":True,"numeric_match":True},"research_universe":"CSL","market_type":"90_MINUTE_MATCH_WINNER"})
    return sorted(rows,key=lambda x:x["confidence"],reverse=True)

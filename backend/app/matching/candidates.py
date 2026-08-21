import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

from app.matching.resolution import resolution_compatibility
from app.schemas.domain import MatchStatus, NormalizedMarket, Platform

STOPWORDS={"will","the","a","an","be","to","of","in","on","at","by","for","and","or","market","event","does","is","vs","versus","win","winner","yes","no","before","after","more","less","than","rate","2025","2026","2027","2028","2029","2030","2035"}
ALIASES={"man utd":"manchester united","man city":"manchester city","psg":"paris saint germain","btc":"bitcoin","eth":"ethereum","usa":"united states","u.s.":"united states"}
ENTITY_HINTS={"fc","united","city","state","states","bitcoin","ethereum","trump","biden","arsenal","chelsea","liverpool","nba","nfl","epl","ufc","fifa"}

def normalize_market_title(value:str)->str:
    value=unicodedata.normalize("NFKD",value).encode("ascii","ignore").decode().lower()
    value=value.replace("versus"," vs ").replace(" v. "," vs ")
    for old,new in ALIASES.items(): value=value.replace(old,new)
    value=re.sub(r"\$\s*([0-9,.]+)\s*([kmbt])?",lambda m:_number(m.group(1),m.group(2)),value)
    value=re.sub(r"[^a-z0-9.%]+"," ",value)
    return " ".join(t for t in value.split() if t not in STOPWORDS)

def _number(raw:str,suffix:str|None=None)->str:
    number=float(raw.rstrip(".,").replace(",","")); number*= {"k":1e3,"m":1e6,"b":1e9,"t":1e12}.get((suffix or "").lower(),1)
    return str(int(number)) if number.is_integer() else str(number)

def extract_numbers(value:str)->tuple[str,...]:
    normalized=normalize_market_title(value)
    return tuple(re.findall(r"(?<![a-z])\d+(?:\.\d+)?%?",normalized))

def extract_entities(value:str)->set[str]:
    normalized=normalize_market_title(value); tokens=normalized.split(); entities={t for t in tokens if len(t)>3 and (t in ENTITY_HINTS or t[0].isalpha())}
    entities.update(" ".join(tokens[i:i+2]) for i in range(len(tokens)-1) if tokens[i] not in STOPWORDS and tokens[i+1] not in STOPWORDS)
    return entities

def _market_text(market:NormalizedMarket)->str:
    # Kalshi commonly keeps the outcome/threshold in subtitle; Gamma descriptions
    # are long-form rules and would pollute entity/number candidate features.
    return f"{market.title} {market.description}".strip() if market.platform==Platform.KALSHI else market.title

@dataclass(frozen=True)
class CandidateFeatures:
    title_similarity:float; entity_similarity:float; date_similarity:float; numeric_similarity:float; category_match:bool
    @property
    def preliminary_score(self)->float:return .38*self.title_similarity+.32*self.entity_similarity+.14*self.date_similarity+.12*self.numeric_similarity+.04*float(self.category_match)

def _features(left:NormalizedMarket,right:NormalizedMarket)->CandidateFeatures|None:
    ln,rn=normalize_market_title(_market_text(left)),normalize_market_title(_market_text(right))
    shared_tokens={x for x in ln.split() if len(x)>=4 and not x[0].isdigit()}&{x for x in rn.split() if len(x)>=4 and not x[0].isdigit()}
    if len(shared_tokens)<2:return None
    left_numbers,right_numbers=extract_numbers(_market_text(left)),extract_numbers(_market_text(right))
    if left_numbers or right_numbers:
        if left_numbers!=right_numbers:return None
        numeric=1.0
    else:numeric=.7
    le,re=extract_entities(_market_text(left)),extract_entities(_market_text(right)); shared=le&re
    entity=len(shared)/max(1,min(len(le),len(re)))
    title=SequenceMatcher(None,ln,rn).ratio()
    left_date=left.event_date or left.close_time; right_date=right.event_date or right.close_time
    delta=abs((left_date-right_date).total_seconds())
    date=1 if delta<=6*3600 else .8 if delta<=24*3600 else .3 if delta<=3*86400 else 0
    sports_terms={"sports","sport","soccer","football","basketball","baseball","tennis","hockey","golf","esports","mma","cricket"}
    is_sports=any(term in left.category.lower() or term in right.category.lower() for term in sports_terms)
    if is_sports and (date<.8 or len(shared)<2):return None
    category=left.category==right.category or "other" in {left.category,right.category}
    if not category and title<.75:return None
    return CandidateFeatures(title,entity,date,numeric,category)

def candidate_pairs(markets:list[NormalizedMarket],threshold:float=.50,limit:int=100)->list[dict]:
    kalshi=[m for m in markets if m.platform==Platform.KALSHI]; poly=[m for m in markets if m.platform==Platform.POLYMARKET]
    token_index:dict[str,set[int]]=defaultdict(set)
    for i,m in enumerate(poly):
        for token in set(normalize_market_title(_market_text(m)).split()):
            if len(token)>=4:token_index[token].add(i)
    rows=[];seen:set[tuple[str,str]]=set()
    for left in kalshi:
        indices:set[int]=set()
        for token in set(normalize_market_title(_market_text(left)).split()):indices.update(token_index.get(token,set()))
        for right in (poly[i] for i in indices):
            title_key=(normalize_market_title(_market_text(left)),normalize_market_title(_market_text(right)))
            if title_key in seen:continue
            seen.add(title_key)
            f=_features(left,right)
            if not f or f.preliminary_score<threshold:continue
            resolution=resolution_compatibility(left.resolution_rules or left.description,right.resolution_rules or right.description)
            confidence=min(1,f.preliminary_score*(.75+.25*resolution.confidence))
            rows.append({"id":f"live-{left.external_id}-{right.external_id}","kalshi_market_id":left.id,"polymarket_market_id":right.id,"title_similarity":f.title_similarity,"entity_similarity":f.entity_similarity,"date_similarity":f.date_similarity,"numeric_similarity":f.numeric_similarity,"category_match":f.category_match,"preliminary_score":f.preliminary_score,"similarity_score":f.preliminary_score,"resolution_compatible":resolution.compatible,"resolution_confidence":resolution.confidence,"differences":resolution.differences,"confidence":confidence,"warnings":resolution.warnings or ["需要人工确认完整结算规则"],"status":MatchStatus.NEEDS_REVIEW,"kalshi_market":left,"polymarket_market":right,"signals":{"date_match":f.date_similarity>=.8,"category_match":f.category_match,"numeric_match":f.numeric_similarity==1}})
    return sorted(rows,key=lambda x:x["confidence"],reverse=True)[:limit]

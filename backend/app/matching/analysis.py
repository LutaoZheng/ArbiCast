from difflib import SequenceMatcher
from app.matching.candidates import _market_text, extract_entities, extract_numbers, normalize_market_title
from app.matching.resolution import resolution_compatibility
from app.schemas.domain import NormalizedMarket

SPORTS={"sports","sport","soccer","football","basketball","baseball","tennis","hockey","golf","esports","mma","cricket"}
SCOPE_SEASON={"season","champion","championship","tournament","league","playoffs","ballon"}
SCOPE_SINGLE={"match","game","today","tonight","vs","wins"}

def analyze_market_pair(left:NormalizedMarket,right:NormalizedMarket)->dict:
    lt,rt=_market_text(left),_market_text(right);ln,rn=normalize_market_title(lt),normalize_market_title(rt)
    le,re=extract_entities(lt),extract_entities(rt);shared=sorted(le&re);entity=len(shared)/max(1,min(len(le),len(re)))
    lnums,rnums=extract_numbers(lt),extract_numbers(rt);numeric=1.0 if lnums==rnums else 0.0
    ld,rd=left.event_date or left.close_time,right.event_date or right.close_time;hours=abs((ld-rd).total_seconds())/3600;date=1 if hours<=6 else .8 if hours<=24 else .3 if hours<=72 else 0
    category=left.category==right.category or "other" in {left.category,right.category}
    title=SequenceMatcher(None,ln,rn).ratio();lscope="season" if any(x in ln for x in SCOPE_SEASON) else "single" if any(x in ln for x in SCOPE_SINGLE) else "unknown";rscope="season" if any(x in rn for x in SCOPE_SEASON) else "single" if any(x in rn for x in SCOPE_SINGLE) else "unknown";scope_match=lscope==rscope or "unknown" in {lscope,rscope}
    resolution=resolution_compatibility(left.resolution_rules or left.description,right.resolution_rules or right.description)
    score=.38*title+.32*entity+.14*date+.12*numeric+.04*float(category)
    reasons=[]
    if len({x for x in ln.split() if len(x)>=4 and not x[0].isdigit()}&{x for x in rn.split() if len(x)>=4 and not x[0].isdigit()})<2:reasons.append("Insufficient shared event entities")
    if lnums!=rnums:reasons.append(f"Numeric threshold mismatch: {lnums or 'none'} vs {rnums or 'none'}")
    is_sports=any(x in left.category.lower() or x in right.category.lower() for x in SPORTS)
    if is_sports and date<.8:reasons.append(f"Sports date mismatch: {ld.date()} vs {rd.date()}")
    if not category and title<.75:reasons.append(f"Category mismatch: {left.category} vs {right.category}")
    if not scope_match:reasons.append(f"Event scope mismatch: {lscope} vs {rscope}")
    reasons.extend(resolution.differences)
    pipeline=[{"step":"candidate_retrieval","status":"PASS"},{"step":"category_filter","status":"PASS" if category or title>=.75 else "FAIL"},{"step":"entity_filter","status":"PASS" if entity>0 else "FAIL"},{"step":"date_filter","status":"PASS" if not is_sports or date>=.8 else "FAIL"},{"step":"numeric_threshold_filter","status":"PASS" if numeric==1 else "FAIL"},{"step":"event_scope","status":"PASS" if scope_match else "FAIL"},{"step":"resolution_compatibility","status":"PASS" if resolution.compatible else "REVIEW"}]
    eligible=not any(x["status"]=="FAIL" for x in pipeline) and score>=.5
    decision="NEEDS_REVIEW" if eligible else "REJECTED";pipeline.append({"step":"final_result","status":decision})
    return {"title_similarity":title,"entity_similarity":entity,"date_similarity":date,"numeric_similarity":numeric,"category_match":category,"event_scope":{"kalshi":lscope,"polymarket":rscope,"match":scope_match},"entities":{"kalshi":sorted(le),"polymarket":sorted(re),"shared":shared},"numbers":{"kalshi":lnums,"polymarket":rnums},"dates":{"kalshi":ld.isoformat(),"polymarket":rd.isoformat(),"difference_hours":hours},"resolution":{"compatible":resolution.compatible,"confidence":resolution.confidence,"warnings":resolution.warnings,"differences":resolution.differences},"final_score":score,"decision":decision,"reasons":reasons,"pipeline":pipeline}

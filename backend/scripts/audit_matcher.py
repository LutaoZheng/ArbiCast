"""Optional read-only live matcher audit; never places orders."""
import asyncio
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.connectors.kalshi import KalshiConnector
from app.connectors.polymarket import PolymarketConnector
from app.matching.candidates import candidate_pairs
from app.matching.analysis import analyze_market_pair

async def main():
    parser=argparse.ArgumentParser(description="Read-only live matcher audit")
    parser.add_argument("--kalshi-id");parser.add_argument("--poly-id")
    args=parser.parse_args()
    settings=get_settings()
    kalshi=KalshiConnector(settings.kalshi_base_url,settings.kalshi_max_markets)
    poly=PolymarketConnector(settings.polymarket_gamma_url,settings.polymarket_clob_url,settings.polymarket_max_markets)
    try:
        if args.kalshi_id and args.poly_id:
            left=await kalshi.get_market(args.kalshi_id);right=await poly.get_market(args.poly_id);analysis=analyze_market_pair(left,right)
            print(f"Kalshi: {left.title}\nPolymarket: {right.title}")
            for key in ["title_similarity","entity_similarity","date_similarity","numeric_similarity","category_match","event_scope","resolution","final_score","decision","reasons","pipeline"]:print(f"{key}: {analysis[key]}")
            return
        left,right=await asyncio.gather(kalshi.get_markets(),poly.get_markets())
        rows=candidate_pairs(left+right,settings.matching_min_score,30)
        print(f"Markets: Kalshi={len(left)} Polymarket={len(right)} Candidates={len(rows)}")
        for row in rows:print(f"{row['confidence']:.3f} | {row['kalshi_market'].title} [{row['kalshi_market'].description}] {row['kalshi_market'].event_date} || {row['polymarket_market'].title} {row['polymarket_market'].event_date}")
    finally:await kalshi.close();await poly.close()
if __name__=="__main__":asyncio.run(main())

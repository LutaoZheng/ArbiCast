import asyncio
import hashlib
from datetime import UTC,datetime
from app.arbitrage.engine import quote_direction
from app.arbitrage.fees import KalshiFeeModel,PolymarketFeeModel
from app.arbitrage.service import evaluate_pair
from app.arbitrage.vwap import calculate_vwap
from app.matching.analysis import analyze_market_pair
from app.paper_trading.execution import execute_opportunity
from app.schemas.domain import Platform

SIZES=(10,25,50,100,250,500)
def stamp(event:str)->dict:return {"timestamp":datetime.now(UTC).isoformat(),"event":event}

class ResearchTestService:
    def __init__(self,runtime):self.runtime=runtime
    def require_live(self):
        if self.runtime.settings.data_mode!="live":raise ValueError("Research Test requires DATA_MODE=live")
    def market(self,market_id,platform=None):
        market=self.runtime.cache.markets.get(market_id)
        if not market or (platform and market.platform!=platform):raise KeyError(market_id)
        return market
    def search(self,platform:str,query:str,limit:int=20):
        self.require_live();q=query.lower().strip();items=[m for m in self.runtime.cache.markets.values() if m.platform.value==platform and (not q or q in m.title.lower() or q in m.description.lower() or q in m.external_id.lower())]
        return sorted(items,key=lambda m:(q not in m.title.lower(),m.close_time))[:limit]
    def analyze(self,kalshi_id:str,polymarket_id:str):
        left=self.market(kalshi_id,Platform.KALSHI);right=self.market(polymarket_id,Platform.POLYMARKET);return {"kalshi_market":left,"polymarket_market":right,"analysis":analyze_market_pair(left,right)}
    def closest(self,market_id:str,limit:int=10):
        source=self.market(market_id);target=Platform.POLYMARKET if source.platform==Platform.KALSHI else Platform.KALSHI;rows=[]
        for other in self.runtime.cache.markets.values():
            if other.platform!=target:continue
            analysis=analyze_market_pair(source,other) if source.platform==Platform.KALSHI else analyze_market_pair(other,source)
            rows.append({"market":other,"analysis":analysis})
        return sorted(rows,key=lambda r:r["analysis"]["final_score"],reverse=True)[:limit]
    async def create_pair(self,kalshi_id:str,polymarket_id:str):
        result=self.analyze(kalshi_id,polymarket_id);analysis=result["analysis"];digest=hashlib.sha1(f"{kalshi_id}|{polymarket_id}".encode()).hexdigest()[:16];pair_id=f"test:{digest}"
        nearest=await self.closest(kalshi_id,10)
        payload={"id":pair_id,"kalshi_market_id":kalshi_id,"polymarket_market_id":polymarket_id,"kalshi_market":result["kalshi_market"].model_dump(mode="json"),"polymarket_market":result["polymarket_market"].model_dump(mode="json"),"confidence":analysis["final_score"],"similarity_score":analysis["final_score"],"resolution_compatible":analysis["resolution"]["compatible"],"warnings":analysis["reasons"],"status":"test_approved","is_test":True,"approval_source":"test","top_10_hit":any(x["market"].id==polymarket_id for x in nearest),"candidate_hit":analysis["decision"]!="REJECTED","analysis":analysis}
        return await self.runtime.repository.create_test_pair(payload)
    async def books(self,kalshi_id:str,polymarket_id:str,refresh:bool=True):
        self.require_live();self.market(kalshi_id,Platform.KALSHI);self.market(polymarket_id,Platform.POLYMARKET)
        if refresh:
            kb,pb=await asyncio.gather(self.runtime.connectors[Platform.KALSHI].get_orderbook(kalshi_id),self.runtime.connectors[Platform.POLYMARKET].get_orderbook(polymarket_id));await self.runtime.cache.update_orderbook(kalshi_id,kb,self.runtime.connectors[Platform.KALSHI].raw_orderbooks.get(kalshi_id));await self.runtime.cache.update_orderbook(polymarket_id,pb,self.runtime.connectors[Platform.POLYMARKET].raw_orderbooks.get(polymarket_id))
        else:kb,pb=self.runtime.cache.orderbooks.get(kalshi_id),self.runtime.cache.orderbooks.get(polymarket_id)
        if not kb or not pb:raise ValueError("Order books unavailable")
        return kb,pb
    @staticmethod
    def sanity(book):
        warnings=[]
        for name,levels,reverse in [("yes_bids",book.yes_bids,True),("yes_asks",book.yes_asks,False),("no_bids",book.no_bids,True),("no_asks",book.no_asks,False)]:
            if any(not 0<=x.price<=1 or x.quantity<=0 for x in levels):warnings.append(f"{name}: invalid price or quantity")
            prices=[x.price for x in levels]
            if prices!=sorted(prices,reverse=reverse):warnings.append(f"{name}: levels not sorted")
        if book.yes_bids and book.yes_asks and book.yes_bids[0].price>book.yes_asks[0].price:warnings.append("YES bid/ask inversion")
        if book.no_bids and book.no_asks and book.no_bids[0].price>book.no_asks[0].price:warnings.append("NO bid/ask inversion")
        return {"passed":not warnings,"warnings":warnings}
    async def inspect_books(self,kalshi_id,polymarket_id):
        kb,pb=await self.books(kalshi_id,polymarket_id);return {"kalshi":kb,"polymarket":pb,"sanity":{"kalshi":self.sanity(kb),"polymarket":self.sanity(pb)}}
    async def calculate(self,kalshi_id,polymarket_id):
        kb,pb=await self.books(kalshi_id,polymarket_id);directions=[("kalshi_yes_polymarket_no",kb.yes_asks,pb.no_asks),("kalshi_no_polymarket_yes",kb.no_asks,pb.yes_asks)];result=[]
        for direction,kl,pl in directions:
            quotes=[]
            for size in SIZES:
                q=quote_direction(direction,kl,pl,size,KalshiFeeModel(),PolymarketFeeModel(),self.runtime.settings.paper_slippage_buffer,self.runtime.settings.arbitrage_safety_buffer);kv,pv=calculate_vwap(kl,size),calculate_vwap(pl,size);quotes.append({"size":size,"kalshi_vwap":kv.vwap,"polymarket_vwap":pv.vwap,"gross_cost":(kv.vwap+pv.vwap) if kv.vwap is not None and pv.vwap is not None else None,"gross_edge":q.gross_edge,"fees":q.fees,"safety_buffer":self.runtime.settings.arbitrage_safety_buffer,"slippage":self.runtime.settings.paper_slippage_buffer,"net_edge":q.net_edge,"available_liquidity":min(sum(x.quantity for x in kl),sum(x.quantity for x in pl)),"expected_profit":q.expected_profit,"sufficient_liquidity":q.sufficient_liquidity})
            result.append({"direction":direction,"quotes":quotes})
        return result
    async def run_pipeline(self,pair_id:str,direction:str,trade_size:float,latency_ms:int,min_net_edge:float):
        pair=next((x for x in await self.runtime.repository.load_test_pairs() if x["id"]==pair_id),None)
        if not pair:raise KeyError(pair_id)
        trace=[stamp("Opportunity created"),stamp("Execution scheduled")];settings=self.runtime.settings.model_copy(update={"default_trade_size":trade_size,"paper_trade_size":trade_size,"paper_execution_latency_ms":latency_ms,"min_net_edge":min_net_edge})
        kb,pb=await self.books(pair["kalshi_market_id"],pair["polymarket_market_id"]);evaluated={d:(p,a) for d,p,a in evaluate_pair(pair,kb,pb,settings)}
        if direction not in evaluated:raise ValueError("Invalid direction")
        payload,_=evaluated[direction];payload.update({"is_test":True,"test_threshold":min_net_edge,"source":"live"})
        if payload["net_edge"]<min_net_edge:raise ValueError(f"Observed edge {payload['net_edge']:.4f} is below test threshold {min_net_edge:.4f}")
        opportunity=await self.runtime.repository.upsert_opportunity(pair_id,direction,payload,True);await self.runtime.repository.save_opportunity_snapshot(opportunity)
        await asyncio.sleep(latency_ms/1000);trace.append(stamp(f"{latency_ms}ms latency elapsed"));kb,pb=await self.books(pair["kalshi_market_id"],pair["polymarket_market_id"],True);trace.extend([stamp("Kalshi orderbook refreshed"),stamp("Polymarket orderbook refreshed")]);execution=execute_opportunity(opportunity,kb,pb,settings);trace.extend([stamp("Leg A simulated"),stamp("Leg B simulated")]);trade=await self.runtime.repository.create_paper_execution(opportunity,execution);trace.append(stamp("PaperTrade created"));trade_id=trade["id"] if trade else f"paper:{opportunity['id']}";ids={"pair_id":pair_id,"opportunity_id":opportunity["id"],"paper_trade_id":trade_id};verification=await self.runtime.repository.test_verification(ids)
        expected=payload["net_edge"];realized=execution["realized_entry_edge"]
        return {"trace":trace,"expected_edge":expected,"realized_entry_edge":realized,"edge_capture_ratio":realized/expected if expected else None,"execution":execution,"ids":verification["ids"],"database_verification":verification,"test_threshold":min_net_edge}

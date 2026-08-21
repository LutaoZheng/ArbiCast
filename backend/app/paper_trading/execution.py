from app.arbitrage.fees import KalshiFeeModel,PolymarketFeeModel
from app.arbitrage.vwap import calculate_vwap

def execute_opportunity(opportunity:dict,kalshi_book,polymarket_book,settings)->dict:
    quantity=settings.paper_trade_size
    if opportunity["direction"]=="kalshi_yes_polymarket_no":klevels,plevels=kalshi_book.yes_asks,polymarket_book.no_asks
    else:klevels,plevels=kalshi_book.no_asks,polymarket_book.yes_asks
    k,p=calculate_vwap(klevels,quantity),calculate_vwap(plevels,quantity)
    hedged=min(k.filled_quantity,p.filled_quantity);full=k.sufficient_liquidity and p.sufficient_liquidity
    if full:status="DUAL_FILLED"
    elif k.filled_quantity and p.filled_quantity:status="PARTIAL_FILL"
    elif k.filled_quantity or p.filled_quantity:status="SINGLE_LEG"
    else:status="FAILED"
    kv,pv=k.vwap or 0,p.vwap or 0;fees=KalshiFeeModel().estimate(kv,hedged)+PolymarketFeeModel().estimate(pv,hedged);slippage=hedged*settings.paper_slippage_buffer;capital=hedged*(kv+pv)+fees+slippage;edge=1-kv-pv-(fees/hedged if hedged else 0)-settings.paper_slippage_buffer
    orders=[{"platform":"kalshi","market_id":opportunity["kalshi_market_id"],"side":opportunity["kalshi_side"],"requested_size":quantity,"fill_price":kv,"filled_size":k.filled_quantity,"status":"FILLED" if k.sufficient_liquidity else "PARTIAL" if k.filled_quantity else "FAILED"},{"platform":"polymarket","market_id":opportunity["polymarket_market_id"],"side":opportunity["polymarket_side"],"requested_size":quantity,"fill_price":pv,"filled_size":p.filled_quantity,"status":"FILLED" if p.sufficient_liquidity else "PARTIAL" if p.filled_quantity else "FAILED"}]
    return {"requested_size":quantity,"hedged_size":hedged,"unhedged_size":max(k.filled_quantity,p.filled_quantity)-hedged,"actual_capital_used":capital,"realized_entry_edge":edge,"expected_profit":hedged*edge,"execution_latency_ms":settings.paper_execution_latency_ms,"fees":fees,"slippage":slippage,"status":status,"orders":orders}

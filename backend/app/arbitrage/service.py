from app.arbitrage.engine import quote_direction
from app.arbitrage.fees import KalshiFeeModel,PolymarketFeeModel
from app.arbitrage.vwap import calculate_vwap

TRADE_SIZES=(10,25,50,100,250,500,1000)

def evaluate_pair(match:dict,kalshi_book,polymarket_book,settings)->list[tuple[str,dict,bool]]:
    rows=[]
    directions=[("kalshi_yes_polymarket_no","YES","NO",kalshi_book.yes_asks,polymarket_book.no_asks),("kalshi_no_polymarket_yes","NO","YES",kalshi_book.no_asks,polymarket_book.yes_asks)]
    for direction,kside,pside,klevels,plevels in directions:
        size_quotes=[]; selected=None
        for size in TRADE_SIZES:
            quote=quote_direction(direction,klevels,plevels,size,KalshiFeeModel(),PolymarketFeeModel(),settings.paper_slippage_buffer,settings.arbitrage_safety_buffer)
            kv,pv=calculate_vwap(klevels,size),calculate_vwap(plevels,size)
            size_quotes.append({"size":size,"net_edge":quote.net_edge if quote.sufficient_liquidity else None,"expected_profit":quote.expected_profit if quote.sufficient_liquidity else None,"liquidity_available":quote.sufficient_liquidity})
            if size==settings.default_trade_size:selected=(quote,kv,pv,size)
        if selected is None:
            size=settings.default_trade_size;quote=quote_direction(direction,klevels,plevels,size,KalshiFeeModel(),PolymarketFeeModel(),settings.paper_slippage_buffer,settings.arbitrage_safety_buffer);kv,pv=calculate_vwap(klevels,size),calculate_vwap(plevels,size);selected=(quote,kv,pv,size)
        quote,kv,pv,size=selected; available=min(sum(x.quantity for x in klevels),sum(x.quantity for x in plevels))
        payload={"event":match["kalshi_market"]["title"],"category":match["kalshi_market"]["category"],"match_id":match["id"],"pair_id":match["id"],"direction":direction,"kalshi_side":kside,"polymarket_side":pside,"kalshi_market_id":match["kalshi_market_id"],"polymarket_market_id":match["polymarket_market_id"],"kalshi_price":kv.vwap or 0,"polymarket_price":pv.vwap or 0,"kalshi_vwap":kv.vwap or 0,"polymarket_vwap":pv.vwap or 0,"gross_edge":quote.gross_edge,"estimated_fees":quote.fees,"slippage":settings.paper_slippage_buffer,"safety_buffer":settings.arbitrage_safety_buffer,"net_edge":quote.net_edge,"available_size":available,"expected_profit":quote.expected_profit,"match_confidence":match["confidence"],"trade_size":size,"size_quotes":size_quotes,"source":"live","fee_assumptions":{"kalshi_coefficient":.07,"polymarket_rate":0}}
        active=quote.sufficient_liquidity and quote.net_edge>=settings.min_net_edge and quote.expected_profit>=settings.min_expected_profit
        rows.append((direction,payload,active))
    return rows

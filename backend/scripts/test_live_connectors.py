import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.connectors.kalshi import KalshiConnector
from app.connectors.polymarket import PolymarketConnector


async def inspect(name, connector):
    try:
        markets = await connector.get_markets()
        print(f"{name}:\nConnected\nMarkets: {len(markets)}")
        candidate = next((m for m in markets if name == "Kalshi" or (m.yes_token_id and m.no_token_id)), None)
        if not candidate: print("Sample market: unavailable\nOrder book: FAILED (no eligible market)"); return
        print(f"Sample market: {candidate.external_id} — {candidate.title}")
        try:
            book = await connector.get_orderbook(candidate.id)
            print(f"Order book: OK (YES {len(book.yes_bids)} bids/{len(book.yes_asks)} asks; NO {len(book.no_bids)} bids/{len(book.no_asks)} asks)")
        except Exception as exc: print(f"Order book: FAILED ({exc})")
    except Exception as exc: print(f"{name}:\nFAILED ({exc})\nMarkets: 0")
    finally: await connector.close()


async def main():
    s=get_settings()
    await inspect("Kalshi",KalshiConnector(s.kalshi_base_url,min(100,s.kalshi_max_markets)))
    await inspect("Polymarket",PolymarketConnector(s.polymarket_gamma_url,s.polymarket_clob_url,min(100,s.polymarket_max_markets)))


if __name__ == "__main__": asyncio.run(main())

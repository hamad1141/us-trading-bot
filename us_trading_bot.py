import os
import asyncio
import alpaca_trade_api as tradeapi

class AlpacaMonitor:
    def __init__(self):
        self.api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        self.base_url = "https://paper-api.alpaca.markets" 
        self.api = tradeapi.REST(self.api_key, self.secret_key, self.base_url, api_version='v2')

    async def display_dashboard(self):
        """Display Balance and Stats in the Black Screen (Logs)"""
        account = self.api.get_account()
        print("-" * 50)
        print(f"--- PORTFOLIO STATUS ---")
        print(f"Equity: ${account.equity}")
        print(f"Buying Power: ${account.buying_power}")
        print(f"Status: {account.status}")
        print("-" * 50)

    async def scan_gap_near_4pct(self):
        """Scan and display stocks near the 4% Gap target"""
        symbols = ["TSLA", "NVDA", "AMD", "MARA", "COIN", "AAPL", "META", "MSFT"]
        print("--- WATCHLIST (Scanning for >4% Gap) ---")
        
        for symbol in symbols:
            try:
                bars = self.api.get_bars(symbol, '1Day', limit=2).df
                if len(bars) < 2: continue
                
                prev_close = bars['close'].iloc[-2]
                curr_open = bars['open'].iloc[-1]
                gap = ((curr_open - prev_close) / prev_close) * 100
                
                # Show status for everything near or above 4%
                status_icon = "🔥 TARGET HIT" if gap >= 4.0 else "👀 Watching"
                print(f"{symbol}: Gap {gap:.2f}% | {status_icon}")
                
                if gap >= 4.0:
                    # Logic to execute trade would go here
                    pass
            except:
                continue
        print("-" * 50)

    async def start(self):
        while True:
            await self.display_dashboard()
            await self.scan_gap_near_4pct()
            print("Refreshing data in 30 seconds...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    monitor = AlpacaMonitor()
    asyncio.run(monitor.start())

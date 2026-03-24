import os
import asyncio
import alpaca_trade_api as tradeapi
from datetime import datetime

class OmniQuantumAlpha:
    def __init__(self):
        # API AUTHENTICATION
        self.api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        self.base_url = "https://paper-api.alpaca.markets" 
        self.api = tradeapi.REST(self.api_key, self.secret_key, self.base_url, api_version='v2')
        
        # PARAMETERS
        self.risk_per_trade = 0.20
        self.min_gap = 4.0
        self.min_profit = 0.015
        self.scan_limit = 200 

    def log_protocol(self):
        print("\n" + "!"*60)
        print(">>> PROTOCOL: SURVIVE OR TERMINATE")
        print(">>> MONITORING TOP 200 ASSETS FOR GAP > 4%")
        print("!"*60 + "\n")

    async def get_stats(self):
        acc = self.api.get_account()
        print(f"\n[VITAL SIGNS] Equity: ${acc.equity} | Power: ${acc.buying_power}")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')} | Status: ACTIVE")

    async def run_scanner(self):
        print(f"--- [LIVE MARKET SCAN: TOP 200] ---")
        assets = self.api.list_assets(status='active', asset_class='us_equity')
        watchlist = [a.symbol for a in assets if a.tradable and a.shortable][:self.scan_limit]
        
        for symbol in watchlist:
            try:
                bars = self.api.get_bars(symbol, '1Day', limit=2).df
                if bars.empty: continue
                prev_close = bars['close'].iloc[-2]
                curr_price = self.api.get_latest_trade(symbol).price
                gap_pct = ((curr_price - prev_close) / prev_close) * 100
                
                # VISUAL MONITORING: Show everything with movement > 0.5%
                if gap_pct >= 0.5:
                    status = "[[ TARGET HIT ]]" if gap_pct >= self.min_gap else "[ Below 4% - No Buy ]"
                    print(f"SYMBOL: {symbol:6} | GAP: {gap_pct:6.2f}% | {status}")

                if gap_pct >= self.min_gap:
                    await self.execute_trade(symbol, curr_price)
            except:
                continue

    async def execute_trade(self, symbol, price):
        acc = self.api.get_account()
        cash = float(acc.cash)
        qty = (cash * self.risk_per_trade) // price
        if qty > 0:
            print("\n" + "*"*60)
            print(f"[*] TRADE TRIGGERED: {symbol} | PRICE: ${price}")
            try:
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc', extended_hours=True)
                tp = price * (1 + self.min_profit)
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=tp, time_in_force='gtc', extended_hours=True)
                print(f"[LOG] BUY ORDER DONE | SELL LIMIT SET AT: ${tp:.2f}")
                print("*"*60 + "\n")
            except Exception as e:
                print(f"[ERROR] {e}")

    async def start(self):
        self.log_protocol()
        while True:
            await self.get_stats()
            await self.run_scanner()
            print("\nCycle Finished. Waiting 30s to avoid API rate limits...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    bot = OmniQuantumAlpha()
    asyncio.run(bot.start())

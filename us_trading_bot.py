import os
import asyncio
import alpaca_trade_api as tradeapi
from datetime import datetime

class OmniQuantumAlpha:
    def __init__(self):
        self.api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        self.base_url = "https://paper-api.alpaca.markets" 
        self.api = tradeapi.REST(self.api_key, self.secret_key, self.base_url, api_version='v2')
        
        self.risk_per_trade = 0.20
        self.min_gap = 4.0
        self.min_profit = 0.015
        self.scan_limit = 150 

    async def get_stats(self):
        acc = self.api.get_account()
        print(f"\n[VITAL SIGNS] Equity: ${acc.equity} | Power: ${acc.buying_power}")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')} | Status: ACTIVE")

    async def run_optimized_scanner(self):
        print(f"--- [ULTRA-FAST SCAN: {self.scan_limit} ASSETS] ---")
        assets = self.api.list_assets(status='active', asset_class='us_equity')
        watchlist = [a.symbol for a in assets if a.tradable and a.shortable][:self.scan_limit]
        
        try:
            # BULK REQUEST: Fetch last 2 days of bars for ALL symbols at once
            all_bars = self.api.get_bars(watchlist, '1Day', limit=2).df
            latest_quotes = self.api.get_latest_quotes(watchlist)
            
            for symbol in watchlist:
                try:
                    symbol_bars = all_bars[all_bars.index == symbol]
                    if len(symbol_bars) < 2: continue
                    
                    prev_close = symbol_bars['close'].iloc[-2]
                    curr_price = latest_quotes[symbol].askprice
                    gap_pct = ((curr_price - prev_close) / prev_close) * 100
                    
                    if gap_pct >= 0.5:
                        status = "!! TARGET !!" if gap_pct >= self.min_gap else "[Monitoring]"
                        print(f"S: {symbol:6} | Gap: {gap_pct:6.2f}% | {status}")

                    if gap_pct >= self.min_gap:
                        await self.execute_trade(symbol, curr_price)
                except:
                    continue
        except Exception as e:
            print(f"Optimized Scan Error: {e}")

    async def execute_trade(self, symbol, price):
        acc = self.api.get_account()
        cash = float(acc.cash)
        qty = (cash * self.risk_per_trade) // price
        if qty > 0:
            print("\n" + "*"*60)
            print(f"[*] TRADE TRIGGERED: {symbol} | QTY: {qty} | PRICE: ${price}")
            try:
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc', extended_hours=True)
                tp = price * (1 + self.min_profit)
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=tp, time_in_force='gtc', extended_hours=True)
                print(f"[SUCCESS] LIMIT ORDER SET AT: ${tp:.2f}")
                print("*"*60 + "\n")
            except Exception as e:
                print(f"[EXECUTION ERROR] {e}")

    async def start(self):
        print(">>> STARTING ULTRA-FAST AGGRESSIVE MODE...")
        while True:
            await self.get_stats()
            await self.run_optimized_scanner()
            await asyncio.sleep(5) 

if __name__ == "__main__":
    bot = OmniQuantumAlpha()
    asyncio.run(bot.start())

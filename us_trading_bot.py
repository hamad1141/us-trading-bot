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
        print("\n" + "="*50)
        print(f" BINANCE STYLE MONITOR | {datetime.now().strftime('%H:%M:%S')}")
        print(f" EQUITY: ${acc.equity} | BUYING POWER: ${acc.buying_power}")
        print("="*50)

    async def run_optimized_scanner(self):
        print(f"{'SYMBOL':<10} | {'PRICE':<10} | {'GAP %':<10} | {'STATUS'}")
        print("-" * 50)
        
        assets = self.api.list_assets(status='active', asset_class='us_equity')
        watchlist = [a.symbol for a in assets if a.tradable and a.shortable][:self.scan_limit]
        
        try:
            all_bars = self.api.get_bars(watchlist, '1Day', limit=2).df
            latest_quotes = self.api.get_latest_quotes(watchlist)
            
            for symbol in watchlist:
                try:
                    symbol_bars = all_bars[all_bars.index == symbol]
                    if len(symbol_bars) < 2: continue
                    
                    prev_close = symbol_bars['close'].iloc[-2]
                    curr_price = latest_quotes[symbol].askprice
                    gap_pct = ((curr_price - prev_close) / prev_close) * 100
                    
                    # عرض الأسهم اللي انحرافها أكثر من 0.5% عشان تشوف الحركة
                    if gap_pct >= 0.5:
                        status = "🚀 TARGET!!" if gap_pct >= self.min_gap else "Watching"
                        print(f"{symbol:<10} | ${curr_price:<9.2f} | {gap_pct:>6.2f}% | {status}")

                    if gap_pct >= self.min_gap:
                        await self.execute_trade(symbol, curr_price)
                except:
                    continue
        except Exception as e:
            print(f"Connection Error: {e}")

    async def execute_trade(self, symbol, price):
        acc = self.api.get_account()
        qty = (float(acc.cash) * self.risk_per_trade) // price
        if qty > 0:
            print(f"\n>>> [ORDER] BUY {qty} {symbol} at ${price}")
            try:
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc', extended_hours=True)
                tp = price * (1 + self.min_profit)
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=tp, time_in_force='gtc', extended_hours=True)
                print(f">>> [LOG] TAKE PROFIT SET: ${tp:.2f}\n")
            except Exception as e:
                print(f"Order Error: {e}")

    async def start(self):
        print(">>> STARTING ULTRA-FAST AGGRESSIVE MODE...")
        while True:
            await self.get_stats()
            await self.run_optimized_scanner()
            await asyncio.sleep(10) 

if __name__ == "__main__":
    bot = OmniQuantumAlpha()
    asyncio.run(bot.start())

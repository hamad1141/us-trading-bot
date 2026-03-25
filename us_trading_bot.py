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
        
        # --- Advanced Settings ---
        self.risk_per_trade = 0.20
        self.min_gap = 4.0           # الشراء عند فجوة 4%
        self.stop_loss_pct = 2.0     # وقف خسارة 2%
        self.trail_activation = 1.5  # تفعيل ملاحقة الربح عند 1.5%
        self.trail_distance = 0.5    # يبيع إذا نزل 0.5% عن أعلى قمة
        
        self.max_price = 50.0
        self.min_volume_usd = 2000000 
        self.scan_limit = 150 

    async def get_stats(self):
        try:
            acc = self.api.get_account()
            print("\n" + "="*60)
            print(f" TRAILING BEAST MODE | {datetime.now().strftime('%H:%M:%S')}")
            print(f" EQUITY: ${acc.equity} | POWER: ${acc.buying_power}")
            print("="*60)
        except: pass

    async def run_hybrid_scanner(self):
        print(f"{'SYMBOL':<10} | {'PRICE':<10} | {'D-GAP%':<8} | {'STATUS'}")
        print("-" * 50)
        
        try:
            assets = self.api.list_assets(status='active', asset_class='us_equity')
            symbols = [a.symbol for a in assets if a.tradable and a.shortable]
            snapshots = self.api.get_snapshots(symbols[:1000])
            
            volatile_pool = []
            for symbol, snap in snapshots.items():
                try:
                    price = snap.latest_quote.ap if hasattr(snap.latest_quote, 'ap') else snap.daily_bar.c
                    vol_usd = snap.daily_bar.v * price
                    if 0 < price <= self.max_price and vol_usd >= self.min_volume_usd:
                        change = abs(snap.daily_bar.c - snap.prev_daily_bar.c) / snap.prev_daily_bar.c if snap.prev_daily_bar else 0
                        volatile_pool.append((symbol, change))
                except: continue
            
            volatile_pool.sort(key=lambda x: x[1], reverse=True)
            watchlist = [x[0] for x in volatile_pool[:self.scan_limit]]
            
            latest_quotes = self.api.get_latest_quotes(watchlist)
            all_daily = self.api.get_bars(watchlist, '1Day', limit=2).df

            for symbol in watchlist:
                try:
                    d_bars = all_daily[all_daily.index == symbol]
                    if len(d_bars) < 2: continue
                    prev_close = d_bars['close'].iloc[-2]
                    curr_price = latest_quotes[symbol].askprice if hasattr(latest_quotes[symbol], 'askprice') else latest_quotes[symbol].ap
                    
                    gap = ((curr_price - prev_close) / prev_close) * 100
                    
                    if gap >= 0.1: # Visual tracking
                        status = "!! TARGET !!" if gap >= self.min_gap else "SCANNING"
                        print(f"{symbol:<10} | ${curr_price:<9.2f} | {gap:>7.2f}% | {status}")
                        if gap >= self.min_gap:
                            await self.execute_trailing_trade(symbol, curr_price)
                except: continue
        except Exception as e: print(f"Scan Error: {e}")

    async def execute_trailing_trade(self, symbol, price):
        try:
            acc = self.api.get_account()
            qty = (float(acc.cash) * self.risk_per_trade) // price
            if qty > 0:
                print(f"\n>>> [ENTRY] BUYING {symbol} AT ${price}")
                # 1. Market Buy
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc', extended_hours=True)
                
                # 2. Trailing Stop Order (The Magic Part)
                # This order will act as BOTH Stop Loss and Trailing Profit
                self.api.submit_order(
                    symbol=symbol, 
                    qty=qty, 
                    side='sell', 
                    type='trailing_stop', 
                    trail_percent=self.stop_loss_pct, # Starts as 2% SL
                    time_in_force='gtc', 
                    extended_hours=True
                )
                print(f">>> [PROTECTION] Trailing Stop Active (2.0% distance)\n")
        except Exception as e: print(f"Trade Error: {e}")

    async def start(self):
        while True:
            await self.get_stats()
            await asyncio.sleep(1) # Extra gap
            await self.run_hybrid_scanner()
            await asyncio.sleep(15) 

if __name__ == "__main__":
    asyncio.run(OmniQuantumAlpha().start())

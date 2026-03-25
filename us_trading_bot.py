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
        
        # --- Settings ---
        self.risk_per_trade = 0.20
        self.min_gap = 4.0          # Trigger Buy at 4%
        self.min_profit = 0.015     # Exit at 1.5% Profit
        self.stop_loss = 0.02       # Exit at 2% Loss
        self.max_price = 50.0
        self.min_volume_usd = 5000000  # [NEW] Min $5M liquidity to avoid "Dead" stocks
        self.scan_limit = 150 

    async def get_stats(self):
        try:
            acc = self.api.get_account()
            print("\n" + "="*60)
            print(f" HYBRID VOLATILITY SCANNER | {datetime.now().strftime('%H:%M:%S')}")
            print(f" EQUITY: ${acc.equity} | BUYING POWER: ${acc.buying_power}")
            print("="*60)
        except: pass

    async def run_hybrid_scanner(self):
        print(f"{'SYMBOL':<10} | {'PRICE':<10} | {'D-GAP%':<8} | {'1H-GAP%':<8} | {'STATUS'}")
        print("-" * 65)
        
        try:
            # 1. Fetch all active tradable stocks
            assets = self.api.list_assets(status='active', asset_class='us_equity')
            symbols = [a.symbol for a in assets if a.tradable and a.shortable]
            
            # 2. Get Snapshots for the first 1000 to filter liquidity
            snapshots = self.api.get_snapshots(symbols[:1000])
            
            volatile_pool = []
            for symbol, snap in snapshots.items():
                try:
                    price = snap.latest_quote.ap if hasattr(snap.latest_quote, 'ap') else snap.daily_bar.c
                    volume_usd = snap.daily_bar.v * price # Current Day Volume in USD
                    
                    # [FILTER] Price < $50 AND Liquidity > $5M
                    if 0 < price <= self.max_price and volume_usd >= self.min_volume_usd:
                        # [MEASURE] Volatility based on Daily Change
                        change = abs(snap.daily_bar.c - snap.prev_daily_bar.c) / snap.prev_daily_bar.c if snap.prev_daily_bar else 0
                        volatile_pool.append((symbol, change, price))
                except: continue
            
            # 3. SORT by Volatility (Highest Change first)
            volatile_pool.sort(key=lambda x: x[1], reverse=True)
            watchlist = [x[0] for x in volatile_pool[:self.scan_limit]]
            
            # 4. Precision Check for the Top 150
            all_daily_bars = self.api.get_bars(watchlist, '1Day', limit=2).df
            all_hourly_bars = self.api.get_bars(watchlist, '1Hour', limit=1).df
            latest_quotes = self.api.get_latest_quotes(watchlist)
            
            for symbol in watchlist:
                try:
                    d_bars = all_daily_bars[all_daily_bars.index == symbol]
                    h_bars = all_hourly_bars[all_hourly_bars.index == symbol]
                    
                    if len(d_bars) < 2 or h_bars.empty: continue
                    
                    prev_close = d_bars['close'].iloc[-2]
                    hour_open = h_bars['open'].iloc[-1]
                    curr_price = latest_quotes[symbol].askprice if hasattr(latest_quotes[symbol], 'askprice') else latest_quotes[symbol].ap
                    
                    if curr_price <= 0: continue

                    daily_gap = ((curr_price - prev_close) / prev_close) * 100
                    hourly_gap = ((curr_price - hour_open) / hour_open) * 100
                    
                    is_target = daily_gap >= self.min_gap or hourly_gap >= self.min_gap
                    
                    # Display threshold (1.5%)
                    if daily_gap >= 1.5 or hourly_gap >= 1.5:
                        status = "!! EXECUTE !!" if is_target else "ACTIVE MOVER"
                        print(f"{symbol:<10} | ${curr_price:<9.2f} | {daily_gap:>7.2f}% | {hourly_gap:>7.2f}% | {status}")

                        if is_target:
                            await self.execute_trade(symbol, curr_price)
                except: continue
        except Exception as e:
            print(f"Scan Error: {e}")

    async def execute_trade(self, symbol, price):
        try:
            acc = self.api.get_account()
            qty = (float(acc.cash) * self.risk_per_trade) // price
            if qty > 0:
                print(f"\n>>> [HYBRID] BUYING {symbol} AT ${price}")
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc', extended_hours=True)
                
                # Bracket protection
                tp = round(price * (1 + self.min_profit), 2)
                sl = round(price * (1 - self.stop_loss), 2)
                
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=tp, time_in_force='gtc', extended_hours=True)
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='stop', stop_price=sl, time_in_force='gtc', extended_hours=True)
                print(f">>> [OK] PROTECTED TRADE: TP ${tp} | SL ${sl}\n")
        except Exception as e:
            print(f"Trade Error: {e}")

    async def start(self):
        while True:
            await self.get_stats()
            await self.run_hybrid_scanner()
            await asyncio.sleep(15) 

if __name__ == "__main__":
    bot = OmniQuantumAlpha()
    asyncio.run(bot.start())

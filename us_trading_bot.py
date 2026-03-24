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
        self.stop_loss = 0.02
        self.max_price = 50.0
        self.scan_limit = 150 

    async def get_stats(self):
        try:
            acc = self.api.get_account()
            print("\n" + "="*60)
            print(f" SAFE AGGRESSIVE MONITOR | {datetime.now().strftime('%H:%M:%S')}")
            print(f" EQUITY: ${acc.equity} | POWER: ${acc.buying_power}")
            print("="*60)
        except Exception as e:
            print(f"Stats Error: {e}")

    async def run_hybrid_scanner(self):
        print(f"{'SYMBOL':<10} | {'PRICE':<10} | {'D-GAP%':<8} | {'1H-GAP%':<8} | {'STATUS'}")
        print("-" * 65)
        
        try:
            # Step 1: Filter active US equities
            assets = self.api.list_assets(status='active', asset_class='us_equity')
            symbols = [a.symbol for a in assets if a.tradable and a.shortable]
            
            # Step 2: Get snapshots to find volatile stocks
            snapshots = self.api.get_snapshots(symbols[:1000])
            
            volatile_pool = []
            for symbol, snap in snapshots.items():
                try:
                    # FIX: Correct way to access price in Alpaca Snapshots
                    price = snap.latest_quote.ap if hasattr(snap.latest_quote, 'ap') else snap.daily_bar.c
                    if 0 < price <= self.max_price:
                        change = abs(snap.daily_bar.c - snap.prev_daily_bar.c) / snap.prev_daily_bar.c if snap.prev_daily_bar else 0
                        volatile_pool.append((symbol, change, price))
                except: continue
            
            # Sort by volatility
            volatile_pool.sort(key=lambda x: x[1], reverse=True)
            watchlist = [x[0] for x in volatile_pool[:self.scan_limit]]
            
            # Batch request for precision
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
                    # FIX: Access ask price safely
                    curr_price = latest_quotes[symbol].askprice if hasattr(latest_quotes[symbol], 'askprice') else latest_quotes[symbol].ap
                    
                    if curr_price <= 0: continue

                    daily_gap = ((curr_price - prev_close) / prev_close) * 100
                    hourly_gap = ((curr_price - hour_open) / hour_open) * 100
                    
                    is_target = daily_gap >= self.min_gap or hourly_gap >= self.min_gap
                    
                    if daily_gap >= 1.5 or hourly_gap >= 1.5:
                        status = "!! EXECUTE !!" if is_target else "VOLATILE"
                        print(f"{symbol:<10} | ${curr_price:<9.2f} | {daily_gap:>7.2f}% | {hourly_gap:>7.2f}% | {status}")

                        if is_target:
                            await self.execute_trade(symbol, curr_price)
                except: continue
        except Exception as e:
            print(f"Detailed Scan Error: {e}")

    async def execute_trade(self, symbol, price):
        try:
            acc = self.api.get_account()
            qty = (float(acc.cash) * self.risk_per_trade) // price
            if qty > 0:
                print(f"\n>>> [ORDER] BUYING {symbol} AT ${price}")
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc', extended_hours=True)
                
                tp_price = round(price * (1 + self.min_profit), 2)
                sl_price = round(price * (1 - self.stop_loss), 2)
                
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='limit', limit_price=tp_price, time_in_force='gtc', extended_hours=True)
                self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='stop', stop_price=sl_price, time_in_force='gtc', extended_hours=True)
                print(f">>> [PROTECTION] TP: ${tp_price} | SL: ${sl_price}\n")
        except Exception as e:
            print(f"Order Execution Error: {e}")

    async def start(self):
        while True:
            await self.get_stats()
            await self.run_hybrid_scanner()
            await asyncio.sleep(15) 

if __name__ == "__main__":
    bot = OmniQuantumAlpha()
    asyncio.run(bot.start())

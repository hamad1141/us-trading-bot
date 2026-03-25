import os
import asyncio
import alpaca_trade_api as tradeapi
import numpy as np
import sys
from datetime import datetime

class BinanceBeastUS:
    def __init__(self):
        # API Configuration
        self.api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        self.base_url = "https://paper-api.alpaca.markets" 
        self.api = tradeapi.REST(self.api_key, self.secret_key, self.base_url, api_version='v2')
        
        # --- Strategy Settings ---
        self.mispricing_threshold = 0.018   
        self.rsi_buy_level = 13            
        self.stop_loss_pct = 1.5           
        self.min_volume_limit = 3000000    
        self.max_price = 50.0              
        self.max_assets = 50               
        self.risk_per_trade = 0.10         
        
    def calculate_rsi(self, series, period=14):
        if len(series) < period + 1: return 50
        delta = np.diff(series)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.mean(gain[-period:])
        avg_loss = np.mean(loss[-period:])
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    async def get_account_info(self):
        try:
            acc = self.api.get_account()
            print("\n" + "="*75)
            print(f"SYSTEM ACTIVE | RISK: 10% | TIME: {datetime.now().strftime('%H:%M:%S')}")
            print(f"CASH: ${acc.cash} | EQUITY: ${acc.equity}")
            print("="*75)
        except Exception as e:
            print(f"Connection Error: {e}")

    async def start_engine(self):
        print(f"{'SYMBOL':<10} | {'PRICE':<10} | {'GAP%':<8} | {'RSI':<6} | {'STATUS'}")
        print("-" * 75)
        
        while True:
            try:
                assets = self.api.list_assets(status='active', asset_class='us_equity')
                symbols = [a.symbol for a in assets if a.tradable and a.shortable]
                
                snapshots = self.api.get_snapshots(symbols[:1000])
                candidates = []
                
                for symbol, snap in snapshots.items():
                    try:
                        price = snap.latest_quote.ap if hasattr(snap.latest_quote, 'ap') and snap.latest_quote.ap > 0 else snap.daily_bar.c
                        bid = snap.latest_quote.bp if hasattr(snap.latest_quote, 'bp') else price
                        ask = snap.latest_quote.ap if hasattr(snap.latest_quote, 'ap') else price
                        volume_usd = snap.daily_bar.v * price
                        
                        if 0 < price <= self.max_price and volume_usd >= self.min_volume_limit:
                            spread = (ask - bid) / price
                            if spread > 0.0020: continue 
                            
                            vola = (snap.daily_bar.h - snap.daily_bar.l) / price
                            candidates.append((symbol, vola, price))
                    except Exception as e:
                        print(f"Snapshot Error {symbol}: {e}")
                        continue

                candidates.sort(key=lambda x: x[1], reverse=True)
                watchlist = [x[0] for x in candidates[:self.max_assets]]
                
                if not watchlist:
                    sys.stdout.write(f"\r[SCANNING] Monitoring market for $3M+ liquidity assets...")
                    sys.stdout.flush()
                else:
                    bars_15m = self.api.get_bars(watchlist, '15Min', limit=30).df
                    latest_quotes = self.api.get_latest_quotes(watchlist)

                    for symbol in watchlist:
                        try:
                            df = bars_15m[bars_15m.index == symbol]
                            if len(df) < 20: continue
                            
                            closes = df['close'].tolist()
                            avg_price = df['close'].mean()
                            curr_price = latest_quotes[symbol].askprice or latest_quotes[symbol].ap
                            
                            gap = (avg_price - curr_price) / avg_price
                            rsi = self.calculate_rsi(closes)
                            rsi_prev = self.calculate_rsi(closes[:-1])

                            cond_gap = gap >= self.mispricing_threshold
                            cond_rsi_low = rsi < self.rsi_buy_level
                            cond_rsi_up = rsi > rsi_prev

                            if gap > 0.005: 
                                status = "ENTRY_TRIGGER" if all([cond_gap, cond_rsi_low, cond_rsi_up]) else "WAITING"
                                print(f"{symbol:<10} | ${curr_price:<9.2f} | {gap*100:>7.2f}% | {rsi:>5.1f} | {status}")

                                if all([cond_gap, cond_rsi_low, cond_rsi_up]):
                                    await self.execute_trade(symbol, curr_price)
                        except Exception as e:
                            print(f"Symbol Error {symbol}: {e}")
                            continue
                
            except Exception as e:
                print(f"\nRuntime Error: {e}")
            
            await asyncio.sleep(20)

    async def execute_trade(self, symbol, price):
        try:
            pos = self.api.list_positions()
            if any(p.symbol == symbol for p in pos): return

            acc = self.api.get_account()
            available_cash = float(acc.cash)
            qty = (available_cash * self.risk_per_trade) // price
            
            if qty > 0:
                print(f"\n>>> [ORDER] BUY {symbol} AT ${price} | QTY: {qty}")
                self.api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc', extended_hours=True)
                
                self.api.submit_order(
                    symbol=symbol, qty=qty, side='sell', type='trailing_stop', 
                    trail_percent=self.stop_loss_pct, 
                    time_in_force='gtc', extended_hours=True
                )
                print(f">>> [TRAILING STOP] ACTIVE AT {self.stop_loss_pct}%\n")
        except Exception as e:
            print(f"Execution Error: {e}")

if __name__ == "__main__":
    bot = BinanceBeastUS()
    asyncio.run(bot.get_account_info())
    asyncio.run(bot.start_engine())

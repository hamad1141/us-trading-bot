import os
import asyncio
import alpaca_trade_api as tradeapi
import numpy as np
import sys
from datetime import datetime

class BinanceBeastUS:
    def __init__(self):
        # API Configuration
        self.api_key    = os.environ.get("ALPACA_API_KEY", "").strip()
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        self.base_url   = "https://paper-api.alpaca.markets"
        self.api = tradeapi.REST(self.api_key, self.secret_key, self.base_url, api_version='v2')

        # --- Optimized Strategy Settings ---
        self.mispricing_threshold = 0.018
        self.rsi_buy_level        = 13
        self.stop_loss_pct        = 1.5
        self.min_volume_limit     = 3000000
        self.max_price            = 50.0
        self.max_assets           = 50
        self.risk_per_trade       = 0.10  # 10% from Cash
        
    def calculate_rsi_wilder(self, series, period=14):
        if len(series) < period + 1: return 50
        delta = np.diff(np.array(series, dtype=float))
        gain  = np.where(delta > 0, delta, 0.0)
        loss  = np.where(delta < 0, -delta, 0.0)
        avg_gain = np.mean(gain[:period])
        avg_loss = np.mean(loss[:period])
        for i in range(period, len(gain)):
            avg_gain = (avg_gain * (period - 1) + gain[i]) / period
            avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    async def get_account_info(self):
        try:
            acc = self.api.get_account()
            print("\n" + "="*75)
            print(f"SYSTEM ACTIVE | MODE: PAPER | TIME: {datetime.now().strftime('%H:%M:%S')}")
            print(f"CASH: ${acc.cash} | EQUITY: ${acc.equity}")
            print("="*75)
        except Exception as e:
            print(f"Connection Error: {e}")

    async def execute_trade(self, symbol, price):
        try:
            # Check for existing positions
            positions = self.api.list_positions()
            if any(p.symbol == symbol for p in positions): return

            # Calculate Quantity based on Cash (As requested)
            acc = self.api.get_account()
            available_cash = float(acc.cash)
            qty = int((available_cash * self.risk_per_trade) // price)

            if qty <= 0:
                print(f"![SKIP] {symbol}: Insufficient cash to trade 10%")
                return

            print(f"\n>>> [ORDER] BUY {symbol} AT ${price:.2f} | QTY: {qty}")
            
            # Entry Order
            self.api.submit_order(
                symbol=symbol, qty=qty, side='buy',
                type='market', time_in_force='day', extended_hours=True
            )
            
            # Trailing Stop Protection
            self.api.submit_order(
                symbol=symbol, qty=qty, side='sell',
                type='trailing_stop', trail_percent=self.stop_loss_pct,
                time_in_force='gtc', extended_hours=True
            )
            print(f">>> [TRAILING STOP] ACTIVE AT {self.stop_loss_pct}%\n")

        except Exception as e:
            print(f"Execution Error {symbol}: {e}")

    async def start_engine(self):
        print(f"{'SYMBOL':<10} | {'PRICE':<10} | {'GAP%':<8} | {'RSI':<6} | {'STATUS'}")
        print("-" * 75)

        while True:
            try:
                # 1. Market Status Check
                clock = self.api.get_clock()
                if not clock.is_open and not clock.next_open:
                    sys.stdout.write("\r[IDLE] Market is closed. Waiting for next session...")
                    sys.stdout.flush()
                    await asyncio.sleep(60)
                    continue

                # 2. Filtering Assets (optimized limit to avoid rate limits)
                assets  = self.api.list_assets(status='active', asset_class='us_equity')
                symbols = [a.symbol for a in assets if a.tradable and a.shortable][:800]
                snapshots = self.api.get_snapshots(symbols)
                
                candidates = []
                for symbol, snap in snapshots.items():
                    try:
                        if not snap or not snap.daily_bar: continue
                        price = snap.latest_quote.ap if hasattr(snap.latest_quote, 'ap') and snap.latest_quote.ap > 0 else snap.daily_bar.c
                        volume_usd = snap.daily_bar.v * price

                        if 0 < price <= self.max_price and volume_usd >= self.min_volume_limit:
                            vola = (snap.daily_bar.h - snap.daily_bar.l) / price
                            candidates.append((symbol, vola, price))
                    except Exception as e:
                        print(f"Snapshot Error {symbol}: {e}")
                        continue

                # 3. Process Watchlist
                candidates.sort(key=lambda x: x[1], reverse=True)
                watchlist = [x[0] for x in candidates[:self.max_assets]]

                if watchlist:
                    bars_df = self.api.get_bars(watchlist, '15Min', limit=30).df
                    latest_quotes = self.api.get_latest_quotes(watchlist)

                    for symbol in watchlist:
                        try:
                            df = bars_df[bars_df.index.get_level_values('symbol') == symbol] if 'symbol' in bars_df.index.names else bars_df[bars_df.index == symbol]
                            if len(df) < 20: continue

                            closes = df['close'].tolist()
                            avg_price = df['close'].mean()
                            q = latest_quotes[symbol]
                            curr_price = getattr(q, 'ap', None) or getattr(q, 'askprice', None) or closes[-1]

                            gap = (avg_price - curr_price) / avg_price
                            rsi = self.calculate_rsi_wilder(closes)
                            rsi_prev = self.calculate_rsi_wilder(closes[:-1])

                            # Trigger Logic
                            if all([gap >= self.mispricing_threshold, rsi < self.rsi_buy_level, rsi > rsi_prev]):
                                print(f"{symbol:<10} | ${curr_price:<9.2f} | {gap*100:>7.2f}% | {rsi:>5.1f} | !! ENTRY !!")
                                await self.execute_trade(symbol, curr_price)
                            elif gap > 0.005:
                                print(f"{symbol:<10} | ${curr_price:<9.2f} | {gap*100:>7.2f}% | {rsi:>5.1f} | SCANNING")
                        except Exception as e:
                            print(f"Symbol Error {symbol}: {e}")
                            continue

            except Exception as e:
                print(f"\nRuntime Error: {e}")

            await asyncio.sleep(15) # Optimized sleep for faster scanning

if __name__ == "__main__":
    bot = BinanceBeastUS()
    asyncio.run(bot.get_account_info())
    asyncio.run(bot.start_engine())

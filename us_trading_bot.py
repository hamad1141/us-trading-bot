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

        # --- Strategy Settings (Optimized for US Stocks) ---
        self.mispricing_threshold = 0.018   # 1.8% Gap from Mean
        self.rsi_buy_level        = 25      # Balanced RSI (Increased from 13 to 25)
        self.min_volume_limit     = 3000000 # $3M Minimum Daily Volume
        self.max_price            = 50.0    # Price Cap
        
        # --- Risk & Portfolio Management ---
        self.risk_per_trade       = 0.10    # 10% of Total Equity per trade
        self.max_parallel_trades  = 10      # Max 10 simultaneous positions (100% Utility)
        
        # --- Advanced Exit Logic (Binance Style Trailing) ---
        self.min_profit_trigger   = 0.012   # Start trailing after 1.2% profit
        self.trailing_percent     = 0.005   # Sell if drops 0.5% from peak
        self.stop_loss_pct        = 0.015   # 1.5% Hard Stop Loss
        
        self.current_trades = {}            # {SYMBOL: ENTRY_PRICE}
        self.peak_prices = {}               # {SYMBOL: MAX_PRICE_SEEN}

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

    async def update_positions(self):
        """Initial sync with Alpaca to recover any open trades"""
        try:
            positions = self.api.list_positions()
            self.current_trades = {p.symbol: float(p.avg_entry_price) for p in positions}
            for p in positions:
                if p.symbol not in self.peak_prices:
                    self.peak_prices[p.symbol] = float(p.current_price)
            if self.current_trades:
                print(f">>> Recovered {len(self.current_trades)} active positions.")
        except Exception as e:
            print(f"Position Sync Error: {e}")

    async def start_engine(self):
        print(f"\n" + "="*60)
        print(f"BEAST US v12.2 | RSI: {self.rsi_buy_level} | SL: {self.stop_loss_pct*100}%")
        print(f"LIQUIDITY MODE: 10 POSITIONS x 10% EQUITY")
        print("="*60 + "\n")
        
        await self.update_positions()
        
        while True:
            current_time = datetime.now().strftime('%H:%M:%S')
            try:
                # 1. Monitor Exits (Trailing Stop & SL)
                await self.monitor_exits()

                # 2. Market Scanning
                assets = self.api.list_assets(status='active', asset_class='us_equity')
                all_symbols = [a.symbol for a in assets if a.tradable and a.shortable]
                
                # Scan top 500 for volatility
                test_symbols = all_symbols[:500]
                snapshots = self.api.get_snapshots(test_symbols)
                candidates = []
                
                for symbol, snap in snapshots.items():
                    try:
                        if snap is None or snap.latest_quote is None or snap.daily_bar is None:
                            continue
                        price = snap.latest_quote.ap if (snap.latest_quote.ap and snap.latest_quote.ap > 0) else snap.daily_bar.c
                        volume_usd = snap.daily_bar.v * price
                        
                        if 0 < price <= self.max_price and volume_usd >= self.min_volume_limit:
                            vola = (snap.daily_bar.h - snap.daily_bar.l) / price
                            candidates.append((symbol, vola, price))
                    except: continue

                print(f"[LOOP {current_time}] Positions: {len(self.current_trades)}/10 | Qualified Assets: {len(candidates)}")

                # 3. Entry Logic (If we have empty slots)
                if len(self.current_trades) < self.max_parallel_trades:
                    candidates.sort(key=lambda x: x[1], reverse=True)
                    watchlist = [x[0] for x in candidates[:25] if x[0] not in self.current_trades]
                    
                    if watchlist:
                        bars_df = self.api.get_bars(watchlist, '15Min', limit=30).df
                        latest_quotes = self.api.get_latest_quotes(watchlist)

                        for symbol in watchlist:
                            if len(self.current_trades) >= self.max_parallel_trades: break
                            try:
                                # Multi-index support
                                if symbol in bars_df.index.get_level_values(0):
                                    df = bars_df.xs(symbol)
                                else: continue

                                if len(df) < 20: continue
                                closes = df['close'].tolist()
                                avg_price = df['close'].mean()
                                q = latest_quotes.get(symbol)
                                if not q: continue
                                
                                curr_price = q.askprice or q.ap or closes[-1]
                                gap = (avg_price - curr_price) / avg_price
                                rsi = self.calculate_rsi(closes)
                                rsi_prev = self.calculate_rsi(closes[:-1])

                                # Log potential setups
                                if gap > 0.008:
                                    is_buy = all([gap >= self.mispricing_threshold, rsi < self.rsi_buy_level, rsi > rsi_prev])
                                    status = "!! BUY !!" if is_buy else "WATCHING"
                                    print(f"{symbol:<8} | Gap:{gap*100:>5.2f}% | RSI:{rsi:>5.1f} | {status}")
                                    
                                    if is_buy:
                                        await self.execute_buy(symbol, curr_price)
                            except: continue

            except Exception as e:
                print(f"Runtime Error: {e}")
            
            await asyncio.sleep(20)

    async def monitor_exits(self):
        try:
            positions = self.api.list_positions()
            for p in positions:
                symbol = p.symbol
                entry_p = float(p.avg_entry_price)
                curr_p = float(p.current_price)
                qty = int(p.qty)
                
                if symbol not in self.peak_prices or curr_p > self.peak_prices[symbol]:
                    self.peak_prices[symbol] = curr_p
                
                profit = (curr_p - entry_p) / entry_p
                
                # Hard Stop Loss
                stop_hit = curr_p <= (entry_p * (1 - self.stop_loss_pct))
                
                # Trailing Stop Logic
                trail_hit = (profit >= self.min_profit_trigger and 
                             curr_p <= (self.peak_prices[symbol] * (1 - self.trailing_percent)))

                if stop_hit or trail_hit:
                    reason = "STOP_LOSS" if stop_hit else "TRAILING_STOP"
                    print(f"\n>>> [SELL] {symbol} | Profit: {profit:.2%} | Reason: {reason}")
                    self.api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
                    self.current_trades.pop(symbol, None)
                    self.peak_prices.pop(symbol, None)
        except: pass

    async def execute_buy(self, symbol, price):
        try:
            acc = self.api.get_account()
            equity = float(acc.equity)
            cash = float(acc.cash)
            
            # Allocation: 10% of total portfolio equity
            order_value = equity * self.risk_per_trade
            
            if cash >= order_value:
                qty = int(order_value // price)
                if qty > 0:
                    print(f"\n>>> [ORDER] BUY {symbol} | Value: ${order_value:.2f} | Qty: {qty}")
                    self.api.submit_order(
                        symbol=symbol, qty=qty, side='buy', 
                        type='market', time_in_force='gtc'
                    )
                    self.current_trades[symbol] = price
                    self.peak_prices[symbol] = price
            else:
                print(f">>> [INSUFFICIENT CASH] Needed ${order_value:.2f} for {symbol}")
        except Exception as e:
            print(f"Buy Order Error {symbol}: {e}")

if __name__ == "__main__":
    bot = BinanceBeastUS()
    asyncio.run(bot.start_engine())

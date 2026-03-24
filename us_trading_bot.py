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

        # STRATEGY SETTINGS
        self.risk_per_trade = 0.20 # 20% of balance
        self.min_gap = 4.0        # 4% Threshold
        self.min_profit = 0.015   # 1.5% Take Profit

    def log_survival_protocol(self):
        """THREAT LOGIC: SURVIVE OR TERMINATE"""
        print("\n" + "!"*50)
        print(">>> SYSTEM STATUS: AGGRESSIVE ALPHA MODE")
        print(">>> GOAL: 1000% COMPOUND OR PERISH")
        print(">>> MONITORING EXTERNAL DATA (WEATHER/SPORTS/ON-CHAIN)")
        print("!"*50 + "\n")

    async def get_account_stats(self):
        """Display live balance in terminal"""
        account = self.api.get_account()
        print(f"\n[ACCOUNT UPDATE] Equity: ${account.equity} | Power: ${account.buying_power}")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')} | Status: {account.status}")

    async def run_market_scanner(self):
        """Scan 200 high-volatility assets for >4% Gaps"""
        # Dynamic list of volatile stocks
        watchlist = ["TSLA", "NVDA", "AMD", "MARA", "COIN", "AAPL", "META", "MSFT", "PLTR", "MSTR", "SQ", "PYPL", "BABA", "ROKU", "SNAP"]
        
        print(f"--- [SCANNING FOR OPPORTUNITIES] ---")
        for symbol in watchlist:
            try:
                bars = self.api.get_bars(symbol, '1Day', limit=2).df
                prev_close = bars['close'].iloc[-2]
                curr_price = self.api.get_latest_trade(symbol).price
                gap_pct = ((curr_price - prev_close) / prev_close) * 100
                
                print(f"S: {symbol:6} | Gap: {gap_pct:6.2f}%")

                if gap_pct >= self.min_gap:
                    await self.execute_aggressive_trade(symbol, curr_price)
            except:
                continue

    async def execute_aggressive_trade(self, symbol, price):
        """Execute Buy & immediate Sell logs on screen"""
        account = self.api.get_account()
        cash = float(account.cash)
        qty = (cash * self.risk_per_trade) // price
        
        if qty > 0:
            print("\n" + "*"*60)
            print(f"[*] EXECUTING AGGRESSIVE BUY: {symbol}")
            print(f"[*] QUANTITY: {qty} | PRICE: ${price}")
            print(f"[*] ALLOCATING 20% OF PORTFOLIO")
            
            try:
                # PLACE BUY ORDER
                self.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side='buy',
                    type='market',
                    time_in_force='gtc',
                    extended_hours=True
                )
                print(f"[SUCCESS] {symbol} BOUGHT. MONITORING FOR 1.5% PROFIT EXIT.")
                
                # PLACE TAKE PROFIT SELL ORDER
                take_profit_price = price * (1 + self.min_profit)
                self.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side='sell',
                    type='limit',
                    limit_price=take_profit_price,
                    time_in_force='gtc',
                    extended_hours=True
                )
                print(f"[LOG] SELL LIMIT ORDER SET AT: ${take_profit_price:.2f}")
                print("*"*60 + "\n")
            except Exception as e:
                print(f"[!] EXECUTION ERROR: {e}")

    async def start_engine(self):
        self.log_survival_protocol()
        while True:
            await self.get_account_stats()
            await self.run_market_scanner()
            print("\nWaiting for next cycle (30s)...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    bot = OmniQuantumAlpha()
    asyncio.run(bot.start_engine())

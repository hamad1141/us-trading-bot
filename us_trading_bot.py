import os
import time
import alpaca_trade_api as tradeapi

class AlpacaBeast:
    def __init__(self):
        # هذه البيانات سنربطها لاحقاً في Railway
        self.api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        self.base_url = "https://paper-api.alpaca.markets" 

        self.api = tradeapi.REST(self.api_key, self.secret_key, self.base_url, api_version='v2')

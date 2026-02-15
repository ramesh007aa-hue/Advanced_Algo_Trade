"""
Order placement via Angel One API.
Used only when LIVE_TRADING is True in config; main.py otherwise only updates
in-memory position (paper trading).
"""
# Angel One placeOrder expects: variety, tradingsymbol, symboltoken, transactiontype,
# exchange (NFO for options), ordertype, producttype, duration, quantity (and optional price)


class OrderManager:

    def __init__(self, api):
        self.api = api

    def _order_params(self, symbol, token, qty, transaction_type):
        """Build order dict for NFO options (INTRADAY, MARKET)."""
        return {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": transaction_type,
            "exchange": "NFO",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "quantity": qty,
        }

    def buy(self, symbol, token, qty):
        """Place BUY order. Returns order_id from API or None."""
        order = self._order_params(symbol, token, qty, "BUY")
        return self.api.placeOrder(order)

    def sell(self, symbol, token, qty):
        """Place SELL order. Returns order_id from API or None."""
        order = self._order_params(symbol, token, qty, "SELL")
        return self.api.placeOrder(order)

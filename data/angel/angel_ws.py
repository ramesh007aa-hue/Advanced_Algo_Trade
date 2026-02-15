from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from data.cache.market_cache import MARKET
import time


class AngelWS:
    """
    WebSocket client for Angel One with improved error handling and reconnection logic
    """

    def __init__(self, jwt, api_key, client, feed):
        """
        Initialize WebSocket connection

        Args:
            jwt: JWT authentication token
            api_key: Angel One API key
            client: Client code
            feed: Feed token
        """
        self.jwt = jwt
        self.api_key = api_key
        self.client = client
        self.feed = feed
        self.ws = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

    def on_open(self, ws):
        """Callback when WebSocket connection opens"""
        print("WebSocket connection established")
        self.is_connected = True
        self.reconnect_attempts = 0

    def on_data(self, ws, message):
        """
        Callback when data is received from WebSocket

        Args:
            ws: WebSocket instance
            message: Market data message
        """
        try:
            token = str(message.get("token", ""))

            # Nifty Spot - Token: 26000
            if token == "26000":
                price = message.get("last_traded_price", 0) / 100
                MARKET.update_spot(price)

            # India VIX - Token: 26017
            elif token == "26017":
                price = message.get("last_traded_price", 0) / 100
                MARKET.update_vix(price)

            # Option contracts
            else:
                MARKET.update_option(token, message)

        except Exception as e:
            print("Error processing WebSocket message:", e)

    def on_error(self, ws, error):
        """Callback when an error occurs"""
        print("WebSocket error:", error)
        self.is_connected = False

    def on_close(self, ws, close_status_code, close_msg):
        """Callback when WebSocket connection closes"""
        print(f"WebSocket closed - Code: {close_status_code}, Message: {close_msg}")
        self.is_connected = False

        # Auto-reconnect logic
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            print(
                f"Attempting reconnect "
                f"({self.reconnect_attempts}/{self.max_reconnect_attempts})..."
            )
            time.sleep(5)
            try:
                self.connect()
            except Exception as e:
                print("Reconnect failed:", e)

    def connect(self):
        """Initialize and connect WebSocket"""
        try:
            self.ws = SmartWebSocketV2(
                auth_token=self.jwt,
                api_key=self.api_key,
                client_code=self.client,
                feed_token=self.feed
            )

            self.ws.on_open = self.on_open
            self.ws.on_data = self.on_data
            self.ws.on_error = self.on_error
            self.ws.on_close = self.on_close

            print("Initiating WebSocket connection...")
            self.ws.connect()

        except Exception as e:
            print("Failed to connect WebSocket:", e)
            raise

    def disconnect(self):
        """Gracefully disconnect WebSocket"""
        try:
            if self.ws and self.is_connected:
                print("Disconnecting WebSocket...")
                self.ws.close()
                self.is_connected = False
                print("WebSocket disconnected successfully")
        except Exception as e:
            print("Error during WebSocket disconnect:", e)

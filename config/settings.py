# Index (standardized per spec: NIFTY, BANKNIFTY)
INDEX = "NIFTY"

# Dynamic risk (per spec)
BASE_RISK = 0.01
TRAIL_FACTOR = 0.5
DECAY_THRESHOLD = 0.6
PARTICIPATION_STRONG = 0.65

# Market hours (IST) per spec: 9:20 AM - 3:28 PM
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 20
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 28

# VIX regime thresholds (per spec: ULTRA_LOW, NORMAL_LOW, SPIKING, PANIC)
VIX_ULTRA_LOW = 12
VIX_NORMAL_LOW = 13
VIX_SPIKING = 14.5
VIX_PANIC = 17

# Adaptive AI confidence threshold by VIX regime (per spec: 75% ULTRA_LOW to 55% PANIC)
CONFIDENCE_ULTRA_LOW = 75
CONFIDENCE_NORMAL_LOW = 70
CONFIDENCE_SPIKING = 60
CONFIDENCE_PANIC = 55
CONFIDENCE_FALLBACK = 50  # on AI failure

# Decision interval (seconds) per spec: e.g. 90s high vol, 240s low volume
DECISION_INTERVAL_HIGH_VOL = 90
DECISION_INTERVAL_LOW_VOL = 240
OPENING_VOLATILITY_THRESHOLD_PCT = 10  # +10% threshold penalty in opening

# Strike alignment (per spec: Delta >= 0.25, IV <= 25%)
STRIKE_DELTA_MIN = 0.25
STRIKE_IV_MAX_PCT = 25

# Circuit breaker
MAX_TRADES = 1000
MAX_DAILY_LOSS = 300000
MIN_WIN_RATE_PCT = 40  # block if historical win rate in current conditions < 40%

# Angel One credentials (replace with env vars in production)
API_KEY = "CPV4voXH"
CLIENT_ID = "ARDA1046"
PASSWORD = "4753"
TOTP_SECRET = "DM4A6M42QQVOAWI4GT4JN6FV7I"

LOT_SIZE = 65

# When False: no broker orders are placed; only in-memory position (paper trading).
# When True: main.py places real orders via OrderManager (option symbol/token resolved from strike).
LIVE_TRADING = False

# Option expiry for NFO (DDMMMYY e.g. "20FEB25"). If None, next Thursday is used.
OPTION_EXPIRY_DDMMMYY = None

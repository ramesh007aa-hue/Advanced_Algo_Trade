from data.cache.market_cache import MARKET


class VolatilityEngine:

    def check(self, prev):

        if prev is None:
            return "UNKNOWN"

        if MARKET.vix > prev:
            return "SUPPORTIVE"

        return "WEAK"

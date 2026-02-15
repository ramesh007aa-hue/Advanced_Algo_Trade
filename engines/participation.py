from data.cache.market_cache import MARKET


class ParticipationEngine:

    def score(self):

        if not MARKET.heavy:
            return 0

        bullish = 0
        for p in MARKET.heavy.values():
            if p > 0:
                bullish += 1

        return bullish / len(MARKET.heavy)

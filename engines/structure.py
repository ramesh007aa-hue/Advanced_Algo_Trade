class StructureEngine:

    def vwap(self, prices):
        return sum(prices[-20:]) / 20

    def bullish(self, price, vwap):
        return price > vwap

    def bearish(self, price, vwap):
        return price < vwap

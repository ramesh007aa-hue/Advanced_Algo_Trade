class ContextEngine:

    def detect(self, prices):

        if len(prices) < 30:
            return "WAIT"

        m = prices[-1] - prices[-20]

        if m > 40:
            return "UPTREND"
        elif m < -40:
            return "DOWNTREND"

        return "RANGE"

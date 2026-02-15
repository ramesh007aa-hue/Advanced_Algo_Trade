class DecayEngine:

    def allow(self, prices):

        if len(prices) < 10:
            return False

        impulse = abs(prices[-1] - prices[-5])

        return impulse > 20

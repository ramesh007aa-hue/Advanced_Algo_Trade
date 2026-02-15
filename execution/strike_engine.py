from execution.greek_engine import GreekEngine


class StrikeEngine:

    def __init__(self):
        self.greeks = GreekEngine()

    def select(self, spot, context, momentum):

        gamma = self.greeks.gamma_mode(context, momentum)

        if gamma == "HIGH":
            strike = round(spot / 50) * 50  # ATM

        else:
            strike = round((spot - 50) / 50) * 50  # ITM bias

        return strike

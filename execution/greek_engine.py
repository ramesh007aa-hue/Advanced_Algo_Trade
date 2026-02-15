class GreekEngine:
    """
    Fast proxy Greeks.
    No Black-Scholes.
    Real-time friendly.
    """

    def delta_zone(self, spot, strike):

        diff = abs(spot - strike)

        if diff <= 50:
            return "ATM"

        elif diff <= 150:
            return "NEAR"

        return "FAR"

    def gamma_mode(self, context, momentum):

        if context == "UPTREND" and momentum > 40:
            return "HIGH"

        return "NORMAL"

    def theta_risk(self, time_factor):

        if time_factor > 0.7:
            return "HIGH"

        return "LOW"

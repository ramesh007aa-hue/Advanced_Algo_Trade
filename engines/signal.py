class SignalEngine:

    def generate(
        self,
        context,
        participation,
        volatility,
        decay,
        bull,
        bear
    ):

        if (
            context == "UPTREND"
            and participation > 0.6
            and volatility == "SUPPORTIVE"
            and decay and bull
        ):
            return "BUY"

        if (
            context == "DOWNTREND"
            and participation < 0.4
            and volatility == "SUPPORTIVE"
            and decay and bear
        ):
            return "SELL"

        return None

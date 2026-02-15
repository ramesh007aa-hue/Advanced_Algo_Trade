class AngelSubscribe:

    def __init__(self, ws):
        self.ws = ws

    def core(self):
        print("Subscribing to core data...")
        # SmartAPI subscribe expects token_list as list of dicts:
        # [{"exchangeType": 1, "tokens": ["26000", "26017", ...]}]
        # exchangeType: 1 = nse_cm, 2 = nse_fo
        token_list = [
            {
                "exchangeType": 1,  # nse_cm (Nifty spot, India VIX, stocks)
                "tokens": [
                    "26000",   # Nifty spot
                    "26017",   # India VIX
                    "2885",
                    "1333",
                    "4963",
                    "1594",
                    "11536",
                ],
            },
        ]

        self.ws.subscribe(
            correlation_id="core",
            mode=1,  # LTP
            token_list=token_list,
        )

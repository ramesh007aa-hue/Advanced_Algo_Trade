class PositionSizer:

    def __init__(self, capital=20000):
        self.capital = capital

    def size(self, risk_pct, stop_distance, lot_size):

        risk_amount = self.capital * risk_pct

        qty = risk_amount / stop_distance

        # round to lot
        qty = int(qty / lot_size) * lot_size

        if qty < lot_size:
            qty = lot_size

        return qty

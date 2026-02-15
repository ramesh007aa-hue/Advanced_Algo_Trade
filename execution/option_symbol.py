"""
Resolve NFO option tradingsymbol and symboltoken from strike and expiry.
Uses Angel One searchScrip API. Format: NIFTY + DD + MMM + YY + strike + CE/PE
e.g. NIFTY20FEB2524000CE
"""
from datetime import datetime, timedelta


def next_thursday_ddmmyy():
    """Next Thursday as DDMMMYY (e.g. 20FEB25). Nifty weekly expires Thursday."""
    today = datetime.now().date()
    # weekday: Monday=0, Thursday=3
    days_ahead = (3 - today.weekday()) % 7
    if days_ahead == 0 and datetime.now().hour >= 15:
        days_ahead = 7  # same-day expiry passed, use next week
    expiry = today + timedelta(days=days_ahead)
    return expiry.strftime("%d%b%y").upper()  # 20FEB25


def build_option_symbol(index, strike, ce_pe, expiry_ddmmyy):
    """Build NFO option symbol: INDEX + DDMMMYY + strike + CE/PE. Strike as 5 digits for Nifty."""
    strike_str = str(int(strike)).zfill(5)  # 24000
    return f"{index}{expiry_ddmmyy}{strike_str}{ce_pe}"


def get_option_symbol_token(api, index, strike, ce_pe, expiry_ddmmyy=None):
    """
    Resolve (tradingsymbol, symboltoken) for NFO option via searchScrip.
    api: SmartConnect instance.
    index: e.g. "NIFTY"
    strike: int, e.g. 24000
    ce_pe: "CE" or "PE"
    expiry_ddmmyy: e.g. "20FEB25" or None for next Thursday.
    Returns (tradingsymbol, symboltoken) or (None, None) on failure.
    """
    if expiry_ddmmyy is None:
        expiry_ddmmyy = next_thursday_ddmmyy()
    symbol = build_option_symbol(index, strike, ce_pe, expiry_ddmmyy)
    try:
        result = api.searchScrip("NFO", symbol)
        if not result or not result.get("status") or not result.get("data"):
            return None, None
        data = result["data"]
        # Prefer exact tradingsymbol match
        for item in data:
            if item.get("tradingsymbol") == symbol:
                return item["tradingsymbol"], str(item["symboltoken"])
        # Else first match (same strike/CE-PE)
        first = data[0]
        return first["tradingsymbol"], str(first["symboltoken"])
    except Exception:
        return None, None

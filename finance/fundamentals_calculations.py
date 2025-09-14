import pandas as pd


def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    df = pd.DataFrame(prices, columns=['timestamp', 'open', 'high', 'low', 'close'])
    df['delta'] = df['close'].diff()

    df['gain'] = df['delta'].apply(lambda x: x if x > 0 else 0)
    df['loss'] = df['delta'].apply(lambda x: -x if x < 0 else 0)

    avg_gain = df['gain'].rolling(window=period).mean()
    avg_loss = df['loss'].rolling(window=period).mean()

    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df['rsi'].iloc[-1]


def calculate_fair_price_fast(fundamentals):
    if fundamentals is None:
        return None
    if fundamentals.eps_forward and fundamentals.forward_pe:
        return fundamentals.eps_forward * fundamentals.forward_pe
    return None


def calculate_ebit(fundamentals):
    if fundamentals is None:
        return None
    ebit = 0
    amortization = 0
    if fundamentals.total_revenue and fundamentals.operating_margins and fundamentals.ebitda:
        ebit = fundamentals.total_revenue * fundamentals.operating_margins
        amortization = fundamentals.ebitda - ebit
    return ebit, amortization


def debt_to_equity(fundamentals):
    equity = fundamentals.market_cap - fundamentals.total_debt + fundamentals.total_cash
    return fundamentals.total_debt/equity


def calculate_cogs(fundamentals):
    if fundamentals is None:
        return None
    gm_percent = fundamentals.gross_margins
    revenue = fundamentals.total_revenue
    gm_value = revenue * gm_percent
    cogs = revenue - gm_value

    return cogs, gm_value


"""かぶミニ戦略を検証するための最小バックテスト基盤。"""
from rakuten_config import DEFAULT_CAPITAL, DEFAULT_SPREAD_RATE, DEFAULT_TAX_RATE


def run_backtest(data, capital=DEFAULT_CAPITAL, spread_rate=DEFAULT_SPREAD_RATE, tax_rate=DEFAULT_TAX_RATE):
    close = data["Close"].dropna().astype(float)
    ma5, ma20 = close.rolling(5).mean(), close.rolling(20).mean()
    cash, shares, entry_cost, trades = float(capital), 0, 0.0, []
    for index in range(1, len(close)):
        crossed_up = ma5.iloc[index] > ma20.iloc[index] and ma5.iloc[index - 1] <= ma20.iloc[index - 1]
        crossed_down = ma5.iloc[index] < ma20.iloc[index] and ma5.iloc[index - 1] >= ma20.iloc[index - 1]
        quote = close.iloc[index]
        if shares == 0 and crossed_up:
            buy_price = quote * (1 + spread_rate)
            shares, entry_cost = int(cash // buy_price), int(cash // buy_price) * buy_price
            cash -= entry_cost
        elif shares > 0 and crossed_down:
            proceeds = shares * quote * (1 - spread_rate)
            profit, tax = proceeds - entry_cost, max(proceeds - entry_cost, 0) * tax_rate
            cash += proceeds - tax
            trades.append({"date": index, "shares": shares, "profit_before_tax": profit, "tax": tax})
            shares, entry_cost = 0, 0.0
    open_value = shares * close.iloc[-1] * (1 - spread_rate) if len(close) else 0
    open_profit = open_value - entry_cost if shares else 0
    final_value = cash + open_value - max(open_profit, 0) * tax_rate
    return {"initial_capital": float(capital), "final_value": final_value, "return_rate": (final_value / float(capital) - 1) * 100 if capital else 0, "trade_count": len(trades), "open_shares": shares, "trades": trades}


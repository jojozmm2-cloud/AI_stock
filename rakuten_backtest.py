"""かぶミニ戦略を検証するための最小バックテスト基盤。"""
from rakuten_config import DEFAULT_CAPITAL, DEFAULT_SPREAD_RATE, DEFAULT_TAX_RATE


def run_backtest(data, capital=DEFAULT_CAPITAL, spread_rate=DEFAULT_SPREAD_RATE, tax_rate=DEFAULT_TAX_RATE):
    close = data["Close"].dropna().astype(float)
    ma5, ma20 = close.rolling(5).mean(), close.rolling(20).mean()
    cash, shares, entry_cost, trades, equity_curve = float(capital), 0, 0.0, [], []
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
        equity_curve.append(cash + shares * quote * (1 - spread_rate))
    open_value = shares * close.iloc[-1] * (1 - spread_rate) if len(close) else 0
    open_profit = open_value - entry_cost if shares else 0
    final_value = cash + open_value - max(open_profit, 0) * tax_rate
    peak, max_drawdown = float(capital), 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            max_drawdown = max(max_drawdown, (peak - value) / peak * 100)
    wins = sum(item["profit_before_tax"] > 0 for item in trades)
    return {"initial_capital": float(capital), "final_value": final_value, "return_rate": (final_value / float(capital) - 1) * 100 if capital else 0, "trade_count": len(trades), "win_rate": wins / len(trades) * 100 if trades else 0, "max_drawdown": max_drawdown, "open_shares": shares, "trades": trades}


def backtest_symbol(code, period="1y", capital=DEFAULT_CAPITAL):
    import yfinance as yf
    from rakuten_market_data import ensure_recent_daily_data

    data = yf.Ticker(code).history(period=period, interval="1d", auto_adjust=True)
    data = data.dropna(subset=["Close"])
    data_time = ensure_recent_daily_data(data)
    result = run_backtest(data, capital=capital)
    result.update({"code": code, "start_date": str(data.index[0].date()), "end_date": str(data_time.date())})
    return result


def create_backtest_embed(results):
    fields = []
    for item in sorted(results, key=lambda row: row["return_rate"], reverse=True)[:10]:
        fields.append({"name": item["code"].replace(".T", ""), "value": f"最終資産 {item['final_value']:,.0f}円 / 損益 {item['return_rate']:+.2f}%\n取引 {item['trade_count']}回 / 勝率 {item['win_rate']:.1f}% / 最大下落 {item['max_drawdown']:.2f}%", "inline": False})
    return {"title": "楽天かぶミニ バックテスト", "description": "5日線と20日線の交差を使った初期検証です。0.22%スプレッドと利益への税を反映しています。", "color": 0xBF0000, "fields": fields, "footer": {"text": "過去の結果は将来の利益を保証しません。"}}

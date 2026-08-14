"""かぶミニ戦略を検証するための最小バックテスト基盤。"""
from rakuten_config import DEFAULT_CAPITAL, DEFAULT_SPREAD_RATE, DEFAULT_TAX_RATE


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    relative_strength = gain / loss.replace(0, float("nan"))
    return (100 - 100 / (1 + relative_strength)).fillna(50)


def run_one_week_backtest(
    data,
    capital=DEFAULT_CAPITAL,
    spread_rate=DEFAULT_SPREAD_RATE,
    tax_rate=DEFAULT_TAX_RATE,
    risk_rate=0.01,
    base_holding_days=5,
    max_holding_days=10,
):
    """3万円・基本5営業日、上昇条件が続く場合のみ最長10日保有する。"""
    frame = data.dropna(subset=["High", "Low", "Close"]).copy()
    if "Open" not in frame:
        frame["Open"] = frame["Close"]
    close = frame["Close"].astype(float)
    high = frame["High"].astype(float)
    low = frame["Low"].astype(float)
    ma5, ma20 = close.rolling(5).mean(), close.rolling(20).mean()
    rsi = _rsi(close)
    previous_close = close.shift(1)
    true_range = (high - low).to_frame("range").join((high - previous_close).abs().rename("high_close")).join((low - previous_close).abs().rename("low_close")).max(axis=1)
    atr = true_range.rolling(14).mean()

    cash, position, pending_signal, trades, equity_curve = float(capital), None, None, [], []
    for index in range(20, len(frame)):
        quote = close.iloc[index]
        if position is None:
            if pending_signal is None:
                signal = ma5.iloc[index] > ma20.iloc[index] and 40 <= rsi.iloc[index] <= 68
                if signal:
                    pending_signal = {
                        "signal_index": index,
                        "stop_distance": max(float(atr.iloc[index]), quote * 0.02),
                    }
                equity_curve.append(cash)
                continue
            entry_quote = float(frame["Open"].iloc[index])
            entry_price = entry_quote * (1 + spread_rate)
            stop_distance = max(pending_signal["stop_distance"], entry_quote * 0.02)
            stop_quote = entry_quote - stop_distance
            target_quote = entry_quote + stop_distance * 2
            loss_per_share = entry_price - stop_quote * (1 - spread_rate)
            shares = min(int(cash // entry_price), int((capital * risk_rate) // loss_per_share))
            if shares <= 0:
                pending_signal = None
                equity_curve.append(cash)
                continue
            entry_cost = shares * entry_price
            cash -= entry_cost
            position = {"signal_index": pending_signal["signal_index"], "entry_index": index, "entry_price": entry_price, "entry_cost": entry_cost, "shares": shares, "stop_quote": stop_quote, "target_quote": target_quote}
            pending_signal = None

        if position is not None:
            held_days = index - position["entry_index"] + 1
            exit_quote, reason = None, None
            day_open = float(frame["Open"].iloc[index])
            if day_open <= position["stop_quote"]:
                exit_quote, reason = day_open, "窓あけ損切り"
            elif day_open >= position["target_quote"]:
                exit_quote, reason = day_open, "窓あけ利確"
            elif low.iloc[index] <= position["stop_quote"]:
                exit_quote, reason = position["stop_quote"], "損切り"
            elif high.iloc[index] >= position["target_quote"]:
                exit_quote, reason = position["target_quote"], "利確"
            elif held_days >= base_holding_days:
                continuation = quote > ma20.iloc[index] and ma5.iloc[index] > ma20.iloc[index] and 45 <= rsi.iloc[index] <= 70 and quote > position["entry_price"]
                if not continuation or held_days >= max_holding_days:
                    exit_quote, reason = quote, "5日終了" if not continuation else "延長上限"
            if exit_quote is not None:
                proceeds = position["shares"] * exit_quote * (1 - spread_rate)
                profit = proceeds - position["entry_cost"]
                tax = max(profit, 0) * tax_rate
                cash += proceeds - tax
                trades.append({"signal_date": frame.index[position["signal_index"]], "entry_date": frame.index[position["entry_index"]], "exit_date": frame.index[index], "holding_days": held_days, "shares": position["shares"], "profit_before_tax": profit, "tax": tax, "reason": reason})
                position = None
        marked_value = cash + (position["shares"] * quote * (1 - spread_rate) if position else 0)
        equity_curve.append(marked_value)

    if position:
        proceeds = position["shares"] * close.iloc[-1] * (1 - spread_rate)
        profit = proceeds - position["entry_cost"]
        tax = max(profit, 0) * tax_rate
        cash += proceeds - tax
        trades.append({"signal_date": frame.index[position["signal_index"]], "entry_date": frame.index[position["entry_index"]], "exit_date": frame.index[-1], "holding_days": len(frame) - position["entry_index"], "shares": position["shares"], "profit_before_tax": profit, "tax": tax, "reason": "検証終了"})

    peak, max_drawdown = float(capital), 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, (peak - value) / peak * 100 if peak else 0)
    wins = sum(item["profit_before_tax"] > 0 for item in trades)
    extended = sum(item["holding_days"] > base_holding_days for item in trades)
    return {"initial_capital": float(capital), "final_value": cash, "return_rate": (cash / float(capital) - 1) * 100 if capital else 0, "trade_count": len(trades), "win_rate": wins / len(trades) * 100 if trades else 0, "max_drawdown": max_drawdown, "average_holding_days": sum(item["holding_days"] for item in trades) / len(trades) if trades else 0, "extended_trade_count": extended, "trades": trades}


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

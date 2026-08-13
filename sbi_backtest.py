from dataclasses import dataclass

import pandas as pd

from sbi_candidates import (
    MARKET_BENCHMARKS, MAX_LIQUID_UNIVERSE, TAX_RATE,
    average_turnover, calculate_atr, download_batches,
    evaluate_market_data, load_prime_universe,
)


STRATEGIES = ("momentum", "pullback")
PARAMETER_SETS = (
    {"stop": 1.0, "reward": 2.0, "holding": 10, "slippage": 0.005},
    {"stop": 1.25, "reward": 2.0, "holding": 15, "slippage": 0.005},
    {"stop": 1.5, "reward": 2.5, "holding": 15, "slippage": 0.005},
)
INITIAL_CAPITAL = 100_000
MAX_POSITIONS = 3
POSITION_FRACTION = 0.34
RISK_FRACTION = 0.01


@dataclass
class Position:
    symbol: str
    strategy: str
    shares: int
    entry: float
    stop: float
    target: float
    opened_index: int
    reserved: float


def period_return(close, days):
    if len(close) <= days:
        return None
    return float((close.iloc[-1] / close.iloc[-days - 1] - 1) * 100)


def relative_signal(data, market_data, sector_return_20, strategy):
    clean = data.dropna(subset=["Close", "High", "Low", "Volume"])
    market = market_data.dropna(subset=["Close"])
    if len(clean) < 65 or len(market) < 61:
        return None
    close, market_close = clean["Close"].astype(float), market["Close"].astype(float)
    ret5, ret20, ret60 = (period_return(close, days) for days in (5, 20, 60))
    market20, market60 = period_return(market_close, 20), period_return(market_close, 60)
    if None in (ret5, ret20, ret60, market20, market60):
        return None
    relative_market = ret20 - market20
    relative_sector = ret20 - sector_return_20
    ma20, price = float(close.tail(20).mean()), float(close.iloc[-1])
    delta = close.diff()
    gains, losses = delta.clip(lower=0).tail(14).mean(), (-delta.clip(upper=0)).tail(14).mean()
    rsi = 100 if losses == 0 else float(100 - 100 / (1 + gains / losses))
    if strategy == "momentum":
        accepted = relative_market >= 2 and relative_sector >= 1 and 1 <= ret5 <= 6 and price > ma20 and 48 <= rsi <= 68
        score = relative_market + relative_sector + ret20 * 0.25
    elif strategy == "pullback":
        accepted = ret60 - market60 >= 4 and relative_sector >= 0 and -3 <= ret5 <= 1 and price >= ma20 * 0.98 and 38 <= rsi <= 55
        score = (ret60 - market60) + relative_sector - abs(ret5) * 0.25
    else:
        raise ValueError(f"未知の戦略: {strategy}")
    return None if not accepted else {
        "score": score, "ret20": ret20, "atr": calculate_atr(clean),
        "relative_market": relative_market,
        "relative_sector": relative_sector,
    }


def historical_market_is_risk_off(benchmarks, signal_date):
    results = [evaluate_market_data(data.loc[:signal_date].tail(60)) for data in benchmarks.values()]
    results = [item for item in results if item]
    return len(results) == 2 and (any(item["sharp_drop"] for item in results) or all(item["weak"] for item in results))


def sector_medians(downloaded, metadata, signal_date):
    grouped = {}
    for symbol, data in downloaded.items():
        close = data.loc[:signal_date]["Close"].dropna().astype(float)
        value = period_return(close, 20)
        if value is not None:
            sector = metadata.get(symbol, {}).get("sector", "不明")
            grouped.setdefault(sector, []).append(value)
    return {sector: float(pd.Series(values).median()) for sector, values in grouped.items()}


def build_daily_signals(downloaded, liquid, metadata, market_data, benchmarks, signal_date, strategy):
    if historical_market_is_risk_off(benchmarks, signal_date):
        return []
    medians = sector_medians(downloaded, metadata, signal_date)
    ranked = []
    for symbol in liquid:
        history = downloaded[symbol].loc[:signal_date].tail(80)
        sector = metadata.get(symbol, {}).get("sector", "不明")
        result = relative_signal(history, market_data.loc[:signal_date].tail(80), medians.get(sector, 0), strategy)
        if result:
            result.update({"symbol": symbol, "strategy": strategy, "sector": sector})
            ranked.append(result)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def close_position(position, row, day_index, params):
    if float(row["Low"]) <= position.stop:
        return position.stop, "loss"
    if float(row["High"]) >= position.target:
        return position.target, "win"
    if day_index - position.opened_index >= params["holding"]:
        return float(row["Close"]), "timeout"
    return None


def summarize(trades, equity_curve, initial_capital):
    gains = sum(max(0, trade["pnl"]) for trade in trades)
    losses = abs(sum(min(0, trade["pnl"]) for trade in trades))
    wins = sum(trade["pnl"] > 0 for trade in trades)
    peak, max_drawdown = initial_capital, 0
    for equity in equity_curve:
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
    return {
        "trades": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100 if trades else 0,
        "average_pnl": sum(t["pnl"] for t in trades) / len(trades) if trades else 0,
        "profit_factor": gains / losses if losses else 0,
        "total_pnl": sum(t["pnl"] for t in trades),
        "max_drawdown": max_drawdown,
    }


def build_signal_cache(downloaded, liquid, metadata, benchmarks, dates):
    market_data = benchmarks["1306.T"]
    cache = {}
    for signal_date in dates:
        for strategy in STRATEGIES:
            cache[(pd.Timestamp(signal_date), strategy)] = build_daily_signals(
                downloaded, liquid, metadata, market_data, benchmarks,
                signal_date, strategy,
            )
    return cache


def simulate_period(downloaded, liquid, metadata, benchmarks, dates, strategy,
                    params, initial_capital=INITIAL_CAPITAL, signal_cache=None):
    cash, positions, trades, equity_curve = float(initial_capital), [], [], []
    market_data = benchmarks["1306.T"]
    for day_index, signal_date in enumerate(dates):
        for position in positions[:]:
            data = downloaded[position.symbol]
            rows = data.loc[data.index.normalize() == signal_date.normalize()]
            if rows.empty:
                continue
            closed = close_position(position, rows.iloc[0], day_index, params)
            if closed:
                exit_price, outcome = closed
                raw = (exit_price - position.entry) * position.shares
                pnl = raw * (1 - TAX_RATE) if raw > 0 else raw
                cash += position.reserved + pnl
                trades.append({"pnl": pnl, "outcome": outcome, "strategy": strategy})
                positions.remove(position)
        if len(positions) < MAX_POSITIONS:
            open_symbols = {position.symbol for position in positions}
            signals = (
                signal_cache.get((pd.Timestamp(signal_date), strategy), [])
                if signal_cache is not None
                else build_daily_signals(
                    downloaded, liquid, metadata, market_data, benchmarks,
                    signal_date, strategy,
                )
            )
            for signal in signals:
                if signal["symbol"] in open_symbols:
                    continue
                future = downloaded[signal["symbol"]].loc[downloaded[signal["symbol"]].index > signal_date]
                if future.empty:
                    continue
                entry = float(future["Open"].iloc[0]) * (1 + params["slippage"])
                risk = max(signal["atr"] * params["stop"], entry * 0.01)
                allocation = min(cash, initial_capital * POSITION_FRACTION)
                shares = min(int(allocation // entry), int((initial_capital * RISK_FRACTION) // risk))
                if shares < 1:
                    continue
                reserved = entry * shares
                cash -= reserved
                positions.append(Position(signal["symbol"], strategy, shares, entry, entry-risk, entry+signal["atr"]*params["reward"], day_index+1, reserved))
                open_symbols.add(signal["symbol"])
                if len(positions) >= MAX_POSITIONS:
                    break
        marked = cash
        for position in positions:
            history = downloaded[position.symbol].loc[:signal_date]
            marked += position.shares * (float(history["Close"].iloc[-1]) if not history.empty else position.entry)
        equity_curve.append(marked)
    return summarize(trades, equity_curve, initial_capital)


def load_backtest_data(years=3):
    import yfinance as yf
    symbols, metadata = load_prime_universe()
    downloaded = download_batches(symbols, period=f"{years + 1}y")
    liquid = sorted(downloaded, key=lambda s: average_turnover(downloaded[s]), reverse=True)[:MAX_LIQUID_UNIVERSE]
    benchmarks = {}
    for symbol in MARKET_BENCHMARKS.values():
        data = yf.download(symbol, period=f"{years + 1}y", auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        benchmarks[symbol] = data
    return downloaded, liquid, metadata, benchmarks


def run_backtest(capital=INITIAL_CAPITAL, years=3):
    capital = int(float(capital))
    downloaded, liquid, metadata, benchmarks = load_backtest_data(years)
    end = min(data.index.max() for data in benchmarks.values()).tz_localize(None).normalize()
    start = end - pd.DateOffset(years=years)
    trading_dates = benchmarks["1306.T"].loc[start:end].index.tz_localize(None)
    print(f"3年分の日次シグナルを作成中: {len(trading_dates)}営業日")
    signal_cache = build_signal_cache(
        downloaded, liquid, metadata, benchmarks, trading_dates,
    )
    folds = []
    cursor = start
    while cursor + pd.DateOffset(months=15) <= end:
        train_end, test_end = cursor + pd.DateOffset(months=12), cursor + pd.DateOffset(months=15)
        train_dates = trading_dates[(trading_dates >= cursor) & (trading_dates < train_end)]
        test_dates = trading_dates[(trading_dates >= train_end) & (trading_dates < test_end)]
        best = None
        for strategy in STRATEGIES:
            for params in PARAMETER_SETS:
                result = simulate_period(
                    downloaded, liquid, metadata, benchmarks, train_dates,
                    strategy, params, capital, signal_cache,
                )
                score = (result["profit_factor"] >= 1, result["average_pnl"], -result["max_drawdown"])
                if result["trades"] >= 15 and (best is None or score > best["score"]):
                    best = {"strategy": strategy, "params": params, "train": result, "score": score}
        if best:
            best["test"] = simulate_period(
                downloaded, liquid, metadata, benchmarks, test_dates,
                best["strategy"], best["params"], capital, signal_cache,
            )
            best["period"] = f"{train_end:%Y-%m}〜{test_end:%Y-%m}"
            folds.append(best)
        cursor += pd.DateOffset(months=3)
    combined = summarize(
        [{"pnl": fold["test"]["total_pnl"]} for fold in folds],
        [capital + sum(item["test"]["total_pnl"] for item in folds[:index+1]) for index in range(len(folds))],
        capital,
    )
    valid_folds = sum(fold["test"]["profit_factor"] > 1 and fold["test"]["average_pnl"] > 0 for fold in folds)
    return {"folds": folds, "valid_folds": valid_folds, "combined": combined, "universe": len(liquid)}


def format_backtest_report(result):
    lines = ["🧪 **SBI相対強度 3年ウォークフォワード**", ""]
    for fold in result["folds"]:
        test = fold["test"]
        lines.append(
            f"{fold['period']}｜{fold['strategy']}｜{test['trades']}件｜"
            f"平均{test['average_pnl']:+,.0f}円｜PF {test['profit_factor']:.2f}｜DD {test['max_drawdown']:.1f}%"
        )
    combined = result["combined"]
    passed = result["folds"] and result["valid_folds"] / len(result["folds"]) >= 0.7 and combined["total_pnl"] > 0
    lines.extend([
        "", f"通過期間：{result['valid_folds']}/{len(result['folds'])}",
        f"検証期間合計損益：{combined['total_pnl']:+,.0f}円",
        f"総合最大DD：{combined['max_drawdown']:.1f}%",
        "✅ 観察運用へ進める基準を通過" if passed else "❌ 観察運用の基準を満たさず",
        "⚠️ 現在の上場銘柄を使うため生存者バイアスがあります。",
    ])
    return "\n".join(lines)

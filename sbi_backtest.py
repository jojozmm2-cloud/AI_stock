from itertools import product

import pandas as pd

from sbi_candidates import (
    MARKET_BENCHMARKS, MAX_LIQUID_UNIVERSE, RISK_RATE, TAX_RATE,
    average_turnover, download_batches, evaluate_market_data,
    load_prime_symbols, score_candidate,
)


STOP_MULTIPLES = (1.0, 1.25, 1.5)
REWARD_MULTIPLES = (1.5, 2.0, 2.5)
HOLDING_DAYS = (5, 10, 15)
SLIPPAGES = (0.003, 0.005, 0.008)


def evaluate_trade(future, entry_price, base_risk, shares, stop_multiple=1.0,
                   reward_multiple=2.0, holding_days=10):
    loss_per_share = base_risk * stop_multiple
    profit_per_share = base_risk * reward_multiple
    target, stop = entry_price + profit_per_share, entry_price - loss_per_share
    window = future.head(holding_days)
    for _, row in window.iterrows():
        if float(row["Low"]) <= stop:
            return {"outcome": "loss", "pnl": -loss_per_share * shares}
        if float(row["High"]) >= target:
            return {"outcome": "win", "pnl": profit_per_share * shares * (1 - TAX_RATE)}
    exit_price = float(window["Close"].iloc[-1])
    raw = (exit_price - entry_price) * shares
    return {"outcome": "timeout", "pnl": raw * (1 - TAX_RATE) if raw > 0 else raw}


def historical_market_is_risk_off(benchmarks, signal_date):
    results = []
    for data in benchmarks.values():
        result = evaluate_market_data(data.loc[:signal_date].tail(60))
        if result:
            results.append(result)
    return len(results) == 2 and (
        any(item["sharp_drop"] for item in results) or all(item["weak"] for item in results)
    )


def summarize(trades):
    gains = sum(max(0, trade["pnl"]) for trade in trades)
    losses = abs(sum(min(0, trade["pnl"]) for trade in trades))
    wins = sum(trade["outcome"] == "win" for trade in trades)
    return {
        "trades": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100 if trades else 0,
        "average_pnl": sum(t["pnl"] for t in trades) / len(trades) if trades else 0,
        "profit_factor": gains / losses if losses else 0,
    }


def build_signals(downloaded, liquid, benchmarks, dates, capital, pullback):
    signals = []
    for signal_date in dates:
        if historical_market_is_risk_off(benchmarks, signal_date):
            continue
        ranked = []
        for symbol in liquid:
            candidate = score_candidate(
                downloaded[symbol].loc[:signal_date].tail(70), capital,
                require_pullback=pullback,
            )
            if candidate:
                candidate.update({"code": symbol, "signal_date": signal_date})
                ranked.append(candidate)
        ranked.sort(key=lambda x: (x["score"], x["average_turnover"]), reverse=True)
        signals.extend(ranked[:5])
    return signals


def test_parameters(signals, downloaded, capital, params):
    stop_multiple, reward_multiple, holding_days, slippage = params
    trades = []
    for signal in signals:
        future = downloaded[signal["code"]].loc[
            downloaded[signal["code"]].index > signal["signal_date"]
        ]
        if len(future) < holding_days:
            continue
        entry = float(future["Open"].iloc[0]) * (1 + slippage)
        base_risk = max(signal["atr"], entry * 0.01)
        shares = min(
            int(capital // entry),
            int((capital * RISK_RATE) // (base_risk * stop_multiple)),
        )
        if shares:
            trades.append(evaluate_trade(
                future, entry, base_risk, shares, stop_multiple,
                reward_multiple, holding_days,
            ))
    return summarize(trades)


def run_backtest(capital=100_000, months=12):
    import yfinance as yf
    capital = int(float(capital))
    symbols, _ = load_prime_symbols()
    downloaded = download_batches(symbols, period="15mo")
    liquid = sorted(downloaded, key=lambda s: average_turnover(downloaded[s]), reverse=True)[:MAX_LIQUID_UNIVERSE]
    benchmarks = {}
    for symbol in MARKET_BENCHMARKS.values():
        data = yf.download(symbol, period="15mo", auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        benchmarks[symbol] = data
    end = pd.Timestamp.now(tz=None).normalize()
    dates = pd.date_range(end - pd.DateOffset(months=months), end, freq="W-FRI")
    split = len(dates) // 2
    train_dates, test_dates = dates[:split], dates[split:]
    options = list(product(STOP_MULTIPLES, REWARD_MULTIPLES, HOLDING_DAYS, SLIPPAGES))
    best = None
    for pullback in (False, True):
        signals = build_signals(downloaded, liquid, benchmarks, train_dates, capital, pullback)
        for params in options:
            result = test_parameters(signals, downloaded, capital, params)
            score = (result["profit_factor"] >= 1, result["average_pnl"], result["profit_factor"])
            if result["trades"] >= 30 and (best is None or score > best["score"]):
                best = {"pullback": pullback, "params": params, "train": result, "score": score}
    if best is None:
        raise RuntimeError("比較に必要な取引件数を確保できませんでした")
    test_signals = build_signals(downloaded, liquid, benchmarks, test_dates, capital, best["pullback"])
    best["test"] = test_parameters(test_signals, downloaded, capital, best["params"])
    best["universe"] = len(liquid)
    return best


def format_result(label, result):
    return (
        f"**{label}**：{result['trades']}件／勝率{result['win_rate']:.1f}%／"
        f"平均{result['average_pnl']:+,.0f}円／PF {result['profit_factor']:.2f}"
    )


def format_backtest_report(result):
    stop, reward, holding, slippage = result["params"]
    verdict = (
        "✅ 後半期間でも採用基準を通過"
        if result["test"]["profit_factor"] > 1 and result["test"]["average_pnl"] > 0
        else "❌ 後半期間では採用基準を満たさず"
    )
    return (
        "🧪 **SBI候補 時系列分割バックテスト**\n\n"
        f"選択条件：押し目={'あり' if result['pullback'] else 'なし'}／"
        f"損切り{stop}ATR／利確{reward}ATR／保有{holding}日／価格ずれ{slippage*100:.1f}%\n"
        f"{format_result('前半6か月（条件探索）', result['train'])}\n"
        f"{format_result('後半6か月（未使用検証）', result['test'])}\n\n"
        f"{verdict}\n"
        "⚠️ 現在の上場銘柄を使うため生存者バイアスがあり、決算除外は過去時点で再現していません。"
    )

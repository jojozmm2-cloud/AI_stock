from datetime import datetime

import pandas as pd

from sbi_candidates import (
    ADVERSE_ENTRY_SLIPPAGE,
    MAX_LIQUID_UNIVERSE,
    REWARD_MULTIPLE,
    RISK_RATE,
    TAX_RATE,
    average_turnover,
    download_batches,
    evaluate_market_data,
    load_prime_symbols,
    score_candidate,
)


HOLDING_DAYS = 10


def evaluate_trade(future, entry_price, risk_per_share, shares):
    target = entry_price + risk_per_share * REWARD_MULTIPLE
    stop = entry_price - risk_per_share
    for _, row in future.head(HOLDING_DAYS).iterrows():
        # 同日に両方へ到達した場合は保守的に損切りを先とする。
        if float(row["Low"]) <= stop:
            return {"outcome": "loss", "pnl": -risk_per_share * shares}
        if float(row["High"]) >= target:
            gross = risk_per_share * REWARD_MULTIPLE * shares
            return {"outcome": "win", "pnl": gross * (1 - TAX_RATE)}
    exit_price = float(future.head(HOLDING_DAYS)["Close"].iloc[-1])
    raw = (exit_price - entry_price) * shares
    return {"outcome": "timeout", "pnl": raw * (1 - TAX_RATE) if raw > 0 else raw}


def historical_market_is_risk_off(benchmarks, signal_date):
    results = []
    for data in benchmarks.values():
        history = data.loc[:signal_date].tail(60)
        result = evaluate_market_data(history)
        if result:
            results.append(result)
    if len(results) < 2:
        return False
    return any(item["sharp_drop"] for item in results) or all(item["weak"] for item in results)


def run_backtest(capital=100_000, months=12):
    import yfinance as yf

    symbols, _ = load_prime_symbols()
    downloaded = download_batches(symbols, period="15mo")
    liquid = sorted(downloaded, key=lambda symbol: average_turnover(downloaded[symbol]), reverse=True)[:MAX_LIQUID_UNIVERSE]
    benchmarks = {}
    for symbol in ("^N225", "^TOPX"):
        data = yf.download(symbol, period="15mo", auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        benchmarks[symbol] = data

    end = pd.Timestamp.now(tz=None).normalize()
    start = end - pd.DateOffset(months=months)
    signal_dates = pd.date_range(start=start, end=end, freq="W-FRI")
    trades = []
    skipped_market_days = 0
    for signal_date in signal_dates:
        if historical_market_is_risk_off(benchmarks, signal_date):
            skipped_market_days += 1
            continue
        ranked = []
        for symbol in liquid:
            data = downloaded[symbol]
            history = data.loc[:signal_date].tail(70)
            candidate = score_candidate(history, capital)
            if candidate:
                candidate["code"] = symbol
                ranked.append(candidate)
        ranked.sort(key=lambda item: (item["score"], item["average_turnover"]), reverse=True)
        for candidate in ranked[:5]:
            data = downloaded[candidate["code"]]
            future = data.loc[data.index > signal_date]
            if future.empty:
                continue
            entry = float(future["Open"].iloc[0]) * (1 + ADVERSE_ENTRY_SLIPPAGE)
            risk_per_share = candidate["assumed_entry_price"] - candidate["stop_loss"]
            shares = min(int(capital // entry), int((capital * RISK_RATE) // risk_per_share))
            if shares < 1 or len(future) < HOLDING_DAYS:
                continue
            result = evaluate_trade(future, entry, risk_per_share, shares)
            result.update({"code": candidate["code"], "signal_date": signal_date.date()})
            trades.append(result)

    wins = [trade for trade in trades if trade["outcome"] == "win"]
    losses = [trade for trade in trades if trade["outcome"] == "loss"]
    gains = sum(max(0, trade["pnl"]) for trade in trades)
    declines = abs(sum(min(0, trade["pnl"]) for trade in trades))
    return {
        "months": months,
        "universe": len(liquid),
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "timeouts": len(trades) - len(wins) - len(losses),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0,
        "total_pnl": sum(trade["pnl"] for trade in trades),
        "average_pnl": sum(trade["pnl"] for trade in trades) / len(trades) if trades else 0,
        "profit_factor": gains / declines if declines else 0,
        "skipped_market_days": skipped_market_days,
    }


def format_backtest_report(result):
    return (
        "🧪 **SBI候補 予備バックテスト**\n\n"
        f"期間：過去{result['months']}か月（週1回判定）\n"
        f"対象：現在の高流動性{result['universe']}銘柄\n"
        f"検証件数：{result['trades']}件　勝率：{result['win_rate']:.1f}%\n"
        f"利確：{result['wins']}　損切り：{result['losses']}　期限終了：{result['timeouts']}\n"
        f"1件平均損益：{result['average_pnl']:+,.0f}円\n"
        f"プロフィットファクター：{result['profit_factor']:.2f}\n"
        f"地合い悪化で見送り：{result['skipped_market_days']}週\n\n"
        "⚠️ 現在の上場銘柄だけを使う予備検証で、生存者バイアスがあります。"
        "決算除外も過去時点では再現しておらず、結果は利益を保証しません。"
    )

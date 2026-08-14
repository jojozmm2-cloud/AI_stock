"""長期の再現性と直近シグナルを分けて評価する短期候補判定。"""

from datetime import timedelta
from pathlib import Path

from rakuten_backtest import run_one_week_backtest
from rakuten_market_data import ensure_recent_daily_data
from rakuten_names import RAKUTEN_NAMES


def _slice_years(data, years):
    end = data.index[-1]
    return data[data.index >= end - timedelta(days=365 * years)]


def _buy_and_hold_return(data, spread_rate=0.0022, tax_rate=0.20315):
    if len(data) < 2:
        return 0.0
    buy = float(data["Close"].iloc[0]) * (1 + spread_rate)
    sell = float(data["Close"].iloc[-1]) * (1 - spread_rate)
    profit_rate = sell / buy - 1
    return (profit_rate - max(profit_rate, 0) * tax_rate) * 100


def evaluate_short_term_candidate(code, data):
    data = data.dropna(subset=["High", "Low", "Close", "Volume"])
    ensure_recent_daily_data(data)
    if len(data) < 200:
        raise ValueError("判定に必要な株価データが不足しています")

    periods = {}
    for years in (1, 3, 5):
        sample = _slice_years(data, years)
        result = run_one_week_backtest(sample)
        result["buy_hold_return"] = _buy_and_hold_return(sample)
        periods[f"{years}y"] = result

    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)
    price = float(close.iloc[-1])
    ma5 = float(close.tail(5).mean())
    ma20 = float(close.tail(20).mean())
    change_5d = float((price / close.iloc[-6] - 1) * 100)
    rsi = _calculate_rsi(close)
    average_volume = float(volume.iloc[-21:-1].mean())
    volume_ratio = float(volume.iloc[-1] / average_volume) if average_volume else 0

    score = 0
    positive_periods = sum(periods[key]["return_rate"] > 0 for key in periods)
    outperformed_periods = sum(
        periods[key]["return_rate"] > periods[key]["buy_hold_return"]
        for key in periods
    )
    score += positive_periods * 8
    score += outperformed_periods * 6
    score += 14 if periods["1y"]["max_drawdown"] <= 10 else (7 if periods["1y"]["max_drawdown"] <= 18 else 0)
    score += 12 if price > ma20 and ma5 > ma20 else (6 if price > ma20 else 0)
    score += 10 if 45 <= rsi <= 65 else (4 if 35 <= rsi <= 70 else 0)
    score += 8 if 0 < change_5d <= 8 else (3 if -2 <= change_5d <= 10 else 0)
    score += 8 if volume_ratio >= 1.2 else (4 if volume_ratio >= 0.9 else 0)

    if periods["1y"]["return_rate"] <= 0 or periods["1y"]["max_drawdown"] > 25:
        score = min(score, 49)
    score = min(int(score), 100)

    if score >= 75:
        status = "短期候補"
    elif score >= 55:
        status = "監視候補"
    else:
        status = "見送り"

    reasons = []
    if positive_periods == 3:
        reasons.append("全期間でプラス")
    if outperformed_periods >= 2:
        reasons.append("買いっぱなしを複数期間で上回る")
    if price > ma20 and ma5 > ma20:
        reasons.append("短期上昇トレンド")
    if 45 <= rsi <= 65:
        reasons.append("RSIが過熱前")
    if volume_ratio >= 1.2:
        reasons.append("出来高増加")
    if not reasons:
        reasons.append("条件不足")

    return {
        "code": code,
        "name": RAKUTEN_NAMES.get(code, "会社名未登録"),
        "score": score,
        "status": status,
        "price": price,
        "rsi": rsi,
        "change_5d": change_5d,
        "volume_ratio": volume_ratio,
        "positive_periods": positive_periods,
        "outperformed_periods": outperformed_periods,
        "reasons": reasons,
        "periods": periods,
    }


def get_short_term_candidates(symbols_filename="rakuten_kabumini_symbols.txt", limit=10):
    import yfinance as yf

    results = []
    for code in _load_symbols(symbols_filename):
        data = yf.Ticker(code).history(period="5y", interval="1d", auto_adjust=True)
        results.append(evaluate_short_term_candidate(code, data))
    return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]


def create_short_term_candidates_embed(results):
    fields = []
    for item in results:
        one_year = item["periods"]["1y"]
        reasons = "・".join(item["reasons"])
        fields.append({
            "name": f"{item['status']}｜{item['name']}（{item['code'].replace('.T', '')}） {item['score']}点",
            "value": (
                f"参考価格 {item['price']:,.2f}円 / 5日 {item['change_5d']:+.2f}% / RSI {item['rsi']:.1f}\n"
                f"1年検証 {one_year['return_rate']:+.2f}% / 最大下落 {one_year['max_drawdown']:.2f}%\n"
                f"1週間型 {one_year['trade_count']}回 / 勝率 {one_year['win_rate']:.1f}% / 平均保有 {one_year['average_holding_days']:.1f}日\n"
                f"安定性 {item['positive_periods']}/3期間 / 買いっぱなし超え {item['outperformed_periods']}/3期間\n"
                f"理由: {reasons}"
            ),
            "inline": False,
        })
    return {
        "title": "楽天かぶミニ 短期候補判定",
        "description": "当日終値で判定し、翌営業日の始値で購入する前提です。3万円・基本5営業日、上昇条件が続く場合だけ最長10営業日まで延長します。",
        "color": 0xBF0000,
        "fields": fields,
        "footer": {"text": "過去の成績は将来の利益を保証しません。古いデータは通知しません。"},
    }
def _load_symbols(filename):
    path = Path(__file__).with_name(filename)
    return [line.strip().upper() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    latest_gain, latest_loss = float(gain.iloc[-1]), float(loss.iloc[-1])
    if latest_loss == 0:
        return 100.0 if latest_gain > 0 else 50.0
    return float((100 - 100 / (1 + gain / loss)).iloc[-1])

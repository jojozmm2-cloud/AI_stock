from pathlib import Path

import pandas as pd
import yfinance as yf


SBI_BLUE = 0x1D5FA7
MIN_AVERAGE_TURNOVER = 100_000_000


def load_symbols():
    path = Path(__file__).with_name("sbi_symbols.txt")
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    latest_gain = float(gain.iloc[-1])
    latest_loss = float(loss.iloc[-1])

    if latest_loss == 0:
        return 100.0 if latest_gain > 0 else 50.0

    relative_strength = gain / loss
    rsi = 100 - (100 / (1 + relative_strength))
    return float(rsi.iloc[-1])


def score_candidate(data, capital):
    data = data.dropna(subset=["Close", "Volume"])
    if len(data) < 25:
        return None

    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)
    price = float(close.iloc[-1])

    if price <= 0 or price > capital:
        return None

    average_turnover = float((close * volume).tail(20).mean())
    if average_turnover < MIN_AVERAGE_TURNOVER:
        return None

    ma5 = float(close.tail(5).mean())
    ma20 = float(close.tail(20).mean())
    change_5d = float((price / close.iloc[-6] - 1) * 100)
    average_volume = float(volume.iloc[-21:-1].mean())
    volume_ratio = (
        float(volume.iloc[-1] / average_volume)
        if average_volume > 0
        else 0
    )
    rsi = calculate_rsi(close)

    if pd.isna(rsi):
        return None

    score = 0
    score += 25 if price > ma20 else 0
    score += 15 if ma5 > ma20 else 0
    score += 20 if 0 < change_5d <= 8 else (10 if -3 <= change_5d <= 12 else 0)
    score += 25 if 45 <= rsi <= 65 else (12 if 35 <= rsi <= 70 else 0)
    score += 15 if volume_ratio >= 1.2 else (8 if volume_ratio >= 0.9 else 0)

    return {
        "price": price,
        "score": score,
        "rsi": rsi,
        "change_5d": change_5d,
        "volume_ratio": volume_ratio,
        "affordable_shares": int(capital // price),
    }


def get_sbi_candidates(capital, limit=5):
    capital = int(float(capital))
    if capital <= 0:
        raise ValueError("運用資金が設定されていません")

    symbols = load_symbols()
    downloaded = yf.download(
        symbols,
        period="3mo",
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False,
    )

    candidates = []
    for symbol in symbols:
        try:
            data = downloaded[symbol] if len(symbols) > 1 else downloaded
            candidate = score_candidate(data, capital)
            if candidate:
                candidate["code"] = symbol
                candidates.append(candidate)
        except (KeyError, IndexError, TypeError, ValueError):
            continue

    return sorted(
        candidates,
        key=lambda item: (
            item["score"],
            item["volume_ratio"],
            item["change_5d"],
        ),
        reverse=True,
    )[:limit]


def create_sbi_candidates_embed(candidates, capital):
    fields = []
    for index, item in enumerate(candidates, start=1):
        code = item["code"].replace(".T", "")
        fields.append({
            "name": f"{index}. {code}  |  判定 {item['score']}点",
            "value": (
                f"参考価格：{item['price']:,.2f}円　"
                f"購入可能：最大{item['affordable_shares']}株\n"
                f"RSI：{item['rsi']:.1f}　"
                f"5日騰落：{item['change_5d']:+.2f}%　"
                f"出来高倍率：{item['volume_ratio']:.2f}倍\n"
                f"詳しく見る：`/sbi 分析 code:{code}`"
            ),
            "inline": False,
        })

    if not fields:
        fields.append({
            "name": "今回の結果",
            "value": "条件に合う候補を取得できませんでした。時間を置いて再実行してください。",
            "inline": False,
        })

    return {
        "title": "🔎 SBI短期売買 候補一覧",
        "description": (
            f"運用資金 **{int(float(capital)):,.0f}円** で1株以上買える銘柄を、"
            "トレンド・RSI・出来高から機械的に順位付けしました。"
        ),
        "color": SBI_BLUE,
        "fields": fields,
        "footer": {
            "text": (
                "買い推奨ではありません。S株対象可否と注文条件は"
                "SBI証券の注文画面で最終確認してください。"
            )
        },
    }

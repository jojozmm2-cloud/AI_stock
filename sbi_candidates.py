from pathlib import Path

import pandas as pd
import yfinance as yf

from sbi_names import SBI_NAMES


SBI_BLUE = 0x1D5FA7
MIN_AVERAGE_TURNOVER = 100_000_000

def load_symbols(filename="sbi_symbols.txt"):
    path = Path(__file__).with_name(filename)
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


def score_candidate(data, capital, max_price=None):
    data = data.dropna(subset=["Close", "Volume"])
    if len(data) < 25:
        return None

    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)
    price = float(close.iloc[-1])

    if price <= 0 or price > capital:
        return None
    if max_price is not None and price > float(max_price):
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

    reasons = []
    if price > ma20 and ma5 > ma20:
        reasons.append("上昇トレンド")
    elif price > ma20:
        reasons.append("20日線より上")
    if 45 <= rsi <= 65:
        reasons.append("RSIが適温")
    elif rsi > 70:
        reasons.append("RSIは過熱気味")
    if volume_ratio >= 1.2:
        reasons.append("出来高が増加")
    if 0 < change_5d <= 8:
        reasons.append("5日間で上昇")

    if rsi > 70:
        status = "🔴 過熱注意"
    elif score >= 85:
        status = "🟢 条件良好"
    elif score >= 70:
        status = "🔵 要チェック"
    else:
        status = "🟠 慎重に確認"

    return {
        "price": price,
        "score": score,
        "rsi": rsi,
        "change_5d": change_5d,
        "volume_ratio": volume_ratio,
        "affordable_shares": int(capital // price),
        "reasons": reasons,
        "status": status,
    }


def get_sbi_candidates(
    capital,
    limit=5,
    max_price=None,
    symbols_filename="sbi_symbols.txt",
):
    capital = int(float(capital))
    if capital <= 0:
        raise ValueError("運用資金が設定されていません")

    symbols = load_symbols(symbols_filename)
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
            candidate = score_candidate(data, capital, max_price=max_price)
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


def create_sbi_candidates_embed(candidates, capital, max_price=None):
    fields = []
    for index, item in enumerate(candidates, start=1):
        code = item["code"].replace(".T", "")
        name = SBI_NAMES.get(item["code"], "会社名未登録")
        reason_text = "・".join(item["reasons"]) or "数値条件の総合判定"
        fields.append({
            "name": f"{index}. {name}（{code}）｜{item['status']}",
            "value": (
                f"**候補理由：{reason_text}**\n"
                f"参考価格：{item['price']:,.2f}円　判定：{item['score']}点\n"
                f"RSI：{item['rsi']:.1f}　"
                f"5日騰落：{item['change_5d']:+.2f}%　"
                f"出来高倍率：{item['volume_ratio']:.2f}倍\n"
                f"資金だけで見た上限：{item['affordable_shares']}株"
                "（推奨株数ではありません）\n"
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

    price_condition = (
        f"・1株 **{float(max_price):,.0f}円以下**"
        if max_price is not None
        else ""
    )

    return {
        "title": (
            "🧪 SBI 1,000円以下候補（テスト）"
            if max_price == 1000
            else "🔎 SBI短期売買 候補一覧"
        ),
        "description": (
            f"運用資金 **{int(float(capital)):,.0f}円** で1株以上買える銘柄"
            f"{price_condition}を、"
            "トレンド・RSI・出来高から機械的に順位付けしました。"
        ),
        "color": SBI_BLUE,
        "fields": fields,
        "footer": {
            "text": (
                "買い推奨ではありません。S株対象可否と注文条件は"
                "SBI証券の注文画面で最終確認してください。テスト用コマンドです。"
            )
        },
    }

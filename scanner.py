from pathlib import Path
import time

import pandas as pd
import yfinance as yf


PAYPAY_LIST = Path(__file__).with_name("paypay_list.txt")

BATCH_SIZE = 50
TOP_N = 20


def load_paypay_symbols():
    with open(PAYPAY_LIST, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip()
        ]


def calculate_rsi(close, period=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    if avg_loss.iloc[-1] == 0:
        return 100.0

    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]

    return 100 - (100 / (1 + rs))


def scan_stock(code, data):
    data = data.dropna(subset=["Close", "Volume"])

    # データ不足は除外
    if len(data) < 30:
        return None

    close = data["Close"]
    volume = data["Volume"]

    price = float(close.iloc[-1])

    # 20日移動平均
    ma20 = float(close.tail(20).mean())

    # RSI
    rsi = calculate_rsi(close)

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    macd_up = macd.iloc[-1] > signal.iloc[-1]

    # 5日間の値動き
    change_5d = (
        (price / float(close.iloc[-6])) - 1
    ) * 100

    # 出来高
    volume_5 = float(volume.tail(5).mean())
    volume_20 = float(volume.tail(20).mean())

    if volume_20 > 0:
        volume_ratio = volume_5 / volume_20
    else:
        volume_ratio = 0

    # -------------------------
    # 高速スキャンスコア
    # -------------------------

    score = 0


    # ① 20日移動平均との位置 20点
    ma_gap = ((price / ma20) - 1) * 100

    if 0 <= ma_gap <= 5:
        ma_score = 12 + (ma_gap / 5) * 8

    elif 5 < ma_gap <= 10:
        ma_score = 20 - ((ma_gap - 5) / 5) * 10

    elif -3 <= ma_gap < 0:
        ma_score = 8 + ma_gap

    else:
        ma_score = 0

    score += ma_score


    # ② MACD 20点
    macd_hist = macd.iloc[-1] - signal.iloc[-1]
    macd_hist_prev = macd.iloc[-2] - signal.iloc[-2]

    if macd_hist > 0 and macd_hist > macd_hist_prev:
        macd_score = 20

    elif macd_hist > 0:
        macd_score = 15

    elif macd_hist <= 0 and macd_hist > macd_hist_prev:
        macd_score = 8

    else:
        macd_score = 0

    score += macd_score


    # ③ RSI 20点
    # RSI55付近を高評価
    rsi_score = 20 - abs(rsi - 55) * 1.2

    rsi_score = max(
        0,
        min(20, rsi_score)
    )

    score += rsi_score


    # ④ 出来高 20点
    if volume_ratio >= 2.0:
        volume_score = 20

    elif volume_ratio >= 1.5:
        volume_score = 16

    elif volume_ratio >= 1.2:
        volume_score = 12

    elif volume_ratio >= 1.0:
        volume_score = 8

    elif volume_ratio >= 0.8:
        volume_score = 4

    else:
        volume_score = 0

    score += volume_score


    # ⑤ 5日間の値動き 20点
    # +4%付近を高評価
    momentum_score = 20 - abs(change_5d - 4) * 2.5

    momentum_score = max(
        0,
        min(20, momentum_score)
    )

    score += momentum_score


    # 最終スコアを整数化
    score = round(score)
    return {
        "code": code,
        "score": score,
        "price": price,
        "rsi": rsi,
        "change_5d": change_5d,
        "volume_ratio": volume_ratio,
    }


def scan_all_stocks():
    symbols = load_paypay_symbols()

    print(f"PayPay証券 {len(symbols)}銘柄を高速スキャンします")
    print()

    results = []

    # 50銘柄ずつ取得
    for start in range(0, len(symbols), BATCH_SIZE):

        batch = symbols[start:start + BATCH_SIZE]

        print(
            f"取得中 "
            f"{start + 1} ～ "
            f"{min(start + BATCH_SIZE, len(symbols))}"
            f" / {len(symbols)}"
        )

        try:
            data = yf.download(
                tickers=batch,
                period="3mo",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
                timeout=20,
            )

        except Exception as e:
            print("取得エラー:", e)
            continue

        for code in batch:

            try:
                if isinstance(data.columns, pd.MultiIndex):

                    if code not in data.columns.get_level_values(0):
                        continue

                    stock_data = data[code]

                else:
                    stock_data = data

                result = scan_stock(
                    code,
                    stock_data
                )

                if result:
                    results.append(result)

            except Exception as e:
                print(f"{code} スキャン失敗:", e)

        # Yahoo側へのアクセスを少し抑える
        time.sleep(1)

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:TOP_N]


if __name__ == "__main__":

    ranking = scan_all_stocks()

    print()
    print("=" * 55)
    print("🏆 高速スキャン TOP20")
    print("=" * 55)

    for i, stock in enumerate(ranking, 1):

        print(
            f"{i:2}. "
            f"{stock['code']:8} "
            f"スコア {stock['score']:3}/100 "
            f"RSI {stock['rsi']:5.1f} "
            f"5日 {stock['change_5d']:+6.2f}% "
            f"出来高 {stock['volume_ratio']:.2f}倍"
        )
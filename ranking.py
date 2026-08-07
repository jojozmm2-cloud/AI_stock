NAMES = {
    "6501.T": "日立製作所",
    "6758.T": "ソニーグループ",
    "6857.T": "アドバンテスト",
    "8035.T": "東京エレクトロン",
    "9984.T": "ソフトバンクグループ",
}

WATCH_LIST = [
    "6501.T",  # 日立
    "6758.T",  # ソニー
    "8035.T",  # 東京エレクトロン
    "6857.T",  # アドバンテスト
    "9984.T",  # ソフトバンクG
]
from test import analyze_stock


def create_ranking():
    ranking = []

    for code in WATCH_LIST:
        try:
            result = analyze_stock(code)

            score = 0

            if "🚀 強い上昇" in result:
                score += 30

            if "🟢 買い" in result:
                score += 25

            if "MACD: 上向き" in result:
                score += 20

            if "RSI: 普通" in result:
                score += 15

            if "価格: 通常の範囲" in result:
                score += 10

            ranking.append((score, code, result))

        except Exception as e:
            print(e)

    ranking.sort(reverse=True)

    return ranking[:5]
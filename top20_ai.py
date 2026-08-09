import re
import time
import json
from pathlib import Path
import yfinance as yf

from scanner import scan_all_stocks
from test import analyze_stock
from news import get_stock_news
from ai_comment import make_ai_comment
from discord_notify import send_discord

def get_company_name(code):
    try:
        info = yf.Ticker(code).get_info()

        name = (
            info.get("shortName")
            or info.get("longName")
            or code
        )

        return name

    except Exception as e:
        print(f"{code} 会社名取得失敗:", e)
        return code

NAMES_FILE = Path(__file__).with_name("paypay_names.json")


def load_company_names():
    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def make_reasons(stock):
    scores = [
        ("移動平均", stock["ma_score"]),
        ("MACD", stock["macd_score"]),
        ("RSI", stock["rsi_score"]),
        ("出来高", stock["volume_score"]),
        ("勢い", stock["momentum_score"]),
    ]

    # 点数が高い順
    scores.sort(
        key=lambda x: x[1],
        reverse=True
    )

    # 上位3項目だけ
    reasons = [
        f"{name} {score}/20"
        for name, score in scores[:3]
    ]

    return reasons
    
def get_ai_probability(ai_comment):
    """
    AIコメントから
    「買い確率 65%」
    の数字を取得
    """

    match = re.search(
        r"買い確率\s*[:：]?\s*(\d{1,3})\s*%",
        ai_comment
    )

    if match:
        probability = int(match.group(1))

        # 念のため0～100に制限
        return max(0, min(probability, 100))

    return 50


def analyze_top20():

    # 298銘柄 → 高速スキャンTOP20
    ranking = scan_all_stocks()

    if not ranking:
        print("候補銘柄がありません")
        return []

    final_results = []

    print()
    print("=" * 60)
    print("🤖 TOP20 AI詳細分析開始")
    print("=" * 60)

    for i, stock in enumerate(ranking, 1):

        code = stock["code"]

        print()
        print(
            f"[{i}/{len(ranking)}] "
            f"{code} をAI分析中..."
        )

        try:
            # 詳細分析
            result = analyze_stock(code)

            # ニュース
            news = get_stock_news(code)

            if news:
                news_text = "\n".join(news)
            else:
                news_text = "ニュースなし"

            # OpenAI
            ai_comment = make_ai_comment(
                result,
                news_text
            )

            # AIの買い確率を取得
            ai_probability = get_ai_probability(
                ai_comment
            )

            # -------------------------
            # 最終スコア
            # -------------------------
            #
            # 高速スキャン 60%
            # AI評価       40%
            #

            final_score = (
                stock["score"] * 0.6
                + ai_probability * 0.4
            )

            final_results.append({
                "code": code,
                "scan_score": stock["score"],
                "ai_probability": ai_probability,
                "final_score": final_score,

                "rsi": stock["rsi"],
                "change_5d": stock["change_5d"],
                "volume_ratio": stock["volume_ratio"],

                "ma_score": stock["ma_score"],
                "macd_score": stock["macd_score"],
                "rsi_score": stock["rsi_score"],
                "volume_score": stock["volume_score"],
                "momentum_score": stock["momentum_score"],

                "result": result,
                "news": news,
                "ai_comment": ai_comment,
            })

            print(
                f"✅ {code} "
                f"高速:{stock['score']} "
                f"AI:{ai_probability}% "
                f"最終:{final_score:.1f}"
            )

        except Exception as e:

            print(
                f"❌ {code} 分析失敗:",
                e
            )

        # APIを連続で叩きすぎないよう少し待つ
        time.sleep(1)

    # 最終スコア順
    final_results.sort(
        key=lambda x: x["final_score"],
        reverse=True
    )

    return final_results


if __name__ == "__main__":

    ranking = analyze_top20()

    print()
    print("=" * 60)
    print("🏆 最終AIランキング TOP10")
    print("=" * 60)

    for i, stock in enumerate(ranking[:10], 1):

        print(
            f"{i:2}. "
            f"{stock['code']:8} "
            f"最終 {stock['final_score']:5.1f}/100 "
            f"高速 {stock['scan_score']:3}/100 "
            f"AI {stock['ai_probability']:3}%"
        )
            # Discord用メッセージ
    company_names = load_company_names()
    message = "🏆 **今日のAI株ランキング TOP10**\n\n"

    for i, stock in enumerate(ranking[:10], 1):

        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = f"{i}位"

        name = company_names.get(
            stock["code"],
            stock["code"]
        )
        reasons = make_reasons(stock)

        reason_text = "\n".join(
            f"・{reason}"
            for reason in reasons
        )

        message += (
            f"{medal} **{name}（{stock['code']}）**\n"
            f"最終スコア: {stock['final_score']:.1f}/100\n"
            f"AI評価: {stock['ai_probability']}%\n"
            f"\n📌 **理由**\n"
            f"{reason_text}\n\n"
        )

    message += "🤖 AI Stock Tool"

    # Discord送信
    if send_discord(message):
        print()
        print("✅ TOP10をDiscordへ送信しました")
    else:
        print()
        print("❌ Discord送信に失敗しました")

        raise RuntimeError(
            "Discordへのランキング送信に失敗しました"
        )
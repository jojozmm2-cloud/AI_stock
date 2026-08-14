import os
import json
import requests
import yfinance as yf

from test import analyze_stock
from sbi_analysis import create_sbi_analysis_embed, get_sbi_trade_plan
from sbi_candidates import create_sbi_candidates_embed, get_sbi_candidates
from sbi_watchlist import create_watchlist_embed, get_watchlist_status
from sbi_timing import create_sbi_timing_embed, get_sbi_timing
from sbi_auto_monitor import get_auto_monitor_embeds
from rakuten_candidates import create_rakuten_candidates_embed, get_rakuten_candidates
from rakuten_trade_plan import create_rakuten_trade_plan_embed, get_rakuten_trade_plan


MODE = os.getenv("MODE", "analysis")
CODE = os.getenv("STOCK_CODE", "").strip().upper()
PORTFOLIO_JSON = os.getenv("PORTFOLIO_JSON", "[]")

REALIZED_PROFIT = float(
    os.getenv("REALIZED_PROFIT", "0") or 0
)
SBI_CAPITAL = os.getenv("SBI_CAPITAL", "0")
SBI_WATCHLIST_JSON = os.getenv("SBI_WATCHLIST_JSON", "[]")
RAKUTEN_CAPITAL = os.getenv("RAKUTEN_CAPITAL", "30000")
RAKUTEN_SPREAD_RATE = float(os.getenv("RAKUTEN_SPREAD_RATE", "0.0022") or 0.0022)

# 6501 → 6501.T のように日本株コードを自動変換
if len(CODE) == 4 and CODE.isdigit():
    CODE = CODE + ".T"

CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")


def send_discord(message):
    url = (
        f"https://discord.com/api/v10/"
        f"channels/{CHANNEL_ID}/messages"
    )

    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    # Discordの文字数制限対策
    for i in range(0, len(message), 1900):
        part = message[i:i + 1900]

        response = requests.post(
            url,
            headers=headers,
            json={"content": part},
            timeout=30
        )

        response.raise_for_status()


def send_discord_embed(embed):
    url = (
        f"https://discord.com/api/v10/"
        f"channels/{CHANNEL_ID}/messages"
    )

    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        headers=headers,
        json={"embeds": [embed]},
        timeout=30
    )

    response.raise_for_status()


def send_discord_embeds(embeds):
    url = (
        f"https://discord.com/api/v10/"
        f"channels/{CHANNEL_ID}/messages"
    )
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    for index in range(0, len(embeds), 10):
        response = requests.post(
            url,
            headers=headers,
            json={"embeds": embeds[index:index + 10]},
            timeout=30
        )
        response.raise_for_status()

def analyze_portfolio():
    portfolio = json.loads(PORTFOLIO_JSON)

    if not portfolio:
        return "📭 保有株が登録されていません。"

    lines = []
    total_cost = 0
    total_value = 0

    for item in portfolio:
        code = str(item["code"]).strip().upper()
        shares = float(item["shares"])
        avg_price = float(item["avg_price"])

        ticker = yf.Ticker(code)
        data = ticker.history(period="5d")

        if data.empty:
            lines.append(
                f"⚠️ **{code}**\n"
                "現在価格を取得できませんでした。"
            )
            continue

        current_price = float(data["Close"].iloc[-1])

        cost = shares * avg_price
        value = shares * current_price
        profit = value - cost
        profit_rate = (
            profit / cost * 100
            if cost > 0
            else 0
        )

        total_cost += cost
        total_value += value

        mark = "🟢" if profit >= 0 else "🔴"

        lines.append(
            f"🏷️ **{code}**\n"
            f"株数：{shares}\n"
            f"平均取得単価：{avg_price:,.2f}円\n"
            f"現在値：{current_price:,.2f}円\n"
            f"評価額：{value:,.0f}円\n"
            f"{mark} 含み損益：{profit:+,.0f}円 "
            f"({profit_rate:+.2f}%)"
        )

    total_profit = total_value - total_cost

    total_rate = (
        total_profit / total_cost * 100
        if total_cost > 0
        else 0
    )

    total_mark = "🟢" if total_profit >= 0 else "🔴"

    return (
        "💼 **保有株分析**\n\n"
        + "\n\n".join(lines)
        + "\n\n━━━━━━━━━━\n"
        + f"💰 取得総額：{total_cost:,.0f}円\n"
        + f"📊 現在評価額：{total_value:,.0f}円\n"
        + f"{total_mark} 合計損益："
        + f"{total_profit:+,.0f}円 "
        + f"({total_rate:+.2f}%)"
    )

def analyze_profit_summary():
    portfolio = json.loads(PORTFOLIO_JSON)

    unrealized_profit = 0
    total_cost = 0

    for item in portfolio:
        code = str(item["code"]).strip().upper()
        shares = float(item["shares"])
        avg_price = float(item["avg_price"])

        ticker = yf.Ticker(code)
        data = ticker.history(period="5d")

        if data.empty:
            continue

        current_price = float(
            data["Close"].iloc[-1]
        )

        cost = shares * avg_price
        value = shares * current_price

        total_cost += cost
        unrealized_profit += value - cost

    total_profit = (
        unrealized_profit
        + REALIZED_PROFIT
    )

    unrealized_mark = (
        "🟢"
        if unrealized_profit >= 0
        else "🔴"
    )

    realized_mark = (
        "🟢"
        if REALIZED_PROFIT >= 0
        else "🔴"
    )

    total_mark = (
        "🟢"
        if total_profit >= 0
        else "🔴"
    )

    return (
        "📊 **損益まとめ**\n\n"
        f"{unrealized_mark} 含み損益："
        f"{unrealized_profit:+,.0f}円\n"
        f"{realized_mark} 実現損益："
        f"{REALIZED_PROFIT:+,.0f}円\n"
        "\n━━━━━━━━━━\n"
        f"{total_mark} **トータル損益："
        f"{total_profit:+,.0f}円**"
    )

def main():
    if not CHANNEL_ID:
        raise RuntimeError("DiscordチャンネルIDがありません")

    if not BOT_TOKEN:
        raise RuntimeError("Discord Bot Tokenがありません")

    try:
        if MODE == "rakuten_candidates":
            candidates = get_rakuten_candidates(RAKUTEN_CAPITAL)
            send_discord_embed(create_rakuten_candidates_embed(candidates, RAKUTEN_CAPITAL))
            return

        if MODE == "rakuten_plan":
            if not CODE:
                raise RuntimeError("銘柄コードがありません")
            plan = get_rakuten_trade_plan(CODE, RAKUTEN_CAPITAL, RAKUTEN_SPREAD_RATE)
            send_discord_embed(create_rakuten_trade_plan_embed(plan))
            return

        # SBI短期売買プラン
        if MODE == "sbi_analysis":
            if not CODE:
                raise RuntimeError("銘柄コードがありません")

            plan = get_sbi_trade_plan(CODE, SBI_CAPITAL)
            embed = create_sbi_analysis_embed(plan)
            send_discord_embed(embed)
            return

        if MODE == "sbi_candidates":
            candidates = get_sbi_candidates(SBI_CAPITAL)
            embed = create_sbi_candidates_embed(candidates, SBI_CAPITAL)
            send_discord_embed(embed)
            return

        if MODE == "sbi_candidates_under_1000":
            candidates = get_sbi_candidates(
                SBI_CAPITAL,
                max_price=1000,
                symbols_filename="sbi_under_1000_symbols.txt",
            )
            embed = create_sbi_candidates_embed(
                candidates,
                SBI_CAPITAL,
                max_price=1000,
            )
            send_discord_embed(embed)
            return

        if MODE == "sbi_watchlist":
            results = get_watchlist_status(SBI_WATCHLIST_JSON)
            embed = create_watchlist_embed(results)
            send_discord_embed(embed)
            return

        if MODE == "sbi_timing":
            if not CODE:
                raise RuntimeError("銘柄コードがありません")
            result = get_sbi_timing(
                CODE,
                SBI_CAPITAL,
                PORTFOLIO_JSON,
                SBI_WATCHLIST_JSON,
            )
            embed = create_sbi_timing_embed(result)
            send_discord_embed(embed)
            return

        if MODE == "sbi_auto_monitor":
            embeds = get_auto_monitor_embeds(
                SBI_CAPITAL,
                PORTFOLIO_JSON,
                SBI_WATCHLIST_JSON,
            )
            if embeds:
                send_discord_embeds(embeds)
            else:
                print("自動監視: 送信対象なし")
            return

    # 保有株分析
        if MODE == "portfolio":
            message = analyze_portfolio()
            send_discord(message)
            return

        # 損益まとめ
        if MODE == "profit_summary":
            message = analyze_profit_summary()
            send_discord(message)
            return

        if not CODE:
            raise RuntimeError("銘柄コードがありません")

        result = analyze_stock(CODE)
        if "株価データを取得できませんでした" in result:
            send_discord(
                f"❌ `{CODE}` の株価データを取得できませんでした。\n"
                "銘柄コードを確認して、もう一度試してください。"
            )
            return
        # AI分析
        if MODE == "ai_analysis":
            from news import get_stock_news
            from ai_comment import make_ai_comment

            news = get_stock_news(CODE)

            if news:
                news_text = "\n".join(news)
                news_display = "\n".join(
                    f"・{item}"
                    for item in news[:3]
                )
            else:
                news_text = "ニュースなし"
                news_display = "・最新ニュースなし"

            ai_comment = make_ai_comment(
                result,
                news_text
            )

            message = f"""🤖 **AI株分析**

🏷️ 銘柄
`{CODE}`

📰 **最新ニュース**
{news_display}

🧠 **AIコメント**
{ai_comment}
"""

        # 通常分析
        else:
            message = f"""📊 **株分析結果**

🏷️ 銘柄
`{CODE}`

{result}
"""

        send_discord(message)

    except Exception as e:
        print(f"エラー: {e}")

        try:
            send_discord(
                f"❌ `{CODE}` の分析中にエラーが発生しました。"
            )
        except Exception:
            pass

        raise


if __name__ == "__main__":
    main()

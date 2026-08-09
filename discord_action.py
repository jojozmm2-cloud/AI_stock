import os
import requests

from test import analyze_stock


MODE = os.getenv("MODE", "analysis")
CODE = os.getenv("STOCK_CODE", "").strip().upper()

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


def main():
    if not CODE:
        raise RuntimeError("銘柄コードがありません")

    if not CHANNEL_ID:
        raise RuntimeError("DiscordチャンネルIDがありません")

    if not BOT_TOKEN:
        raise RuntimeError("Discord Bot Tokenがありません")

    try:
        result = analyze_stock(CODE)

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
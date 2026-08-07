import os
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_discord(message):
    if not WEBHOOK_URL:
        print("Webhook URLが設定されていません")
        return False

    try:
        response = requests.post(
            WEBHOOK_URL,
            json={"content": message},
            timeout=10
        )

        print("Discord送信結果:", response.status_code)
        print("Discord応答:", response.text)

        response.raise_for_status()
        return True

    except requests.RequestException as e:
        print("Discord送信エラー:", e)
        return False
def create_analysis_message(code, result):
    lines = result.splitlines()

    important = []

    important = []
    ai_mode = False

    for line in lines:
        if "🤖 AIコメント" in line:
            ai_mode = True
            important.append(line)
            continue

        if ai_mode:
            important.append(line)
            continue

        if (
            "今日" in line
            or "20日平均との差" in line
            or "RSI:" in line
            or "MACD:" in line
            or "総合判定" in line
            or "🚀" in line
            or "📉" in line
            or "🔴" in line
            or "🟢" in line
            or "📰 最新ニュース" in line
            or line.startswith("・")
            or "AI評価" in line
        ):
            important.append(line)

    body = "\n".join(important)

    return f"""📊 **AI株分析結果**

━━━━━━━━━━━━━━
🏷️ 銘柄
`{code}`

━━━━━━━━━━━━━━
📈 分析結果

{body}

━━━━━━━━━━━━━━
🤖 AI Stock Tool
"""
def create_price_alert_message(code, price, alert_type):
    icon = "📈" if alert_type == "upper" else "📉"

    return f"""🚨 **価格アラート**

{icon} 銘柄
`{code}`

💰 現在価格
{price:,.2f}円

⚠️ {("上限価格に到達しました" if alert_type=="upper" else "下限価格に到達しました")}

━━━━━━━━━━━━━━
🤖 AI Stock Tool
"""
def create_ranking_message(ranking, names):
    message = "🏆 **今日のAIおすすめランキング**\n\n"

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    for i, (score, code, result) in enumerate(ranking):
        name = names.get(code, code)

        message += f"{medals[i]} **{name}**\n"
        message += f"📈 AIスコア: {score}/100\n"

        if score >= 70:
            message += "🟢 買い候補\n"
        elif score >= 50:
            message += "🟡 様子見\n"
        else:
            message += "🔴 注意\n"

        message += "\n"

    return message
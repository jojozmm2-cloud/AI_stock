from top20_ai import make_reasons, load_company_names
from discord_notify import send_discord


stock = {
    "code": "6305.T",
    "final_score": 84.0,
    "ai_probability": 75,

    # 今回追加したスコア内訳
    "ma_score": 16,
    "macd_score": 20,
    "rsi_score": 19,
    "volume_score": 8,
    "momentum_score": 20,
}


company_names = load_company_names()

name = company_names.get(
    stock["code"],
    stock["code"]
)

reasons = make_reasons(stock)

reason_text = "\n".join(
    f"・{reason}"
    for reason in reasons
)

message = (
    "🧪 **スコア理由テスト**\n\n"
    f"🥇 **{name}（{stock['code']}）**\n"
    f"最終スコア: {stock['final_score']:.1f}/100\n"
    f"AI評価: {stock['ai_probability']}%\n"
    f"\n📌 **理由**\n"
    f"{reason_text}\n\n"
    "🤖 AI Stock Tool"
)

send_discord(message)
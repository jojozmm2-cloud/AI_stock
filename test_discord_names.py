import json
from pathlib import Path

from discord_notify import send_discord


NAMES_FILE = Path(__file__).with_name("paypay_names.json")


with open(NAMES_FILE, "r", encoding="utf-8") as f:
    company_names = json.load(f)


# テスト用の3銘柄
codes = [
    "6273.T",
    "6305.T",
    "1514.T",
]


message = "🧪 **会社名表示テスト**\n\n"

for i, code in enumerate(codes, 1):

    name = company_names.get(
        code,
        code
    )

    message += (
        f"{i}位 **{name}（{code}）**\n"
    )


message += "\n🤖 AI Stock Tool"


if send_discord(message):
    print("✅ Discordテスト送信成功")
else:
    print("❌ Discordテスト送信失敗")
import os

import requests
from dotenv import load_dotenv


load_dotenv()

token = os.getenv("DISCORD_BOT_TOKEN")
application_id = os.getenv("DISCORD_APPLICATION_ID")

if not token or not application_id:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN と DISCORD_APPLICATION_ID を .env に設定してください"
    )

base_url = (
    "https://discord.com/api/v10/"
    f"applications/{application_id}/commands"
)

headers = {
    "Authorization": f"Bot {token}",
    "Content-Type": "application/json"
}

response = requests.get(
    base_url,
    headers=headers,
    timeout=30
)
response.raise_for_status()

legacy_commands = [
    command
    for command in response.json()
    if command.get("name") == "sbi分析"
]

if not legacy_commands:
    print("旧コマンド /sbi分析 は登録されていません。")

for command in legacy_commands:
    command_id = command["id"]

    delete_response = requests.delete(
        f"{base_url}/{command_id}",
        headers=headers,
        timeout=30
    )

    print(
        "Delete legacy /sbi分析 status:",
        delete_response.status_code
    )
    delete_response.raise_for_status()

print("新しい /sbi 分析 はそのまま利用できます。")

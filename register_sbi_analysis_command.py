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

url = (
    "https://discord.com/api/v10/"
    f"applications/{application_id}/commands"
)

headers = {
    "Authorization": f"Bot {token}",
    "Content-Type": "application/json"
}

command = {
    "name": "sbi分析",
    "type": 1,
    "description": "SBI短期売買用の株数・利確・損切り候補を計算します",
    "options": [
        {
            "name": "code",
            "description": "銘柄コード 例: 6501",
            "type": 3,
            "required": True
        }
    ]
}

response = requests.post(
    url,
    headers=headers,
    json=command,
    timeout=30
)

print("SBI analysis command status:", response.status_code)
print(response.text)
response.raise_for_status()

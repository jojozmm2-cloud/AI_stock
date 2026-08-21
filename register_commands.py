import time
import os
import requests
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
APPLICATION_ID = os.getenv("DISCORD_APPLICATION_ID")


url = (
    f"https://discord.com/api/v10/"
    f"applications/{APPLICATION_ID}/commands"
)

headers = {
    "Authorization": f"Bot {TOKEN}",
    "Content-Type": "application/json"
}

command = {
    "name": "保有追加",
    "type": 1,
    "description": "保有株を登録または更新します",
    "options": [
        {
            "name": "code",
            "description": "銘柄コード 例: 6501",
            "type": 3,
            "required": True
        },
        {
            "name": "shares",
            "description": "保有株数 例: 4.2",
            "type": 10,
            "required": True
        },
        {
            "name": "avg_price",
            "description": "平均取得単価 例: 4737.57",
            "type": 10,
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

print("status:", response.status_code)
print(response.text)

command_list = {
    "name": "保有一覧",
    "type": 1,
    "description": "登録している保有株を一覧表示します"
}

response = requests.post(
    url,
    headers=headers,
    json=command_list,
    timeout=30
)

print("保有一覧 status:", response.status_code)
print(response.text)
command_delete = {
    "name": "保有削除",
    "type": 1,
    "description": "保有株を削除します",
    "options": [
        {
            "name": "code",
            "description": "削除する銘柄コード 例: 6501",
            "type": 3,
            "required": True
        }
    ]
}
command_portfolio = {
    "name": "保有分析",
    "type": 1,
    "description": "保有株の現在価格と含み損益を分析します"
}

response = requests.post(
    url,
    headers=headers,
    json=command_portfolio,
    timeout=30
)

print("保有分析 status:", response.status_code)
print(response.text)

response = requests.post(
    url,
    headers=headers,
    json=command_delete,
    timeout=30
)

print("保有削除 status:", response.status_code)
print(response.text)
command_buy_more = {
    "name": "買い増し",
    "type": 1,
    "description": "保有株を買い増して平均取得単価を再計算します",
    "options": [
        {
            "name": "code",
            "description": "銘柄コード 例: 6501",
            "type": 3,
            "required": True
        },
        {
            "name": "shares",
            "description": "買い増す株数 例: 1",
            "type": 10,
            "required": True
        },
        {
            "name": "price",
            "description": "購入価格 例: 5500",
            "type": 10,
            "required": True
        }
    ]
}

response = requests.post(
    url,
    headers=headers,
    json=command_buy_more,
    timeout=30
)

print("買い増し status:", response.status_code)
print(response.text)

command_sell = {
    "name": "一部売却",
    "type": 1,
    "description": "保有株を一部または全部売却します",
    "options": [
        {
            "name": "code",
            "description": "銘柄コード 例: 6501",
            "type": 3,
            "required": True
        },
        {
            "name": "shares",
            "description": "売却する株数 例: 1",
            "type": 10,
            "required": True
        },
        {
            "name": "price",
            "description": "売却価格 例: 5600",
            "type": 10,
            "required": True
        }
    ]
}

while True:
    response = requests.post(
        url,
        headers=headers,
        json=command_sell,
        timeout=30
    )

    if response.status_code != 429:
        break

    data = response.json()
    wait_time = data.get("retry_after", 3)

    print(
        f"レート制限中です。{wait_time}秒待ちます..."
    )

    time.sleep(wait_time + 1)

print("一部売却 status:", response.status_code)
print(response.text)

command_history = {
    "name": "売買履歴",
    "type": 1,
    "description": "買い増し・売却の履歴を表示します"
}

while True:
    response = requests.post(
        url,
        headers=headers,
        json=command_history,
        timeout=30
    )

    if response.status_code != 429:
        break

    data = response.json()
    wait_time = data.get("retry_after", 3)

    print(
        f"レート制限中です。{wait_time}秒待ちます..."
    )

    time.sleep(wait_time + 1)

print("売買履歴 status:", response.status_code)
print(response.text)

command_profit = {
    "name": "実現損益",
    "type": 1,
    "description": "売却した取引の実現損益を集計します"
}

while True:
    response = requests.post(
        url,
        headers=headers,
        json=command_profit,
        timeout=30
    )

    if response.status_code != 429:
        break

    data = response.json()
    wait_time = data.get("retry_after", 3)

    print(
        f"レート制限中です。{wait_time}秒待ちます..."
    )

    time.sleep(wait_time + 1)

print("実現損益 status:", response.status_code)
print(response.text)

command_profit_summary = {
    "name": "損益まとめ",
    "type": 1,
    "description": "含み損益と実現損益をまとめて表示します"
}

while True:
    response = requests.post(
        url,
        headers=headers,
        json=command_profit_summary,
        timeout=30
    )

    if response.status_code != 429:
        break

    data = response.json()
    wait_time = data.get("retry_after", 3)

    print(
        f"レート制限中です。{wait_time}秒待ちます..."
    )

    time.sleep(wait_time + 1)

print("損益まとめ status:", response.status_code)
print(response.text)
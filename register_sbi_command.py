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
    "name": "sbi",
    "type": 1,
    "description": "SBI短期売買支援AIを使います",
    "options": [
        {
            "name": "状態",
            "description": "運用資金と準備状態を表示します",
            "type": 1
        },
        {
            "name": "設定",
            "description": "SBI短期売買の運用資金を設定します",
            "type": 1,
            "options": [
                {
                    "name": "capital",
                    "description": "運用資金（円） 例: 70000",
                    "type": 10,
                    "required": True,
                    "min_value": 1
                }
            ]
        },
        {
            "name": "分析",
            "description": "株数・利確・損切り・税引後利益を計算します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "銘柄コード 例: 6501",
                    "type": 3,
                    "required": True
                }
            ]
        },
        {
            "name": "候補",
            "description": "値動きと出来高から短期売買の候補を探します",
            "type": 1
        },
        {
            "name": "千円候補",
            "description": "1株1,000円以下の候補を探します（テスト用）",
            "type": 1
        },
        {
            "name": "監視追加",
            "description": "利確・損切り候補を指定して銘柄を監視します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "銘柄コード 例: 2503",
                    "type": 3,
                    "required": True
                },
                {
                    "name": "take_profit",
                    "description": "利確候補価格 例: 3253.5",
                    "type": 10,
                    "required": True,
                    "min_value": 0.01
                },
                {
                    "name": "stop_loss",
                    "description": "損切り候補価格 例: 2975.25",
                    "type": 10,
                    "required": True,
                    "min_value": 0.01
                }
            ]
        },
        {
            "name": "監視一覧",
            "description": "監視銘柄の現在価格と目標までの距離を表示します",
            "type": 1
        },
        {
            "name": "監視削除",
            "description": "監視一覧から銘柄を削除します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "削除する銘柄コード 例: 2503",
                    "type": 3,
                    "required": True
                }
            ]
        },
        {
            "name": "注文判断",
            "description": "5分足とVWAPから次のS株注文タイミングを確認します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "銘柄コード 例: 2503",
                    "type": 3,
                    "required": True
                }
            ]
        },
        {
            "name": "自動通知",
            "description": "10:00・13:30のS株注文判断通知を切り替えます",
            "type": 1,
            "options": [
                {
                    "name": "enabled",
                    "description": "オンなら有効、オフなら停止",
                    "type": 5,
                    "required": True
                }
            ]
        },
        {
            "name": "注文中",
            "description": "S株の未約定注文を仮登録します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "銘柄コード 例: 8410",
                    "type": 3,
                    "required": True
                },
                {
                    "name": "shares",
                    "description": "注文した株数 例: 1",
                    "type": 4,
                    "required": True,
                    "min_value": 1
                }
            ]
        },
        {
            "name": "約定",
            "description": "注文中のS株を実際の約定価格で保有記録に移します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "銘柄コード 例: 8410",
                    "type": 3,
                    "required": True
                },
                {
                    "name": "price",
                    "description": "1株あたりの実際の約定価格",
                    "type": 10,
                    "required": True,
                    "min_value": 0.01
                }
            ]
        },
        {
            "name": "取消",
            "description": "未約定注文の仮記録を取り消します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "銘柄コード 例: 8410",
                    "type": 3,
                    "required": True
                }
            ]
        },
        {
            "name": "購入",
            "description": "SBI証券で約定した購入内容を記録します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "銘柄コード 例: 6501",
                    "type": 3,
                    "required": True
                },
                {
                    "name": "shares",
                    "description": "約定した株数 例: 4",
                    "type": 4,
                    "required": True,
                    "min_value": 1
                },
                {
                    "name": "price",
                    "description": "1株あたりの実際の約定価格",
                    "type": 10,
                    "required": True,
                    "min_value": 0.01
                }
            ]
        },
        {
            "name": "保有",
            "description": "Discordに記録したSBI保有株を表示します",
            "type": 1
        },
        {
            "name": "売却",
            "description": "SBI証券で約定した売却内容を記録します",
            "type": 1,
            "options": [
                {
                    "name": "code",
                    "description": "銘柄コード 例: 6501",
                    "type": 3,
                    "required": True
                },
                {
                    "name": "shares",
                    "description": "約定した売却株数",
                    "type": 4,
                    "required": True,
                    "min_value": 1
                },
                {
                    "name": "price",
                    "description": "1株あたりの実際の約定価格",
                    "type": 10,
                    "required": True,
                    "min_value": 0.01
                }
            ]
        },
        {
            "name": "履歴",
            "description": "SBIの購入・売却記録を新しい順に表示します",
            "type": 1
        },
        {
            "name": "損益",
            "description": "SBIで記録した売却の概算税引後損益を表示します",
            "type": 1
        }
    ]
}

response = requests.post(
    url,
    headers=headers,
    json=command,
    timeout=30
)

print("SBI command status:", response.status_code)
print(response.text)
response.raise_for_status()

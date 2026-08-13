import json

from sbi_names import SBI_NAMES


SBI_BLUE = 0x1D5FA7


def get_watchlist_status(watchlist_json):
    import yfinance as yf

    items = json.loads(watchlist_json or "[]")
    results = []

    for item in items:
        code = str(item.get("code", "")).strip().upper()
        take_profit = float(item.get("take_profit", 0))
        stop_loss = float(item.get("stop_loss", 0))

        if not code or take_profit <= 0 or stop_loss <= 0:
            continue

        data = yf.Ticker(code).history(period="5d", auto_adjust=True)
        data = data.dropna(subset=["Close"])
        if data.empty:
            results.append({
                "code": code,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "error": "現在価格を取得できませんでした",
            })
            continue

        current_price = float(data["Close"].iloc[-1])
        target_distance = (take_profit / current_price - 1) * 100
        stop_distance = (stop_loss / current_price - 1) * 100

        if current_price >= take_profit:
            status = "🎯 利確候補に到達"
        elif current_price <= stop_loss:
            status = "🛑 損切り候補に到達"
        else:
            status = "👀 監視中"

        results.append({
            "code": code,
            "current_price": current_price,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "target_distance": target_distance,
            "stop_distance": stop_distance,
            "status": status,
        })

    return results


def create_watchlist_embed(results):
    fields = []

    for item in results[:25]:
        code = item["code"]
        short_code = code.replace(".T", "")
        company_name = SBI_NAMES.get(code, "会社名未登録")

        if item.get("error"):
            value = f"⚠️ {item['error']}"
        else:
            value = (
                f"**{item['status']}**\n"
                f"現在価格：{item['current_price']:,.2f}円\n"
                f"🎯 利確：{item['take_profit']:,.2f}円 "
                f"（現在値から{item['target_distance']:+.2f}%）\n"
                f"🛑 損切り：{item['stop_loss']:,.2f}円 "
                f"（現在値から{item['stop_distance']:+.2f}%）\n"
                f"再分析：`/sbi 分析 code:{short_code}`"
            )

        fields.append({
            "name": f"{company_name}（{short_code}）",
            "value": value,
            "inline": False,
        })

    return {
        "title": "👀 SBI監視一覧",
        "description": "登録した利確・損切り候補と現在価格を比較しました。",
        "color": SBI_BLUE,
        "fields": fields,
        "footer": {
            "text": (
                "株価は取得時点の参考値です。到達表示は注文や売却を自動実行しません。"
            )
        },
    }

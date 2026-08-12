import json
from datetime import datetime

from sbi_timing import JST, create_sbi_timing_embed, get_sbi_timing


def get_auto_monitor_embeds(capital, portfolio_json, watchlist_json):
    watches = json.loads(watchlist_json or "[]")[:10]
    today = datetime.now(JST).date()
    embeds = []

    for watch in watches:
        code = str(watch.get("code", "")).strip().upper()
        if not code:
            continue

        try:
            result = get_sbi_timing(
                code,
                capital,
                portfolio_json,
                watchlist_json,
            )
        except Exception as error:
            print(f"自動監視エラー {code}: {error}")
            continue

        if result.get("data_date") != today.isoformat():
            print(f"自動監視スキップ {code}: 当日の株価データなし")
            continue

        embed = create_sbi_timing_embed(result)
        embed["title"] = "🔔 自動通知｜" + embed["title"].replace("⏱️ ", "")
        embeds.append(embed)

    return embeds

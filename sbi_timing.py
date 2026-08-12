import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sbi_analysis import calculate_atr, calculate_trade_plan, normalize_code
from sbi_names import SBI_NAMES


SBI_BLUE = 0x1D5FA7
JST = ZoneInfo("Asia/Tokyo")
SPARKS = "▁▂▃▄▅▆▇█"


def make_sparkline(values):
    values = [float(value) for value in values]
    if not values:
        return "データなし"

    low = min(values)
    high = max(values)
    if high == low:
        return SPARKS[3] * len(values)

    return "".join(
        SPARKS[round((value - low) / (high - low) * (len(SPARKS) - 1))]
        for value in values
    )


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    latest_gain = float(gain.iloc[-1])
    latest_loss = float(loss.iloc[-1])
    if latest_loss == 0:
        return 100.0 if latest_gain > 0 else 50.0
    relative_strength = latest_gain / latest_loss
    return 100 - (100 / (1 + relative_strength))


def next_sbi_window(now=None):
    now = now or datetime.now(JST)
    local_time = now.timetz().replace(tzinfo=None)

    if now.weekday() >= 5:
        return "次の営業日 7:00まで", "次の営業日 9:00頃"

    if local_time < time(7, 0):
        return "本日 7:00まで", "本日 9:00頃"
    if local_time < time(10, 30):
        return "本日 10:30まで", "本日 12:30頃"
    if local_time < time(14, 0):
        return "本日 14:00まで", "本日 15:30頃"

    return "次の営業日 7:00まで", "次の営業日 9:00頃"


def decide_buy(current, vwap, rsi, momentum, ma5, ma20):
    vwap_gap = (current / vwap - 1) * 100 if vwap > 0 else 0

    if rsi >= 70 or vwap_gap >= 2 or momentum >= 2:
        return "🟠 今回は追いかけず待つ", "短期的な過熱または急上昇が見られます"
    if current >= vwap and ma5 >= ma20 and 45 <= rsi < 70 and momentum > -1:
        return "🟢 次の注文枠で検討", "VWAP上・日足上向きで、過熱は強くありません"
    if current < vwap and momentum < 0:
        return "🔵 反転を待つ", "VWAPを下回り、直近5分足も弱めです"
    return "⚪ 様子見", "方向感が揃っていません"


def decide_sell(current, vwap, momentum, take_profit, stop_loss):
    if take_profit > 0 and current >= take_profit:
        return "🎯 利確を検討", "登録した利確候補に到達しています"
    if stop_loss > 0 and current <= stop_loss:
        return "🛑 損切りを検討", "登録した損切り候補に到達しています"
    if current < vwap and momentum < -0.5:
        return "🟠 保有継続は慎重に", "VWAPを下回り、短期の勢いも低下しています"
    return "👀 保有継続", "利確・損切り候補には未到達です"


def make_action_comment(result):
    decision = result["decision"]

    if result["action"] == "buy":
        if "次の注文枠で検討" in decision:
            if result["market_open"]:
                return (
                    "条件は比較的そろっています。"
                    f"**{result['shares']}株を上限候補に、次のS株注文枠で買いを検討できる状態**です。"
                    "締切前に価格が大きく動いた場合は、もう一度確認してください。"
                )
            return (
                "本日の終了時点では、買いを検討できる数値条件です。"
                "ただし市場終了後の判定なので、**翌営業日の注文前にもう一度実行してから判断**してください。"
            )
        if "追いかけず待つ" in decision:
            return (
                "銘柄自体は候補ですが、今は高値を追いかける場面ではありません。"
                "**今回は買わず、過熱が落ち着くまで待つ候補**です。"
            )
        if "反転を待つ" in decision:
            return (
                "今は短期の流れが弱いため、買い急がない方が安全寄りです。"
                "**VWAP回復や5分足の反転を確認してから再判断**します。"
            )
        return (
            "買い条件がまだ十分にそろっていません。"
            "**今回は様子見し、次の確認時刻に再判断**する候補です。"
        )

    if "利確" in decision:
        return (
            "登録した利確候補に到達しています。"
            "**次のS株注文締切までに売却を検討できる状態**ですが、約定価格は表示値と異なります。"
        )
    if "損切り" in decision:
        return (
            "登録した損切り候補に到達しています。"
            "**次の締切までにSBI証券を確認し、損失拡大を避ける判断を優先**してください。"
        )
    if "慎重" in decision:
        return (
            "利確・損切り候補には未到達ですが、短期の勢いが弱まっています。"
            "**保有継続だけでなく、早めの売却も比較する状態**です。"
        )
    return (
        "現時点では利確・損切り候補に未到達です。"
        "**保有継続候補ですが、次の確認時刻にも再判定**します。"
    )


def get_sbi_timing(code, capital, portfolio_json="[]", watchlist_json="[]"):
    import yfinance as yf

    code = normalize_code(code)
    capital = int(float(capital))
    holdings = json.loads(portfolio_json or "[]")
    watches = json.loads(watchlist_json or "[]")
    holding = next((item for item in holdings if item.get("code") == code), None)
    watch = next((item for item in watches if item.get("code") == code), None)

    ticker = yf.Ticker(code)
    intraday = ticker.history(period="5d", interval="5m", auto_adjust=True)
    daily = ticker.history(period="3mo", auto_adjust=True)
    intraday = intraday.dropna(subset=["High", "Low", "Close", "Volume"])
    daily = daily.dropna(subset=["High", "Low", "Close"])

    if len(intraday) < 4 or len(daily) < 20:
        raise ValueError("注文判断に必要な株価データを取得できませんでした")

    latest_day = intraday.index[-1].date()
    today_data = intraday[intraday.index.date == latest_day]
    if today_data.empty:
        today_data = intraday.tail(20)

    typical_price = (today_data["High"] + today_data["Low"] + today_data["Close"]) / 3
    total_volume = float(today_data["Volume"].sum())
    vwap = (
        float((typical_price * today_data["Volume"]).sum() / total_volume)
        if total_volume > 0
        else float(today_data["Close"].mean())
    )
    current = float(today_data["Close"].iloc[-1])
    momentum_base = float(intraday["Close"].iloc[-4])
    momentum = float((current / momentum_base - 1) * 100)
    close_daily = daily["Close"].astype(float)
    rsi = calculate_rsi(close_daily)
    ma5 = float(close_daily.tail(5).mean())
    ma20 = float(close_daily.tail(20).mean())
    atr = calculate_atr(daily)
    plan = calculate_trade_plan(capital, current, atr)

    take_profit = float(watch.get("take_profit", 0)) if watch else plan["take_profit"]
    stop_loss = float(watch.get("stop_loss", 0)) if watch else plan["stop_loss"]

    if holding:
        decision, reason = decide_sell(
            current, vwap, momentum, take_profit, stop_loss
        )
        shares = int(holding["shares"])
        avg_price = float(holding["avg_price"])
        gross_profit = (current - avg_price) * shares
        tax = max(gross_profit, 0) * 0.20315
        net_profit = gross_profit - tax
        action = "sell"
    else:
        decision, reason = decide_buy(current, vwap, rsi, momentum, ma5, ma20)
        shares = plan["shares"]
        avg_price = 0
        gross_profit = 0
        net_profit = 0
        action = "buy"

    now = datetime.now(JST)
    deadline, execution = next_sbi_window(now)
    current_time = now.timetz().replace(tzinfo=None)
    market_open = (
        now.weekday() < 5
        and (
            time(9, 0) <= current_time <= time(11, 30)
            or time(12, 30) <= current_time <= time(15, 30)
        )
    )
    latest_timestamp = intraday.index[-1]

    return {
        "code": code,
        "action": action,
        "decision": decision,
        "reason": reason,
        "current": current,
        "vwap": vwap,
        "vwap_gap": (current / vwap - 1) * 100 if vwap else 0,
        "momentum": momentum,
        "rsi": rsi,
        "ma5": ma5,
        "ma20": ma20,
        "day_high": float(today_data["High"].max()),
        "day_low": float(today_data["Low"].min()),
        "sparkline": make_sparkline(today_data["Close"].tail(12).tolist()),
        "shares": shares,
        "avg_price": avg_price,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "deadline": deadline,
        "execution": execution,
        "market_open": market_open,
        "data_time": latest_timestamp.strftime("%m/%d %H:%M"),
    }


def create_sbi_timing_embed(result):
    code = result["code"].replace(".T", "")
    name = SBI_NAMES.get(result["code"], "会社名未登録")
    action_name = "売却判断" if result["action"] == "sell" else "購入判断"

    action_comment = make_action_comment(result)
    fields = [
        {
            "name": "📌 今回の判断",
            "value": f"**{result['decision']}**\n{result['reason']}",
            "inline": False,
        },
        {
            "name": "💬 アシストコメント",
            "value": action_comment,
            "inline": False,
        },
        {
            "name": "📉 5分足の流れ",
            "value": (
                f"`{result['sparkline']}`\n"
                f"直近15分：{result['momentum']:+.2f}%\n"
                f"当日高値：{result['day_high']:,.2f}円　"
                f"当日安値：{result['day_low']:,.2f}円"
            ),
            "inline": False,
        },
        {
            "name": "📊 VWAPとの比較",
            "value": (
                f"参考価格：{result['current']:,.2f}円\n"
                f"VWAP：{result['vwap']:,.2f}円\n"
                f"差：{result['vwap_gap']:+.2f}%"
            ),
            "inline": True,
        },
        {
            "name": "📈 日足の状態",
            "value": (
                f"RSI：{result['rsi']:.1f}\n"
                f"5日線：{result['ma5']:,.2f}円\n"
                f"20日線：{result['ma20']:,.2f}円"
            ),
            "inline": True,
        },
        {
            "name": "⏰ 次のS株注文枠",
            "value": (
                f"注文締切：**{result['deadline']}**\n"
                f"約定予定：**{result['execution']}**\n"
                "表示価格での約定ではありません。"
            ),
            "inline": False,
        },
    ]

    if result["action"] == "sell":
        fields.insert(1, {
            "name": "💼 保有株の概算",
            "value": (
                f"保有：{result['shares']}株　平均取得：{result['avg_price']:,.2f}円\n"
                f"現在の税引前損益：{result['gross_profit']:+,.0f}円\n"
                f"概算税引後損益：**{result['net_profit']:+,.0f}円**\n"
                f"利確候補：{result['take_profit']:,.2f}円　"
                f"損切り候補：{result['stop_loss']:,.2f}円"
            ),
            "inline": False,
        })
    else:
        fields.insert(1, {
            "name": "🛒 現在価格での株数候補",
            "value": (
                f"{result['shares']}株\n"
                "運用資金と最大損失1%から再計算しています。"
            ),
            "inline": False,
        })

    return {
        "title": f"⏱️ SBI{action_name}｜{name}（{code}）",
        "description": "5分足・VWAP・日足を組み合わせた注文タイミング候補です。",
        "color": SBI_BLUE,
        "fields": fields,
        "footer": {
            "text": (
                f"株価データ時点：{result['data_time']}｜参考情報であり、売買推奨や約定価格の保証ではありません"
            )
        },
    }

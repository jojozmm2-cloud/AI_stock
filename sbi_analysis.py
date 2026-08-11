import math


RISK_RATE = 0.01
REWARD_RISK_RATIO = 2.0
SBI_BLUE = 0x1D5FA7


def normalize_code(code):
    code = str(code or "").strip().upper()

    if len(code) == 4 and code.isdigit():
        return code + ".T"

    return code


def calculate_atr(data, period=14):
    previous_close = data["Close"].shift(1)
    true_range = (
        (data["High"] - data["Low"])
        .to_frame("high_low")
        .join((data["High"] - previous_close).abs().rename("high_close"))
        .join((data["Low"] - previous_close).abs().rename("low_close"))
        .max(axis=1)
    )

    return float(true_range.tail(period).mean())


def calculate_trade_plan(capital, current_price, atr):
    capital = max(int(float(capital)), 0)
    current_price = float(current_price)
    atr = float(atr)

    stop_distance = max(atr, current_price * 0.02)
    target_distance = stop_distance * REWARD_RISK_RATIO
    risk_budget = capital * RISK_RATE

    shares_by_capital = math.floor(capital / current_price)
    shares_by_risk = math.floor(risk_budget / stop_distance)
    shares = max(min(shares_by_capital, shares_by_risk), 0)

    investment = shares * current_price
    max_loss = shares * stop_distance

    return {
        "capital": capital,
        "current_price": current_price,
        "atr": atr,
        "shares": shares,
        "investment": investment,
        "take_profit": current_price + target_distance,
        "stop_loss": max(current_price - stop_distance, 0),
        "max_loss": max_loss,
        "risk_budget": risk_budget,
        "risk_rate": (max_loss / capital * 100) if capital else 0,
        "take_profit_rate": target_distance / current_price * 100,
        "stop_loss_rate": stop_distance / current_price * 100
    }


def get_sbi_trade_plan(code, capital):
    import yfinance as yf

    code = normalize_code(code)

    if not code:
        raise ValueError("銘柄コードがありません")

    ticker = yf.Ticker(code)
    data = ticker.history(period="3mo", auto_adjust=True)
    data = data.dropna(subset=["High", "Low", "Close"])

    if len(data) < 20:
        raise ValueError("株価データを十分に取得できませんでした")

    current_price = float(data["Close"].iloc[-1])
    atr = calculate_atr(data)

    plan = calculate_trade_plan(
        capital,
        current_price,
        atr
    )
    plan["code"] = code

    return plan


def create_sbi_analysis_embed(plan):
    shares = plan["shares"]

    if shares > 0:
        status = "🟢 資金・リスク条件内"
        shares_text = f"{shares}株"
        investment_text = f"{plan['investment']:,.0f}円"
        color = SBI_BLUE
    else:
        status = "🟠 今回は見送り候補"
        shares_text = "0株"
        investment_text = "1株あたりのリスクが上限を超えます"
        color = 0xD9822B

    return {
        "title": f"SBI短期売買プラン | {plan['code']}",
        "description": status,
        "color": color,
        "fields": [
            {
                "name": "💹 参考価格",
                "value": f"{plan['current_price']:,.2f}円",
                "inline": True
            },
            {
                "name": "💰 運用資金",
                "value": f"{plan['capital']:,.0f}円",
                "inline": True
            },
            {
                "name": "🛒 購入候補",
                "value": f"{shares_text}\n{investment_text}",
                "inline": False
            },
            {
                "name": "🎯 利確候補",
                "value": (
                    f"{plan['take_profit']:,.2f}円 "
                    f"(+{plan['take_profit_rate']:.2f}%)"
                ),
                "inline": True
            },
            {
                "name": "🛑 損切り候補",
                "value": (
                    f"{plan['stop_loss']:,.2f}円 "
                    f"(-{plan['stop_loss_rate']:.2f}%)"
                ),
                "inline": True
            },
            {
                "name": "⚖️ 最大想定損失",
                "value": (
                    f"約{plan['max_loss']:,.0f}円 "
                    f"(資金の{plan['risk_rate']:.2f}%)\n"
                    f"許容上限：約{plan['risk_budget']:,.0f}円"
                ),
                "inline": False
            },
            {
                "name": "📊 計算根拠",
                "value": (
                    f"14日ATR：{plan['atr']:,.2f}円\n"
                    "リスク上限：運用資金の1%\n"
                    "リスク・リワード：1 : 2"
                ),
                "inline": False
            },
            {
                "name": "⏰ S株の注意",
                "value": (
                    "表示価格で即時約定するわけではありません。\n"
                    "注文時刻により、前場始値・後場始値・後場引け・"
                    "翌営業日前場始値のいずれかで約定します。"
                ),
                "inline": False
            }
        ],
        "footer": {
            "text": "目標価格は予測ではなく計算上の候補です。最終判断はご自身で行ってください"
        }
    }

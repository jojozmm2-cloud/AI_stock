import yfinance as yf
from ta.momentum import RSIIndicator
from alerts import send_notification
from ta.trend import MACD
from ta.volatility import BollingerBands

def format_number(value, decimals=2):
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}"

    return "不明"


def format_trillion(value):
    if isinstance(value, (int, float)):
        return f"{value / 1_000_000_000_000:.2f}兆円"

    return "不明"

def analyze_stock(code):

    result = ""

    print("\n=== 前日との比較 ===\n")
    result += "=== 前日との比較 ===\n\n"

    ticker = yf.Ticker(code)
    data = ticker.history(period="3mo")

    info = ticker.info

    per = info.get("trailingPE", "不明")
    pbr = info.get("priceToBook", "不明")
    market_cap = info.get("marketCap", "不明")
    dividend = info.get("dividendYield", "不明")
    revenue = info.get("totalRevenue", "不明")
    operating_income = info.get("operatingMargins", "不明")
    net_income = info.get("netIncomeToCommon", "不明")
    eps = info.get("trailingEps", "不明")
    print("売上高:", revenue)
    print("営業利益率:", operating_income)
    print("純利益:", net_income)
    print("EPS:", eps)

    print("PER:", per)
    print("PBR:", pbr)
    print("配当:", dividend)
    print("時価総額:", market_cap)

    data = data.dropna(subset=["Close"])

    if data.empty or len(data) < 20:
        return f"{code} の株価データを取得できませんでした。\n銘柄コードを確認して、もう一度試してください。"

    name = code
    currency = "円" if code.endswith(".T") else "ドル"

    if len(data) >= 20:
            yesterday = data["Close"].iloc[-2]
            today = data["Close"].iloc[-1]
            daily_change = today - yesterday
            daily_change_rate = daily_change / yesterday * 100
            ma20 = data["Close"].rolling(20).mean().iloc[-1]

            rate = (today - ma20) / ma20 * 100

            rsi = RSIIndicator(data["Close"], window=14)
            rsi_value = rsi.rsi().iloc[-1]

            macd = MACD(data["Close"])
            macd_value = macd.macd().iloc[-1]
            macd_signal = macd.macd_signal().iloc[-1]
            bb = BollingerBands(data["Close"])
            bb_upper = bb.bollinger_hband().iloc[-1]
            bb_lower = bb.bollinger_lband().iloc[-1]

            print(f"{name} 今日: {today:.2f}円 / 20日平均: {ma20:.2f}円")
            result += f"{name} 今日: {today:.2f}{currency} / 20日平均: {ma20:.2f}{currency}\n"
            result += f"前日比: {daily_change:+.2f}{currency} ({daily_change_rate:+.2f}%)\n"
            print(f"20日平均との差: {rate:.2f}%")
            result += f"20日平均との差: {rate:.2f}%\n"
            print(f"RSI: {rsi_value:.2f}")
            result += f"RSI: {rsi_value:.2f}\n"
            result += f"MACD: {macd_value:.2f}\n"
            result += f"MACDシグナル: {macd_signal:.2f}\n"
            result += f"ボリンジャー上限: {bb_upper:.2f}\n"
            result += f"ボリンジャー下限: {bb_lower:.2f}\n"
            result += f"PER: {format_number(per)}倍\n"
            result += f"PBR: {format_number(pbr)}倍\n"
            result += f"配当利回り: {format_number(dividend)}%\n"
            result += f"時価総額: {format_trillion(market_cap)}\n"

            result += f"EPS: {eps}円\n"
            result += f"売上高: {format_trillion(revenue)}\n"

            if isinstance(operating_income, (int, float)):
                result += f"営業利益率: {operating_income * 100:.1f}%\n"
            else:
                result += "営業利益率: 不明\n"

            if isinstance(net_income, (int, float)):
                result += f"純利益: {net_income / 1_000_000_000:.1f}億円\n"
            else:
                result += "純利益: 不明\n"

            if today > bb_upper:
               result += "⚠️ 価格: 高め\n"
            elif today < bb_lower:
               result += "🟢 価格: 安め\n"
            else:
               result += "⚪ 価格: 通常の範囲\n"

            if macd_value > macd_signal:
                result += "📈 MACD: 上向き\n"
            else:
                result += "📉 MACD: 下向き\n"

            if rsi_value >= 70:
                print("🔴 RSI：買われすぎ")
                result += "🔴 RSI: 買われすぎ\n"
            elif rsi_value <= 30:
                print("🟢 RSI：売られすぎ")
                result += "🟢 RSI: 売られすぎ\n"
            else:
                print("⚪ RSI：普通")
                result += "⚪ RSI: 普通\n"

            if rate >= 5:
                print(f"{name}: 🚀 強い上昇")
                result += f"{name}: 🚀 強い上昇\n"
            elif rate >= 0:
                print(f"{name}: 📈 上昇傾向")
                result += f"{name}: 📈 上昇傾向\n"
            elif rate >= -5:
                print(f"{name}: 📉 下降傾向")
                result += f"{name}: 📉 下降傾向\n"
            else:
                print(f"{name}: ⚠️ 強い下落")
                result += f"{name}: ⚠️ 強い下落\n"
            if rate >= 0 and 30 <= rsi_value <= 70 and macd_value > macd_signal:
               print("総合判定: 買い候補")
               result += "総合判定: 買い候補\n"
            elif rate < 0 and macd_value < macd_signal:
               print("総合判定: 売り警戒")
               result += "総合判定: 売り警戒\n"
            else:
               print("総合判定: 様子見")
               result += "総合判定: 様子見\n"

    result += "\n"

    return result
"""3万円運用を想定した、かぶミニの売買プラン計算。"""
import math
from rakuten_config import DEFAULT_CAPITAL, DEFAULT_REWARD_RISK_RATIO, DEFAULT_RISK_RATE, DEFAULT_SPREAD_RATE, DEFAULT_TAX_RATE
from rakuten_names import RAKUTEN_NAMES
from sbi_analysis import calculate_atr, normalize_code


def calculate_rakuten_trade_plan(current_price, atr, capital=DEFAULT_CAPITAL, spread_rate=DEFAULT_SPREAD_RATE, tax_rate=DEFAULT_TAX_RATE, risk_rate=DEFAULT_RISK_RATE, reward_risk_ratio=DEFAULT_REWARD_RISK_RATIO):
    """spread_rateを売買それぞれに適用し、表示価格と想定約定価格を分けて返す。"""
    capital, current_price, atr, spread_rate = max(int(float(capital)), 0), float(current_price), float(atr), float(spread_rate)
    if current_price <= 0 or atr < 0 or not 0 <= spread_rate < 1:
        raise ValueError("価格、ATR、スプレッド率を確認してください")
    entry_price = current_price * (1 + spread_rate)
    stop_distance = max(atr, current_price * 0.02)
    target_quote = current_price + stop_distance * reward_risk_ratio
    stop_quote = max(current_price - stop_distance, 0)
    target_exit_price = target_quote * (1 - spread_rate)
    stop_exit_price = stop_quote * (1 - spread_rate)
    loss_per_share = max(entry_price - stop_exit_price, 0)
    risk_budget = capital * risk_rate
    shares_by_capital = math.floor(capital / entry_price)
    shares_by_risk = math.floor(risk_budget / loss_per_share) if loss_per_share else shares_by_capital
    shares = max(min(shares_by_capital, shares_by_risk), 0)
    investment = shares * entry_price
    gross_after_spread = shares * (target_exit_price - entry_price)
    estimated_tax = max(gross_after_spread, 0) * tax_rate
    spread_cost = shares * ((entry_price - current_price) + (target_quote - target_exit_price))
    return {"capital": capital, "current_price": current_price, "atr": atr, "spread_rate": spread_rate, "entry_price": entry_price, "shares": shares, "shares_by_capital": shares_by_capital, "shares_by_risk": shares_by_risk, "investment": investment, "take_profit_quote": target_quote, "take_profit_execution": target_exit_price, "stop_loss_quote": stop_quote, "stop_loss_execution": stop_exit_price, "max_loss": shares * loss_per_share, "risk_budget": risk_budget, "gross_profit_after_spread": gross_after_spread, "estimated_tax": estimated_tax, "net_profit": gross_after_spread - estimated_tax, "spread_cost_at_target": spread_cost}


def get_rakuten_trade_plan(code, capital=DEFAULT_CAPITAL, spread_rate=DEFAULT_SPREAD_RATE):
    import yfinance as yf
    code = normalize_code(code)
    data = yf.Ticker(code).history(period="3mo", auto_adjust=True).dropna(subset=["High", "Low", "Close"])
    if len(data) < 20:
        raise ValueError("売買プランに必要な株価データを取得できませんでした")
    plan = calculate_rakuten_trade_plan(float(data["Close"].iloc[-1]), calculate_atr(data), capital, spread_rate)
    plan["code"] = code
    return plan


def create_rakuten_trade_plan_embed(plan):
    code = plan["code"]
    name = RAKUTEN_NAMES.get(code, "会社名未登録")
    return {"title": f"楽天かぶミニ 売買プラン：{name}（{code.replace('.T', '')}）", "description": "1株単位・リアルタイム取引を想定した試算です。", "color": 0xBF0000, "fields": [
        {"name": "購入プラン", "value": f"{plan['shares']}株 / 約 {plan['investment']:,.0f}円", "inline": False},
        {"name": "想定買い約定価格", "value": f"{plan['entry_price']:,.2f}円", "inline": True},
        {"name": "利確の表示価格", "value": f"{plan['take_profit_quote']:,.2f}円", "inline": True},
        {"name": "損切りの表示価格", "value": f"{plan['stop_loss_quote']:,.2f}円", "inline": True},
        {"name": "最大想定損失", "value": f"約 {plan['max_loss']:,.0f}円", "inline": True},
        {"name": "税引後の想定利益", "value": f"約 {plan['net_profit']:,.0f}円", "inline": True},
        {"name": "スプレッド想定コスト", "value": f"約 {plan['spread_cost_at_target']:,.0f}円", "inline": True}],
        "footer": {"text": f"スプレッドは売買それぞれ {plan['spread_rate'] * 100:.2f}% として試算。実際の約定を保証しません。"}}


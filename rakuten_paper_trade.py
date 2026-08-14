"""楽天かぶミニ向けの、実注文を行わない紙上取引記録。"""

import json
import math
from datetime import date
from pathlib import Path

from rakuten_config import DEFAULT_CAPITAL, DEFAULT_SPREAD_RATE, DEFAULT_TAX_RATE


def load_paper_state(path, capital=DEFAULT_CAPITAL):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"initial_capital": float(capital), "cash": float(capital), "pending": None,
            "position": None, "closed_trades": [], "last_market_date": None}


def save_paper_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _close_position(state, quote, market_date, reason, spread_rate, tax_rate):
    position = state["position"]
    execution = float(quote) * (1 - spread_rate)
    proceeds = execution * position["shares"]
    gross_profit = proceeds - position["cost"]
    tax = max(gross_profit, 0) * tax_rate
    state["cash"] += proceeds - tax
    trade = {**position, "exit_date": market_date, "exit_price": execution,
             "profit": gross_profit - tax, "tax": tax, "exit_reason": reason}
    state["closed_trades"].append(trade)
    state["position"] = None
    return f"仮売却: {position['name']}（{reason}） {trade['profit']:+,.0f}円"


def update_paper_state(state, candidates, spread_rate=DEFAULT_SPREAD_RATE,
                       tax_rate=DEFAULT_TAX_RATE):
    """1営業日分を反映する。同じ市場日を二重処理しない。"""
    if not candidates:
        return state, ["株価データを取得できませんでした"]
    by_code = {item["code"]: item for item in candidates}
    market_date = max(item["market_date"] for item in candidates)
    if state.get("last_market_date") == market_date:
        return state, ["本日の紙上取引はすでに記録済みです"]

    events = []
    pending = state.get("pending")
    if pending and pending["signal_date"] < market_date:
        item = by_code.get(pending["code"])
        if item:
            quote = float(item["latest_open"])
            entry = quote * (1 + spread_rate)
            stop_distance = max(float(pending["atr"]), quote * 0.02)
            stop_quote = max(quote - stop_distance, 0)
            risk_per_share = entry - stop_quote * (1 - spread_rate)
            capital_shares = math.floor(state["cash"] / entry)
            risk_shares = math.floor(state["initial_capital"] * 0.01 / risk_per_share)
            shares = max(min(capital_shares, risk_shares), 0)
            if shares:
                cost = entry * shares
                state["cash"] -= cost
                state["position"] = {
                    "code": item["code"], "name": item["name"],
                    "signal_date": pending["signal_date"], "entry_date": market_date,
                    "entry_price": entry, "shares": shares, "cost": cost,
                    "stop_quote": stop_quote, "target_quote": quote + stop_distance * 2,
                    "holding_days": 0,
                }
                events.append(f"仮購入: {item['name']} {shares}株 × {entry:,.2f}円")
            state["pending"] = None

    position = state.get("position")
    if position:
        item = by_code.get(position["code"])
        if item:
            position["holding_days"] += 1
            if float(item["latest_low"]) <= position["stop_quote"]:
                events.append(_close_position(state, position["stop_quote"], market_date,
                                              "損切り", spread_rate, tax_rate))
            elif float(item["latest_high"]) >= position["target_quote"]:
                events.append(_close_position(state, position["target_quote"], market_date,
                                              "利確", spread_rate, tax_rate))
            else:
                continuation = item["score"] >= 55 and item["latest_close"] > item["ma20"]
                if position["holding_days"] >= 10:
                    events.append(_close_position(state, item["latest_close"], market_date,
                                                  "最大10営業日", spread_rate, tax_rate))
                elif position["holding_days"] >= 5 and not continuation:
                    events.append(_close_position(state, item["latest_close"], market_date,
                                                  "上昇条件終了", spread_rate, tax_rate))

    if not state.get("position") and not state.get("pending"):
        eligible = [item for item in candidates if item["score"] >= 75]
        if eligible:
            best = max(eligible, key=lambda item: item["score"])
            state["pending"] = {"code": best["code"], "name": best["name"],
                                "signal_date": market_date, "signal_price": best["latest_close"],
                                "atr": best["atr"]}
            events.append(f"翌営業日の仮購入を予約: {best['name']}（{best['score']}点）")

    state["last_market_date"] = market_date
    if not events:
        events.append("売買なし: 短期候補が出るまで現金で待機")
    return state, events


def create_paper_trade_embed(state, events):
    position, pending = state.get("position"), state.get("pending")
    closed = state.get("closed_trades", [])
    realized = sum(float(item["profit"]) for item in closed)
    if position:
        status = f"保有中: {position['name']} {position['shares']}株 / {position['holding_days']}営業日"
    elif pending:
        status = f"購入待ち: {pending['name']}（次の営業日始値）"
    else:
        status = "保有なし（現金で待機）"
    return {"title": "楽天かぶミニ 3万円紙上取引",
            "description": "実際の注文は行わず、買ったつもりで成績を記録します。",
            "color": 0x2E8B57,
            "fields": [
                {"name": "本日の動き", "value": "\n".join(events), "inline": False},
                {"name": "現在の状態", "value": status, "inline": False},
                {"name": "現金残高", "value": f"{state['cash']:,.0f}円", "inline": True},
                {"name": "確定損益", "value": f"{realized:+,.0f}円", "inline": True},
                {"name": "終了した取引", "value": f"{len(closed)}回", "inline": True}],
            "footer": {"text": f"最終記録日: {state.get('last_market_date') or date.today().isoformat()} / スプレッド・税を考慮"}}

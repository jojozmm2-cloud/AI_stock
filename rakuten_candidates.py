"""かぶミニ向け銘柄候補の管理とランキング。"""

from sbi_candidates import load_symbols, score_candidate
from rakuten_names import RAKUTEN_NAMES

RAKUTEN_RED = 0xBF0000


def get_rakuten_candidates(capital=30_000, limit=5, symbols_filename="rakuten_kabumini_symbols.txt"):
    import yfinance as yf
    capital = int(float(capital))
    if capital <= 0:
        raise ValueError("運用資金は1円以上にしてください")
    symbols = load_symbols(symbols_filename)
    downloaded = yf.download(symbols, period="3mo", auto_adjust=True, group_by="ticker", threads=True, progress=False)
    candidates = []
    for symbol in symbols:
        try:
            data = downloaded[symbol] if len(symbols) > 1 else downloaded
            candidate = score_candidate(data, capital)
            if candidate:
                candidate["code"] = symbol
                candidates.append(candidate)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return sorted(candidates, key=lambda item: (item["score"], item["volume_ratio"], item["change_5d"]), reverse=True)[:limit]


def create_rakuten_candidates_embed(candidates, capital):
    fields = []
    for index, item in enumerate(candidates, start=1):
        code = item["code"].replace(".T", "")
        name = RAKUTEN_NAMES.get(item["code"], "会社名未登録")
        reasons = "・".join(item["reasons"]) or "数値条件による総合判定"
        fields.append({"name": f"{index}. {name}（{code}）", "value": f"参考価格 **{item['price']:,.2f}円** / スコア {item['score']}点\n買える上限 {item['affordable_shares']}株 / RSI {item['rsi']:.1f}\n理由: {reasons}", "inline": False})
    if not fields:
        fields.append({"name": "今回の結果", "value": "条件に合う候補がありませんでした。", "inline": False})
    return {"title": "楽天かぶミニ 銘柄候補", "description": f"運用資金 {int(float(capital)):,.0f}円。既存の分析条件で順位付けしました。", "color": RAKUTEN_RED, "fields": fields, "footer": {"text": "売買推奨ではありません。注文前にリアルタイム取引対象か確認してください。"}}

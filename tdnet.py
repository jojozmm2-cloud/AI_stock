from datetime import date, timedelta
from html import unescape
from io import BytesIO
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


TDNET_BASE = "https://www.release.tdnet.info/inbs"
POSITIVE_TERMS = (
    "上方修正", "増配", "自己株式の取得", "自己株式取得", "自社株買い",
    "株式分割", "最高益", "受注", "業務提携",
)
NEGATIVE_TERMS = (
    "下方修正", "減配", "無配", "赤字", "特別損失", "債務超過",
    "不正", "行政処分", "訴訟", "事故", "回収", "継続企業の前提",
)
HIGH_VALUE_TERMS = (
    "業績予想", "配当", "自己株式", "自社株", "特別利益", "特別損失",
    "債務超過", "継続企業", "不正", "訴訟", "行政処分",
)
TITLE_NEUTRAL_TERMS = (
    "スポンサー", "協賛", "サービス開始", "サービス提供", "PR情報",
    "取得状況", "取得終了", "月次", "訂正", "取消", "経過",
)


def _text(value):
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _cell(row, class_name):
    match = re.search(
        rf'<td[^>]*class=["\'][^"\']*{class_name}[^"\']*["\'][^>]*>(.*?)</td>',
        row, flags=re.I | re.S,
    )
    return _text(match.group(1)) if match else ""


def parse_tdnet_html(html, disclosed_on):
    disclosures = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.I | re.S):
        code = _cell(row, "kjCode")
        title = _cell(row, "kjTitle")
        if not re.fullmatch(r"\d{4,5}", code) or not title:
            continue
        link = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', row, flags=re.I)
        url = link.group(1) if link else ""
        url = urljoin(f"{TDNET_BASE}/", url)
        disclosures.append({
            "date": disclosed_on,
            "time": _cell(row, "kjTime"),
            "code": code[:4],
            "company": _cell(row, "kjName"),
            "title": title,
            "url": url,
        })
    return disclosures


def classify_disclosure(title):
    if any(term in title for term in NEGATIVE_TERMS):
        return "negative"
    if any(term in title for term in TITLE_NEUTRAL_TERMS):
        return "neutral"
    # 提携は規模や業績影響が本文で確認できるまでは中立。
    if "提携" in title or "基本合意" in title:
        return "neutral"
    if any(term in title for term in POSITIVE_TERMS):
        return "positive"
    return "neutral"


def extract_pdf_text(url, max_pages=8):
    if not url:
        return ""
    from pypdf import PdfReader

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        reader = PdfReader(BytesIO(response.read()))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:max_pages])


def analyze_disclosure_document(item, text):
    compact = re.sub(r"\s+", "", text)
    title = item["title"]
    base = classify_disclosure(title)
    metrics = []
    for value in re.findall(r"(?:増減率|修正率|取得割合|上限)[：:]?([▲△+\-]?\d+(?:\.\d+)?)%", compact):
        if value not in metrics:
            metrics.append(value)
    impact_unknown = any(phrase in compact for phrase in (
        "業績に与える影響は軽微", "業績への影響は軽微", "影響はありません",
        "現時点では未定", "精査中",
    ))
    negative = base == "negative" or any(term in compact for term in NEGATIVE_TERMS)
    positive = base == "positive"
    if "提携" in title or "基本合意" in title:
        positive = (
            not impact_unknown
            and any(term in compact for term in ("業績予想を上方修正", "売上高への影響", "営業利益への影響"))
        )
    if any(term in title for term in TITLE_NEUTRAL_TERMS):
        positive = False
    sentiment = "negative" if negative else "positive" if positive else "neutral"
    return {
        "sentiment": sentiment,
        "document_checked": bool(text),
        "impact_unknown": impact_unknown,
        "metrics": metrics[:4],
    }


def enrich_disclosures(items, max_documents=20):
    checked = 0
    attempted = 0
    for item in items:
        if attempted >= max_documents or not any(term in item["title"] for term in HIGH_VALUE_TERMS):
            item.setdefault("document_checked", False)
            continue
        attempted += 1
        try:
            text = extract_pdf_text(item["url"])
            item.update(analyze_disclosure_document(item, text))
            checked += 1
        except Exception as error:
            item["document_checked"] = False
            item["document_error"] = str(error)
    return items


def fetch_recent_tdnet(days=7, today=None, max_pages=5):
    today = today or date.today()
    result = {}
    for offset in range(days):
        disclosed_on = today - timedelta(days=offset)
        for page in range(1, max_pages + 1):
            url = f"{TDNET_BASE}/I_list_{page:03d}_{disclosed_on:%Y%m%d}.html"
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urlopen(request, timeout=20) as response:
                    html = response.read().decode("utf-8", errors="replace")
            except (HTTPError, URLError, TimeoutError, OSError):
                break
            items = parse_tdnet_html(html, disclosed_on)
            if not items:
                break
            for item in items:
                item["sentiment"] = classify_disclosure(item["title"])
                result.setdefault(item["code"], []).append(item)
    return result


def summarize_tdnet(items):
    if not items:
        return {"confidence": "中立", "negative": False, "items": []}
    ordered = sorted(items, key=lambda item: (item["date"], item["time"]), reverse=True)
    negative = any(item["sentiment"] == "negative" for item in ordered)
    positive = any(item["sentiment"] == "positive" for item in ordered)
    return {
        "confidence": (
            "高（TDnet本文確認済み）"
            if any(item.get("document_checked") for item in ordered)
            else "高（TDnet公式表題）"
        ),
        "negative": negative,
        "positive": positive and not negative,
        "items": ordered[:3],
    }


def create_tdnet_test_embed(disclosures):
    all_items = [item for items in disclosures.values() for item in items]
    all_items.sort(key=lambda item: (item["date"], item["time"]), reverse=True)
    relevant = [item for item in all_items if any(term in item["title"] for term in HIGH_VALUE_TERMS)]
    enrich_disclosures(relevant, max_documents=30)
    positive = [item for item in all_items if item["sentiment"] == "positive"]
    negative = [item for item in all_items if item["sentiment"] == "negative"]
    attempted = [item for item in relevant if item.get("document_checked") or item.get("document_error")]
    failures = [item for item in attempted if item.get("document_error")]

    def format_items(items, empty):
        if not items:
            return empty
        lines = []
        for item in items[:5]:
            label = f"{item['code']} {item['company']}｜{item['title']}"
            checked = "本文確認" if item.get("document_checked") else "表題判定"
            metrics = f"｜数値: {', '.join(item.get('metrics', []))}%" if item.get("metrics") else ""
            lines.append(f"・[{label}]({item['url']})（{item['date']:%m/%d} {item['time']}｜{checked}{metrics}）")
        return "\n".join(lines)

    return {
        "title": "🏛️ TDnet公式情報 取得テスト",
        "description": (
            "JPXの適時開示情報を直近7日分確認しました。\n"
            f"取得：**{len(all_items)}件／{len(disclosures)}銘柄**　"
            f"好材料候補：{len(positive)}件　注意材料：{len(negative)}件\n"
            f"PDF本文確認：**{sum(bool(item.get('document_checked')) for item in relevant)}件**／"
            f"試行{len(attempted)}件　失敗{len(failures)}件"
        ),
        "color": 0x1D5FA7,
        "fields": [
            {"name": "🟢 好材料候補", "value": format_items(positive, "該当なし"), "inline": False},
            {"name": "🔴 注意材料", "value": format_items(negative, "該当なし"), "inline": False},
            *([{
                "name": "⚠️ PDF取得エラー",
                "value": f"{failures[0]['url']}\n{failures[0]['document_error'][:500]}",
                "inline": False,
            }] if failures else []),
        ],
        "footer": {"text": "公式PDF本文を優先し、本文未確認の資料は売買根拠に使用しません。"},
    }


def run_tdnet_event_test(days=7):
    """TDnet好材料後の短期リターンをTOPIXと比較する予備検証。"""
    import pandas as pd
    import yfinance as yf

    disclosures = fetch_recent_tdnet(days=days)
    all_items = [item for items in disclosures.values() for item in items]
    relevant = [item for item in all_items if any(term in item["title"] for term in HIGH_VALUE_TERMS)]
    enrich_disclosures(relevant, max_documents=60)
    events = [
        item for item in relevant
        if item.get("document_checked") and item.get("sentiment") == "positive"
    ]
    if not events:
        return {"events": [], "evaluated": 0, "wins": 0, "average_excess": 0.0}

    symbols = sorted({f"{item['code']}.T" for item in events})
    start = min(item["date"] for item in events) - timedelta(days=5)
    end = date.today() + timedelta(days=1)
    prices = yf.download(
        symbols + ["1306.T"], start=start, end=end, auto_adjust=True,
        group_by="ticker", threads=True, progress=False,
    )

    def frame(symbol):
        try:
            data = prices[symbol] if len(symbols) + 1 > 1 else prices
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data.dropna(subset=["Open", "Close"])
        except (KeyError, TypeError):
            return pd.DataFrame()

    benchmark = frame("1306.T")
    results = []
    for item in events:
        stock = frame(f"{item['code']}.T")
        if stock.empty or benchmark.empty:
            continue
        disclosed = pd.Timestamp(item["date"])
        # 15時以降の開示は翌営業日、場中開示は次の始値から測る。
        stock_future = stock.loc[stock.index.tz_localize(None).normalize() > disclosed]
        benchmark_future = benchmark.loc[benchmark.index.tz_localize(None).normalize() > disclosed]
        if stock_future.empty or benchmark_future.empty:
            continue
        stock_return = (float(stock_future["Close"].iloc[-1]) / float(stock_future["Open"].iloc[0]) - 1) * 100
        market_return = (float(benchmark_future["Close"].iloc[-1]) / float(benchmark_future["Open"].iloc[0]) - 1) * 100
        excess = stock_return - market_return
        results.append({**item, "stock_return": stock_return, "market_return": market_return, "excess": excess})
    wins = sum(item["excess"] > 0 for item in results)
    return {
        "events": results,
        "evaluated": len(results),
        "wins": wins,
        "average_excess": sum(item["excess"] for item in results) / len(results) if results else 0.0,
    }


def create_tdnet_event_test_embed(result):
    evaluated = result["evaluated"]
    win_rate = result["wins"] / evaluated * 100 if evaluated else 0
    rows = []
    for item in sorted(result["events"], key=lambda value: value["excess"], reverse=True)[:10]:
        rows.append(
            f"・{item['code']} {item['company']}｜株 {item['stock_return']:+.2f}%｜"
            f"対TOPIX {item['excess']:+.2f}%"
        )
    verdict = (
        "✅ 予備検証では改善傾向" if evaluated >= 5 and win_rate >= 55 and result["average_excess"] > 0
        else "❌ 現時点では改善を確認できず"
    )
    return {
        "title": "🧪 TDnet好材料 短期イベント検証",
        "description": (
            f"本文確認済みの好材料を、発表後の株価とTOPIXで比較しました。\n"
            f"評価可能：**{evaluated}件**｜対TOPIX勝率：**{win_rate:.1f}%**｜"
            f"平均超過収益：**{result['average_excess']:+.2f}%**\n{verdict}"
        ),
        "color": 0x1D5FA7,
        "fields": [{"name": "イベント別結果", "value": "\n".join(rows) or "評価可能なイベントなし", "inline": False}],
        "footer": {"text": "直近7日だけの予備検証です。候補戦略全体の勝率ではありません。"},
    }

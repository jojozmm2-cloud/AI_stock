from io import BytesIO
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd

from sbi_names import SBI_NAMES
from tdnet import fetch_recent_tdnet, summarize_tdnet


SBI_BLUE = 0x1D5FA7
JPX_LIST_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
MIN_AVERAGE_TURNOVER = 100_000_000
MAX_LIQUID_UNIVERSE = 500
DOWNLOAD_BATCH_SIZE = 100
RISK_RATE = 0.01
REWARD_MULTIPLE = 2.0
TAX_RATE = 0.20315
MARKET_BENCHMARKS = {"日経平均": "^N225", "TOPIX連動ETF": "1306.T"}
EARNINGS_CHECK_POOL = 30
JST = ZoneInfo("Asia/Tokyo")
ADVERSE_ENTRY_SLIPPAGE = 0.005
MIN_LIVE_SCORE = 92
MIN_HISTORY_SIGNALS = 5
MIN_HISTORY_WIN_RATE = 55.0
MIN_HISTORY_PROFIT_FACTOR = 1.20
HISTORY_HOLDING_DAYS = 10


class CandidateList(list):
    def __init__(self, values=(), market=None):
        super().__init__(values)
        self.market = market or {"status": "unknown", "label": "地合い取得失敗"}


def load_symbols(filename="sbi_symbols.txt"):
    path = Path(__file__).with_name(filename)
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def load_prime_universe():
    """JPXの最新一覧からプライム内国普通株と業種情報を取得する。"""
    try:
        request = Request(JPX_LIST_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=30) as response:
            listed = pd.read_excel(BytesIO(response.read()))
        market_column = next(column for column in listed.columns if "市場・商品区分" in str(column))
        code_column = next(column for column in listed.columns if str(column).strip() == "コード")
        name_column = next(column for column in listed.columns if "銘柄名" in str(column))
        sector_column = next(
            (column for column in listed.columns if "33業種区分" in str(column)),
            None,
        )
        prime = listed[listed[market_column].astype(str).str.contains("プライム（内国株式）")]
        symbols = []
        metadata = {}
        for _, row in prime.iterrows():
            code = str(row[code_column]).strip()
            if code.isdigit() and len(code) == 4:
                symbol = f"{code}.T"
                symbols.append(symbol)
                metadata[symbol] = {
                    "name": str(row[name_column]).strip(),
                    "sector": (
                        str(row[sector_column]).strip()
                        if sector_column is not None else "不明"
                    ),
                }
        if not symbols:
            raise ValueError("プライム銘柄を取得できませんでした")
        return symbols, metadata
    except (OSError, StopIteration, TypeError, ValueError, URLError) as error:
        print(f"JPX銘柄一覧の取得に失敗。固定リストを使用します: {error}")
        return load_symbols(), {}


def load_prime_symbols():
    symbols, metadata = load_prime_universe()
    return symbols, {
        symbol: item.get("name", "会社名未登録")
        for symbol, item in metadata.items()
    }


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    latest_gain = float(gain.iloc[-1])
    latest_loss = float(loss.iloc[-1])
    if latest_loss == 0:
        return 100.0 if latest_gain > 0 else 50.0
    relative_strength = gain / loss
    return float((100 - (100 / (1 + relative_strength))).iloc[-1])


def calculate_atr(data, period=14):
    high = data["High"].astype(float)
    low = data["Low"].astype(float)
    close = data["Close"].astype(float)
    true_range = pd.concat(
        [(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return float(true_range.tail(period).mean())


def average_turnover(data):
    clean = data.dropna(subset=["Close", "Volume"])
    if len(clean) < 20:
        return 0.0
    return float((clean["Close"].astype(float) * clean["Volume"].astype(float)).tail(20).mean())


def evaluate_market_data(data):
    clean = data.dropna(subset=["Close"])
    if len(clean) < 21:
        return None
    close = clean["Close"].astype(float)
    price = float(close.iloc[-1])
    ma20 = float(close.tail(20).mean())
    change_5d = float((price / close.iloc[-6] - 1) * 100)
    return {
        "price": price,
        "ma20": ma20,
        "change_5d": change_5d,
        "weak": price < ma20,
        "sharp_drop": change_5d <= -3,
    }


def get_market_regime():
    """日経平均とTOPIXから、候補数を調整するための地合いを判定する。"""
    import yfinance as yf

    details = {}
    for name, symbol in MARKET_BENCHMARKS.items():
        try:
            data = yf.download(
                symbol,
                period="3mo",
                auto_adjust=True,
                progress=False,
                timeout=20,
            )
            # yfinanceの単一銘柄でもMultiIndexになる版に対応する。
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            result = evaluate_market_data(data)
            if result:
                details[name] = result
        except Exception as error:
            print(f"地合いデータ取得失敗 {name}: {error}")

    if len(details) < len(MARKET_BENCHMARKS):
        return {
            "status": "unknown",
            "label": "⚪ 地合い判定なし",
            "description": "指数データを取得できなかったため、地合いによる除外はしていません。",
            "limit": 5,
            "details": details,
        }
    weak_count = sum(item["weak"] for item in details.values())
    sharp_drop = any(item["sharp_drop"] for item in details.values())
    if sharp_drop or weak_count == 2:
        return {
            "status": "risk_off",
            "label": "🔴 地合い悪化・見送り",
            "description": "日経平均・TOPIXの下落条件により、今日は新規候補を出しません。",
            "limit": 0,
            "details": details,
        }
    if weak_count == 1:
        return {
            "status": "cautious",
            "label": "🟡 地合い注意",
            "description": "指数の一方が20日線を下回っているため、候補を最大3銘柄に絞ります。",
            "limit": 3,
            "details": details,
        }
    return {
        "status": "normal",
        "label": "🟢 地合い良好",
        "description": "日経平均・TOPIXとも極端な悪化条件には該当していません。",
        "limit": 5,
        "details": details,
    }


def in_earnings_blackout(earnings_date, today=None):
    if not earnings_date:
        return False
    today = today or datetime.now(JST).date()
    if isinstance(earnings_date, datetime):
        earnings_date = earnings_date.date()
    start = (pd.Timestamp(earnings_date) - pd.offsets.BDay(3)).date()
    end = (pd.Timestamp(earnings_date) + pd.offsets.BDay(1)).date()
    return start <= today <= end


def get_next_earnings_date(symbol, today=None):
    """Yahoo Financeから直近の決算予定日を取得する。取れない場合はNone。"""
    import yfinance as yf

    today = today or datetime.now(JST).date()
    try:
        calendar = yf.Ticker(symbol).calendar
        if not calendar:
            return None
        raw_dates = calendar.get("Earnings Date") or calendar.get("EarningsDate")
        if not isinstance(raw_dates, (list, tuple)):
            raw_dates = [raw_dates]
        dates = []
        for raw_date in raw_dates:
            if raw_date is None:
                continue
            value = pd.Timestamp(raw_date).date()
            if value >= today - pd.Timedelta(days=1):
                dates.append(value)
        return min(dates) if dates else None
    except Exception as error:
        print(f"決算予定日取得失敗 {symbol}: {error}")
        return None


def next_weekday(value):
    value += timedelta(days=1)
    while value.weekday() >= 5:
        value += timedelta(days=1)
    return value


def get_next_s_stock_execution(now=None):
    """SBI公表のS株注文時間から次回約定時刻の目安を返す。祝日は最終画面で要確認。"""
    now = now or datetime.now(JST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    current_date = now.date()
    if current_date.weekday() >= 5:
        target_date = current_date
        while target_date.weekday() >= 5:
            target_date += timedelta(days=1)
        target_time = datetime_time(9, 0)
    elif now.time() < datetime_time(7, 0):
        target_date, target_time = current_date, datetime_time(9, 0)
    elif now.time() < datetime_time(10, 30):
        target_date, target_time = current_date, datetime_time(12, 30)
    elif now.time() < datetime_time(14, 0):
        target_date, target_time = current_date, datetime_time(15, 30)
    else:
        target_date, target_time = next_weekday(current_date), datetime_time(9, 0)
    execution = datetime.combine(target_date, target_time, tzinfo=JST)
    return {
        "datetime": execution,
        "label": execution.strftime("%Y-%m-%d %H:%Mごろ"),
    }


def score_candidate(data, capital, max_price=None, require_pullback=False):
    data = data.dropna(subset=["Close", "High", "Low", "Volume"])
    if len(data) < 25:
        return None
    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)
    price = float(close.iloc[-1])
    if price <= 0 or price > capital or (max_price is not None and price > float(max_price)):
        return None

    turnover = average_turnover(data)
    if turnover < MIN_AVERAGE_TURNOVER:
        return None
    ma5 = float(close.tail(5).mean())
    ma20 = float(close.tail(20).mean())
    change_5d = float((price / close.iloc[-6] - 1) * 100)
    change_1d = float((price / close.iloc[-2] - 1) * 100)
    average_volume = float(volume.iloc[-21:-1].mean())
    volume_ratio = float(volume.iloc[-1] / average_volume) if average_volume > 0 else 0
    rsi = calculate_rsi(close)
    atr = calculate_atr(data)
    if pd.isna(rsi) or pd.isna(atr) or atr <= 0:
        return None

    # S株は約定タイミングが限定されるため、過熱・急騰・下降トレンドを候補から外す。
    if rsi > 70 or not (price > ma20 and ma5 > ma20) or not (-1 <= change_5d <= 8):
        return None
    ma5_distance_atr = (price - ma5) / atr
    day_range = float(data["High"].iloc[-1] - data["Low"].iloc[-1])
    close_location = (
        float((price - data["Low"].iloc[-1]) / day_range)
        if day_range > 0 else 0.5
    )
    if require_pullback and not (
        1 <= change_5d <= 4
        and -0.25 <= ma5_distance_atr <= 1.0
        and change_1d <= 2.5
        and close_location <= 0.8
    ):
        return None

    assumed_entry_price = price * (1 + ADVERSE_ENTRY_SLIPPAGE)
    risk_per_share = max(atr, assumed_entry_price * 0.01)
    capital_shares = int(capital // assumed_entry_price)
    risk_budget = capital * RISK_RATE
    risk_shares = int(risk_budget // risk_per_share)
    shares = min(capital_shares, risk_shares)
    if shares < 1:
        return None

    stop_loss = max(1.0, assumed_entry_price - risk_per_share)
    take_profit = assumed_entry_price + risk_per_share * REWARD_MULTIPLE
    planned_loss = (assumed_entry_price - stop_loss) * shares
    gross_profit = (take_profit - assumed_entry_price) * shares
    take_profit_net_profit = gross_profit * (1 - TAX_RATE)
    reward_ratio = take_profit_net_profit / planned_loss if planned_loss else 0
    target_net_return = take_profit_net_profit / (assumed_entry_price * shares) * 100
    stress_loss_1_5x = planned_loss * 1.5
    stress_loss_2x = planned_loss * 2

    trend_score = min(25, 15 + max(0, min(10, (price / ma20 - 1) * 200)))
    rsi_score = max(5, 20 - abs(rsi - 54) * 0.8)
    momentum_score = max(5, 18 - abs(change_5d - 2.5) * 2)
    volume_score = min(15, 6 + volume_ratio * 5)
    liquidity_score = min(12, 3 + turnover / 200_000_000)
    profit_score = min(10, 4 + take_profit_net_profit / max(100, capital * 0.002))
    score = round(
        trend_score + rsi_score + momentum_score + volume_score
        + liquidity_score + profit_score
    )

    reasons = ["上昇トレンド", "S株向けリスク内"]
    if 45 <= rsi <= 62:
        reasons.append("RSIが適温")
    if volume_ratio >= 1.2:
        reasons.append("出来高が増加")
    if turnover >= 1_000_000_000:
        reasons.append("売買代金が十分")
    status = "🟢 条件良好" if score >= 85 else "🔵 要チェック"
    return {
        "price": price,
        "assumed_entry_price": assumed_entry_price,
        "score": score,
        "rsi": rsi,
        "change_5d": change_5d,
        "change_1d": change_1d,
        "atr": atr,
        "ma5_distance_atr": ma5_distance_atr,
        "close_location": close_location,
        "volume_ratio": volume_ratio,
        "average_turnover": turnover,
        "shares": shares,
        "investment": assumed_entry_price * shares,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "take_profit_net_profit": take_profit_net_profit,
        "planned_loss": planned_loss,
        "stress_loss_1_5x": stress_loss_1_5x,
        "stress_loss_2x": stress_loss_2x,
        "reward_ratio": reward_ratio,
        "target_net_return": target_net_return,
        "reasons": reasons,
        "status": status,
    }


def validate_candidate_history(data):
    """現在と同じ押し目条件が、過去データでプラスだったかを保守的に検証する。"""
    if not {"Open", "Close", "High", "Low", "Volume"}.issubset(data.columns):
        return None
    clean = data.dropna(subset=["Open", "Close", "High", "Low", "Volume"]).copy()
    if len(clean) < 120:
        return None

    outcomes = []
    for index in range(25, len(clean) - HISTORY_HOLDING_DAYS - 1):
        history = clean.iloc[:index + 1]
        close = history["Close"].astype(float)
        volume = history["Volume"].astype(float)
        price = float(close.iloc[-1])
        ma5 = float(close.tail(5).mean())
        ma20 = float(close.tail(20).mean())
        atr = calculate_atr(history)
        rsi = calculate_rsi(close)
        change_5d = float((price / close.iloc[-6] - 1) * 100)
        change_1d = float((price / close.iloc[-2] - 1) * 100)
        average_volume = float(volume.iloc[-21:-1].mean())
        volume_ratio = float(volume.iloc[-1] / average_volume) if average_volume > 0 else 0
        day_range = float(history["High"].iloc[-1] - history["Low"].iloc[-1])
        close_location = float((price - history["Low"].iloc[-1]) / day_range) if day_range > 0 else 0.5
        ma5_distance_atr = (price - ma5) / atr if atr > 0 else 99

        signal = (
            price > ma20 and ma5 > ma20
            and 45 <= rsi <= 62
            and 1 <= change_5d <= 4
            and change_1d <= 2.5
            and -0.25 <= ma5_distance_atr <= 1.0
            and close_location <= 0.8
            and volume_ratio >= 1.1
        )
        if not signal:
            continue

        future = clean.iloc[index + 1:index + 1 + HISTORY_HOLDING_DAYS]
        entry = float(future["Open"].iloc[0]) * (1 + ADVERSE_ENTRY_SLIPPAGE)
        risk = max(atr, entry * 0.01)
        stop, target = entry - risk, entry + risk * REWARD_MULTIPLE
        exit_price = float(future["Close"].iloc[-1])
        for _, row in future.iterrows():
            # 同日に両方へ触れた場合も損切りを先にした保守的な判定。
            if float(row["Low"]) <= stop:
                exit_price = stop
                break
            if float(row["High"]) >= target:
                exit_price = target
                break
        raw_return = (exit_price / entry - 1) * 100
        net_return = raw_return * (1 - TAX_RATE) if raw_return > 0 else raw_return
        outcomes.append(net_return)

    if len(outcomes) < MIN_HISTORY_SIGNALS:
        return None
    gains = sum(value for value in outcomes if value > 0)
    losses = abs(sum(value for value in outcomes if value < 0))
    profit_factor = gains / losses if losses else float("inf")
    win_rate = sum(value > 0 for value in outcomes) / len(outcomes) * 100
    average_return = sum(outcomes) / len(outcomes)
    return {
        "signals": len(outcomes),
        "win_rate": win_rate,
        "average_return": average_return,
        "profit_factor": profit_factor,
        "passed": (
            win_rate >= MIN_HISTORY_WIN_RATE
            and average_return > 0
            and profit_factor >= MIN_HISTORY_PROFIT_FACTOR
        ),
    }


def download_batches(symbols, period="3mo"):
    import yfinance as yf

    result = {}
    for start in range(0, len(symbols), DOWNLOAD_BATCH_SIZE):
        batch = symbols[start:start + DOWNLOAD_BATCH_SIZE]
        try:
            downloaded = yf.download(
                batch,
                period=period,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=30,
            )
            for symbol in batch:
                try:
                    result[symbol] = downloaded[symbol] if len(batch) > 1 else downloaded
                except (KeyError, TypeError):
                    continue
        except Exception as error:
            print(f"株価取得バッチをスキップ: {error}")
        time.sleep(0.3)
    return result


def get_sbi_candidates(capital, limit=3, max_price=None, symbols_filename=None):
    capital = int(float(capital))
    if capital <= 0:
        raise ValueError("運用資金が設定されていません")
    market = get_market_regime()
    effective_limit = min(limit, market["limit"])
    if effective_limit == 0:
        return CandidateList(market=market)
    if symbols_filename:
        symbols, dynamic_names = load_symbols(symbols_filename), {}
    else:
        symbols, dynamic_names = load_prime_symbols()
    downloaded = download_batches(symbols, period="1y")
    liquid_symbols = sorted(
        downloaded,
        key=lambda symbol: average_turnover(downloaded[symbol]),
        reverse=True,
    )[:MAX_LIQUID_UNIVERSE]
    candidates = []
    for symbol in liquid_symbols:
        try:
            candidate = score_candidate(
                downloaded[symbol], capital, max_price=max_price, require_pullback=True,
            )
            if candidate and candidate["score"] >= MIN_LIVE_SCORE and candidate["volume_ratio"] >= 1.1:
                validation = validate_candidate_history(downloaded[symbol])
                if not validation or not validation["passed"]:
                    continue
                candidate["history"] = validation
                candidate["reasons"].append("過去の同条件が検証基準を通過")
                candidate["code"] = symbol
                candidate["name"] = dynamic_names.get(symbol) or SBI_NAMES.get(symbol, "会社名未登録")
                candidates.append(candidate)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    ranked = sorted(
        candidates,
        key=lambda item: (item["score"], item["take_profit_net_profit"], item["average_turnover"]),
        reverse=True,
    )
    try:
        tdnet_by_code = fetch_recent_tdnet(days=7)
    except Exception as error:
        print(f"TDnet取得失敗（公式材料は未確認扱い）: {error}")
        tdnet_by_code = {}
    earnings_checked = []
    for candidate in ranked[:EARNINGS_CHECK_POOL]:
        code = candidate["code"].replace(".T", "")
        official_news = summarize_tdnet(tdnet_by_code.get(code, []))
        if official_news["negative"]:
            print(f"TDnet悪材料のため候補除外: {candidate['code']}")
            continue
        candidate["official_news"] = official_news
        earnings_date = get_next_earnings_date(candidate["code"])
        if in_earnings_blackout(earnings_date):
            print(f"決算前後のため候補除外: {candidate['code']} ({earnings_date})")
            continue
        candidate["earnings_date"] = earnings_date
        candidate["earnings_checked"] = earnings_date is not None
        earnings_checked.append(candidate)
        if len(earnings_checked) >= effective_limit:
            break
    return CandidateList(earnings_checked, market=market)


def create_sbi_candidates_embed(candidates, capital, max_price=None):
    fields = []
    execution = get_next_s_stock_execution()
    for index, item in enumerate(candidates, start=1):
        code = item["code"].replace(".T", "")
        reason_text = "・".join(item["reasons"])
        earnings_text = (
            f"次回決算予定：{item['earnings_date']:%Y-%m-%d}（除外期間外）"
            if item.get("earnings_checked")
            else "次回決算予定：取得できず（要確認）"
        )
        official = item.get("official_news", {"confidence": "中立", "items": []})
        if official["items"]:
            material = official["items"][0]
            official_text = (
                f"公式材料：[{material['title']}]({material['url']})\n"
                f"発表：{material['date']:%Y-%m-%d} {material['time']}　情報信頼度：{official['confidence']}"
            )
        else:
            official_text = "公式材料：直近7日間に判定対象のTDnet開示なし（中立）"
        fields.append({
            "name": f"{index}. {item.get('name', '会社名未登録')}（{code}）｜{item['status']}",
            "value": (
                f"**候補理由：{reason_text}**\n"
                f"現在の参考価格：{item['price']:,.2f}円　判定：{item['score']}点\n"
                f"保守的な想定買付価格（+0.5%）：{item['assumed_entry_price']:,.2f}円\n"
                f"購入候補：**{item['shares']}株**（想定約{item['investment']:,.0f}円）\n"
                f"利確候補：{item['take_profit']:,.2f}円　損切り候補：{item['stop_loss']:,.2f}円\n"
                f"利確到達時の税引後利益：約**{item['take_profit_net_profit']:,.0f}円**\n"
                f"損切り価格で約定した場合の想定損失：約{item['planned_loss']:,.0f}円\n"
                f"ストレス損失（値幅1.5倍／2倍）：約{item['stress_loss_1_5x']:,.0f}円／"
                f"約{item['stress_loss_2x']:,.0f}円\n"
                f"税引後RR：{item['reward_ratio']:.2f}倍　利確時税引後騰落率：{item['target_net_return']:.2f}%\n"
                f"RSI：{item['rsi']:.1f}　5日騰落：{item['change_5d']:+.2f}%　"
                f"出来高倍率：{item['volume_ratio']:.2f}倍\n"
                f"過去同条件：{item['history']['signals']}回　勝率：{item['history']['win_rate']:.1f}%　"
                f"平均損益：{item['history']['average_return']:+.2f}%　PF：{item['history']['profit_factor']:.2f}\n"
                f"{official_text}\n"
                f"{earnings_text}\n"
                f"詳しく見る：`/sbi 分析 code:{code}`"
            ),
            "inline": False,
        })
    market = getattr(candidates, "market", {"label": "⚪ 地合い判定なし", "description": ""})
    if not fields:
        no_candidate_text = (
            market["description"] if market.get("status") == "risk_off"
            else "⏸️ 待機：現在の厳格なスコアと過去検証基準を両方満たす銘柄はありません。今回は買わず、次の強いシグナルを待ちます。"
        )
        fields.append({"name": "今回の結果", "value": no_candidate_text, "inline": False})
    price_condition = f"・1株 **{float(max_price):,.0f}円以下**" if max_price is not None else ""
    return {
        "title": "🧪 SBI 1,000円以下候補（テスト）" if max_price == 1000 else "🔎 SBI短期売買 候補一覧",
        "description": (
            f"運用資金 **{int(float(capital)):,.0f}円**{price_condition}。"
            "東証プライムの高流動性最大500銘柄から、92点以上かつ過去の同条件がプラスだった銘柄だけを最大3件通知します。\n"
            f"{market['label']}：{market['description']}\n"
            f"次回S株約定目安：**{execution['label']}**（営業日・注文状況はSBI画面で要確認）"
        ),
        "color": SBI_BLUE,
        "fields": fields,
        "footer": {"text": "利益を保証するものではありません。S株対象可否と注文条件はSBI証券の注文画面で最終確認してください。"},
    }

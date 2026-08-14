"""楽天モード用の株価データ鮮度チェック。"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


TOKYO = ZoneInfo("Asia/Tokyo")


class StaleMarketDataError(RuntimeError):
    """株価が古く、安全に通知できない場合の例外。"""


def _as_utc(value):
    timestamp = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=TOKYO)
    return timestamp.astimezone(timezone.utc)


def market_is_open(now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(TOKYO)
    current = now.time()
    morning = time(9, 0) <= current <= time(11, 30)
    afternoon = time(12, 30) <= current <= time(15, 30)
    return now.weekday() < 5 and (morning or afternoon)


def ensure_fresh_quote(data, now=None):
    """取引中は20分、時間外は直近営業日相当（最大96時間）まで許可する。"""
    if data is None or data.empty:
        raise StaleMarketDataError("最新株価を取得できないため通知を中止しました")
    now_utc = _as_utc(now or datetime.now(timezone.utc))
    data_time = _as_utc(data.index[-1])
    max_age = timedelta(minutes=20) if market_is_open(now_utc) else timedelta(hours=96)
    age = now_utc - data_time
    if age < timedelta(minutes=-5) or age > max_age:
        raise StaleMarketDataError(
            f"株価データが古いため通知を中止しました（最終データ: {data_time.astimezone(TOKYO):%Y-%m-%d %H:%M}）"
        )
    return data_time


def ensure_recent_daily_data(data, now=None, max_age_days=7):
    if data is None or data.empty:
        raise StaleMarketDataError("バックテスト用データを取得できませんでした")
    now_utc = _as_utc(now or datetime.now(timezone.utc))
    data_time = _as_utc(data.index[-1])
    if now_utc - data_time > timedelta(days=max_age_days):
        raise StaleMarketDataError("バックテスト用データの最終日が古すぎます")
    return data_time

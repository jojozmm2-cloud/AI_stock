import re
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


URL = "https://www.paypay-sec.co.jp/stock/list/"

OUTPUT_FILE = Path(__file__).with_name("paypay_list.txt")
NAMES_FILE = Path(__file__).with_name("paypay_names.json")


def get_paypay_stocks():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        print("PayPay証券の銘柄一覧を取得中...")

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        text = page.locator("body").inner_text()

        browser.close()

    # -------------------------
    # 日本株部分だけ切り出す
    # -------------------------

    start = text.find("日本株 個別銘柄")
    end = text.find("国内ETF", start)

    if start == -1:
        raise RuntimeError(
            "日本株一覧が見つかりませんでした"
        )

    if end == -1:
        raise RuntimeError(
            "国内ETFが見つかりませんでした"
        )

    stock_text = text[start:end]

    # 空行を除いて1行ずつにする
    lines = [
        line.strip()
        for line in stock_text.splitlines()
        if line.strip()
    ]

    stocks = {}

    # -------------------------
    # コード → 次の行を会社名として取得
    # -------------------------

    code_pattern = re.compile(
        r"^(?:\d{4}|\d{3}[A-Z])$"
    )

    for i, line in enumerate(lines):

        if not code_pattern.match(line):
            continue

        if i + 1 >= len(lines):
            continue

        code = line
        name = lines[i + 1]

        # 会社名としておかしいものは除外
        if (
            name == "成長投資"
            or code_pattern.match(name)
        ):
            continue

        symbol = f"{code}.T"

        stocks[symbol] = name

    return stocks


def save_paypay_stocks():

    stocks = get_paypay_stocks()

    if len(stocks) < 10:
        raise RuntimeError(
            f"取得件数が少なすぎます: {len(stocks)}件"
        )

    # -------------------------
    # yfinance用銘柄リスト
    # -------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for symbol in stocks:
            f.write(symbol + "\n")

    # -------------------------
    # 日本語会社名
    # -------------------------

    with open(
        NAMES_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            stocks,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("✅ 取得成功")
    print(f"PayPay証券の日本株: {len(stocks)}件")
    print()
    print("銘柄リスト:")
    print(OUTPUT_FILE)
    print()
    print("会社名リスト:")
    print(NAMES_FILE)

    print()
    print("最初の10銘柄:")

    for symbol, name in list(stocks.items())[:10]:
        print(f"{symbol} → {name}")


if __name__ == "__main__":
    save_paypay_stocks()
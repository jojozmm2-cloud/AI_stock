from playwright.sync_api import sync_playwright


URL = "https://www.paypay-sec.co.jp/stock/list/"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    page.goto(
        URL,
        wait_until="networkidle",
        timeout=60000
    )

    page.wait_for_timeout(3000)

    text = page.locator("body").inner_text()

    browser.close()


# 6273 の周辺だけ表示
position = text.find("6273")

if position == -1:
    print("6273が見つかりません")
else:
    print(text[position:position + 500])
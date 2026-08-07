import feedparser
from urllib.parse import quote


def get_stock_news(code, limit=3):
    query = quote(code.replace(".T", ""))

    url = (
        f"https://news.google.com/rss/search?"
        f"q={query}+株&hl=ja&gl=JP&ceid=JP:ja"
    )

    feed = feedparser.parse(url)

    news = []
    seen = set()

    for entry in feed.entries:
        title = entry.title.strip()

        if title in seen:
            continue

        seen.add(title)
        news.append(title)

        if len(news) >= limit:
            break

    return news

def analyze_news(news_list):
    if not news_list:
        return "ニュースはありません"

    positive = [
        "増益",
        "上方修正",
        "AI",
        "半導体",
        "最高益",
        "受注",
        "増配",
        "提携",
        "買収",
        "成長"
    ]

    negative = [
        "減益",
        "下方修正",
        "赤字",
        "不正",
        "事故",
        "訴訟",
        "リストラ",
        "下落",
        "悪化"
    ]

    score = 0

    for title in news_list:
        for word in positive:
            if word in title:
                score += 1

        for word in negative:
            if word in title:
                score -= 1

    if score >= 2:
        return "📈 AI評価：好材料が多いです"

    if score <= -2:
        return "📉 AI評価：悪材料が目立ちます"

    return "➖ AI評価：中立です"
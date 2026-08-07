import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)
def make_ai_comment(result, news):
    prompt = f"""
あなたはプロの日本株アナリストです。

以下の分析結果とニュースから、
初心者にも分かりやすく投資判断をしてください。

分析結果
{result}

ニュース
{news}

以下の形式で回答してください。

評価
★★★★★（5段階）

判断
🟢 買い / 🟡 様子見 / 🔴 売り

買い確率
○○%

良い点
・

悪い点
・

リスク
・

おすすめ
・

200文字以内で、日本語で簡潔に回答してください。
"""

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content
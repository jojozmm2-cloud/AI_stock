import os

import asyncio

import discord
from discord import app_commands
from dotenv import load_dotenv

from test import analyze_stock
from news import get_stock_news
from ai_comment import make_ai_comment

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")


class StockBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


bot = StockBot()


@bot.tree.command(
    name="test",
    description="AI Stock Toolの動作確認"
)
async def test(
    interaction: discord.Interaction
):
    await interaction.response.send_message(
        "✅ AI Stock Tool 動いてます！"
    )

@bot.tree.command(
    name="分析",
    description="銘柄コードを指定して株を分析"
)
@app_commands.describe(
    code="銘柄コード 例: 6501.T"
)
async def analyze(
    interaction: discord.Interaction,
    code: str
):
    await interaction.response.defer(
        thinking=True
    )

    code = code.strip().upper()

    try:
        result = analyze_stock(code)

        if len(result) > 1900:
            result = result[:1900] + "\n..."

        await interaction.followup.send(
            f"""📊 **株分析結果**

🏷️ 銘柄
`{code}`

{result}
"""
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ {code} の分析中にエラーが発生しました。\n{e}"
        )
@bot.tree.command(
    name="ai分析",
    description="最新ニュースとAIを使って株を詳しく分析"
)
@app_commands.describe(
    code="銘柄コード 例: 6501.T"
)
async def ai_analyze(
    interaction: discord.Interaction,
    code: str
):
    await interaction.response.defer(
        thinking=True
    )

    code = code.strip().upper()

    try:
        # 株価・テクニカル分析
        result = await asyncio.to_thread(
            analyze_stock,
            code
        )

        # 最新ニュース取得
        news = await asyncio.to_thread(
            get_stock_news,
            code
        )

        if news:
            news_text = "\n".join(news)
            news_display = "\n".join(
                f"・{item}"
                for item in news[:3]
            )
        else:
            news_text = "ニュースなし"
            news_display = "・最新ニュースなし"

        # OpenAIで分析
        ai_comment = await asyncio.to_thread(
            make_ai_comment,
            result,
            news_text
        )

        message = f"""🤖 **AI株分析**

🏷️ 銘柄
`{code}`

📰 **最新ニュース**
{news_display}

🧠 **AIコメント**
{ai_comment}
"""

        if len(message) > 1900:
            message = message[:1900] + "\n..."

        await interaction.followup.send(
            message
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ {code} のAI分析中にエラーが発生しました。\n{e}"
        )
bot.run(TOKEN)
from tkinter import messagebox

from dashboard import update_dashboard
from discord_notify import create_analysis_message, send_discord
from history import save_notification
from test import analyze_stock
from ui import show_result
from news import get_stock_news, analyze_news
from ai_comment import make_ai_comment

def run_analysis(
    code,
    code_entry,
    result_text,
    window,
    stock_label,
    updated_label,
    price_label,
    change_label,
    rsi_label,
    macd_label,
    band_label,
    decision_label,
    last_alert,
    check_price_alert,
    current_settings
):
    # 銘柄コードが渡されなかった場合は入力欄から取得
    if code is None:
        raw_codes = (
            code_entry.get()
            .replace(",", "\n")
            .splitlines()
        )

        codes = [
            item.strip().upper()
            for item in raw_codes
            if item.strip()
        ]
    else:
        codes = [code.strip().upper()]

    if not codes:
        messagebox.showwarning(
            "銘柄コード",
            "銘柄コードを入力してください"
        )
        return

    # 複数銘柄を順番に分析
    for stock_code in codes:
        show_result(result_text, f"{stock_code} を分析中...\n")
        window.update_idletasks()

        result = analyze_stock(stock_code)

        news = get_stock_news(stock_code)
        comment = analyze_news(news)
        ai_comment = make_ai_comment(
            result,
            "\n".join(news)
)
        print(news)
        if news:
            result += "\n\n📰 最新ニュース\n"
            result += "\n".join(f"・{n}" for n in news)
            result += "\n\n" + comment
            result += "\n\n🤖 AIコメント\n" + ai_comment
        update_dashboard(
            stock_code,
            result,
            stock_label,
            updated_label,
            price_label,
            change_label,
            rsi_label,
            macd_label,
            band_label,
            decision_label
        )

        message = create_analysis_message(stock_code, result)
        send_discord(message)
        print("価格アラート判定を実行:", stock_code)
        check_price_alert(stock_code, result, current_settings)
        show_result(result_text, result)

        alert = ""

        if "総合判定: 買い候補" in result:
            alert = f"🟢 {stock_code}: 買いシグナルです"

        elif "総合判定: 売り警戒" in result:
            alert = f"🔴 {stock_code}: 売り警戒シグナルです"


        if alert and alert != last_alert.get(stock_code):
            messagebox.showinfo("株価通知", alert)
            save_notification(alert)

            send_discord(
                f"""🚨 **売買シグナル**

        🏷️ 銘柄
        `{stock_code}`

        {alert}

        🤖 AI Stock Tool
        """
            )

        last_alert[stock_code] = alert
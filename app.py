from ranking import create_ranking, NAMES
from watchlist_ui import manage_watchlist
from price_alert import (
    load_price_alerts,
    check_price_alert,
    show_price_alert_settings
)
from analysis import run_analysis
from discord_notify import (
    create_analysis_message,
    create_ranking_message,
    send_discord
)
from settings import load_settings
from settings import show_settings
from ui import (
    create_title,
    create_code_entry,
    create_button,
    show_result,
    create_dashboard
)
from dashboard import update_dashboard
from chart import show_chart
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime
import yfinance as yf
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "Meiryo"
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from test import analyze_stock
from watchlist import (
    load_watchlist as load_watchlist_file,
    save_watchlist as save_watchlist_file
)
from history import save_notification, clear_history
from auto import (
    save_interval as save_interval_to_file,
    load_interval as load_interval_from_file,
    start_auto,
    stop_auto
)

window = tk.Tk()
window.title("AI株分析ツール")
window.geometry("400x600")
current_settings = load_settings()

if current_settings.get("dark_mode", False):
    bg_color = "#2b2b2b"
    fg_color = "white"
else:
    bg_color = "white"
    fg_color = "black"

window.config(bg=bg_color)
title_label = create_title(
    window,
    bg_color,
    fg_color
)
code_entry = create_code_entry(
    window,
    bg_color,
    fg_color
)

last_alert = {}
auto_running = False
interval_var = tk.StringVar(value="5")

def show_ranking():
    ranking = create_ranking()

    text = "🏆 AIおすすめランキング\n\n"

    for i, (score, code, result) in enumerate(ranking, start=1):
        name = NAMES.get(code, code)

        text += f"{i}位 {name}\n"
        text += f"コード: {code}\n"
        text += f"AIスコア: {score}/100\n"

        if score >= 70:
            text += "🟢 買い候補\n"
        elif score >= 50:
            text += "🟡 様子見\n"
        else:
            text += "🔴 注意\n"

        text += "\n"

    discord_message = create_ranking_message(ranking, NAMES)
    send_discord(discord_message)

    messagebox.showinfo("ランキング", text)

def show_summary():
    
    codes = [
        item.strip().upper()
        for item in code_entry.get().split(",")
        if item.strip()
    ]

    summary_window = tk.Toplevel(window)
    summary_window.title("銘柄一覧")
    summary_window.geometry("400x350")

    summary_text = scrolledtext.ScrolledText(
        summary_window,
        width=40,
        height=16,
        font=("Arial", 12)
    )
    summary_text.pack(padx=10, pady=10)

    for code in codes:
        result = analyze_stock(code)

        if "総合判定: 買い候補" in result:
            status = "買い候補"
        elif "総合判定: 売り警戒" in result:
            status = "売り警戒"
        elif "取得できませんでした" in result:
            status = "データ取得失敗"
        else:
            status = "様子見"

        summary_text.insert(tk.END, f"{code}: {status}\n")

    summary_text.config(state="disabled")        

def show_history():
    history_window = tk.Toplevel(window)
    history_window.title("通知履歴")
    history_window.geometry("500x400")

    history_text = scrolledtext.ScrolledText(
        history_window,
        width=55,
        height=20,
        font=("Arial", 10)
    )
    history_text.pack(padx=10, pady=10)

    try:
        with open("notification_history.txt", "r", encoding="utf-8") as file:
            history_text.insert(tk.END, file.read())

    except FileNotFoundError:
        history_text.insert(tk.END, "通知履歴はまだありません。")

    history_text.config(state="disabled")

def save_interval():
    save_interval_to_file(interval_var.get())
def load_interval():
    value = load_interval_from_file()

    if value in ("5", "15", "30"):
        interval_var.set(value)

def save_watchlist():
    codes = [
        code.strip().upper()
        for code in code_entry.get()
        .replace("\n", ",")
        .split(",")
        if code.strip()
    ]

    save_watchlist_file(codes)

    messagebox.showinfo(
        "監視銘柄",
        "監視銘柄を保存しました"
    )


def load_watchlist():
    codes = load_watchlist_file()

    if codes:
        code_entry.delete(0, tk.END)
        code_entry.insert(
            0,
            ", ".join(codes)
        )
def analyze(code=None, use_ai=True):
    run_analysis(
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
        current_settings,
        use_ai
    )
analysis_section = tk.Label(
    window,
    text="分析",
    font=("Arial", 11, "bold"),
    bg=bg_color,
    fg=fg_color
)
analysis_section.pack(pady=(10, 5))
analyze_button = create_button(
    window,
    "分析する",
    analyze,
    bg_color,
    fg_color
)
auto_section = tk.Label(
    window,
    text="自動監視",
    font=("Arial", 11, "bold"),
    bg=bg_color,
    fg=fg_color
)
auto_section.pack(pady=(15, 5))
interval_label = tk.Label(
    window,
    text="自動分析の間隔（分）",
    bg=bg_color,
    fg=fg_color
)
interval_label.pack(pady=5)

interval_menu = tk.OptionMenu(
    window,
    interval_var,
    "5",
    "15",
    "30",
    command=lambda value: save_interval()
)
interval_menu.config(
    bg="#404040" if bg_color != "white" else "white",
    fg=fg_color,
    activebackground="#505050" if bg_color != "white" else "#dddddd",
    activeforeground=fg_color,
    highlightthickness=0
)

interval_menu["menu"].config(
    bg="#404040" if bg_color != "white" else "white",
    fg=fg_color
)
interval_menu.pack(pady=5)
auto_button_frame = tk.Frame(
    window,
    bg=bg_color
)
auto_button_frame.pack(pady=5)
start_auto_button = create_button(
    auto_button_frame,
    "自動分析を開始",
    lambda: start_auto(
        window,
        interval_var,
        code_entry,
        analyze,
        auto_status_label
    ),
    bg_color,
    fg_color
)

stop_button = create_button(
    auto_button_frame,
    "自動分析を停止",
    lambda: stop_auto(auto_status_label),
    bg_color,
    fg_color
)
manage_section = tk.Label(
    window,
    text="履歴・管理",
    font=("Arial", 11, "bold"),
    bg=bg_color,
    fg=fg_color
)
manage_section.pack(pady=(15, 5))
watchlist_button = create_button(
    window,
    "監視銘柄を保存",
    save_watchlist,
    bg_color,
    fg_color
)
manage_button = create_button(
    window,
    "監視銘柄を管理",
    lambda: manage_watchlist(window, code_entry),
    bg_color,
    fg_color
)
alert_button = create_button(
    window,
    "価格アラートを設定",
    lambda: show_price_alert_settings(window, code_entry),
    bg_color,
    fg_color
)

chart_button = create_button(
    window,
    "株価グラフを見る",
    lambda: show_chart(
        window,
        code_entry.get().split(",")[0].strip().upper()
    ),
    bg_color,
    fg_color
)
ranking_button = tk.Button(
    window,
    text="AIランキング",
    command=show_ranking
)

ranking_button.pack(pady=5)

history_button = create_button(
    window,
    "通知履歴を見る",
    show_history,
    bg_color,
    fg_color
)
clear_button = create_button(
    window,
    "通知履歴を消去",
    clear_history,
    bg_color,
    fg_color
)
summary_button = create_button(
    window,
    "銘柄一覧を見る",
    show_summary,
    bg_color,
    fg_color
)

settings_button = create_button(
    window,
    "⚙ 設定",
    lambda: show_settings(window),
    bg_color,
    fg_color
)

(
    dashboard_frame,
    stock_label,
    updated_label,
    auto_status_label,
    price_label,
    change_label,
    decision_label,
    rsi_label,
    macd_label,
    band_label
) = create_dashboard(
    window,
    bg_color,
    fg_color
)
result_text = scrolledtext.ScrolledText(
    window,
    width=45,
    height=20,
    font=("Arial", 10),
    bg="#202020" if bg_color != "white" else "white",
    fg=fg_color,
    insertbackground=fg_color,
    selectbackground="#505050"
)
result_text.pack(padx=10, pady=10)

load_price_alerts()
load_interval()
load_watchlist()

window.mainloop()
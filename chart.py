import tkinter as tk
import yfinance as yf
import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import messagebox

def show_chart(window, code):
    data = yf.Ticker(code).history(period="3mo")

    if data.empty:
        messagebox.showerror("株価グラフ", f"{code} のデータを取得できませんでした")
        return
    data["MA20"] = data["Close"].rolling(20).mean()
    std = data["Close"].rolling(20).std()
    data["Upper"] = data["MA20"] + std * 2
    data["Lower"] = data["MA20"] - std * 2
    data["EMA12"] = data["Close"].ewm(span=12, adjust=False).mean()
    data["EMA26"] = data["Close"].ewm(span=26, adjust=False).mean()
    data["MACD"] = data["EMA12"] - data["EMA26"]
    data["Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
    data["BuySignal"] = (
    (data["MACD"] > data["Signal"]) &
    (data["MACD"].shift(1) <= data["Signal"].shift(1))
)

    data["SellSignal"] = (
    (data["MACD"] < data["Signal"]) &
    (data["MACD"].shift(1) >= data["Signal"].shift(1))
)
    chart_window = tk.Toplevel(window)
    chart_window.title(f"{code} の株価グラフ")
    chart_window.geometry("950x700")

    figure = plt.Figure(figsize=(8, 6.5), dpi=100)
    graph = figure.add_subplot(211)
    macd_graph = figure.add_subplot(212)
    graph.plot(data.index, data["Close"], label="株価")
    graph.plot(data.index, data["MA20"], label="20日移動平均")
    graph.plot(data.index, data["Upper"], label="上限")
    graph.plot(data.index, data["Lower"], label="下限")
    graph.fill_between(
    data.index,
    data["Lower"],
    data["Upper"],
    alpha=0.15,
    label="ボリンジャーバンド"
)
    graph.legend()
    macd_graph.plot(data.index, data["MACD"], label="MACD")
    macd_graph.plot(data.index, data["Signal"], label="シグナル")
    buy_points = data[data["BuySignal"]]
    sell_points = data[data["SellSignal"]]

    macd_graph.scatter(
    buy_points.index,
    buy_points["MACD"],
    marker="^",
    s=80,
    label="上抜け"
)

    macd_graph.scatter(
    sell_points.index,
    sell_points["MACD"],
    marker="v",
    s=80,
    label="下抜け"
)
    macd_graph.axhline(0)
    macd_graph.set_title("MACD")
    macd_graph.set_xlabel("日付")
    macd_graph.set_ylabel("値")
    macd_graph.legend()

    figure.subplots_adjust(
    top=0.90,
    bottom=0.10,
    hspace=0.60
)
    graph.set_title(f"{code} 株価推移（3か月）")
    graph.set_xlabel("日付")
    graph.set_ylabel("株価")

    canvas = FigureCanvasTkAgg(figure, master=chart_window)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)     
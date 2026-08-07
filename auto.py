from tkinter import messagebox

auto_running = False

def save_interval(interval):
    with open("interval.txt", "w", encoding="utf-8") as file:
        file.write(interval)
def load_interval():
    try:
        with open("interval.txt", "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        return "5"        
def auto_analyze(
    window,
    interval_var,
    code_entry,
    analyze,
):
    global auto_running

    if not auto_running:
        return

    raw_codes = (
        code_entry.get()
        .replace(",", "\n")
        .splitlines()
    )

    codes = [
        code.strip().upper()
        for code in raw_codes
        if code.strip()
    ]

    for stock_code in codes:
        analyze(stock_code)

    window.after(
        int(interval_var.get()) * 60000,
        lambda: auto_analyze(
            window,
            interval_var,
            code_entry,
            analyze,
        )
    )  
def start_auto(
    window,
    interval_var,
    code_entry,
    analyze,
    auto_status_label
):
    global auto_running

    if not auto_running:
        auto_running = True

        auto_status_label.config(
            text=f"自動分析: 実行中（{interval_var.get()}分ごと）",
            fg="green"
        )

        auto_analyze(
            window,
            interval_var,
            code_entry,
            analyze
        )

        messagebox.showinfo(
            "自動分析",
            f"{interval_var.get()}分ごとに自動分析を始めました"
        )
def stop_auto(auto_status_label):
    global auto_running

    auto_running = False

    auto_status_label.config(
        text="自動分析: 停止中",
        fg="red"
    )

    messagebox.showinfo(
        "自動分析",
        "自動分析を停止しました"
    )
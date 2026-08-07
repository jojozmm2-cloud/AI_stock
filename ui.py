import tkinter as tk

def create_title(window, bg_color, fg_color):
    title_label = tk.Label(
        window,
        text="AI株分析ツール",
        font=("Arial", 20),
        bg=bg_color,
        fg=fg_color
    )
    title_label.pack(pady=30)

    return title_label
def create_code_entry(window, bg_color, fg_color):
    code_entry = tk.Entry(
        window,
        width=20,
        font=("Arial", 12),
        bg="white" if bg_color == "white" else "#404040",
        fg=fg_color,
        insertbackground=fg_color
    )

    code_entry.insert(0, "6501.T")
    code_entry.pack(pady=5)

    return code_entry
def create_button(window, text, command, bg_color, fg_color):
    button = tk.Button(
        window,
        text=text,
        command=command,
        bg="#404040" if bg_color != "white" else "white",
        fg=fg_color,
        activebackground="#505050" if bg_color != "white" else "#dddddd",
        activeforeground=fg_color,
        width=15
    )

    button.pack(pady=5)

    return button
def show_result(result_text, text):
    result_text.delete("1.0", "end")
    result_text.insert("end", text)
def create_dashboard(window, bg_color, fg_color):
    dashboard_frame = tk.LabelFrame(
        window,
        text="📊 分析ダッシュボード",
        padx=10,
        pady=10,
        bg=bg_color,
        fg=fg_color
    )
    dashboard_frame.pack(fill="x", padx=10, pady=10)

    stock_label = tk.Label(
        dashboard_frame,
        text="銘柄: --",
        font=("Arial", 12, "bold"),
        bg=bg_color,
        fg=fg_color
    )
    stock_label.pack(anchor="w", padx=10, pady=(5, 0))

    updated_label = tk.Label(
        dashboard_frame,
        text="最終更新: --",
        bg=bg_color,
        fg=fg_color
    )
    updated_label.pack(anchor="w", padx=10)

    auto_status_label = tk.Label(
        dashboard_frame,
        text="自動分析: 停止中",
        bg=bg_color,
        fg="#ff5555"
    )
    auto_status_label.pack(anchor="w", padx=10)

    price_label = tk.Label(
        dashboard_frame,
        text="価格: --",
        font=("Arial", 12),
        bg=bg_color,
        fg=fg_color
    )
    price_label.pack(anchor="w", padx=10)

    change_label = tk.Label(
        dashboard_frame,
        text="前日比: --",
        bg=bg_color,
        fg=fg_color
    )
    change_label.pack(anchor="w", padx=10)

    decision_label = tk.Label(
        dashboard_frame,
        text="総合判定: --",
        bg=bg_color,
        fg="#ffd700"
    )
    decision_label.pack(anchor="w", padx=10)

    rsi_label = tk.Label(
        dashboard_frame,
        text="RSI: --",
        bg=bg_color,
        fg=fg_color
    )
    rsi_label.pack(anchor="w", padx=10)

    macd_label = tk.Label(
        dashboard_frame,
        text="MACD: --",
        bg=bg_color,
        fg=fg_color
    )
    macd_label.pack(anchor="w", padx=10)

    band_label = tk.Label(
        dashboard_frame,
        text="ボリンジャー: --",
        bg=bg_color,
        fg=fg_color
    )
    band_label.pack(anchor="w", padx=10, pady=(0, 5))

    return (
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
    ) 
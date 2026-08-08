import tkinter as tk

from watchlist import save_watchlist

def manage_watchlist(window, code_entry):
    manager = tk.Toplevel(window)
    manager.title("監視銘柄の管理")
    manager.geometry("350x400")

    stock_list = tk.Listbox(manager, font=("Arial", 12))
    stock_list.pack(padx=10, pady=10, fill="both", expand=True)

    for code in code_entry.get().split(","):
        code = code.strip().upper()
        if code:
            stock_list.insert(tk.END, code)

    new_code_entry = tk.Entry(manager, font=("Arial", 12))
    new_code_entry.pack(padx=10, pady=5, fill="x")

    def add_stock():
        code = new_code_entry.get().strip().upper()

        if code and code not in stock_list.get(0, tk.END):
            stock_list.insert(tk.END, code)
            new_code_entry.delete(0, tk.END)

    def remove_stock():
        selected = stock_list.curselection()

        if selected:
            stock_list.delete(selected[0])

    def save_changes():
        codes = stock_list.get(0, tk.END)

        code_entry.delete(0, tk.END)
        code_entry.insert(0, ", ".join(codes))

        save_watchlist(list(codes))
        
        manager.destroy()

    tk.Button(
        manager,
        text="銘柄を追加",
        command=add_stock
    ).pack(pady=3)

    tk.Button(
        manager,
        text="選択した銘柄を削除",
        command=remove_stock
    ).pack(pady=3)

    tk.Button(
        manager,
        text="保存して閉じる",
        command=save_changes
    ).pack(pady=10)   
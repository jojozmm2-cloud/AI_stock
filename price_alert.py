from discord_notify import send_discord, create_price_alert_message
from pathlib import Path
PRICE_ALERTS_FILE = Path(__file__).with_name("price_alerts.json")
import json
import tkinter as tk
from tkinter import messagebox
from tkinter import messagebox


price_alerts = {}


def load_price_alerts():
    global price_alerts

    try:
        with open(PRICE_ALERTS_FILE, "r", encoding="utf-8") as f:
            import json
            price_alerts = json.load(f)
    except:
        price_alerts = {}


def save_price_alerts():
    import json

    with open(PRICE_ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(price_alerts, f, ensure_ascii=False, indent=4)

    print("保存先:", PRICE_ALERTS_FILE)


def check_price_alert(code, result, current_settings):
    if code not in price_alerts:
        return

    alert = price_alerts[code]

    if "今日:" not in result:
        return

    try:
        price = float(
            result.split("今日:")[1]
            .split("円")[0]
            .replace(",", "")
        )
    except:
        return

    upper = alert.get("upper")
    lower = alert.get("lower")

    if upper and price >= upper and not current_settings.get("upper_notified", False):
        messagebox.showinfo(
            "価格アラート",
            f"{code} が {upper} 円以上になりました"
        )

        send_discord(
            create_price_alert_message(code, price, "upper")
        )

        current_settings["upper_notified"] = True

    elif upper and price < upper:
        current_settings["upper_notified"] = False


    if lower and price <= lower and not current_settings.get("lower_notified", False):
        messagebox.showwarning(
            "価格アラート",
            f"{code} が {lower} 円以下になりました"
        )

        send_discord(
            create_price_alert_message(code, price, "lower")
        )

        current_settings["lower_notified"] = True

    elif lower and price > lower:
        current_settings["lower_notified"] = False
def show_price_alert_settings(window, code_entry):
    settings = tk.Toplevel(window)
    settings.title("価格アラート設定")
    settings.geometry("350x250")

    tk.Label(settings, text="銘柄コード").pack()

    code_var = tk.StringVar()
    code_var.set(code_entry.get().split(",")[0].strip())

    code_box = tk.Entry(settings, textvariable=code_var)
    code_box.pack(pady=5)

    tk.Label(settings, text="上限価格").pack()
    upper_entry = tk.Entry(settings)
    upper_entry.pack(pady=5)

    tk.Label(settings, text="下限価格").pack()
    lower_entry = tk.Entry(settings)
    lower_entry.pack(pady=5)

    def save_price_alert():
        code = code_var.get().strip().upper()

        if not code:
            messagebox.showerror("価格アラート", "銘柄コードを入力してください")
            return
        try:
            upper = float(upper_entry.get()) if upper_entry.get() else None
            lower = float(lower_entry.get()) if lower_entry.get() else None
        except ValueError:
            messagebox.showerror("価格アラート", "価格は数字で入力してください")
        return
        price_alerts[code] = {
            "upper": upper,
            "lower": lower
        }

        save_price_alerts()

        messagebox.showinfo("価格アラート", f"{code} の設定を保存しました")
        settings.destroy()
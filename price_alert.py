from pathlib import Path
import json
import re
import tkinter as tk
from tkinter import messagebox

from discord_notify import (
    send_discord,
    create_price_alert_message
)


PRICE_ALERTS_FILE = Path(__file__).with_name(
    "price_alerts.json"
)

price_alerts = {}

# 銘柄ごとの通知済み状態
notification_state = {}


def load_price_alerts():
    global price_alerts

    try:
        with open(
            PRICE_ALERTS_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            price_alerts = json.load(f)

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):
        price_alerts = {}

    return price_alerts


def save_price_alerts():
    with open(
        PRICE_ALERTS_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            price_alerts,
            f,
            ensure_ascii=False,
            indent=4
        )

    print("保存先:", PRICE_ALERTS_FILE)


def get_current_price(result):
    match = re.search(
        r"今日:\s*([\d,]+(?:\.\d+)?)",
        result
    )

    if not match:
        return None

    return float(
        match.group(1).replace(",", "")
    )


def check_price_alert(
    code,
    result,
    current_settings=None
):
    if code not in price_alerts:
        return

    price = get_current_price(result)

    if price is None:
        return

    alert = price_alerts[code]

    upper = alert.get("upper")
    lower = alert.get("lower")

    state = notification_state.setdefault(
        code,
        {
            "upper": False,
            "lower": False
        }
    )

    # 上限
    if upper is not None:

        if price >= upper and not state["upper"]:

            messagebox.showinfo(
                "価格アラート",
                f"{code} が {upper} 円以上になりました"
            )

            send_discord(
                create_price_alert_message(
                    code,
                    price,
                    "upper"
                )
            )

            state["upper"] = True

        elif price < upper:
            state["upper"] = False

    # 下限
    if lower is not None:

        if price <= lower and not state["lower"]:

            messagebox.showwarning(
                "価格アラート",
                f"{code} が {lower} 円以下になりました"
            )

            send_discord(
                create_price_alert_message(
                    code,
                    price,
                    "lower"
                )
            )

            state["lower"] = True

        elif price > lower:
            state["lower"] = False


def show_price_alert_settings(
    window,
    code_entry
):
    settings = tk.Toplevel(window)
    settings.title("価格アラート設定")
    settings.geometry("350x280")

    initial_code = (
        code_entry.get()
        .split(",")[0]
        .strip()
        .upper()
    )

    tk.Label(
        settings,
        text="銘柄コード"
    ).pack(pady=(15, 3))

    code_var = tk.StringVar(
        value=initial_code
    )

    code_box = tk.Entry(
        settings,
        textvariable=code_var
    )
    code_box.pack(
        padx=20,
        fill="x"
    )

    tk.Label(
        settings,
        text="上限価格"
    ).pack(pady=(15, 3))

    upper_entry = tk.Entry(settings)
    upper_entry.pack(
        padx=20,
        fill="x"
    )

    tk.Label(
        settings,
        text="下限価格"
    ).pack(pady=(15, 3))

    lower_entry = tk.Entry(settings)
    lower_entry.pack(
        padx=20,
        fill="x"
    )

    # 保存済み設定を表示
    saved_alert = price_alerts.get(
        initial_code,
        {}
    )

    if saved_alert.get("upper") is not None:
        upper_entry.insert(
            0,
            str(saved_alert["upper"])
        )

    if saved_alert.get("lower") is not None:
        lower_entry.insert(
            0,
            str(saved_alert["lower"])
        )

    def save_price_alert():
        code = (
            code_var.get()
            .strip()
            .upper()
        )

        if not code:
            messagebox.showerror(
                "価格アラート",
                "銘柄コードを入力してください"
            )
            return

        try:
            upper = (
                float(upper_entry.get())
                if upper_entry.get()
                else None
            )

            lower = (
                float(lower_entry.get())
                if lower_entry.get()
                else None
            )

        except ValueError:
            messagebox.showerror(
                "価格アラート",
                "価格は数字で入力してください"
            )
            return

        price_alerts[code] = {
            "upper": upper,
            "lower": lower
        }

        save_price_alerts()

        # 設定を変更したら通知状態もリセット
        notification_state.pop(
            code,
            None
        )

        messagebox.showinfo(
            "価格アラート",
            f"{code} の設定を保存しました"
        )

        settings.destroy()

    tk.Button(
        settings,
        text="価格アラートを保存",
        command=save_price_alert
    ).pack(pady=20)
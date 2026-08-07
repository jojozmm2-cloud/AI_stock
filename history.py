from tkinter import messagebox
from datetime import datetime


def save_notification(alert):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open("notification_history.txt", "a", encoding="utf-8") as file:
        file.write(f"{timestamp} | {alert}\n")


def clear_history():
    confirm = messagebox.askyesno(
        "履歴を消去",
        "通知履歴をすべて消去しますか？"
    )

    if confirm:
        with open("notification_history.txt", "w", encoding="utf-8") as file:
            file.write("")

        messagebox.showinfo(
            "履歴を消去",
            "通知履歴を消去しました"
        )
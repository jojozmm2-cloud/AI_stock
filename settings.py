import tkinter as tk
import json

SETTINGS_FILE = "settings.json"


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "notification_enabled": True,
            "dark_mode": False
        }

def save_settings_to_file(settings_data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            settings_data,
            file,
            ensure_ascii=False,
            indent=2
        )
def show_settings(window):
    settings = tk.Toplevel(window)
    settings.title("設定")
    settings.geometry("350x300")

    tk.Label(
        settings,
        text="⚙ 設定",
        font=("Arial", 16, "bold")
    ).pack(pady=15)

    current_settings = load_settings()

    notification_var = tk.BooleanVar(
    value=current_settings.get("notification_enabled", True)
)

    notification_check = tk.Checkbutton(
        settings,
        text="通知を有効にする",
        variable=notification_var
    )
    notification_check.pack(pady=10)
    dark_mode_var = tk.BooleanVar(
    value=current_settings.get("dark_mode", False)
)

    dark_mode_check = tk.Checkbutton(
    settings,
    text="ダークモード",
    variable=dark_mode_var
)

    dark_mode_check.pack(pady=10)

    def save_settings():
        settings_data = {
            "notification_enabled": notification_var.get(),
            "dark_mode": dark_mode_var.get()
        }

        save_settings_to_file(settings_data)

        settings.destroy()

    save_button = tk.Button(
        settings,
        text="保存",
        command=save_settings
    )
    save_button.pack(pady=20)
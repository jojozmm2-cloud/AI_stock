import schedule
import time
import threading

from ranking import create_ranking, NAMES
from discord_notify import create_ranking_message, send_discord


def send_daily_ranking():
    ranking = create_ranking()
    message = create_ranking_message(ranking, NAMES)
    send_discord(message)
    print("今日のランキングをDiscordへ送信しました。")


def scheduler_loop():
    schedule.every().day.at("09:00").do(send_daily_ranking)

    while True:
        schedule.run_pending()
        time.sleep(30)


def start_scheduler():
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
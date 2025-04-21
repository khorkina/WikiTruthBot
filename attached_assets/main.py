from app import app
import threading
import time
import requests

def keep_alive():
    while True:
        try:
            print("[KeepAlive] Pinging self to stay awake...")
            requests.get("https://wikitruth.onrender.com/")  # Заменить на твой актуальный URL
        except Exception as e:
            print("[KeepAlive] Ping failed:", e)
        time.sleep(600)  # Пинг каждые 10 минут

if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)

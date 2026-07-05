"""
Telegram 手動指令 — 在 Telegram 傳 /photo 給 Bot，立即回傳一張現場截圖。

用 long polling（getUpdates）輪詢新訊息，不需要對外開 port（跟 webhook 比起來
更適合家用網路，不用處理 NAT / 固定 IP）。
"""
import threading
import time
from datetime import datetime

import config
import telegram_notify
import video_monitor


def command_loop(reader: video_monitor.StreamReader):
    """獨立執行緒：輪詢 Telegram 新訊息，收到 PHOTO_COMMAND 就立即截圖回傳。"""
    offset = None

    # 開機先把之前累積的舊訊息清掉（只拿 offset，不執行），
    # 避免程式沒開的這段時間傳過的 /photo 一開機就被全部觸發。
    try:
        old_updates = telegram_notify.get_updates(offset=None, timeout=1)
        if old_updates:
            offset = old_updates[-1]["update_id"] + 1
    except Exception as e:
        print(f"[指令] 初始化輪詢失敗: {e}")

    print(f"[指令] Telegram 指令監聽已啟動，傳 {config.PHOTO_COMMAND} 可立即拍照。")

    while True:
        try:
            updates = telegram_notify.get_updates(
                offset=offset, timeout=config.TELEGRAM_POLL_TIMEOUT
            )
        except Exception as e:
            print(f"[指令] 輪詢失敗: {e}")
            time.sleep(5)
            continue

        for update in updates:
            offset = update["update_id"] + 1

            msg = update.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "").strip()

            if chat_id != str(config.TELEGRAM_CHAT_ID):
                continue  # 不是自己的聊天室，忽略（避免陌生人觸發拍照）

            if text == config.PHOTO_COMMAND:
                now = datetime.now().strftime("%H:%M:%S")
                frame = reader.get_frame(timeout=2.0)
                if frame is not None:
                    telegram_notify.send_photo(frame, caption=f"📷 手動截圖（{now}）")
                else:
                    telegram_notify.send_text(f"📷 手動截圖失敗（{now}），攝影機連不上")


def start(reader: video_monitor.StreamReader):
    threading.Thread(target=command_loop, args=(reader,), daemon=True).start()

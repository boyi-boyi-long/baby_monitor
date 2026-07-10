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


def build_help_text() -> str:
    """使用說明＋指令列表。開機通知跟 /help、/start 指令共用同一份文字。"""
    return (
        "👶 嬰兒睡眠監測系統\n\n"
        "系統運作中會自動通知：\n"
        "🚨 偵測到寶寶哭聲\n"
        "📱 活動量持續偏高，可能醒了\n"
        f"📷 每 {config.PERIODIC_SNAPSHOT_SEC // 60} 分鐘定時回報現場畫面\n\n"
        "可用指令：\n"
        f"{config.PHOTO_COMMAND} — 立即拍一張現場照片\n"
        f"{config.STATUS_COMMAND} — 查詢目前是安靜還是可能醒了（附照片）\n"
        f"{config.SOUND_COMMAND} — 回傳最近現場錄音片段＋目前哭聲分數狀態\n"
        f"{config.HELP_COMMAND} — 顯示這則說明\n\n"
        f"⏳ 提醒：程式每次重開機後，📱 自動預警需要先收集 "
        f"{config.MOTION_WINDOW_SEC // 60} 分鐘活動資料才會開始判斷（避免誤報），"
        f"這段時間內可以用 {config.STATUS_COMMAND} 查看即時狀態（開機滿 "
        f"{config.MOTION_RECENT_SEC} 秒即可查）。"
    )


def send_startup_message():
    """程式開機時發一次上線通知＋使用說明（LOG_ONLY 校準模式不發，跟其他通知一致）。"""
    if config.LOG_ONLY:
        return
    telegram_notify.send_text("✅ 系統已啟動，開始監測。\n\n" + build_help_text())


def command_loop(reader: video_monitor.StreamReader, activity_monitor: video_monitor.ActivityMonitor, audio_monitor):
    """獨立執行緒：輪詢 Telegram 新訊息，收到 PHOTO_COMMAND 就立即截圖回傳，
    收到 STATUS_COMMAND 就回報目前是安靜還是可能醒了＋截圖，
    收到 SOUND_COMMAND 就回傳最近現場錄音片段＋目前哭聲分數狀態。
    """
    offset = None

    # 開機先把之前累積的舊訊息清掉（只拿 offset，不執行），
    # 避免程式沒開的這段時間傳過的 /photo 一開機就被全部觸發。
    try:
        old_updates = telegram_notify.get_updates(offset=None, timeout=1)
        if old_updates:
            offset = old_updates[-1]["update_id"] + 1
    except Exception as e:
        print(f"[指令] 初始化輪詢失敗: {e}")

    print(
        f"[指令] Telegram 指令監聽已啟動："
        f"{config.PHOTO_COMMAND} 拍照／{config.STATUS_COMMAND} 查狀態／"
        f"{config.SOUND_COMMAND} 錄音／{config.HELP_COMMAND} 說明"
    )

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

            elif text == config.STATUS_COMMAND:
                now = datetime.now().strftime("%H:%M:%S")
                status_text = activity_monitor.get_status_text()
                frame = reader.get_frame(timeout=2.0)
                if frame is not None:
                    telegram_notify.send_photo(frame, caption=f"{status_text}\n（{now}）")
                else:
                    telegram_notify.send_text(f"{status_text}\n（{now}，攝影機截圖失敗）")

            elif text == config.SOUND_COMMAND:
                now = datetime.now().strftime("%H:%M:%S")
                status_text = audio_monitor.get_status_text()
                clip = audio_monitor.get_recent_clip()
                if len(clip) >= config.SAMPLE_RATE:
                    secs = len(clip) // config.SAMPLE_RATE
                    ok = telegram_notify.send_audio_clip(
                        clip, caption=f"{status_text}\n（{now}，最近 {secs} 秒現場錄音）"
                    )
                    if not ok:
                        telegram_notify.send_text(status_text + "（錄音傳送失敗）")
                else:
                    telegram_notify.send_text(status_text + "\n（錄音資料不足，請稍後再試）")

            elif text in (config.HELP_COMMAND, "/start"):
                telegram_notify.send_text(build_help_text())


def start(reader: video_monitor.StreamReader, activity_monitor: video_monitor.ActivityMonitor, audio_monitor):
    threading.Thread(
        target=command_loop, args=(reader, activity_monitor, audio_monitor), daemon=True
    ).start()

"""Telegram 通知模組：發文字、發圖片。所有呼叫都不會拋出例外影響主程式。"""
import cv2
import requests
import config

API_BASE = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def send_text(message: str) -> bool:
    try:
        r = requests.post(
            f"{API_BASE}/sendMessage",
            data={"chat_id": config.TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] 發送文字失敗: {e}")
        return False


def send_photo(frame, caption: str = "") -> bool:
    """frame 是 OpenCV 的 BGR ndarray，在記憶體內編碼成 JPEG 直接上傳。"""
    try:
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            print("[Telegram] JPEG 編碼失敗")
            return False
        r = requests.post(
            f"{API_BASE}/sendPhoto",
            data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption},
            files={"photo": ("alert.jpg", jpg.tobytes(), "image/jpeg")},
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] 發送圖片失敗: {e}")
        return False

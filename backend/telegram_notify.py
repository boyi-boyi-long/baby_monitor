"""Telegram 通知模組：發文字、發圖片、發音訊片段。所有呼叫都不會拋出例外影響主程式。"""
import io
import wave

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


def send_audio_clip(samples, caption: str = "") -> bool:
    """samples 是 int16 的 numpy 陣列（16kHz 單聲道），
    在記憶體內包成 WAV 檔直接上傳（sendDocument），不落地。
    用 sendDocument 而非 sendAudio：Telegram 的 sendAudio 只收 MP3/M4A，
    WAV 走文件通道，手機端一樣可以直接點開播放。
    """
    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)                    # int16 = 2 bytes
            w.setframerate(config.SAMPLE_RATE)
            w.writeframes(samples.tobytes())
        r = requests.post(
            f"{API_BASE}/sendDocument",
            data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption},
            files={"document": ("cry_clip.wav", buf.getvalue(), "audio/wav")},
            timeout=30,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] 發送音訊片段失敗: {e}")
        return False


def get_updates(offset=None, timeout: int = 25) -> list:
    """向 Telegram 拉取新訊息（long polling）。
    offset：上次處理到的 update_id + 1；傳 None 表示從最新的開始拉。
    逾時內沒有新訊息就回傳空 list（不是錯誤）。
    """
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    r = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=timeout + 10)
    r.raise_for_status()
    return r.json().get("result", [])

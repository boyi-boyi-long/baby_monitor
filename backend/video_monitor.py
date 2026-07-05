"""
嬰兒活動量偵測 — 筆電後端（階段3）

流程：
  StreamReader 執行緒：常駐連著 ESP32-CAM，不斷讀 MJPEG 串流，
                       永遠只保留「最新一張」畫面（斷線自動重連）
  → activity_loop 執行緒：每秒跟前一幀比對灰階差異，算出「這一秒有沒有在動」
  → 3 分鐘滑動視窗內「有在動」比例超標，且最近 30 秒仍在動
    → 📱「可能醒了」預警（附截圖）
"""
import csv
import os
import threading
import time
from collections import deque
from datetime import datetime
from queue import Queue, Empty

import cv2

import config
import telegram_notify


class StreamReader:
    """獨立執行緒：不斷從 ESP32-CAM 讀取 MJPEG 串流，永遠只留「最新一張」畫面。
    斷線時自動重連；重試間有間隔，避免瘋狂重連把 ESP32-CAM 打死。
    """

    def __init__(self, url: str):
        self.url = url
        self._latest = Queue(maxsize=1)
        self._stop = False

    def get_frame(self, timeout=2.0):
        """取得最新一幀；逾時沒有畫面就回傳 None（不拋例外，呼叫端自行判斷）。"""
        try:
            return self._latest.get(timeout=timeout)
        except Empty:
            return None

    def _push(self, frame):
        if self._latest.full():
            try:
                self._latest.get_nowait()  # 丟掉舊畫面，只留最新
            except Empty:
                pass
        self._latest.put_nowait(frame)

    def _run(self):
        while not self._stop:
            cap = cv2.VideoCapture(self.url)
            if not cap.isOpened():
                print("[影像] 串流連線失敗，5 秒後重試...")
                cap.release()
                time.sleep(5)
                continue

            print("[影像] 串流連線成功。")
            while not self._stop:
                ok, frame = cap.read()
                if not ok:
                    print("[影像] 串流中斷，重新連線...")
                    break
                self._push(frame)
            cap.release()
            time.sleep(2)

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        return self


def send_motion_alert(reader: StreamReader, mean_ratio: float):
    """發送「可能醒了」預警（在獨立執行緒執行，不阻塞活動量判斷主迴圈）。"""
    now = datetime.now().strftime("%H:%M:%S")
    caption = f"📱 寶寶持續活動，可能醒了（{now}，活動比例 {mean_ratio:.2f}）"
    frame = reader.get_frame(timeout=1.0)
    if frame is not None:
        telegram_notify.send_photo(frame, caption=caption)
    else:
        telegram_notify.send_text(caption + "（攝影機截圖失敗）")


def activity_loop(reader: StreamReader):
    """獨立執行緒：每秒計算一次活動量，判斷是否要發「可能醒了」預警。"""
    window = deque(maxlen=config.MOTION_WINDOW_SEC)
    prev_gray = None
    last_alert_time = 0.0

    new_file = not os.path.exists(config.MOTION_LOG_CSV)
    log_f = open(config.MOTION_LOG_CSV, "a", newline="", encoding="utf-8")
    log_w = csv.writer(log_f)
    if new_file:
        log_w.writerow(["time", "motion_ratio", "active", "mean_180s"])

    while True:
        time.sleep(1)

        frame = reader.get_frame(timeout=2.0)
        if frame is None:
            continue  # 串流還沒接上或暫時沒畫面，這一輪先跳過

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_gray is None:
            prev_gray = gray
            continue  # 第一幀沒有「前一幀」可比對

        diff = cv2.absdiff(gray, prev_gray)
        motion_ratio = float((diff > config.MOTION_DIFF_PIXEL_THRESHOLD).sum() / diff.size)
        prev_gray = gray

        active = motion_ratio > config.MOTION_PIXEL_RATIO_THRESHOLD
        window.append(active)
        mean_full = sum(window) / len(window)

        log_w.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"{motion_ratio:.4f}",
            int(active),
            f"{mean_full:.4f}",
        ])
        log_f.flush()

        if len(window) < window.maxlen:
            continue  # 資料還沒滿 3 分鐘，先不做預警判斷

        recent = list(window)[-config.MOTION_RECENT_SEC:]
        mean_recent = sum(recent) / len(recent)
        still_active_now = mean_recent >= config.MOTION_STILL_RATIO

        if (
            mean_full > config.MOTION_ALERT_RATIO
            and still_active_now
            and time.time() - last_alert_time > config.MOTION_ALERT_COOLDOWN_SEC
        ):
            last_alert_time = time.time()
            window.clear()
            print(">>> 觸發「可能醒了」預警！<<<")
            if not config.LOG_ONLY:
                threading.Thread(
                    target=send_motion_alert, args=(reader, mean_full), daemon=True
                ).start()
        elif mean_full > config.MOTION_ALERT_RATIO and not still_active_now:
            print("（活動量曾升高但最近已恢復平靜，視為短暫扭動，不通知）")

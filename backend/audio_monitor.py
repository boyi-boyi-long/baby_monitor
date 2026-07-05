"""
嬰兒睡眠監測 — 筆電後端主程式（階段1+2+3）

流程：
  UDP 接收 ESP32+INMP441 音訊 → 環形緩衝區（最近1秒）
  → 每 0.5 秒跑一次 YAMNet → 哭聲分數
  → 滑動視窗判斷（6次中4次超過門檻）→ 🚨 Telegram 哭聲警報（附攝影機截圖）

  同時常駐一條 StreamReader 讀 ESP32-CAM 串流（見 video_monitor.py），
  每秒算幀差活動量，持續偏高 → 📱「可能醒了」預警（見 video_monitor.py）。

執行：python audio_monitor.py
停止：Ctrl+C
"""
import csv
import os
import socket
import threading
import time
from collections import deque
from datetime import datetime

import numpy as np

import config
import telegram_commands
import telegram_notify
import video_monitor

# ---------- 載入 YAMNet（第一次執行會自動下載模型，約 4MB）----------
print("載入 YAMNet 模型中（第一次執行需要下載，請稍候）...")
import tensorflow as tf          # noqa: E402
import tensorflow_hub as hub     # noqa: E402

yamnet = hub.load("https://tfhub.dev/google/yamnet/1")

# 讀出 521 個類別名稱
class_map_path = yamnet.class_map_path().numpy().decode()
class_names = []
with tf.io.gfile.GFile(class_map_path) as f:
    for row in csv.DictReader(f):
        class_names.append(row["display_name"])

CRY_IDX = [i for i, n in enumerate(class_names) if n in config.CRY_CLASSES]
print(f"YAMNet 就緒。監看類別: {[class_names[i] for i in CRY_IDX]}")

# ---------- 共享狀態 ----------
ring = deque(maxlen=config.SAMPLE_RATE)   # 最近 1 秒的音訊樣本
ring_lock = threading.Lock()
last_packet_time = [0.0]                  # 最後收到音訊封包的時間


def udp_receiver():
    """獨立執行緒：不停接收 ESP32 送來的音訊封包，塞進環形緩衝區。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", config.UDP_PORT))
    print(f"UDP 監聽中：0.0.0.0:{config.UDP_PORT}，等待 ESP32 音訊...")
    while True:
        data, _addr = sock.recvfrom(4096)
        samples = np.frombuffer(data, dtype=np.int16)
        with ring_lock:
            ring.extend(samples)
        last_packet_time[0] = time.time()


def send_alert(stream_reader: video_monitor.StreamReader, cry_score: float):
    """發送哭聲警報（在獨立執行緒執行，不阻塞音訊判斷主迴圈）。
    截圖改跟階段3常駐的 StreamReader 要最新畫面，不再自己開一條攝影機連線
    （ESP32-CAM 同時只服務得了一個串流 client）。
    """
    now = datetime.now().strftime("%H:%M:%S")
    caption = f"🚨 偵測到寶寶哭聲！({now}, 分數 {cry_score:.2f})"
    frame = stream_reader.get_frame(timeout=1.0)
    if frame is not None:
        telegram_notify.send_photo(frame, caption=caption)
    else:
        telegram_notify.send_text(caption + "（攝影機截圖失敗）")


def main():
    threading.Thread(target=udp_receiver, daemon=True).start()

    stream_reader = video_monitor.StreamReader(config.STREAM_URL).start()
    activity_monitor = video_monitor.ActivityMonitor()
    threading.Thread(target=activity_monitor.run, args=(stream_reader,), daemon=True).start()
    threading.Thread(
        target=video_monitor.periodic_snapshot_loop, args=(stream_reader,), daemon=True
    ).start()
    telegram_commands.start(stream_reader, activity_monitor)
    telegram_commands.send_startup_message()

    cry_history = deque(maxlen=config.CRY_WINDOW)
    last_alert_time = 0.0
    offline_warned = False

    # 分數紀錄檔（校準用）
    new_file = not os.path.exists(config.LOG_CSV)
    log_f = open(config.LOG_CSV, "a", newline="", encoding="utf-8")
    log_w = csv.writer(log_f)
    if new_file:
        log_w.writerow(["time", "cry_score", "top_class", "top_score"])

    print("開始監測。Ctrl+C 停止。")
    if config.LOG_ONLY:
        print("*** 校準模式（LOG_ONLY=True）：只記錄分數，不發通知 ***")

    while True:
        time.sleep(0.5)

        # --- 音訊節點離線偵測 ---
        silent_for = time.time() - last_packet_time[0]
        if last_packet_time[0] > 0 and silent_for > config.OFFLINE_WARN_SEC:
            if not offline_warned:
                print("⚠️ 音訊節點離線！")
                if not config.LOG_ONLY:
                    telegram_notify.send_text("⚠️ 音訊節點離線超過 1 分鐘，請檢查 ESP32 麥克風。")
                offline_warned = True
            continue
        if offline_warned and silent_for < 5:
            offline_warned = False
            print("音訊節點恢復連線。")
            if not config.LOG_ONLY:
                telegram_notify.send_text("✅ 音訊節點已恢復連線。")

        # --- 湊滿 1 秒音訊才推論 ---
        with ring_lock:
            if len(ring) < config.SAMPLE_RATE:
                continue
            waveform = np.array(ring, dtype=np.float32) / 32768.0

        scores, _embeddings, _spec = yamnet(waveform)
        mean_scores = scores.numpy().mean(axis=0)

        cry_score = float(max(mean_scores[i] for i in CRY_IDX))
        top_i = int(mean_scores.argmax())

        # 紀錄到 CSV（校準的黃金資料）
        log_w.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"{cry_score:.4f}",
            class_names[top_i],
            f"{mean_scores[top_i]:.4f}",
        ])
        log_f.flush()

        # 終端機即時顯示
        bar = "#" * int(cry_score * 40)
        print(f"哭聲 {cry_score:.2f} |{bar:<40}| 最強類別: {class_names[top_i]}")

        # --- 滑動視窗判斷 + 冷卻 ---
        cry_history.append(cry_score > config.CRY_SCORE_THRESHOLD)
        if (
            sum(cry_history) >= config.CRY_TRIGGER_COUNT
            and time.time() - last_alert_time > config.ALERT_COOLDOWN_SEC
        ):
            last_alert_time = time.time()
            cry_history.clear()
            print(">>> 觸發哭聲警報！<<<")
            if not config.LOG_ONLY:
                threading.Thread(
                    target=send_alert, args=(stream_reader, cry_score), daemon=True
                ).start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止監測。")

# SPEC — 技術規格書

| 項目 | 內容 |
|---|---|
| 文件版本 | v1.0（對應階段 1+2 實作） |
| 日期 | 2026-07-05 |
| 對應 PRD | doc/PRD.md v1.0 |

---

## 1. 系統架構

```
【感測層（嬰兒房，零智慧）】
  節點A  ESP32-CAM (OV3660)
         └─ MJPEG 串流  http://<cam-ip>:81/stream
  節點B  ESP32 DevKit (ESP-WROOM-32, CP2102) + INMP441
         └─ UDP 音訊串流 → 筆電:5005

【運算層（筆電，Python 3.x）】
  backend/audio_monitor.py（主程式）
  ├─ Thread-1  udp_receiver：收音訊 → 環形緩衝區
  ├─ 主迴圈    每 0.5s：YAMNet 推論 → 滑動視窗判斷 → 警報決策
  ├─ Thread-N  send_alert：抓截圖 + Telegram 發送（每次警報一條）
  ├─ Thread    video_monitor.StreamReader：常駐讀 ESP32-CAM，只留最新一幀
  ├─ Thread    video_monitor.activity_loop：每秒幀差 → 活動量判斷 →「可能醒了」預警
  ├─ Thread    video_monitor.periodic_snapshot_loop：每 15 分鐘定時拍照
  └─ Thread    telegram_commands.command_loop：輪詢 /photo 指令 → 立即截圖回傳

【通知層】
  Telegram Bot API（HTTPS，僅出網的通道；getUpdates 為唯一入網的通道）
```

## 2. 硬體規格

### 2.1 音訊節點接線（INMP441 → ESP32 DevKit）

| INMP441 | ESP32 GPIO | 訊號 |
|---|---|---|
| VDD | 3V3 | 電源（禁用 5V） |
| GND | GND | 接地 |
| SCK | 26 | I2S 位元時脈 BCLK |
| WS  | 25 | I2S 字選 LRCLK |
| SD  | 33 | I2S 資料 DIN |
| L/R | GND | 左聲道 |

### 2.2 影像節點
- AI-Thinker ESP32-CAM，OV3660 感光晶片，標準鏡頭（含 IR 濾光片，僅亮環境）
- 階段 5 更換：無 IR 濾光片魚眼鏡頭（24-pin FPC）＋850nm 補光燈（獨立 USB 供電）
- 韌體：`esp32_cam_firmware/esp32_cam_firmware.ino`（網路上取得後客製化，port 80 網頁 ＋ port 81 MJPEG 串流）
  - 用 DHCP 動態配置 IP，**每次重開機 IP 可能改變**，需看 Serial Monitor 開機輸出，
    更新 `backend/config.py` 的 `STREAM_URL`

## 3. 通訊協定

### 3.1 音訊串流（節點B → 筆電）
| 項目 | 規格 |
|---|---|
| 傳輸 | UDP，目的埠 5005 |
| 取樣率 | 16000 Hz、單聲道 |
| 樣本格式 | int16 little-endian（韌體由 32-bit I2S 原始樣本 >> GAIN_SHIFT=11 轉換，含削波保護） |
| 封包 | 512 樣本 = 1024 bytes = 32ms 音訊/包（約 31 包/秒） |
| 遺失處理 | 允許丟包（UDP 特性）；環形緩衝區自然覆蓋，不重傳 |

### 3.2 影像串流（節點A → 筆電）
- MJPEG over HTTP，`cv2.VideoCapture(STREAM_URL)` 讀取
- 階段 2 僅在警報時連線抓單張；階段 3 改為常駐 StreamReader
  （獨立執行緒 + Queue(maxsize=1) + 滿則丟舊幀 + 斷線自動重連）

### 3.3 Telegram
- `POST /bot<token>/sendMessage`（文字）
- `POST /bot<token>/sendPhoto`（multipart，JPEG 品質 85，記憶體內編碼不落地）
- `POST /bot<token>/sendDocument`（哭聲錄音片段：int16 樣本記憶體內包成 WAV 上傳，
  檔名 cry_clip.wav；用 sendDocument 而非 sendAudio 因後者只收 MP3/M4A）
- `GET /bot<token>/getUpdates`（long polling 拉取使用者傳給 Bot 的訊息，見 3.4）
- 所有呼叫含 timeout（10~15s）與例外吞噬，失敗不影響主迴圈

### 3.4 手動指令 / 定時拍照（backend/telegram_commands.py、video_monitor.py）
- `telegram_commands.command_loop`：long polling 輪詢 `getUpdates`
  （逾時 `TELEGRAM_POLL_TIMEOUT` 秒），`chat_id` 需符合 `config.TELEGRAM_CHAT_ID` 才處理指令，
  其餘一律忽略（防止陌生人傳訊息觸發拍照）：
  - `PHOTO_COMMAND`（預設 `/photo`）：立即截圖回傳
  - `STATUS_COMMAND`（預設 `/status`）：呼叫 `ActivityMonitor.get_status_text()`
    （只看最近 `MOTION_RECENT_SEC` 秒活動比例，不等滿 3 分鐘）回報安靜／可能醒了文字＋截圖
  - `HELP_COMMAND`（預設 `/help`）或 Telegram 內建 `/start`：回報 `build_help_text()`
    （使用說明＋指令列表）
- `telegram_commands.send_startup_message()`：程式啟動時發一次「系統已啟動」＋
  `build_help_text()`，`LOG_ONLY=True` 時不發（跟其他通知一致）。
- 開機時會先呼叫一次 `getUpdates` 只取 offset、不執行動作，清掉離線期間累積的舊訊息，
  避免一開機就被回放觸發。
- `video_monitor.periodic_snapshot_loop`：每 `PERIODIC_SNAPSHOT_SEC` 秒（預設 900 = 15 分鐘）
  自動傳一張畫面，`LOG_ONLY=True` 時不發送。
- `video_monitor.ActivityMonitor`：把活動視窗（`self.window`）包成 class 而非函式區域變數，
  讓 `activity_loop` 執行緒（寫入）與 `command_loop` 執行緒（`/status` 讀取）共用同一份資料。

## 4. 演算法規格

### 4.1 哭聲偵測（階段 1，主幹）
```
環形緩衝區：deque(maxlen=16000)   # 最近 1 秒音訊
推論頻率：每 0.5 秒
模型：YAMNet（TF-Hub google/yamnet/1，521 類，凍結權重，僅推論）
輸入：float32 波形 = int16 / 32768.0
分數：cry_score = max(平均分數[c] for c in 監看類別)
監看類別：{"Baby cry, infant cry", "Crying, sobbing", "Whimper"}
```

### 4.2 警報決策
```
滑動視窗：deque(maxlen=6)  存最近 6 次 (cry_score > THRESHOLD) 布林值
觸發條件：視窗內 True 數 >= 4（約 3 秒內多數判定為哭）
觸發後：清空視窗 + 進入冷卻 120 秒
```

### 4.3 活動量偵測（階段 3，程式完成，見 backend/video_monitor.py）
```
每秒一次：
  diff = cv2.absdiff(gray_now, gray_prev)
  motion = (diff > 25).sum() / diff.size        # 變動像素比例
活動視窗：deque(maxlen=180)                      # 最近 3 分鐘
預警條件：mean(最近180s) > MOTION_THRESHOLD 且持續 → 低級通知
歸零條件：mean(最近30s) < 靜止門檻 → 視為睡眠週期扭動，不通知
（門檻由階段 4 校準資料決定）
```

### 4.4 離線偵測
- 最後音訊封包時間距今 > 60 秒 → 發離線通知（一次），恢復後發復原通知

## 5. 設定參數（backend/config.py）

| 參數 | 預設值 | 說明 |
|---|---|---|
| UDP_PORT | 5005 | 音訊接收埠 |
| STREAM_URL | http://10.244.134.75:81/stream | ESP32-CAM 串流 |
| CRY_SCORE_THRESHOLD | 0.3 | 哭聲分數門檻（待校準） |
| CRY_WINDOW / CRY_TRIGGER_COUNT | 6 / 4 | 滑動視窗長度 / 觸發票數 |
| ALERT_COOLDOWN_SEC | 120 | 警報冷卻 |
| OFFLINE_WARN_SEC | 60 | 離線通知門檻 |
| SEND_CRY_CLIP | True | 哭聲警報是否附帶現場錄音片段（WAV） |
| CRY_CLIP_SECONDS | 10 | 錄音片段長度：觸發當下往回取最近 N 秒 |
| LOG_ONLY | False | True = 校準模式（只記錄不通知） |
| MOTION_DIFF_PIXEL_THRESHOLD | 25 | 單一像素亮度差門檻 |
| MOTION_PIXEL_RATIO_THRESHOLD | 0.02 | 一幀「變動像素」佔比門檻，超過算這一秒「有在動」 |
| MOTION_WINDOW_SEC / MOTION_RECENT_SEC | 180 / 30 | 活動視窗長度（3分鐘）／近期把關視窗（30秒） |
| MOTION_ALERT_RATIO / MOTION_STILL_RATIO | 0.3 / 0.1 | 3分鐘視窗預警門檻／30秒視窗靜止門檻（皆待階段4校準） |
| MOTION_ALERT_COOLDOWN_SEC | 120 | 活動量預警冷卻 |
| PERIODIC_SNAPSHOT_SEC | 900 | 定時拍照間隔（秒） |
| TELEGRAM_POLL_TIMEOUT | 25 | 指令輪詢 long-poll 逾時秒數 |
| PHOTO_COMMAND | "/photo" | 觸發手動拍照的指令文字 |
| STATUS_COMMAND | "/status" | 觸發狀態查詢（安靜／可能醒了＋截圖）的指令文字 |
| HELP_COMMAND | "/help" | 觸發使用說明的指令文字（`/start` 也會觸發同一份說明） |

韌體端參數：GAIN_SHIFT=11（增益，9~13 可調）、SAMPLES_PER_PACKET=512。

## 6. 資料與檔案

| 檔案 | 內容 | Git 追蹤 |
|---|---|---|
| backend/config.py | 實際設定（含 Telegram Token） | ❌ .gitignore |
| backend/config.example.py | 設定範本（無金鑰） | ✅ |
| backend/cry_scores.csv | 每 0.5s 的分數紀錄（校準用） | ❌ .gitignore |
| backend/motion_scores.csv | 每秒的活動量紀錄（校準用） | ❌ .gitignore |

CSV 欄位：
- cry_scores.csv：`time, cry_score, top_class, top_score`
- motion_scores.csv：`time, motion_ratio, active, mean_180s`

## 7. 錯誤處理原則

1. **主迴圈永不因周邊失敗而死**：Telegram / 截圖 / 網路例外一律捕捉記錄後繼續；
2. **感測端斷線 = 正常事件**：兩端皆自動重連，並以通知讓使用者知情；
3. **部署**：Windows 以 NSSM 掛服務（或開機捷徑），崩潰自動重啟（階段 4 後實施）。

## 8. 已定案的關鍵技術決策（ADR 摘要）

| # | 決策 | 理由 |
|---|---|---|
| D1 | 推論全在筆電，ESP32 零智慧 | Edge Impulse 自訓模型因 domain shift 部署失效；微控制器小模型泛化差 |
| D2 | 麥克風 INMP441（I2S）取代 MAX9814（類比） | 繞過 ESP32 ADC 噪聲/非線性、無 AGC 干擾、硬體時脈保證取樣率 |
| D3 | 哭聲模型用 YAMNet 預訓練 | 免訓練免標註、對麥克風差異抗性強；升級路線＝embedding＋自訓分類頭 |
| D4 | 聲音為警報主幹、影像為輔助 | 哭聲是「需要父母」最可靠訊號；影像價值在預警與截圖給人判斷 |
| D5 | 第一版不做姿勢分類 | 由「活動量預警＋截圖」覆蓋；避免 MediaPipe 在嬰兒體型/遮擋下的不穩定 |
| D6 | UDP 傳音訊（非 TCP） | 即時性優先，丟包可容忍；TCP 重傳反而造成延遲累積 |

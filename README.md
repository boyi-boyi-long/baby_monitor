# 嬰兒監測系統（階段 1~3：哭聲警報機 + 活動量預警）

架構：`ESP32+INMP441 →(UDP音訊)→ 筆電 YAMNet → Telegram 警報（附 ESP32-CAM 截圖）`

## 一、硬體接線（INMP441 → ESP32 DevKit）

| INMP441 | ESP32 |
|---|---|
| VDD | 3V3 |
| GND | GND |
| SCK | GPIO 26 |
| WS  | GPIO 25 |
| SD  | GPIO 33 |
| L/R | GND |

## 二、燒錄韌體

1. Arduino IDE 開啟 `esp32_mic_firmware/esp32_mic_firmware.ino`
2. 修改檔案最上方三行：WiFi 名稱、密碼、**筆電 IP**
   - 筆電 IP 查法：cmd 輸入 `ipconfig`，看「無線區域網路介面卡 Wi-Fi」的 IPv4 位址
3. 開發板選「**ESP32 Dev Module**」，燒錄
4. 開序列埠監控視窗（115200），看到「WiFi 已連線」「開始串流音訊」即成功

## 三、申請 Telegram Bot（一次性，約 10 分鐘）

1. Telegram 搜尋 **@BotFather** → 傳 `/newbot` → 取名 → 拿到 **Bot Token**
2. 在 Telegram 找到你剛建立的 bot，**先傳給它任意一句話**
3. 瀏覽器開啟：`https://api.telegram.org/bot<你的Token>/getUpdates`
   - 在回傳的 JSON 裡找 `"chat":{"id":987654321` → 那串數字就是 **Chat ID**
4. 把 Token 和 Chat ID 填進 `backend/config.py`

## 四、筆電後端

```
cd backend
pip install -r requirements.txt
python audio_monitor.py
```

第一次執行會自動下載 YAMNet 模型（約 4MB）。
看到終端機開始滾動「哭聲 0.xx |####...|」就代表整條管線通了。

**Windows 防火牆**：第一次執行若跳出防火牆詢問視窗，務必勾選「允許存取」
（私人網路），否則 UDP 收不到音訊。

## 五、測試流程

1. 對著 INMP441 講話 → 終端機「最強類別」應顯示 Speech 之類
2. 用手機播放 YouTube 嬰兒哭聲影片對著麥克風 → 哭聲分數應明顯上升
3. 分數連續超過門檻 → Telegram 應收到警報＋攝影機截圖

## 六、校準（正式上線前建議做 3~5 天）

1. `config.py` 設 `LOG_ONLY = True` → 只記錄不通知
2. 正常生活幾天，所有分數會存在 `cry_scores.csv`（活動量存在 `motion_scores.csv`）
3. 跑 `python backend/analyze_calibration.py`，自動統計背景噪音／疑似哭聲的分數分布，
   並印出建議的 `CRY_SCORE_THRESHOLD`（同時存成 `backend/calibration_report.txt`）
4. 把門檻值填回 `config.py`，改回 `LOG_ONLY = False`

## 五之二、定時拍照 / 手動拍照指令

- 程式會每 15 分鐘自動傳一張現場畫面到 Telegram（`config.py` 的 `PERIODIC_SNAPSHOT_SEC` 可調）。
- 想臨時看一眼寶寶現在的樣子：直接在 Telegram 傳 `/photo` 給你的 Bot，幾秒內會回傳一張現場截圖。
- 想知道現在是安靜還是可能醒了：傳 `/status` 給 Bot，會回傳文字判斷（🌟可能醒了／😴看起來在睡覺）＋現場截圖。
- 想聽聽現場最近的聲音（測試麥克風/校準用）：傳 `/sound` 給 Bot，會回傳最近一段現場錄音（WAV）＋目前哭聲分數狀態。
- 忘記有哪些指令：傳 `/help` 給 Bot（或在 Bot 對話框按 Telegram 內建的「Start」）即可再看一次說明。程式開機時也會自動發一次同樣的說明訊息。

## 五之三、活動量預警（可能醒了）的暖機時間

**⏳ 程式每次重開機後，前 3 分鐘（`MOTION_WINDOW_SEC`）不會觸發 📱「可能醒了」自動預警**，這是設計上刻意的行為，不是 bug：

- 判斷邏輯是看「最近 3 分鐘」的活動比例平均值，用意是分辨「寶寶醒了持續活動」跟「睡眠週期中短暫翻身扭動一下」——只看單一秒的瞬間活動會太容易誤報。
- 這個 3 分鐘的滑動視窗需要先蓄滿真實資料，統計出來的平均值才有意義；剛開機的前 3 分鐘視窗還沒蓄滿，判斷邏輯會直接跳過，不會誤觸發也不會漏判，等資料蓄滿後就會持續每秒往前滾動，不用再重新等待（除非又重開機）。
- 這段暖機期間如果想確認系統活著、有沒有偵測到活動，可以用 `/status`（只需開機滿 30 秒`MOTION_RECENT_SEC`），不受這個限制。

## 常見問題

- **終端機一直沒有分數滾動** → ESP32 韌體裡的筆電 IP 填錯，或防火牆擋了 UDP 5005
- **聲音分數怪怪的** → 調整韌體裡的 `GAIN_SHIFT`（太小聲改 9，爆音改 13）
- **警報沒截圖只有文字** → `config.py` 的 `STREAM_URL` 檢查一下，ESP32-CAM 是否在線

## 下一階段

- 階段 3：影像幀差活動量 → 「可能醒了」預警（程式已完成，待接上 ESP32-CAM 實測）
- 階段 4：校準週定案門檻（`backend/analyze_calibration.py` 已可分析 `cry_scores.csv`／`motion_scores.csv`，統計背景噪音與疑似哭聲分數分布，給門檻建議值）
- 階段 5：夜視鏡頭＋850nm 補光燈到貨 → 24 小時版

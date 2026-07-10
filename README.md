# 嬰兒監測系統（階段 1+2：哭聲警報機 + 截圖）

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
2. 正常生活幾天，所有分數會存在 `cry_scores.csv`
3. 用 Excel 打開 CSV 畫折線圖：日常噪音的分數 vs 真哭時的分數
4. 把 `CRY_SCORE_THRESHOLD` 設在兩者中間，改回 `LOG_ONLY = False`



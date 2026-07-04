# ============================================================
# 嬰兒監測系統 — 所有可調參數集中在這裡
# ============================================================

# ---- 網路 ----
UDP_PORT = 5005                                    # 接收 ESP32 音訊的埠（要和韌體一致）
STREAM_URL = "http://10.244.134.75:81/stream"      # ESP32-CAM 影像串流網址

# ---- Telegram（去找 @BotFather 申請，詳見 README）----
TELEGRAM_BOT_TOKEN = "在這裡填入你的BotToken"
TELEGRAM_CHAT_ID   = "在這裡填入你的ChatID"

# ---- 音訊 / YAMNet ----
SAMPLE_RATE = 16000
CRY_CLASSES = {"Baby cry, infant cry", "Crying, sobbing", "Whimper"}

CRY_SCORE_THRESHOLD = 0.3   # 哭聲分數門檻（校準模式跑幾天後再定案）
CRY_WINDOW = 6              # 滑動視窗長度：最近 6 次判斷（約 3 秒）
CRY_TRIGGER_COUNT = 4       # 視窗內超過門檻的次數 >= 4 才觸發警報

# ---- 警報行為 ----
ALERT_COOLDOWN_SEC = 120    # 警報冷卻：觸發後 120 秒內不重複轟炸
OFFLINE_WARN_SEC = 60       # 音訊節點斷訊超過 60 秒發離線通知

# ---- 校準模式 ----
LOG_ONLY = False            # True = 只記錄分數到 CSV，不發任何 Telegram 通知
LOG_CSV = "cry_scores.csv"  # 分數紀錄檔（校準用，永遠都會寫）

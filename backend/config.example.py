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

# ---- 影像活動量偵測（階段3）----
MOTION_DIFF_PIXEL_THRESHOLD = 25    # 單一像素亮度差異門檻(0-255)，超過視為「這個像素變動了」
MOTION_PIXEL_RATIO_THRESHOLD = 0.02 # 一幀裡「變動像素」佔比超過多少才算這一秒「有在動」（粗值，階段4再校準）
MOTION_WINDOW_SEC = 180             # 活動視窗長度：最近 3 分鐘（每秒判斷一次）
MOTION_RECENT_SEC = 30              # 判斷「目前是否仍在動」用的近期視窗
MOTION_ALERT_RATIO = 0.3            # 3分鐘視窗內「有在動」比例超過多少才預警（粗值，階段4再校準）
MOTION_STILL_RATIO = 0.1            # 最近30秒「有在動」比例低於此值＝已經靜止，視為短暫扭動不通知
MOTION_ALERT_COOLDOWN_SEC = 120     # 預警冷卻，同哭聲警報
MOTION_LOG_CSV = "motion_scores.csv" # 活動量紀錄檔（校準用，永遠都會寫）

# ---- 定時拍照 / 手動拍照指令 ----
PERIODIC_SNAPSHOT_SEC = 900   # 定時拍照間隔（秒），15 分鐘
TELEGRAM_POLL_TIMEOUT = 25    # 輪詢 Telegram 新訊息的 long-poll 逾時秒數
PHOTO_COMMAND = "/photo"      # 在 Telegram 傳這個文字給 Bot，立即回傳一張截圖
STATUS_COMMAND = "/status"    # 在 Telegram 傳這個文字給 Bot，回報目前是安靜還是可能醒了＋截圖

# ---- 校準模式 ----
LOG_ONLY = False            # True = 只記錄分數到 CSV，不發任何 Telegram 通知
LOG_CSV = "cry_scores.csv"  # 分數紀錄檔（校準用，永遠都會寫）

# CHANGELOG — 開發日誌

依日期記錄每次修改了什麼、為什麼改，方便回頭查閱進度。

---

## 2026-07-05　新增 ESP32-CAM 韌體存檔 ＋ /status 狀態查詢指令

**新增**
- `esp32_cam_firmware/esp32_cam_firmware.ino`：影像節點韌體存進版控（原取自網路範例，
  移除品牌字樣，WiFi 帳密改回預留文字避免明文密碼進 git）。
- `/status` 指令（`config.STATUS_COMMAND`）：Telegram 傳 `/status` 給 Bot，
  回報「目前看起來安靜／可能醒了」文字判斷＋現場截圖。判斷邏輯只看**最近 30 秒**
  活動比例（`MOTION_RECENT_SEC`），不用等滿 3 分鐘的預警視窗，做為即時查詢用途。

**修改**
- `backend/video_monitor.py`：把 `activity_loop` 函式改寫成 `ActivityMonitor` class，
  活動視窗（`self.window`）從函式區域變數改成物件屬性，讓 `activity_loop` 執行緒（寫入）
  跟 `telegram_commands` 的 `/status` 處理（讀取）能共用同一份資料。
- `backend/telegram_commands.py`：`command_loop`/`start` 多接一個 `activity_monitor` 參數。
- `backend/audio_monitor.py`：`main()` 改成先建立 `ActivityMonitor` 實例再啟動執行緒。
- `config.py`/`config.example.py`：新增 `STATUS_COMMAND` 參數。
- 同步更新 PRD（F2-5、US-7）、SPEC（3.4節）、README。

**下一步**
- 實測 `/status`：程式跑滿 30 秒後傳 `/status`，確認回報的安靜／可能醒了跟實際狀態一致；
  也測開機不滿 30 秒時傳 `/status`，應回報「資料收集中」而不是報錯。

---

## 2026-07-05　定時拍照＋Telegram 手動拍照指令

**新增**
- `backend/telegram_commands.py`
  - `command_loop`：long polling 輪詢 `getUpdates`，收到 `/photo`（`config.PHOTO_COMMAND`）
    且來自 `config.TELEGRAM_CHAT_ID` 才觸發即時截圖回傳；其餘訊息忽略（防陌生人觸發）。
  - 開機時先取一次 offset、不執行動作，清掉離線期間累積的舊訊息，避免一開機被回放觸發。
- `backend/video_monitor.py` 新增 `periodic_snapshot_loop`：每 `PERIODIC_SNAPSHOT_SEC`
  （預設 900 秒＝15 分鐘）自動傳一張現場畫面；`LOG_ONLY=True` 時不發送。
- `telegram_notify.py` 新增 `get_updates()`：呼叫 Telegram `getUpdates` API。

**修改**
- `backend/config.py`、`backend/config.example.py`：新增 `PERIODIC_SNAPSHOT_SEC`、
  `TELEGRAM_POLL_TIMEOUT`、`PHOTO_COMMAND` 三個參數。
- `audio_monitor.py`：`main()` 多啟動兩條執行緒（定時拍照、指令監聽）。
- `doc/PRD.md`：階段2新增 F2-3（定時拍照）、F2-4（手動拍照指令）、US-6。
- `doc/SPEC.md`：架構圖補上新執行緒、新增 3.4 節說明、參數表補三列。
- `README.md`：新增「定時拍照／手動拍照指令」使用說明。

**下一步**
- 實測 `/photo` 指令：程式跑起來後在 Telegram 傳 `/photo` 給 Bot，確認幾秒內收到截圖。
- 確認換人手機、或陌生人傳 `/photo` 給同一個 Bot 時**不會**觸發（`chat_id` 過濾是否生效）。
- 15 分鐘定時拍照比較難即時驗證，可以先把 `PERIODIC_SNAPSHOT_SEC` 臨時調成 60 秒測完再改回 900。

---

## 2026-07-05　階段 3：影像活動量「可能醒了」預警

**新增**
- `backend/video_monitor.py`
  - `StreamReader`：常駐執行緒讀取 ESP32-CAM MJPEG 串流，永遠只保留最新一幀，斷線自動重連。
  - `activity_loop`：每秒算幀差活動量（`cv2.absdiff`），維護 3 分鐘滑動視窗；
    視窗平均超標且「最近 30 秒仍在動」才觸發 📱 預警（避免扭動已停止卻延遲通知）；
    每秒把資料寫進 `backend/motion_scores.csv`（校準用）。
- `doc/CHANGELOG.md`（本檔案）

**修改**
- `backend/audio_monitor.py`
  - 哭聲警報截圖改跟 `video_monitor.StreamReader` 共用，不再自己另開攝影機連線
    （原因：ESP32-CAM 同時只服務得了一個串流 client，兩條邏輯各自連線會互搶）。
  - `main()` 啟動 `StreamReader` + `activity_loop` 兩條新執行緒。
  - 移除已不再使用的 `cv2` import（截圖邏輯搬到 `video_monitor.py`）。
- `backend/config.py`、`backend/config.example.py`
  - 新增 7 個活動量參數：`MOTION_DIFF_PIXEL_THRESHOLD`、`MOTION_PIXEL_RATIO_THRESHOLD`、
    `MOTION_WINDOW_SEC`、`MOTION_RECENT_SEC`、`MOTION_ALERT_RATIO`、`MOTION_STILL_RATIO`、
    `MOTION_ALERT_COOLDOWN_SEC`、`MOTION_LOG_CSV`。
  - 目前門檻皆為粗值，待階段 4 用真實資料校準。
- `.gitignore`：加入 `backend/motion_scores.csv`（校準資料，不進版控）。
- `doc/PRD.md`、`doc/SPEC.md`、`doc/README.md`、`CLAUDE.md`：階段 3 狀態由「⬜ 未開始」更新為「✅ 程式完成，待實測」。

**下一步（依 CLAUDE.md 開發流程）**
1. 這次改動目前在 `main` branch 上，尚未 commit——CLAUDE.md 規定新功能應在 `develop` branch 開發，建議先切過去再 commit。
2. 實機測試：
   - 確認 ESP32-CAM 串流網址（`config.py` 的 `STREAM_URL`）能連得到；
   - 跑 `python backend/audio_monitor.py`，對著鏡頭動一動，觀察終端機與 Telegram 是否如預期收到「可能醒了」預警；
   - 檢查 `backend/motion_scores.csv` 累積的 `motion_ratio` 數值分布，評估目前門檻（`MOTION_ALERT_RATIO=0.3` 等）是否合理。
3. 實測沒問題後，進入**階段 4：校準模式**——把 `LOG_ONLY=True` 跑個幾天收真實資料，再回頭調整哭聲與活動量門檻。

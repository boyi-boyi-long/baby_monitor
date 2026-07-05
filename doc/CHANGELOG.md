# CHANGELOG — 開發日誌

依日期記錄每次修改了什麼、為什麼改，方便回頭查閱進度。

---

## 2026-07-05　技術筆記（供專家複核）＋ 產品化規劃

**新增**
- `doc/TECH_NOTE_video_pipeline.md`：說明 `requirements.txt` 裡 numpy 為何必要
  （幀差演算法 `(diff > threshold).sum()` 本身就是 numpy 陣列運算，且
  `opencv-python` 本來就把 numpy 列為硬性依賴）；並檢視
  `esp32_cam_firmware.ino`，發現 **`loop()` 沒有 Wi-Fi 斷線重連機制**
  （對照 `esp32_mic_firmware.ino` 已有這段邏輯，音訊節點跟影像節點待遇不一致）。
- `doc/TECH_NOTE_detection_methods.md`：整理聲音線（YAMNet，深度學習）與
  影像線（幀差法，傳統演算法）的核心技術，以及兩條線各自被捨棄/未採用的前版方案：
  聲音線 MAX9814→INMP441、Edge Impulse 自訓模型→YAMNet；影像線考慮過但未採用 MediaPipe 姿勢辨識。

**下一步（明天）**

1. **補上 ESP32-CAM 的 Wi-Fi 自動重連**（`esp32_cam_firmware.ino`）
   直接抄 `esp32_mic_firmware.ino` 的 `loop()` 寫法：每輪迴圈檢查
   `WiFi.status() != WL_CONNECTED` 就呼叫重連，讓兩個感測端待遇一致，
   避免整夜因訊號閃斷而斷線不回來。

2. **硬體實測（阻塞其他所有階段的前置作業）**
   - INMP441 焊接組裝、接線（見 `doc/SPEC.md` 2.1 節）
   - 兩片 ESP32 燒錄韌體，確認各自 Serial Monitor 印出的 IP
   - 更新 `backend/config.py` 的 `STREAM_URL`／`LAPTOP_IP`
   - 跑 `python backend/audio_monitor.py`，走一次完整端到端流程：
     哭聲觸發警報＋截圖、活動量觸發「可能醒了」預警、`/photo`／`/status`／`/help` 指令

3. **把兩條偵測線「整合成產品級系統」要做的事**
   先釐清現況：`audio_monitor.py` 本來就是**唯一入口**，內部用 threading 把
   哭聲偵測（UDP＋YAMNet）、影像活動量偵測（`StreamReader`＋`ActivityMonitor`）、
   定時拍照、Telegram 指令輪詢全部跑在同一個 process 裡，兩條線本身已經是整合的——
   不是「兩支獨立程式」要合併。真正離「產品級」還缺的是**無人值守長期運行的可靠度**：

   | 項目 | 現況 | 要做的事 |
   |---|---|---|
   | 開機自動啟動 | 需手動執行 `python audio_monitor.py` | 用 NSSM 把它掛成 Windows 服務，開機自動啟動 |
   | 崩潰自動重啟 | 程式掛了沒人知道、不會自動恢復 | NSSM 服務設定 crash 自動重啟；或外層 watchdog script 定期檢查 process 是否存活 |
   | Log 管理 | 全部 `print` 到終端機，關掉視窗就消失 | 導到檔案＋做 log rotation（避免無限增長吃滿硬碟） |
   | ESP32-CAM IP 位址 | DHCP 動態配置，每次重開機要人工更新 `STREAM_URL` | 到路由器設定 **DHCP 固定保留（static lease）**，兩個感測端 IP 固定下來，一勞永逸 |
   | 感測端斷線通知 | 音訊節點離線已有通知（F1-5） | 影像節點（`StreamReader`）斷線目前只在終端機印訊息，沒有 Telegram 通知，建議補上，跟音訊節點待遇一致 |
   | 校準 | 門檻皆為粗值（`MOTION_ALERT_RATIO`、`CRY_SCORE_THRESHOLD` 等） | 待 1、2 完成、系統穩定跑起來後，進入**階段 4**：`LOG_ONLY=True` 收集 3~5 天真實資料再定門檻 |

   建議順序：先做 1（Wi-Fi 重連，小改動）→ 2（硬體實測，驗證整條 pipeline 真的能動）
   → 校準門檻（階段 4）→ 最後才做服務化／自動重啟（放到最後是因為要等邏輯與門檻都穩定，
   不然服務化後每次改程式都要重新部署，效率低）。

---

## 2026-07-05　開機說明訊息 ＋ /help 指令

**新增**
- `telegram_commands.build_help_text()`：組出「系統說明＋指令列表」文字，
  給開機通知跟 `/help`／`/start` 共用，避免同一段文字寫兩次。
- `telegram_commands.send_startup_message()`：程式啟動時發一次「✅ 系統已啟動」＋說明文字，
  `LOG_ONLY=True` 時不發（跟其他通知一致）。
- `/help` 指令（`config.HELP_COMMAND`）：隨時可查說明；Telegram 內建的 `/start`
  （使用者第一次點 Bot 的「Start」按鈕會自動傳這個文字）也觸發同一份說明——
  這樣不管是「使用者第一次連上 Bot」還是「程式重開機」，都會看到使用說明。
- `config.py`/`config.example.py` 新增 `HELP_COMMAND`。

**修改**
- `backend/audio_monitor.py`：`main()` 最後呼叫 `telegram_commands.send_startup_message()`。
- 同步更新 PRD（F2-6、US-8）、SPEC（3.4節、參數表）、README。

**下一步**
- 實測：把程式跑起來，確認 Telegram 收到「✅ 系統已啟動」的說明訊息；
  再傳 `/help` 確認能重複查到同一份說明。

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

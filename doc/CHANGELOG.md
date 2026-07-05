# CHANGELOG — 開發日誌

依日期記錄每次修改了什麼、為什麼改，方便回頭查閱進度。

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

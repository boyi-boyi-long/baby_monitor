# CLAUDE.md — 專案開發規範

## 語言規則
- 所有回應、文件、註解一律使用**繁體中文**。

## 專案簡介
嬰兒睡眠與哭聲監測系統：
- 感測端：ESP32-CAM（MJPEG 影像串流）＋ ESP32 DevKit + INMP441（UDP 音訊串流）
- 運算端：筆電 Python 後端（YAMNet 哭聲偵測、幀差活動量偵測）
- 通知端：Telegram Bot（警報＋截圖）

核心設計原則：**感測端零智慧、推論全在筆電**；聲音是警報主幹，影像是輔助偵察。
完整架構與階段規劃見 `doc/README.md`。

## 開發流程（依 AI Coding SOP）
- 開發在 `develop` branch 進行，`main` 為穩定版。
- 每次改完都要 commit，訊息用繁體中文說明改了什麼。
- 新功能先寫規格（propose）再動工（apply），完成後歸檔（archive）。

## 安全鐵則
- `backend/config.py` 含 Telegram Bot Token，**已加入 .gitignore，絕不 commit**。
- 新開發者請複製 `backend/config.example.py` 為 `config.py` 再填入金鑰。

## 目前進度（2026-07-05）
- ✅ 階段 1+2：哭聲警報機＋警報截圖（程式完成，待接線燒錄實測）
- ✅ 階段 3：影像幀差活動量「可能醒了」預警（程式完成，待實測；門檻為粗值，待階段4校準）
- ⬜ 階段 4：校準週（LOG_ONLY 模式收集資料定門檻）
- ⬜ 階段 5：夜視鏡頭＋850nm 紅外補光（硬體網購中）

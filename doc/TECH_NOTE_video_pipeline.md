# 技術筆記 — 影像節點韌體檢視 ＋ numpy 依賴說明

| 項目 | 內容 |
|---|---|
| 用途 | 供外部專家複核，非正式規格文件 |
| 對應檔案 | `esp32_cam_firmware/esp32_cam_firmware.ino`、`backend/video_monitor.py`、`backend/requirements.txt` |
| 日期 | 2026-07-05 |

---

## 1. `requirements.txt` 為何有 numpy？（影像這條線沒有 AI 模型，為何仍需要）

**結論：numpy 不是給哭聲 AI（YAMNet）用的，是影像「幀差活動量演算法」本身的計算引擎，屬必要依賴，非多餘套件。**

活動量偵測（階段 3）沒有用機器學習模型，用的是傳統影像處理的「幀間差異法」，但這個演算法的每一步運算都是 numpy 陣列運算，只是透過 OpenCV 間接呼叫，程式裡沒有寫 `import numpy as np`：

| 程式碼位置 | 動作 | 資料型別 |
|---|---|---|
| `video_monitor.py:52` `cv2.VideoCapture(...).read()` | 從 MJPEG 串流解碼出一張畫面 | 回傳值 `frame` 是 **numpy.ndarray**（形狀 H×W×3，dtype=uint8）——這是 `opencv-python` 套件的既定行為，其底層本身就是用 numpy 陣列表示影像 |
| `video_monitor.py:136` `cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)` | 彩色轉灰階 | 輸入輸出皆 ndarray |
| `video_monitor.py:141` `cv2.absdiff(gray, self.prev_gray)` | 逐像素算亮度差的絕對值 | 回傳 ndarray（H×W，dtype=uint8） |
| `video_monitor.py:142` `(diff > config.MOTION_DIFF_PIXEL_THRESHOLD).sum()` | **這行就是純 numpy 運算**：`diff > 25` 是 numpy 逐元素比較，回傳布林陣列；`.sum()` 是 numpy 陣列加總，算出「有幾個像素亮度差超過門檻」 | numpy bool ndarray → 純量 |
| 同一行 `/ diff.size` | 換算成「變動像素佔全畫面的比例」 | numpy 純量除法 |

**技術上為什麼不能省略 numpy**：`opencv-python` 這個 pip 套件在 `setup.py` 裡把 numpy 列為**硬性依賴（install_requires）**，只要裝 opencv-python，pip 一定會連帶裝 numpy，兩者無法分離。就算 `requirements.txt` 不寫 numpy，`pip install opencv-python` 時它還是會被自動裝進來——目前寫在 `requirements.txt` 只是把這個隱性依賴**明確列出來**，方便看依賴清單時知道專案實際用到什麼，這是正常且建議的作法，不是誤植。

**給專家複核的問題**：目前 `requirements.txt`（見下）沒有版本號鎖定，也沒有註解說明每個套件對應哪個功能模組。是否建議補上版本號與用途註解，避免日後套件升級造成 `cv2`/numpy API 不相容？

```
numpy            # 影像幀差運算（video_monitor.py 透過 cv2 陣列間接使用）
tensorflow       # YAMNet 哭聲偵測模型執行環境
tensorflow_hub   # 載入 YAMNet 預訓練權重
requests         # Telegram Bot API 呼叫
opencv-python    # MJPEG 串流讀取、影像格式轉換、幀差計算
```

---

## 2. `esp32_cam_firmware.ino` 檢視結果

範圍：完整讀過全檔（176 行），檢查攝影機初始化、雙 HTTP server（port 80 網頁／port 81 MJPEG 串流）、`setup()`/`loop()` 邏輯。

### 2.1 沒有發現邏輯錯誤
- 攝影機腳位設定（AI-Thinker 固定腳位）、`camera_config_t` 參數、雙 httpd server 註冊流程皆正確，`stream_handler` 的 multipart MJPEG 傳輸格式（boundary/content-length）符合標準寫法。

### 2.2 發現一項可靠度風險（建議修正）

**問題**：`loop()`（第 172~175 行）內容只有 `delay(10000)`，完全沒有偵測 Wi-Fi 連線狀態的邏輯。`setup()` 只在開機當下做一次 `WiFi.begin()` 並等待連線成功；一旦連線建立之後，程式**不會再檢查連線是否還活著**。

**影響**：若夜間 Wi-Fi 訊號短暫中斷（AP 重開機、訊號干擾、路由器排程重啟等常見情境），ESP32-CAM 不會自動重新連線，串流會整晚斷線，直到有人手動重新供電開機才會恢復。對於「整夜監測寶寶」的使用情境，這是實際的可靠度缺口。

**建議修正方向**（尚未動手改，待你確認要不要做）：在 `loop()` 內定期（例如每 10 秒）檢查 `WiFi.status() != WL_CONNECTED`，若斷線則呼叫 `WiFi.reconnect()` 並記錄 log，不需更動攝影機或串流的既有邏輯。

### 2.3 非問題、僅供專家參考的既有設計（文件中已載明，非本次發現）
- DHCP 動態配置 IP：每次重開機 IP 可能改變，需人工從 Serial Monitor 讀取後更新 `backend/config.py` 的 `STREAM_URL`（見 `doc/SPEC.md` 2.2 節），這是刻意的簡化設計，非 bug。
- `config.xclk_freq_hz = 10000000`、`jpeg_quality = 12`、`FRAMESIZE_QVGA` 屬影像品質/頻寬的既定選擇，未發現需要調整的訊號。

---

## 3. 待專家複核清單（摘要）

1. Wi-Fi 斷線後 ESP32-CAM 不會自動重連（2.2 節）——是否同意這是需要修的可靠度問題？
2. `requirements.txt` 缺版本鎖定與用途註解（1 節末）——是否建議補上？

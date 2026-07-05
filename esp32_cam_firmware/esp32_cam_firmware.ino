/*
 * 嬰兒監測系統 — 影像節點韌體
 * 板子：AI-Thinker ESP32-CAM
 *
 * 功能：開機連上 Wi-Fi 後，同時提供：
 *   Port 80：網頁（嵌入即時畫面，方便用瀏覽器直接看）
 *   Port 81：/stream，MJPEG 純串流（backend/video_monitor.py 讀這個網址）
 *
 * 開機時 Serial Monitor（115200）會印出目前實際拿到的 IP，
 * 因為是 DHCP 動態配置，每次重開機都要重新確認，
 * 並把 http://<IP>:81/stream 更新到 backend/config.py 的 STREAM_URL。
 */
#include "esp_camera.h"    // ESP32 攝影機函式庫
#include <WiFi.h>           // Wi-Fi 連線函式庫
#include "esp_http_server.h" // HTTP 伺服器函式庫

// ===== 請改成你自己的 Wi-Fi 名稱和密碼 =====
const char* ssid = "你的WiFi名稱";
const char* password = "你的WiFi密碼";

// ===== AI-Thinker ESP32-CAM 攝影機腳位（固定的，不用改）=====
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ===== MJPEG 串流格式定義（HTTP 多段傳輸用，不用改）=====
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// 兩個伺服器：一個放網頁(port 80)，一個放串流(port 81)
httpd_handle_t stream_httpd = NULL;
httpd_handle_t page_httpd = NULL;

// ========== 串流處理：不斷擷取畫面並傳給瀏覽器 ==========
static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t *fb = NULL;  // fb = frame buffer，存放一幀畫面
    char part_buf[64];

    // 設定回傳格式為 MJPEG 串流
    esp_err_t res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    // 無限迴圈：持續拍照 → 傳送 → 拍照 → 傳送...
    while (true) {
        fb = esp_camera_fb_get();           // 從攝影機取得一幀 JPEG 圖片
        if (!fb) { res = ESP_FAIL; break; } // 拍照失敗就跳出

        // 把這幀圖片用 HTTP chunk 方式傳給瀏覽器
        size_t hlen = snprintf(part_buf, 64, _STREAM_PART, fb->len);
        res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
        if (res == ESP_OK) res = httpd_resp_send_chunk(req, part_buf, hlen);
        if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
        esp_camera_fb_return(fb);           // 用完歸還 buffer

        if (res != ESP_OK) break;           // 傳送失敗（瀏覽器關閉）就停止
    }
    return res;
}

// ========== 首頁：顯示標題和嵌入串流畫面 ==========
static esp_err_t index_handler(httpd_req_t *req) {
    // 這段是完整的 HTML 網頁，會顯示在瀏覽器上
    const char html[] = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32-CAM 網路串流 - 育兒導航全攻略</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#111;color:#eee;font-family:Arial,sans-serif;text-align:center}
h1{font-size:20px;padding:8px 0 2px;color:#e94560}
.sub{font-size:12px;color:#888;padding-bottom:6px}
img{width:100%;max-width:640px;display:block;margin:0 auto;border-radius:6px}
</style>
</head>
<body>
<h1>ESP32-CAM 網路串流</h1>
<p class="sub">育兒導航全攻略</p>
<img id="stream" src="">
<script>
// 自動偵測 ESP32-CAM 的 IP，接上 port 81 的串流網址
var h=location.hostname;
document.getElementById('stream').src='http://'+h+':81/stream';
</script>
</body>
</html>
)rawliteral";
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, html, strlen(html));
}

void setup() {
    Serial.begin(115200);

    // ===== 攝影機硬體設定（腳位對應，固定的）=====
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer   = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;   config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;   config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;   config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;   config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk  = XCLK_GPIO_NUM;   config.pin_pclk  = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;   config.pin_href  = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM; config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn  = PWDN_GPIO_NUM;    config.pin_reset = RESET_GPIO_NUM;

    // ===== 攝影機參數設定（可以調整的部分）=====
    config.xclk_freq_hz = 10000000;       // 時鐘頻率 10MHz（降低可減少條紋）
    config.pixel_format = PIXFORMAT_JPEG;  // 輸出格式為 JPEG
    config.frame_size   = FRAMESIZE_QVGA;  // 解析度 320x240（小但流暢）
    config.jpeg_quality = 12;              // JPEG 品質 0~63，數字越小畫質越好
    config.fb_count     = psramFound() ? 2 : 1; // 有 PSRAM 用雙緩衝，串流更順

    // 啟動攝影機，失敗就停在這裡
    if (esp_camera_init(&config) != ESP_OK) {
        Serial.println("攝影機啟動失敗！請檢查排線");
        return;
    }
    Serial.println("攝影機啟動成功");

    // ===== 連接 Wi-Fi =====
    WiFi.begin(ssid, password);
    WiFi.setSleep(false);  // 關閉省電模式，串流更穩定
    Serial.print("正在連接 Wi-Fi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWi-Fi 已連線！");

    // ===== 啟動 Port 80 網頁伺服器（顯示有標題的控制頁面）=====
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = 80;
    httpd_uri_t index_uri = { .uri = "/", .method = HTTP_GET, .handler = index_handler, .user_ctx = NULL };
    if (httpd_start(&page_httpd, &cfg) == ESP_OK) {
        httpd_register_uri_handler(page_httpd, &index_uri);
    }

    // ===== 啟動 Port 81 串流伺服器（提供 MJPEG 影像串流）=====
    cfg.server_port = 81;
    cfg.ctrl_port += 1;
    httpd_uri_t stream_uri = { .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL };
    if (httpd_start(&stream_httpd, &cfg) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &stream_uri);
    }

    // 印出網址，複製貼到瀏覽器就能看到畫面
    Serial.println("=========================================");
    Serial.printf("  開啟網頁：http://%s\n", WiFi.localIP().toString().c_str());
    Serial.printf("  純串流：  http://%s:81/stream\n", WiFi.localIP().toString().c_str());
    Serial.println("=========================================");
}

// loop 裡不需要做任何事，伺服器在背景自動運作
void loop() {
    delay(10000);
}

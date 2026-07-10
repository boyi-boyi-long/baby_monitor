/*
 * 嬰兒哭聲監測 — 音訊節點韌體
 * 板子：ESP32 DevKit (ESP-WROOM-32, CP2102)
 * 麥克風：INMP441 (I2S 數位麥克風)
 *
 * 功能：以 16kHz 讀取 INMP441，轉成 16-bit 樣本，
 *       透過 UDP 持續發送到筆電後端。
 *
 * 接線（左邊 INMP441 腳位 → 右邊 ESP32 腳位）：
 *   VDD → 3V3
 *   GND → GND
 *   SCK → GPIO 26
 *   WS  → GPIO 25
 *   SD  → GPIO 33
 *   L/R → GND（選擇左聲道）
 *
 * Arduino IDE 設定：開發板選「ESP32 Dev Module」
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>

// ======== 請修改這三行 ========
const char* WIFI_SSID = "你的WiFi名稱";
const char* WIFI_PASS = "你的WiFi密碼";
const char* LAPTOP_IP = "10.244.134.160";   // 筆電的區網 IP（cmd 輸入 ipconfig 查）
// ==============================

const int UDP_PORT = 5005;

// I2S 腳位
#define I2S_SCK 26
#define I2S_WS  25
#define I2S_SD  33

#define SAMPLE_RATE        16000
#define SAMPLES_PER_PACKET 512     // 每個 UDP 封包 512 樣本 = 1024 bytes = 32ms
#define GAIN_SHIFT         11      // 右移位數。聲音太小就調小(如 9)，爆音就調大(如 13)

WiFiUDP udp;
int32_t rawBuf[SAMPLES_PER_PACKET];
int16_t pktBuf[SAMPLES_PER_PACKET];

void setupI2S() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
  cfg.sample_rate = SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;   // INMP441 為 24-bit 資料放在 32-bit 框
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;    // L/R 接 GND = 左聲道
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;

  i2s_pin_config_t pins = {};
  pins.bck_io_num = I2S_SCK;
  pins.ws_io_num = I2S_WS;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = I2S_SD;

  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("連接 WiFi 中");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi 已連線！本機 IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("音訊發送目標: ");
  Serial.print(LAPTOP_IP);
  Serial.print(":");
  Serial.println(UDP_PORT);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  connectWiFi();
  setupI2S();
  Serial.println("開始串流音訊...");
}

void loop() {
  // WiFi 斷線自動重連
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi 斷線，重連中...");
    connectWiFi();
  }

  // 讀滿一個封包的樣本（阻塞直到讀滿）
  size_t bytesRead = 0;
  i2s_read(I2S_NUM_0, rawBuf, sizeof(rawBuf), &bytesRead, portMAX_DELAY);
  int n = bytesRead / sizeof(int32_t);

  // 32-bit 原始樣本 → 16-bit（含增益與削波保護）
  for (int i = 0; i < n; i++) {
    int32_t s = rawBuf[i] >> GAIN_SHIFT;
    if (s >  32767) s =  32767;
    if (s < -32768) s = -32768;
    pktBuf[i] = (int16_t)s;
  }

  udp.beginPacket(LAPTOP_IP, UDP_PORT);
  udp.write((uint8_t*)pktBuf, n * sizeof(int16_t));
  udp.endPacket();
}

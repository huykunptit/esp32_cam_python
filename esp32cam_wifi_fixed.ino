#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <HardwareSerial.h>
#include <Preferences.h>

#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// ===========================
// CẤU HÌNH AP CÀI ĐẶT WIFI
// ===========================
const char* AP_SSID = "ESP32CAM-Setup";
const char* AP_PASS = "12345678"; // có thể đổi

// ===========================
// LƯU WIFI VÀO FLASH (NVS)
// ===========================
Preferences prefs;
String wifiSSID = "";
String wifiPASS = "";

// ===========================
// UART2 VỚI ESP32 THƯỜNG (GẬY)
// ===========================
// ESP32-CAM: GPIO13 = RX, GPIO12 = TX
#define RXD2 13 // Nhận từ ESP32 thường (TX2=GPIO18)
#define TXD2 12 // Gửi đến ESP32 thường (RX2=GPIO19)
HardwareSerial SerialESP(2); // UART2

// ===========================
// BIẾN TOÀN CỤC
// ===========================
String sensorData = "{\"distance_mm\":-1,\"pip\":\"NONE\",\"warning\":0}";
unsigned long lastSensorUpdate = 0;
bool uartConnected = false;

// ==== BIẾN AI NHẬN TỪ PC ====
String aiLabel = "";
float  aiConfidence = 0.0;
unsigned long lastAIUpdate = 0;

// Chế độ hoạt động
enum AppMode { MODE_CONFIG, MODE_NORMAL };
AppMode appMode = MODE_CONFIG;

WebServer server(80);

// ===========================
// HÀM KHỞI TẠO CAMERA
// ===========================
void initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  if (psramFound()) {
    config.frame_size   = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count     = 2;
    config.grab_mode    = CAMERA_GRAB_LATEST;
    config.fb_location  = CAMERA_FB_IN_PSRAM;
  } else {
    config.frame_size   = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count     = 1;
    config.fb_location  = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ Camera init failed: 0x%x\n", err);
    delay(5000);
    ESP.restart();
  }
  Serial.println("✅ Camera initialized");
}

// ===========================
// TRANG WEB CONFIG WIFI (FIXED)
// ===========================
void handleConfigPage() {
  Serial.println("📡 Starting WiFi scan...");
  
  // QUAN TRỌNG: Đảm bảo WiFi mode là AP_STA để có thể quét
  WiFi.mode(WIFI_AP_STA);
  
  // Đợi một chút để WiFi mode ổn định
  delay(100);
  
  // Bắt đầu quét WiFi (async)
  int n = WiFi.scanNetworks();
  
  // Nếu scan chưa hoàn thành, đợi thêm
  int scanAttempts = 0;
  while (n < 0 && scanAttempts < 10) {
    delay(500);
    n = WiFi.scanNetworks();
    scanAttempts++;
    Serial.print(".");
  }
  
  Serial.println();
  Serial.printf("✅ Found %d networks\n", n);

  String html;
  html.reserve(5000);
  html += "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>ESP32-CAM WiFi Setup</title>";
  html += "<style>";
  html += "body{font-family:Arial,sans-serif;background:#222;color:#fff;padding:20px;}";
  html += ".card{background:#fff;color:#333;padding:20px;border-radius:12px;max-width:500px;margin:0 auto;}";
  html += "h1{text-align:center;}";
  html += "label{display:block;margin-top:10px;font-weight:bold;}";
  html += "select,input{width:100%;padding:8px;margin-top:5px;border-radius:6px;border:1px solid #ccc;}";
  html += ".btn{margin-top:15px;width:100%;padding:10px;border:none;border-radius:8px;background:#667eea;color:#fff;font-size:16px;cursor:pointer;}";
  html += ".btn:hover{background:#5568d3;}";
  html += ".btn-refresh{background:#28a745;margin-left:10px;}";
  html += ".btn-refresh:hover{background:#218838;}";
  html += "</style></head><body>";
  html += "<div class='card'>";
  html += "<h1>ESP32-CAM WiFi Setup</h1>";
  html += "<p>Kết nối điện thoại vào WiFi <strong>";
  html += AP_SSID;
  html += "</strong> (pass: ";
  html += AP_PASS;
  html += "), sau đó chọn WiFi để ESP32-CAM kết nối.</p>";
  html += "<form method='POST' action='/save'>";
  html += "<label>Chọn WiFi: <a href='/' class='btn btn-refresh' style='display:inline-block;width:auto;padding:5px 10px;margin-left:10px;'>🔄 Quét lại</a></label>";
  html += "<select name='ssid'>";
  
  if (n <= 0) {
    html += "<option value=''>Không tìm thấy WiFi (nhấn Quét lại hoặc nhập thủ công)</option>";
  } else {
    // Sắp xếp theo signal strength (RSSI)
    int indices[n];
    for (int i = 0; i < n; i++) {
      indices[i] = i;
    }
    // Bubble sort đơn giản
    for (int i = 0; i < n - 1; i++) {
      for (int j = 0; j < n - i - 1; j++) {
        if (WiFi.RSSI(indices[j]) < WiFi.RSSI(indices[j + 1])) {
          int temp = indices[j];
          indices[j] = indices[j + 1];
          indices[j + 1] = temp;
        }
      }
    }
    
    for (int i = 0; i < n; i++) {
      int idx = indices[i];
      String ssid = WiFi.SSID(idx);
      int rssi = WiFi.RSSI(idx);
      String encryption = (WiFi.encryptionType(idx) == WIFI_AUTH_OPEN) ? "🔓" : "🔒";
      
      html += "<option value='" + ssid + "'";
      if (ssid == wifiSSID) html += " selected";
      html += ">";
      html += encryption + " " + ssid;
      html += " (";
      html += rssi;
      html += " dBm)";
      html += "</option>";
    }
  }
  
  html += "</select>";
  html += "<label>Hoặc nhập SSID thủ công:</label>";
  html += "<input type='text' name='ssid_manual' placeholder='Nhập tên WiFi'>";
  html += "<label>Mật khẩu WiFi:</label>";
  html += "<input type='password' name='pass' placeholder='Nhập password WiFi'>";
  html += "<button class='btn' type='submit'>Lưu & Kết nối</button>";
  html += "</form>";
  
  if (wifiSSID.length() > 0) {
    html += "<p>WiFi đã lưu trước đây: <strong>" + wifiSSID + "</strong></p>";
  }
  
  html += "</div></body></html>";
  server.send(200, "text/html", html);
}

// ===========================
// URL DECODE (để xử lý ký tự đặc biệt trong SSID)
// ===========================
String urlDecode(String str) {
  String decoded = "";
  char temp[] = "0x00";
  unsigned int len = str.length();
  unsigned int i = 0;
  while (i < len) {
    char decodedChar;
    char encodedChar = str.charAt(i);
    if ((encodedChar == '%') && (i + 1 < len) && (i + 2 < len)) {
      temp[2] = str.charAt(i + 1);
      temp[3] = str.charAt(i + 2);
      decodedChar = strtol(temp, NULL, 16);
      i += 2;
    } else if (encodedChar == '+') {
      decodedChar = ' ';
    } else {
      decodedChar = encodedChar;
    }
    decoded += decodedChar;
    i++;
  }
  return decoded;
}

// ===========================
// LƯU WIFI + KẾT NỐI (FIXED)
// ===========================
void handleSaveWifi() {
  // LẤY DỮ LIỆU TRƯỚC KHI GỬI RESPONSE
  String ssidToUse = "";
  
  // Lấy SSID từ form (ưu tiên ssid_manual)
  if (server.hasArg("ssid_manual") && server.arg("ssid_manual").length() > 0) {
    ssidToUse = urlDecode(server.arg("ssid_manual"));
    ssidToUse.trim();
  } else if (server.hasArg("ssid") && server.arg("ssid").length() > 0) {
    ssidToUse = urlDecode(server.arg("ssid"));
    ssidToUse.trim();
  }
  
  String passToUse = urlDecode(server.arg("pass"));
  passToUse.trim();
  
  // Gửi response ngay để client không bị timeout
  server.sendHeader("Connection", "close");
  server.send(200, "text/html", "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta http-equiv='refresh' content='5;url=/'><title>Đang kết nối...</title></head><body style='font-family:Arial;padding:20px;text-align:center;'><h2>⏳ Đang kết nối WiFi...</h2><p>Vui lòng đợi trong giây lát...</p><p>Trang sẽ tự động chuyển hướng sau 5 giây.</p></body></html>");
  server.client().stop();
  
  // Đợi một chút để response được gửi đi
  delay(200);
  
  if (ssidToUse.length() == 0) {
    Serial.println("❌ Error: Missing SSID");
    // Bật lại AP
    WiFi.mode(WIFI_AP_STA);
    delay(100);
    WiFi.softAP(AP_SSID, AP_PASS);
    delay(500);
    Serial.println("📡 AP restarted");
    return;
  }

  wifiSSID = ssidToUse;
  wifiPASS = passToUse;

  // Lưu vào NVS
  prefs.putString("ssid", wifiSSID);
  prefs.putString("pass", wifiPASS);
  prefs.end(); // Đóng NVS để đảm bảo dữ liệu được lưu
  
  Serial.println("📡 Saving WiFi:");
  Serial.print("  SSID: "); Serial.println(wifiSSID);
  Serial.print("  PASS: "); Serial.println(wifiPASS.length() > 0 ? "***" : "(empty)");

  // Ngắt AP trước
  WiFi.softAPdisconnect(true);
  delay(500);
  
  // Chuyển sang STA mode
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  
  // Bắt đầu kết nối
  WiFi.begin(wifiSSID.c_str(), wifiPASS.c_str());
  
  Serial.print("🔗 Connecting to ");
  Serial.println(wifiSSID);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    appMode = MODE_NORMAL;
    IPAddress ip = WiFi.localIP();
    Serial.println("✅ WiFi CONNECTED!");
    Serial.print("🌐 IP Address: ");
    Serial.println(ip);
  } else {
    appMode = MODE_CONFIG;
    Serial.println("❌ WiFi connection FAILED!");
    
    // Bật lại AP để config tiếp
    delay(500);
    WiFi.mode(WIFI_AP_STA);
    delay(100);
    
    if (!WiFi.softAP(AP_SSID, AP_PASS)) {
      Serial.println("❌ Failed to restart AP, retrying...");
      delay(500);
      WiFi.softAP(AP_SSID, AP_PASS);
    }
    
    delay(500);
    Serial.print("📡 AP restarted for re-configuration. IP: ");
    Serial.println(WiFi.softAPIP());
  }
  
  // Mở lại NVS cho lần sau
  prefs.begin("wifi", false);
}

// ===========================
// HANDLER TRANG WEB CHÍNH (CAM + SENSOR + AI)
// ===========================
void handleMainPage() {
  String ipAddress;
  if (WiFi.status() == WL_CONNECTED) {
    ipAddress = WiFi.localIP().toString();
  } else {
    ipAddress = WiFi.softAPIP().toString();
  }

  String html;
  html.reserve(8000);
  html += "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>ESP32-CAM Blind Assistance</title>";
  html += "<style>";
  html += "body { font-family: Arial, sans-serif; background: linear-gradient(135deg,#667eea 0%,#764ba2 100%); margin:0; padding:20px; color:white; }";
  html += ".card { background:white; color:#333; padding:20px; margin:10px 0; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1); }";
  html += ".status { padding:12px; border-radius:8px; margin:10px 0; font-weight:bold; }";
  html += ".connected { background:#d4edda; color:#155724; }";
  html += ".disconnected { background:#f8d7da; color:#721c24; }";
  html += "img { width:100%; max-width:640px; border-radius:8px; border:3px solid #667eea; }";
  html += ".btn { display:inline-block; background:#667eea; color:white; padding:10px 18px; margin:5px; border-radius:8px; text-decoration:none; transition:0.3s; border:none; cursor:pointer; }";
  html += ".btn:hover { background:#5568d3; transform:translateY(-2px); }";
  html += ".sensor-value { font-size:18px; font-weight:bold; color:#667eea; margin:10px 0; }";
  html += "h1 { text-shadow:2px 2px 4px rgba(0,0,0,0.2); }";
  html += "#soundStatus { font-weight:bold; }";
  html += "</style>";
  html += "</head><body>";
  html += "<h1>🎯 ESP32-CAM Blind Assistance</h1>";

  // CAMERA
  html += "<div class='card'><h2>📸 Live Camera Feed</h2>";
  html += "<img src='/capture' id='photo' alt='Camera feed'>";
  html += "<script>";
  html += "setInterval(function(){ document.getElementById('photo').src='/capture?t=' + Date.now(); }, 2000);";
  html += "</script>";
  html += "</div>";

  // SENSOR + AI + SOUND
  html += "<div class='card'><h2>📊 Sensor &amp; AI &amp; Voice</h2>";
  html += "<div id='sensorData' class='sensor-value'>Loading...</div>";
  html += "<div id='uartStatus' class='status disconnected'>UART: Checking...</div>";
  html += "<button class='btn' id='soundBtn' onclick='enableSound()'>🔊 Bật âm thanh mô tả</button> ";
  html += "<span id='soundStatus'>Âm thanh: đang tắt</span>";
  html += "</div>";

  // API
  html += "<div class='card'><h2>🔗 API Endpoints</h2>";
  html += "<a href='/capture' class='btn'>📷 /capture</a>";
  html += "<a href='/distance' class='btn'>📊 /distance</a>";
  html += "<a href='/results' class='btn'>📤 /results (POST)</a>";
  html += "</div>";

  // NETWORK INFO
  html += "<div class='card'><h2>🌐 Network Info</h2>";
  html += "<p><strong>IP Address:</strong> " + ipAddress + "</p>";
  html += "<p><strong>UART Pins (ESP32-CAM):</strong> RX=GPIO13, TX=GPIO12</p>";
  html += "<p><strong>Kết nối từ ESP32 (gậy):</strong> TX2(GPIO18)→13, RX2(GPIO19)←12</p>";
  html += "<p><strong>AI endpoint (PC → ESP32):</strong> POST <code>/ai</code> với JSON <code>{\"label\":\"person\",\"confidence\":0.9}</code></p>";
  html += "<p><strong>Results endpoint (PC → ESP32):</strong> POST <code>/results</code> với JSON kết quả detection</p>";
  html += "</div>";

  // ===========================
  // JAVASCRIPT: SPEECH + SENSOR + AI
  // ===========================
  html += "<script>";
  html += "let audioEnabled = false;";
  html += "let lastSpokenText = '';";
  html += "let lastSpeakTime = 0;";

  // Bật/Tắt âm thanh
  html += "function enableSound(){";
  html += "  audioEnabled = true;";
  html += "  document.getElementById('soundStatus').textContent = 'Âm thanh: đang bật';";
  html += "  document.getElementById('soundStatus').style.color = 'green';";
  html += "  const btn = document.getElementById('soundBtn');";
  html += "  btn.textContent = '🔇 Tắt âm thanh mô tả';";
  html += "  btn.onclick = disableSound;";
  html += "}";
  html += "function disableSound(){";
  html += "  audioEnabled = false;";
  html += "  document.getElementById('soundStatus').textContent = 'Âm thanh: đang tắt';";
  html += "  document.getElementById('soundStatus').style.color = 'red';";
  html += "  const btn = document.getElementById('soundBtn');";
  html += "  btn.textContent = '🔊 Bật âm thanh mô tả';";
  html += "  btn.onclick = enableSound;";
  html += "}";

  // Hàm speak tiếng Việt
  html += "function speak(text){";
  html += "  if(!audioEnabled) return;";
  html += "  if(!('speechSynthesis' in window)) return;";
  html += "  const now = Date.now();";
  html += "  if(text === lastSpokenText && (now - lastSpeakTime) < 3000) return;"; // tránh spam
  html += "  const u = new SpeechSynthesisUtterance(text);";
  html += "  u.lang = 'vi-VN';";
  html += "  window.speechSynthesis.speak(u);";
  html += "  lastSpokenText = text;";
  html += "  lastSpeakTime = now;";
  html += "}";

  // Map label tiếng Anh -> tiếng Việt
  html += "function labelToVietnamese(label){";
  html += "  if(label === 'person') return 'người';";
  html += "  if(label === 'chair') return 'ghế';";
  html += "  if(label === 'car') return 'xe ô tô';";
  html += "  if(label === 'bicycle') return 'xe đạp';";
  html += "  if(label === 'bus') return 'xe buýt';";
  html += "  return label;";
  html += "}";

  // Cập nhật sensor + AI
  html += "function updateSensorData(){";
  html += "  fetch('/distance')";
  html += "    .then(r => r.json())";
  html += "    .then(data => {";
  html += "      let htmlTxt = '';";
  html += "      htmlTxt += '<strong>Distance:</strong> ' + data.distance_mm + ' mm<br>';";  
  html += "      htmlTxt += '<strong>PIP Level:</strong> ' + data.pip + '<br>';";  
  html += "      if(data.front_cm !== undefined) htmlTxt += '<strong>Front:</strong> ' + data.front_cm + ' cm<br>';";  
  html += "      if(data.left_cm  !== undefined) htmlTxt += '<strong>Left:</strong> '  + data.left_cm  + ' cm<br>';";  
  html += "      if(data.right_cm !== undefined) htmlTxt += '<strong>Right:</strong> ' + data.right_cm + ' cm<br>';";  

  // AI info
  html += "      const aiLabel = data.ai_label || '';";  
  html += "      const aiConf  = data.ai_confidence || 0;";  
  html += "      if(aiLabel){";
  html += "        htmlTxt += '<strong>AI:</strong> ' + aiLabel + ' (' + (aiConf*100).toFixed(1) + '%)<br>';";  
  html += "      }";
  html += "      document.getElementById('sensorData').innerHTML = htmlTxt;";

  // UART status
  html += "      let uartDiv = document.getElementById('uartStatus');";
  html += "      if(data.uart_connected){";
  html += "        uartDiv.className = 'status connected';";
  html += "        uartDiv.innerHTML = '✅ UART CONNECTED (ESP32 gậy)';";
  html += "      } else {";
  html += "        uartDiv.className = 'status disconnected';";
  html += "        uartDiv.innerHTML = '❌ UART DISCONNECTED - Kiểm tra dây TX/RX';";
  html += "      }";

  // Ghép câu đọc: "Phía trước có ... cách ... cm"
  html += "      const warning = data.warning || 0;";
  html += "      const dist_cm = data.front_cm || -1;";
  html += "      if(aiLabel && dist_cm > 0 && warning > 0 && aiConf > 0.5){";
  html += "        const nameVi = labelToVietnamese(aiLabel);";
  html += "        const sentence = 'Phía trước có ' + nameVi + ', cách khoảng ' + dist_cm + ' xăng ti mét';";
  html += "        speak(sentence);";
  html += "      }";
  html += "    })";
  html += "    .catch(e => {";
  html += "      document.getElementById('sensorData').innerHTML = 'Error: ' + e;";
  html += "    });";
  html += "}";
  html += "updateSensorData();";
  html += "setInterval(updateSensorData, 600);";
  html += "</script>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}

// ===========================
// HANDLER ROOT CHUNG: CHỌN THEO MODE
// ===========================
void handleRoot() {
  if (appMode == MODE_CONFIG) {
    handleConfigPage();
  } else {
    handleMainPage();
  }
}

// ===========================
// HANDLER /CAPTURE
// ===========================
void handleCapture() {
  if (appMode != MODE_NORMAL) {
    server.send(403, "text/plain", "Not available in config mode");
    return;
  }
  
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// ===========================
// HANDLER /DISTANCE (JSON)
// ===========================
void handleDistance() {
  StaticJsonDocument<256> responseDoc;
  
  if (sensorData.length() > 10) {
    StaticJsonDocument<256> sensorDoc;
    DeserializationError err = deserializeJson(sensorDoc, sensorData);
    if (!err) {
      responseDoc["distance_mm"] = sensorDoc["distance_mm"].as<int>();
      responseDoc["pip"]         = sensorDoc["pip"].as<String>();
      responseDoc["front_cm"]    = sensorDoc["front_cm"].as<int>();
      responseDoc["left_cm"]     = sensorDoc["left_cm"].as<int>();
      responseDoc["right_cm"]    = sensorDoc["right_cm"].as<int>();
      responseDoc["warning"]     = sensorDoc["warning"].as<int>();
    } else {
      responseDoc["distance_mm"] = -1;
      responseDoc["pip"]         = "NONE";
      responseDoc["warning"]     = 0;
    }
  } else {
    responseDoc["distance_mm"] = -1;
    responseDoc["pip"]         = "NONE";
    responseDoc["warning"]     = 0;
  }

  // Thêm thông tin AI
  responseDoc["ai_label"]      = aiLabel;
  responseDoc["ai_confidence"] = aiConfidence;
  responseDoc["ai_age_ms"]     = (lastAIUpdate == 0) ? -1 : (long)(millis() - lastAIUpdate);
  responseDoc["timestamp"]      = millis();
  responseDoc["uart_connected"] = uartConnected;
  
  if (WiFi.status() == WL_CONNECTED) {
    responseDoc["ip"] = WiFi.localIP().toString();
  } else {
    responseDoc["ip"] = WiFi.softAPIP().toString();
  }

  String response;
  serializeJson(responseDoc, response);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", response);
}

// ===========================
// HANDLER /AI – nhận kết quả AI từ PC
// ===========================
void handleAI() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Use POST");
    return;
  }
  
  String body = server.arg("plain");
  if (body.length() == 0) {
    server.send(400, "text/plain", "Empty body");
    return;
  }

  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    server.send(400, "text/plain", "Invalid JSON");
    return;
  }

  aiLabel      = doc["label"]      | "";
  aiConfidence = doc["confidence"] | 0.0;
  lastAIUpdate = millis();

  Serial.print("🤖 AI label: ");
  Serial.print(aiLabel);
  Serial.print("  conf: ");
  Serial.println(aiConfidence, 2);

  server.send(200, "text/plain", "OK");
}

// ===========================
// HANDLER /RESULTS – nhận kết quả detection từ PC
// ===========================
void handleResults() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Use POST");
    return;
  }
  
  String body = server.arg("plain");
  if (body.length() == 0) {
    server.send(400, "text/plain", "Empty body");
    return;
  }

  StaticJsonDocument<1024> doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    server.send(400, "text/plain", "Invalid JSON: " + String(err.c_str()));
    return;
  }

  // Lưu thông tin từ results
  if (doc.containsKey("distance_mm")) {
    // Có thể cập nhật sensor data nếu cần
  }
  
  if (doc.containsKey("pip")) {
    String pip = doc["pip"] | "NONE";
    // Xử lý pip alert nếu cần
  }
  
  if (doc.containsKey("objects")) {
    JsonArray objects = doc["objects"];
    Serial.print("📦 Received ");
    Serial.print(objects.size());
    Serial.println(" detected objects");
    
    for (JsonObject obj : objects) {
      String className = obj["class"] | "unknown";
      float confidence = obj["confidence"] | 0.0;
      Serial.printf("  - %s: %.2f\n", className.c_str(), confidence);
    }
  }

  server.send(200, "application/json", "{\"status\":\"ok\"}");
}

// ===========================
// SETUP
// ===========================
void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();
  Serial.println("🚀 ESP32-CAM Blind Assistance + AI Starting...");

  // UART2
  SerialESP.begin(115200, SERIAL_8N1, RXD2, TXD2);
  Serial.println("📡 UART2 initialized:");
  Serial.println("   RX=GPIO13 (from ESP32 gậy TX2)");
  Serial.println("   TX=GPIO12 (to ESP32 gậy RX2)");

  // CAMERA
  initCamera();

  // Đọc WiFi đã lưu
  prefs.begin("wifi", false);
  wifiSSID = prefs.getString("ssid", "");
  wifiPASS = prefs.getString("pass", "");

  // Thử kết nối WiFi đã lưu
  if (wifiSSID.length() > 0) {
    Serial.print("📡 Trying saved WiFi: ");
    Serial.println(wifiSSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(wifiSSID.c_str(), wifiPASS.c_str());
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      delay(500);
      Serial.print(".");
      attempts++;
    }
    Serial.println();
    
    if (WiFi.status() == WL_CONNECTED) {
      appMode = MODE_NORMAL;
      Serial.println("✅ WiFi CONNECTED with saved credentials!");
      Serial.print("🌐 IP Address: ");
      Serial.println(WiFi.localIP());
    } else {
      appMode = MODE_CONFIG;
      Serial.println("❌ Saved WiFi failed. Enter CONFIG mode.");
    }
  } else {
    appMode = MODE_CONFIG;
    Serial.println("ℹ️ No saved WiFi. Enter CONFIG mode.");
  }

  // Nếu cần cấu hình -> bật AP với mode AP_STA để có thể quét WiFi
  if (appMode == MODE_CONFIG) {
    // QUAN TRỌNG: Dùng WIFI_AP_STA để vừa chạy AP vừa quét được WiFi
    WiFi.mode(WIFI_AP_STA);
    delay(100);
    
    // Đảm bảo AP được bật
    if (!WiFi.softAP(AP_SSID, AP_PASS)) {
      Serial.println("❌ Failed to start AP, retrying...");
      delay(500);
      WiFi.softAP(AP_SSID, AP_PASS);
    }
    
    delay(500); // Đợi AP khởi động hoàn toàn
    
    Serial.print("📡 AP started. SSID: ");
    Serial.print(AP_SSID);
    Serial.print("  PASS: ");
    Serial.println(AP_PASS);
    Serial.print("AP IP: ");
    Serial.println(WiFi.softAPIP());
    Serial.println("✅ WiFi mode: AP_STA (có thể quét WiFi)");
  }

  // WEB SERVER ROUTES
  server.on("/",         HTTP_GET, handleRoot);
  server.on("/save",     HTTP_POST, handleSaveWifi);
  server.on("/capture",  HTTP_GET, handleCapture);
  server.on("/distance", HTTP_GET, handleDistance);
  server.on("/ai",       HTTP_POST, handleAI);
  server.on("/results",  HTTP_POST, handleResults);  // <-- Endpoint mới cho results
  
  server.begin();
  Serial.println("✅ HTTP Server Started");
}

// ===========================
// LOOP - NHẬN DATA TỪ UART2 + KIỂM TRA WIFI
// ===========================
void loop() {
  server.handleClient();

  // Kiểm tra và đảm bảo AP luôn bật khi ở chế độ config
  if (appMode == MODE_CONFIG) {
    static unsigned long lastAPCheck = 0;
    if (millis() - lastAPCheck > 5000) { // Kiểm tra mỗi 5 giây
      lastAPCheck = millis();
      if (WiFi.getMode() != WIFI_AP_STA && WiFi.getMode() != WIFI_AP) {
        Serial.println("⚠️ AP mode lost, restarting...");
        WiFi.mode(WIFI_AP_STA);
        delay(100);
        WiFi.softAP(AP_SSID, AP_PASS);
        delay(500);
        Serial.print("📡 AP restarted. IP: ");
        Serial.println(WiFi.softAPIP());
      } else if (!WiFi.softAPgetStationNum()) {
        // AP đang chạy nhưng không có client, đảm bảo nó vẫn hoạt động
        IPAddress apIP = WiFi.softAPIP();
        if (apIP.toString() == "0.0.0.0") {
          Serial.println("⚠️ AP IP lost, restarting...");
          WiFi.softAPdisconnect(true);
          delay(200);
          WiFi.softAP(AP_SSID, AP_PASS);
          delay(500);
          Serial.print("📡 AP restarted. IP: ");
          Serial.println(WiFi.softAPIP());
        }
      }
    }
  }

  // Kiểm tra WiFi connection nếu đang ở chế độ normal
  if (appMode == MODE_NORMAL) {
    static unsigned long lastWiFiCheck = 0;
    if (millis() - lastWiFiCheck > 10000) { // Kiểm tra mỗi 10 giây
      lastWiFiCheck = millis();
      if (WiFi.status() != WL_CONNECTED) {
        Serial.println("⚠️ WiFi connection lost, switching to config mode...");
        appMode = MODE_CONFIG;
        WiFi.mode(WIFI_AP_STA);
        delay(100);
        WiFi.softAP(AP_SSID, AP_PASS);
        delay(500);
        Serial.print("📡 AP started. IP: ");
        Serial.println(WiFi.softAPIP());
      }
    }
  }

  // Nhận dữ liệu từ ESP32 (gậy)
  if (SerialESP.available()) {
    String receivedData = SerialESP.readStringUntil('\n');
    receivedData.trim();
    
    if (receivedData.length() > 0) {
      Serial.print("📨 UART2 Raw: ");
      Serial.println(receivedData);
      uartConnected    = true;
      lastSensorUpdate = millis();
      
      if (receivedData.startsWith("SENSORS:")) {
        sensorData = receivedData.substring(8); // sau "SENSORS:"
        Serial.print("✅ Parsed sensorData: ");
        Serial.println(sensorData);
      } else {
        Serial.println("⚠️ Invalid format - expected 'SENSORS:' prefix");
      }
    }
  }

  // TIMEOUT UART (10 giây không nhận data)
  if (uartConnected && millis() - lastSensorUpdate > 10000) {
    uartConnected = false;
    sensorData = "{\"distance_mm\":-1,\"pip\":\"NONE\",\"warning\":0}";
    Serial.println("⚠️ UART timeout - connection lost");
  }

  delay(10);
}


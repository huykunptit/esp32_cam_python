#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <HardwareSerial.h>
#include <Preferences.h>

#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

const char* AP_SSID = "ESP32CAM-Setup";
const char* AP_PASS = "12345678";

Preferences prefs;
String wifiSSID = "";
String wifiPASS = "";

#define RXD2 13
#define TXD2 12
HardwareSerial SerialESP(2);

String sensorData = "{\"distance_mm\":-1,\"pip\":\"NONE\",\"warning\":0}";
unsigned long lastSensorUpdate = 0;
bool uartConnected = false;

// Dữ liệu từ PC qua /results
int pcDistance_mm = -1;
String pcPip = "NONE";
bool pcPipAlert = false;
String pcObjectsJson = "[]";
unsigned long lastPCUpdate = 0;

String aiLabel = "";
float aiConfidence = 0.0;
unsigned long lastAIUpdate = 0;

enum AppMode { MODE_CONFIG, MODE_NORMAL };
AppMode appMode = MODE_CONFIG;

WebServer server(80);

void initCamera() {
  Serial.println("Setting up camera pins...");
  delay(100);
  
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  Serial.print("PSRAM: ");
  if (psramFound()) {
    Serial.println("Found");
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
    config.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    Serial.println("Not found");
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  Serial.println("Initializing camera hardware...");
  delay(200);
  
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("ERROR: Camera init failed with code: 0x%x\n", err);
    Serial.println("Will restart in 5 seconds...");
    delay(5000);
    ESP.restart();
    return;
  }
  Serial.println("OK: Camera initialized successfully");
}

void handleConfigPage() {
  Serial.println("Scanning WiFi...");
  // Đảm bảo ở chế độ AP_STA để có thể quét WiFi
  if (WiFi.getMode() != WIFI_AP_STA) {
    WiFi.mode(WIFI_AP_STA);
    delay(200);
    if (!WiFi.softAP(AP_SSID, AP_PASS)) {
      WiFi.softAP(AP_SSID, AP_PASS);
    }
  }
  
  int n = WiFi.scanNetworks();
  if (n < 0) {
    delay(1000);
    n = WiFi.scanNetworks();
  }
  
  Serial.printf("Found %d networks\n", n);

  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>ESP32-CAM WiFi Setup</title>";
  html += "<style>body{font-family:Arial;background:#222;color:#fff;padding:20px;}";
  html += ".card{background:#fff;color:#333;padding:20px;border-radius:12px;max-width:500px;margin:0 auto;}";
  html += "h1{text-align:center;color:#667eea;}";
  html += "label{display:block;margin-top:15px;font-weight:bold;}";
  html += "select,input{width:100%;padding:10px;margin-top:5px;border-radius:6px;border:1px solid #ccc;box-sizing:border-box;}";
  html += ".btn{margin-top:20px;width:100%;padding:12px;border:none;border-radius:8px;background:#667eea;color:#fff;font-size:16px;cursor:pointer;font-weight:bold;}";
  html += ".btn:hover{background:#5568d3;}";
  html += ".btn-refresh{background:#28a745;width:auto;display:inline-block;padding:8px 15px;margin-left:10px;font-size:14px;}";
  html += ".btn-refresh:hover{background:#218838;}";
  html += ".info{background:#e7f3ff;padding:10px;border-radius:6px;margin-bottom:15px;color:#004085;}";
  html += "</style></head><body>";
  html += "<div class='card'>";
  html += "<h1>📡 ESP32-CAM WiFi Setup</h1>";
  html += "<div class='info'>";
  html += "<strong>Hướng dẫn:</strong><br>";
  html += "1. Kết nối điện thoại vào WiFi <strong>" + String(AP_SSID) + "</strong><br>";
  html += "2. Chọn WiFi từ danh sách bên dưới<br>";
  html += "3. Nhập mật khẩu và nhấn 'Lưu & Kết nối'";
  html += "</div>";
  html += "<form method='POST' action='/save'>";
  html += "<label>Chọn WiFi: <a href='/' class='btn-refresh' onclick='location.reload();return false;'>🔄 Quét lại</a></label>";
  html += "<select name='ssid' required>";
  
  if (n > 0) {
    // Sắp xếp theo signal strength
    int indices[n];
    for (int i = 0; i < n; i++) indices[i] = i;
    for (int i = 0; i < n - 1; i++) {
      for (int j = 0; j < n - i - 1; j++) {
        if (WiFi.RSSI(indices[j]) < WiFi.RSSI(indices[j + 1])) {
          int temp = indices[j];
          indices[j] = indices[j + 1];
          indices[j + 1] = temp;
        }
      }
    }
    
    html += "<option value=''>-- Chọn WiFi --</option>";
    for (int i = 0; i < n; i++) {
      int idx = indices[i];
      String ssid = WiFi.SSID(idx);
      int rssi = WiFi.RSSI(idx);
      String enc = (WiFi.encryptionType(idx) == WIFI_AUTH_OPEN) ? "🔓" : "🔒";
      String selected = (ssid == wifiSSID) ? " selected" : "";
      html += "<option value='" + ssid + "'" + selected + ">" + enc + " " + ssid + " (" + String(rssi) + " dBm)</option>";
    }
  } else {
    html += "<option value=''>Không tìm thấy WiFi. Nhấn Quét lại hoặc nhập thủ công.</option>";
  }
  
  html += "</select>";
  html += "<label>Hoặc nhập tên WiFi thủ công:</label>";
  html += "<input type='text' name='ssid_manual' placeholder='Nhập tên WiFi'>";
  html += "<label>Mật khẩu WiFi:</label>";
  html += "<input type='password' name='pass' placeholder='Nhập mật khẩu (để trống nếu WiFi mở)'>";
  html += "<button class='btn' type='submit'>💾 Lưu & Kết nối</button>";
  html += "</form>";
  
  if (wifiSSID.length() > 0) {
    html += "<div style='margin-top:15px;padding:10px;background:#fff3cd;border-radius:6px;color:#856404;'>";
    html += "<strong>WiFi đã lưu trước:</strong> " + wifiSSID;
    html += "</div>";
  }
  
  html += "</div></body></html>";
  
  server.send(200, "text/html", html);
}

void handleSaveWifi() {
  String ssid = "";
  if (server.hasArg("ssid_manual") && server.arg("ssid_manual").length() > 0) {
    ssid = server.arg("ssid_manual");
  } else if (server.hasArg("ssid")) {
    ssid = server.arg("ssid");
  }
  
  String pass = server.arg("pass");
  
  if (ssid.length() == 0) {
    server.send(400, "text/plain", "Missing SSID");
    return;
  }

  wifiSSID = ssid;
  wifiPASS = pass;

  prefs.putString("ssid", wifiSSID);
  prefs.putString("pass", wifiPASS);
  
  Serial.println("Saving WiFi: " + wifiSSID);

  // Gửi response trước
  server.send(200, "text/html", "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta http-equiv='refresh' content='5;url=/'><title>Đang kết nối...</title></head><body style='font-family:Arial;padding:20px;text-align:center;'><h2>⏳ Đang kết nối WiFi...</h2><p>Vui lòng đợi trong giây lát...</p><p>Trang sẽ tự động chuyển hướng sau 5 giây.</p></body></html>");
  delay(300);
  
  // KHÔNG tắt AP, chỉ thêm STA mode
  WiFi.mode(WIFI_AP_STA);
  delay(200);
  
  // Bắt đầu kết nối WiFi
  WiFi.begin(wifiSSID.c_str(), wifiPASS.c_str());
  
  Serial.print("Connecting to " + wifiSSID);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    appMode = MODE_NORMAL;
    String newIP = WiFi.localIP().toString();
    Serial.println("✅ WiFi connected! IP: " + newIP);
    
    // Đảm bảo AP vẫn chạy
    if (WiFi.getMode() != WIFI_AP_STA) {
      WiFi.mode(WIFI_AP_STA);
      delay(200);
      WiFi.softAP(AP_SSID, AP_PASS);
      delay(500);
    }
    
    Serial.println("✅ AP still running. AP IP: " + WiFi.softAPIP().toString());
    Serial.println("✅ Python can get IP from: http://" + newIP + "/ip");
    Serial.println("✅ Web interface: http://" + newIP);
  } else {
    appMode = MODE_CONFIG;
    Serial.println("❌ WiFi connection failed!");
    // Đảm bảo AP vẫn chạy
    if (WiFi.getMode() != WIFI_AP_STA) {
      WiFi.mode(WIFI_AP_STA);
      delay(200);
      WiFi.softAP(AP_SSID, AP_PASS);
      delay(500);
    }
    Serial.println("✅ AP still running. AP IP: " + WiFi.softAPIP().toString());
  }
  
  // Đảm bảo server vẫn hoạt động
  delay(500);
}

void handleMainPage() {
  String ip = (WiFi.status() == WL_CONNECTED) ? WiFi.localIP().toString() : WiFi.softAPIP().toString();
  
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>ESP32-CAM</title>";
  html += "<style>body{font-family:Arial;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);margin:0;padding:20px;color:white;}";
  html += ".card{background:white;color:#333;padding:20px;margin:10px 0;border-radius:12px;}";
  html += "img{width:100%;max-width:640px;border-radius:8px;border:3px solid #667eea;}";
  html += ".btn{display:inline-block;background:#667eea;color:white;padding:10px 18px;margin:5px;border-radius:8px;text-decoration:none;}</style>";
  html += "</head><body><h1>ESP32-CAM Blind Assistance</h1>";
  html += "<div class='card'><h2>Live Camera</h2>";
  html += "<img src='/capture' id='photo' alt='Camera'>";
  html += "<script>setInterval(function(){document.getElementById('photo').src='/capture?t='+Date.now();},2000);</script></div>";
  html += "<div class='card'><h2>Sensor & AI</h2>";
  html += "<div id='sensorData'>Loading...</div>";
  html += "<div id='alertStatus' style='padding:10px;margin-top:10px;border-radius:8px;display:none;'></div></div>";
  html += "<div class='card'><h2>API</h2>";
  html += "<a href='/capture' class='btn'>/capture</a>";
  html += "<a href='/distance' class='btn'>/distance</a>";
  html += "<a href='/results' class='btn'>/results</a></div>";
  html += "<div class='card'><h2>Network</h2>";
  html += "<p><strong>WiFi IP:</strong> " + ip + "</p>";
  html += "<p><strong>AP IP:</strong> " + WiFi.softAPIP().toString() + "</p>";
  if (WiFi.status() == WL_CONNECTED) {
    html += "<p style='color:green;'><strong>✅ WiFi Connected</strong></p>";
    html += "<p>Python can get IP from: <code>http://" + ip + "/ip</code></p>";
  } else {
    html += "<p style='color:orange;'><strong>⚠️ WiFi Not Connected</strong></p>";
    html += "<p>Please configure WiFi from the setup page.</p>";
  }
  html += "</div>";
  html += "<script>";
  html += "let lastPipAlert = false;";
  html += "let audioContext = null;";
  html += "function playBeep(){";
  html += "  if(!audioContext)audioContext=new(window.AudioContext||window.webkitAudioContext)();";
  html += "  const osc=audioContext.createOscillator();";
  html += "  const gain=audioContext.createGain();";
  html += "  osc.connect(gain);";
  html += "  gain.connect(audioContext.destination);";
  html += "  osc.frequency.value=800;";
  html += "  osc.type='sine';";
  html += "  gain.gain.setValueAtTime(0.3,audioContext.currentTime);";
  html += "  gain.gain.exponentialRampToValueAtTime(0.01,audioContext.currentTime+0.1);";
  html += "  osc.start(audioContext.currentTime);";
  html += "  osc.stop(audioContext.currentTime+0.1);";
  html += "}";
  html += "function updateSensor(){fetch('/distance').then(r=>r.json()).then(d=>{";
  html += "let txt='Distance: '+d.distance_mm+' mm<br>PIP: '+d.pip+'<br>';";
  html += "if(d.pip_alert!==undefined)txt+='PIP Alert: '+(d.pip_alert?'⚠️ YES':'✅ NO')+'<br>';";
  html += "if(d.objects&&d.objects.length>0){txt+='Objects: '+d.objects.length+'<br>';";
  html += "d.objects.forEach((o,i)=>{txt+='- '+o.class+' ('+(o.confidence*100).toFixed(1)+'%)<br>';});}";
  html += "if(d.ai_label)txt+='AI: '+d.ai_label+' ('+(d.ai_confidence*100).toFixed(1)+'%)<br>';";
  html += "if(d.pc_connected)txt+='<span style=\"color:green;\">✅ PC Connected</span><br>';";
  html += "document.getElementById('sensorData').innerHTML=txt;";
  html += "let alertDiv=document.getElementById('alertStatus');";
  html += "if(d.pip_alert===true){";
  html += "  alertDiv.style.display='block';";
  html += "  alertDiv.style.background='#f8d7da';";
  html += "  alertDiv.style.color='#721c24';";
  html += "  alertDiv.innerHTML='⚠️ PIP ALERT! Cảnh báo nguy hiểm!';";
  html += "  if(!lastPipAlert){playBeep();lastPipAlert=true;}";
  html += "}else{";
  html += "  if(lastPipAlert){alertDiv.style.display='none';lastPipAlert=false;}";
  html += "}";
  html += "}).catch(e=>console.error(e));}";
  html += "updateSensor();setInterval(updateSensor,500);";
  html += "</script></body></html>";
  
  server.send(200, "text/html", html);
}

void handleRoot() {
  // Kiểm tra lại mode trước khi xử lý
  if (WiFi.status() == WL_CONNECTED && appMode == MODE_NORMAL) {
    handleMainPage();
  } else {
    // Nếu WiFi chưa kết nối, chuyển về config mode
    if (appMode == MODE_NORMAL) {
      appMode = MODE_CONFIG;
    }
    handleConfigPage();
  }
}

void handleCapture() {
  // Cho phép capture trong mọi mode để test
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "0");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

void handleDistance() {
  StaticJsonDocument<512> doc;
  
  // Ưu tiên dữ liệu từ PC (mới nhất)
  if (millis() - lastPCUpdate < 5000) { // Dữ liệu PC còn mới (< 5 giây)
    doc["distance_mm"] = pcDistance_mm;
    doc["pip"] = pcPip;
    doc["pip_alert"] = pcPipAlert;
    // Parse objects từ JSON string
    StaticJsonDocument<1024> objDoc;
    if (deserializeJson(objDoc, pcObjectsJson) == DeserializationError::Ok) {
      doc["objects"] = objDoc["objects"];
    } else {
      doc["objects"] = JsonArray();
    }
  } else if (sensorData.length() > 10) {
    // Dùng dữ liệu từ UART nếu không có từ PC
    StaticJsonDocument<256> sensorDoc;
    if (deserializeJson(sensorDoc, sensorData) == DeserializationError::Ok) {
      doc["distance_mm"] = sensorDoc["distance_mm"].as<int>();
      doc["pip"] = sensorDoc["pip"].as<String>();
      doc["pip_alert"] = false;
      doc["front_cm"] = sensorDoc["front_cm"].as<int>();
      doc["left_cm"] = sensorDoc["left_cm"].as<int>();
      doc["right_cm"] = sensorDoc["right_cm"].as<int>();
      doc["warning"] = sensorDoc["warning"].as<int>();
    }
  } else {
    doc["distance_mm"] = -1;
    doc["pip"] = "NONE";
    doc["pip_alert"] = false;
  }
  
  doc["ai_label"] = aiLabel;
  doc["ai_confidence"] = aiConfidence;
  doc["uart_connected"] = uartConnected;
  doc["pc_connected"] = (millis() - lastPCUpdate < 5000);
  doc["ip"] = (WiFi.status() == WL_CONNECTED) ? WiFi.localIP().toString() : WiFi.softAPIP().toString();
  doc["ap_ip"] = WiFi.softAPIP().toString();
  
  String response;
  serializeJson(doc, response);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", response);
}

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
  if (deserializeJson(doc, body) != DeserializationError::Ok) {
    server.send(400, "text/plain", "Invalid JSON");
    return;
  }

  aiLabel = doc["label"] | "";
  aiConfidence = doc["confidence"] | 0.0;
  lastAIUpdate = millis();

  Serial.println("AI: " + aiLabel + " (" + String(aiConfidence, 2) + ")");
  server.send(200, "text/plain", "OK");
}

void handleResults() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Use POST");
    return;
  }
  
  String body = server.arg("plain");
  StaticJsonDocument<2048> doc;
  DeserializationError err = deserializeJson(doc, body);
  
  if (err == DeserializationError::Ok) {
    // Lưu dữ liệu từ PC
    pcDistance_mm = doc["distance_mm"] | -1;
    pcPip = doc["pip"] | "NONE";
    pcPipAlert = doc["pip_alert"] | false;
    lastPCUpdate = millis();
    
    // Lưu objects
    if (doc.containsKey("objects")) {
      JsonArray objects = doc["objects"];
      StaticJsonDocument<1024> objDoc;
      objDoc["objects"] = objects;
      serializeJson(objDoc, pcObjectsJson);
      Serial.println("Received from PC: distance=" + String(pcDistance_mm) + "mm, pip=" + pcPip + ", alert=" + String(pcPipAlert ? "true" : "false") + ", objects=" + String(objects.size()));
    } else {
      pcObjectsJson = "[]";
      Serial.println("Received from PC: distance=" + String(pcDistance_mm) + "mm, pip=" + pcPip + ", alert=" + String(pcPipAlert ? "true" : "false"));
    }
    
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", "{\"status\":\"ok\"}");
  } else {
    Serial.println("JSON parse error: " + String(err.c_str()));
    server.send(400, "text/plain", "Invalid JSON: " + String(err.c_str()));
  }
}

// Endpoint để Python lấy IP hiện tại của ESP32-CAM
void handleGetIP() {
  StaticJsonDocument<256> doc;
  
  if (WiFi.status() == WL_CONNECTED) {
    doc["status"] = "connected";
    doc["ip"] = WiFi.localIP().toString();
    doc["ssid"] = WiFi.SSID();
    doc["rssi"] = WiFi.RSSI();
  } else {
    doc["status"] = "not_connected";
    doc["ip"] = "";
    doc["ssid"] = "";
  }
  
  doc["ap_ip"] = WiFi.softAPIP().toString();
  doc["ap_ssid"] = AP_SSID;
  doc["mode"] = (appMode == MODE_NORMAL) ? "normal" : "config";
  
  String response;
  serializeJson(doc, response);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", response);
}

void setup() {
  // Khởi tạo Serial với delay đủ lâu
  Serial.begin(115200);
  delay(2000);  // Tăng delay để Serial ổn định
  Serial.println();
  Serial.println("=================================");
  Serial.println("ESP32-CAM Starting...");
  Serial.println("=================================");
  delay(500);

  // Khởi tạo UART2
  SerialESP.begin(115200, SERIAL_8N1, RXD2, TXD2);
  delay(100);
  Serial.println("UART2 initialized");

  // Khởi tạo Camera với xử lý lỗi tốt hơn
  Serial.println("Initializing camera...");
  delay(500);
  initCamera();
  delay(500);

  // Đọc WiFi đã lưu
  Serial.println("Reading saved WiFi credentials...");
  prefs.begin("wifi", false);
  wifiSSID = prefs.getString("ssid", "");
  wifiPASS = prefs.getString("pass", "");
  prefs.end();
  delay(200);
  
  if (wifiSSID.length() > 0) {
    Serial.println("Found saved WiFi: " + wifiSSID);
  } else {
    Serial.println("No saved WiFi found");
  }

  // LUÔN BẬT AP ĐẦU TIÊN để điện thoại có thể kết nối
  Serial.println("Starting WiFi AP...");
  WiFi.mode(WIFI_AP_STA);
  delay(500);
  
  if (!WiFi.softAP(AP_SSID, AP_PASS)) {
    Serial.println("ERROR: Failed to start AP, retrying...");
    delay(1000);
    WiFi.softAP(AP_SSID, AP_PASS);
  }
  
  delay(1000);
  IPAddress apIP = WiFi.softAPIP();
  Serial.println("OK: AP started");
  Serial.println("  SSID: " + String(AP_SSID));
  Serial.println("  Password: " + String(AP_PASS));
  Serial.println("  IP: " + apIP.toString());

  // KHÔNG tự động kết nối WiFi - luôn ở chế độ config để người dùng chọn
  appMode = MODE_CONFIG;
  Serial.println("=================================");
  Serial.println("Mode: CONFIG (waiting for user)");
  Serial.println("Connect to WiFi: " + String(AP_SSID));
  Serial.println("Then open: http://" + apIP.toString());
  Serial.println("=================================");

  // Setup routes
  Serial.println("Setting up HTTP routes...");
  server.on("/", HTTP_GET, handleRoot);
  server.on("/save", HTTP_POST, handleSaveWifi);
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/distance", HTTP_GET, handleDistance);
  server.on("/ai", HTTP_POST, handleAI);
  server.on("/results", HTTP_POST, handleResults);
  server.on("/ip", HTTP_GET, handleGetIP);
  
  server.begin();
  delay(200);
  Serial.println("OK: HTTP Server Started");
  Serial.println("Ready!");
  Serial.println();
}

void loop() {
  server.handleClient();

  if (SerialESP.available()) {
    String data = SerialESP.readStringUntil('\n');
    data.trim();
    if (data.length() > 0) {
      Serial.println("UART: " + data);
      uartConnected = true;
      lastSensorUpdate = millis();
      if (data.startsWith("SENSORS:")) {
        sensorData = data.substring(8);
        Serial.println("Sensor: " + sensorData);
      }
    }
  }

  if (uartConnected && millis() - lastSensorUpdate > 10000) {
    uartConnected = false;
    sensorData = "{\"distance_mm\":-1,\"pip\":\"NONE\",\"warning\":0}";
  }

  delay(10);
}


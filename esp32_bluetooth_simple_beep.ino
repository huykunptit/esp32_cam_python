#include "BluetoothA2DPSource.h"

BluetoothA2DPSource a2dp_source;

// Cấu hình beep
const float beep_freq = 800.0;        // Tần số beep (Hz)
const int sample_rate = 44100;        // Sample rate
unsigned long last_beep = 0;
const unsigned long beep_interval = 2000;  // 2 giây giữa mỗi lần beep
bool is_playing = false;
int beep_count = 0;

// Buffer audio
int16_t* audio_buffer = NULL;
int audio_buffer_size = 0;

// Hàm tạo dữ liệu âm thanh beep
int32_t get_audio_data_frame(uint8_t *data, int32_t len) {
  int16_t *samples = (int16_t *)data;
  int sample_count = len / 2;  // 16-bit = 2 bytes per sample
  
  static float phase = 0.0;
  static int beep_samples_remaining = 0;
  
  // Nếu chưa đến lúc beep
  if (!is_playing && (millis() - last_beep) < beep_interval) {
    // Tạo silence
    for (int i = 0; i < sample_count; i++) {
      samples[i] = 0;
    }
    return len;
  }
  
  // Bắt đầu beep mới
  if (!is_playing && (millis() - last_beep) >= beep_interval) {
    is_playing = true;
    beep_samples_remaining = (int)(sample_rate * 0.2);  // 200ms beep
    phase = 0.0;
    beep_count++;
    Serial.printf("Beep %d\n", beep_count);
    
    // Sau 2 beeps, reset
    if (beep_count >= 2) {
      beep_count = 0;
      last_beep = millis();
    }
  }
  
  // Tạo beep sound
  if (is_playing && beep_samples_remaining > 0) {
    for (int i = 0; i < sample_count; i++) {
      // Sine wave
      float amplitude = sin(phase) * 8000.0;
      
      // Fade in/out để tránh click
      float fade = 1.0;
      int remaining = beep_samples_remaining - (sample_count - i);
      if (remaining < sample_rate * 0.01) {  // Fade out cuối
        fade = remaining / (sample_rate * 0.01);
      } else if (remaining > beep_samples_remaining - sample_rate * 0.01) {  // Fade in đầu
        fade = (beep_samples_remaining - remaining) / (sample_rate * 0.01);
      }
      
      samples[i] = (int16_t)(amplitude * fade);
      
      phase += 2.0 * PI * beep_freq / sample_rate;
      if (phase > 2.0 * PI) {
        phase -= 2.0 * PI;
      }
      
      beep_samples_remaining--;
      
      if (beep_samples_remaining <= 0) {
        is_playing = false;
        // Điền silence cho phần còn lại
        for (int j = i + 1; j < sample_count; j++) {
          samples[j] = 0;
        }
        break;
      }
    }
  } else {
    // Silence
    for (int i = 0; i < sample_count; i++) {
      samples[i] = 0;
    }
  }
  
  return len;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n===================================");
  Serial.println("ESP32 Bluetooth A2DP Beep Generator");
  Serial.println("===================================\n");
  
  // Khởi động A2DP Source
  a2dp_source.start("ESP32_Beep_Device", get_audio_data_frame);
  
  Serial.println("[OK] Bluetooth A2DP Source đã khởi động!");
  Serial.println("[INFO] Tên thiết bị: ESP32_Beep_Device");
  Serial.println("[INFO] Kết nối thiết bị này từ điện thoại/loa Bluetooth");
  Serial.println("[INFO] Sẽ phát 'pip pip' mỗi 2 giây\n");
  
  last_beep = millis();
}

void loop() {
  delay(100);
  
  // Kiểm tra trạng thái kết nối
  static unsigned long last_status = 0;
  if (millis() - last_status > 5000) {
    if (a2dp_source.is_connected()) {
      Serial.println("[OK] Đã kết nối - Đang phát beep...");
    } else {
      Serial.println("[INFO] Chờ kết nối Bluetooth...");
    }
    last_status = millis();
  }
}


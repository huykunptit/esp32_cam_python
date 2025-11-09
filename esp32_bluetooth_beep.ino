#include "BluetoothA2DPSink.h"

BluetoothA2DPSink a2dp_sink;

// Cấu hình âm thanh
const int sample_rate = 44100;
const int channels = 2;  // Stereo
const int bit_depth = 16;

// Biến để tạo beep
bool is_beeping = false;
unsigned long beep_start_time = 0;
unsigned long beep_duration = 200;  // Thời gian mỗi beep (ms)
unsigned long beep_interval = 500;   // Khoảng cách giữa các beep (ms)
unsigned long last_beep_time = 0;
int beep_count = 0;
const int total_beeps = 2;  // Số lượng beep (pip pip = 2 beeps)

// Tần số beep (Hz) - 800Hz cho âm pip
const float beep_frequency = 800.0;

// Buffer để chứa âm thanh
int16_t audio_buffer[512];

// Hàm callback để tạo dữ liệu âm thanh
int32_t get_data_stream(Channels* data, int32_t len) {
  // Tính toán thời gian hiện tại
  unsigned long current_time = millis();
  
  // Tạo dữ liệu âm thanh
  for (int i = 0; i < len; i++) {
    int16_t sample = 0;
    
    // Kiểm tra xem có đang trong thời gian beep không
    if (is_beeping && (current_time - beep_start_time) < beep_duration) {
      // Tạo sine wave cho beep
      float t = (float)(i + (current_time - beep_start_time) * sample_rate / 1000) / sample_rate;
      sample = (int16_t)(sin(2.0 * PI * beep_frequency * t) * 8000);  // Amplitude
      
      // Fade in/out để tránh click
      float fade = 1.0;
      unsigned long beep_elapsed = current_time - beep_start_time;
      if (beep_elapsed < 10) {
        fade = beep_elapsed / 10.0;  // Fade in
      } else if (beep_elapsed > beep_duration - 10) {
        fade = (beep_duration - beep_elapsed) / 10.0;  // Fade out
      }
      sample = (int16_t)(sample * fade);
    }
    
    // Ghi vào cả 2 kênh (stereo)
    data[i].channel1 = sample;
    data[i].channel2 = sample;
  }
  
  // Kiểm tra xem đã hết beep chưa
  if (is_beeping && (current_time - beep_start_time) >= beep_duration) {
    is_beeping = false;
    last_beep_time = current_time;
    beep_count++;
    
    // Nếu chưa đủ số beep, chuẩn bị beep tiếp theo
    if (beep_count < total_beeps) {
      // Sẽ bắt đầu beep tiếp theo sau interval
    } else {
      // Đã phát xong tất cả beep
      beep_count = 0;
    }
  }
  
  // Kiểm tra xem có cần bắt đầu beep tiếp theo không
  if (!is_beeping && beep_count > 0 && beep_count < total_beeps) {
    if ((current_time - last_beep_time) >= beep_interval) {
      is_beeping = true;
      beep_start_time = current_time;
    }
  }
  
  return len;
}

void setup() {
  Serial.begin(115200);
  Serial.println("\nESP32 Bluetooth A2DP Beep Generator");
  Serial.println("====================================");
  
  // Cấu hình A2DP Sink
  i2s_pin_config_t pin_config = {
    .bck_io_num = 26,      // I2S bit clock
    .ws_io_num = 25,       // I2S word select
    .data_out_num = 22,    // I2S data out (không dùng cho A2DP Source)
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  
  // Khởi động A2DP Sink
  a2dp_sink.set_pin_config(pin_config);
  a2dp_sink.set_stream_reader(get_data_stream);
  a2dp_sink.start("ESP32_Beep_Device");  // Tên thiết bị Bluetooth
  
  Serial.println("Bluetooth A2DP đã khởi động!");
  Serial.println("Tên thiết bị: ESP32_Beep_Device");
  Serial.println("Đang chờ kết nối từ thiết bị khác...");
  Serial.println("\nSẽ phát 'pip pip' liên tục mỗi 2 giây");
  
  // Bắt đầu beep đầu tiên
  is_beeping = true;
  beep_start_time = millis();
  beep_count = 0;
}

void loop() {
  // Kiểm tra kết nối Bluetooth
  if (a2dp_sink.is_connected()) {
    // Kiểm tra xem cần bắt đầu chuỗi beep mới không
    unsigned long current_time = millis();
    
    // Nếu đã phát xong tất cả beep và đã qua 2 giây, bắt đầu lại
    if (!is_beeping && beep_count == 0) {
      static unsigned long last_cycle_time = 0;
      if ((current_time - last_cycle_time) >= 2000) {  // 2 giây
        is_beeping = true;
        beep_start_time = current_time;
        beep_count = 0;
        last_cycle_time = current_time;
        Serial.println("Pip pip!");
      }
    }
  } else {
    // Chưa có kết nối
    static unsigned long last_check = 0;
    if (millis() - last_check > 3000) {
      Serial.println("Đang chờ kết nối Bluetooth...");
      last_check = millis();
    }
  }
  
  delay(10);
}

// Hàm callback khi có thiết bị kết nối
void audio_state_changed(esp_a2d_connection_state_t state, void *ptr) {
  if (state == ESP_A2D_CONNECTION_STATE_CONNECTED) {
    Serial.println("\n[OK] Đã kết nối Bluetooth!");
  } else if (state == ESP_A2D_CONNECTION_STATE_DISCONNECTED) {
    Serial.println("\n[INFO] Đã ngắt kết nối Bluetooth");
  }
}


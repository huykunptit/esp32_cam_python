# ESP32 Bluetooth Beep Generator

Code để ESP32 phát tín hiệu "pip pip" qua Bluetooth A2DP.

## Yêu cầu

### Phần cứng:
- ESP32 (ESP32 DevKit, ESP32-WROOM, v.v.)
- Loa Bluetooth hoặc điện thoại để nhận âm thanh

### Phần mềm:
- Arduino IDE hoặc PlatformIO
- Thư viện: **ESP32-audioI2S** hoặc **BluetoothA2DPSource**

## Cài đặt thư viện

### Cách 1: Arduino IDE Library Manager
1. Mở Arduino IDE
2. Vào `Sketch` → `Include Library` → `Manage Libraries`
3. Tìm: **ESP32-audioI2S** hoặc **BluetoothA2DPSource**
4. Cài đặt

### Cách 2: GitHub
```bash
# Clone repository
git clone https://github.com/pschatzmann/ESP32-audioI2S.git
# Hoặc download ZIP và cài đặt trong Arduino IDE
```

## Cấu hình ESP32

1. Mở file `esp32_bluetooth_simple_beep.ino` trong Arduino IDE
2. Chọn board: `Tools` → `Board` → `ESP32 Arduino` → `ESP32 Dev Module`
3. Chọn Port: `Tools` → `Port` → Chọn port COM của ESP32
4. Upload code

## Sử dụng

1. Upload code lên ESP32
2. Mở Serial Monitor (115200 baud) để xem log
3. Trên điện thoại/loa Bluetooth:
   - Vào Settings → Bluetooth
   - Tìm thiết bị tên: **ESP32_Beep_Device**
   - Kết nối
4. ESP32 sẽ tự động phát "pip pip" mỗi 2 giây

## Tùy chỉnh

Trong file `.ino`, bạn có thể thay đổi:

```cpp
const float beep_freq = 800.0;              // Tần số beep (Hz)
const unsigned long beep_interval = 2000;  // Khoảng cách giữa các beep (ms)
```

- **beep_freq**: Tần số âm thanh (400-2000 Hz)
- **beep_interval**: Thời gian giữa mỗi chuỗi beep (ms)

## Giải thích code

### `esp32_bluetooth_simple_beep.ino` (Khuyến nghị)
- Đơn giản, dễ hiểu
- Phát beep liên tục qua Bluetooth
- Sử dụng `BluetoothA2DPSource`

### `esp32_bluetooth_beep.ino` (Nâng cao)
- Nhiều tính năng hơn
- Có fade in/out
- Cấu hình chi tiết hơn

## Xử lý lỗi

### Không nghe được âm thanh:
1. Kiểm tra đã kết nối Bluetooth chưa
2. Kiểm tra Serial Monitor để xem log
3. Đảm bảo thiết bị nhận (loa/điện thoại) hỗ trợ A2DP

### ESP32 không compile:
1. Kiểm tra đã cài đúng board ESP32 chưa
2. Kiểm tra đã cài thư viện chưa
3. Xem lỗi trong Serial Monitor

## Mở rộng

Bạn có thể mở rộng để:
- Phát âm thanh từ file MP3
- Điều khiển bằng nút nhấn
- Phát theo pattern khác nhau
- Kết nối với cảm biến để phát cảnh báo

## Tham khảo

- [ESP32-audioI2S GitHub](https://github.com/pschatzmann/ESP32-audioI2S)
- [ESP32 Bluetooth A2DP Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_a2dp.html)


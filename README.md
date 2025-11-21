# ESP32-CAM Object Detection với Python

Chương trình Python để nhận diện người và đồ vật từ ESP32-CAM qua web server.

## Yêu cầu

- ESP32-CAM đã được cài đặt và chạy web server
- Python 3.7+
- Kết nối mạng giữa máy tính và ESP32-CAM

## Cài đặt

1. Cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt
```

## Sử dụng

### 🎯 Nhận diện kết hợp (Khuyến nghị)

Detector kết hợp cả người và đồ vật:

```bash
python esp32_combined_detector.py
```

**Tính năng:**
- ✅ Nhận diện người và mặt
- ✅ Nhận diện đồ vật (xe, đồng hồ, mắt, nụ cười...)
- ✅ Smoothing để giảm nhiễu
- ✅ Hiển thị thống kê chi tiết
- ✅ Chuyển đổi hiển thị chi tiết

### 🚗 Nhận diện đồ vật nâng cao

Sử dụng MobileNet SSD để nhận diện 80+ loại đồ vật:

```bash
python esp32_object_detector.py
```

**Tính năng:**
- ✅ Nhận diện 80+ loại đồ vật
- ✅ Chế độ Advanced (MobileNet SSD) và Simple (Haar Cascade)
- ✅ Tự động tải model files
- ✅ Hiển thị confidence score
- ✅ Top objects được nhận diện

### 📱 Nhận diện đồ vật đơn giản

Sử dụng Haar Cascade có sẵn:

```bash
python esp32_simple_object_detector.py
```

**Tính năng:**
- ✅ Nhận diện xe, đồng hồ, mắt (đã tối ưu tham số)
- ✅ Không cần tải model lớn
- ✅ Chạy nhanh và nhẹ
- ✅ Thống kê chi tiết

### 🧠 Nhận diện đồ vật thông minh

Detector với logic lọc false positive:

```bash
python esp32_smart_object_detector.py
```

**Tính năng:**
- ✅ Logic lọc thông minh để giảm false positive
- ✅ Confidence scoring dựa trên kích thước và vị trí
- ✅ Smoothing với lịch sử detection
- ✅ Điều chỉnh confidence threshold
- ✅ Loại bỏ smile cascade (quá nhạy)

### 👥 Nhận diện người tối ưu

Detector được tối ưu hóa đặc biệt cho ESP32-CAM:

```bash
python esp32_optimized_detector.py
```

**Tính năng:**
- ✅ Tối ưu hóa cho ESP32-CAM lag
- ✅ Logic thông minh: đếm người từ faces
- ✅ Loại bỏ detections trùng lặp
- ✅ Smoothing để giảm nhiễu
- ✅ Hiển thị FPS và thống kê

### 🔧 Phiên bản cải tiến

Phiên bản đã được cải tiến với nhiều tính năng:

```bash
python esp32_simple_detector.py
```

**Tính năng:**
- ✅ Nhận diện mặt frontal và profile
- ✅ Logic ước tính người từ faces
- ✅ Loại bỏ faces trùng lặp
- ✅ Thống kê chi tiết

### 🚀 Phiên bản nâng cao

Sử dụng MobileNet SSD để nhận diện nhiều loại đồ vật:

```bash
python esp32_detector.py
```

**Tính năng:**
- Nhận diện 80+ loại đồ vật (người, xe, động vật, đồ dùng...)
- Độ chính xác cao hơn
- Cần tải model files (~10MB)
- Hiển thị confidence score

## Điều khiển

### Nhận diện kết hợp:
- **'q'**: Thoát chương trình
- **'s'**: Chụp ảnh
- **'r'**: Reset thống kê
- **'t'**: Chuyển đổi hiển thị chi tiết

### Nhận diện đồ vật nâng cao:
- **'q'**: Thoát chương trình
- **'s'**: Chụp ảnh
- **'r'**: Reset thống kê
- **'m'**: Chuyển đổi chế độ (Advanced/Simple)

### Nhận diện đồ vật đơn giản:
- **'q'**: Thoát chương trình
- **'s'**: Chụp ảnh
- **'r'**: Reset thống kê
- **'i'**: Thông tin cascade

### Nhận diện đồ vật thông minh:
- **'q'**: Thoát chương trình
- **'s'**: Chụp ảnh
- **'r'**: Reset thống kê
- **'c'**: Thay đổi confidence threshold
- **'i'**: Thông tin cascade

### Nhận diện người tối ưu:
- **'q'**: Thoát chương trình
- **'s'**: Chụp ảnh
- **'r'**: Reset thống kê
- **'i'**: Thông tin chi tiết

### Phiên bản cải tiến:
- **'q'**: Thoát chương trình
- **'s'**: Chụp ảnh
- **'r'**: Reset thống kê

### Phiên bản nâng cao:
- **'q'**: Thoát chương trình

## Cấu hình

Thay đổi IP của ESP32-CAM trong file:

```python
detector = ESP32CamDetector("192.168.1.14")  # Thay IP của bạn
```

## Xử lý lỗi

### Lỗi kết nối ESP32-CAM
- Kiểm tra IP address của ESP32-CAM
- Đảm bảo ESP32-CAM và máy tính cùng mạng
- Kiểm tra web server ESP32-CAM hoạt động tại `http://IP/capture`

### Lỗi tải model files
- Kiểm tra kết nối internet
- Model files sẽ được tải tự động lần đầu chạy

## Cấu trúc file

```
├── esp32_combined_detector.py      # Nhận diện kết hợp (khuyến nghị)
├── esp32_object_detector.py        # Nhận diện đồ vật nâng cao
├── esp32_simple_object_detector.py # Nhận diện đồ vật đơn giản
├── esp32_smart_object_detector.py  # Nhận diện đồ vật thông minh
├── esp32_optimized_detector.py     # Nhận diện người tối ưu
├── esp32_simple_detector.py        # Phiên bản cải tiến
├── esp32_detector.py               # Phiên bản nâng cao với MobileNet SSD
├── requirements.txt                 # Dependencies
└── README.md                        # Hướng dẫn này
```

## Cải tiến cho ESP32-CAM

### Vấn đề đã giải quyết:
- ✅ **Lag và chậm**: Giảm timeout, resize frame, tối ưu tham số
- ✅ **Faces nhưng People = 0**: Logic thông minh ước tính người từ mặt
- ✅ **Detections trùng lặp**: Thuật toán IoU để loại bỏ trùng lặp
- ✅ **Nhiễu**: Smoothing với buffer để ổn định kết quả
- ✅ **Hiệu suất**: Giảm kích thước frame, tối ưu cascade parameters

## Lưu ý

- ESP32-CAM cần có endpoint `/capture` để chụp ảnh
- Chương trình sẽ tự động tải model files nếu chưa có
- Khuyến nghị sử dụng phiên bản đơn giản cho bắt đầu

# Hướng dẫn tải Model Files cho MobileNet SSD

Chương trình cần 2 file model để hoạt động:

1. **MobileNetSSD_deploy.prototxt** - File cấu hình
2. **MobileNetSSD_deploy.caffemodel** - File model (~23MB)

## Cách tải thủ công:

### Cách 1: Từ GitHub (Khuyến nghị)

1. Truy cập: https://github.com/chuanqi305/MobileNet-SSD
2. Download repository hoặc:
   - Vào thư mục `examples/MobileNetSSD_deploy.prototxt`
   - Vào thư mục `MobileNetSSD_deploy.caffemodel` (hoặc tìm trong Releases)

### Cách 2: Direct Download Links

**File prototxt:**
```
https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/examples/MobileNetSSD_deploy.prototxt
```

**File caffemodel:**
- Tìm trong Releases của repo trên
- Hoặc: https://drive.google.com/file/d/0B3gersZ2c1xRakFZSmQwSUpmbEE/view

### Cách 3: Sử dụng wget hoặc curl (Windows PowerShell)

```powershell
# Tải prototxt
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/examples/MobileNetSSD_deploy.prototxt" -OutFile "MobileNetSSD_deploy.prototxt"

# Tải caffemodel (cần tìm link đúng)
# Tìm trong Releases hoặc dùng link Google Drive ở trên
```

### Cách 4: Tìm trên Google

Tìm kiếm: "MobileNetSSD_deploy.caffemodel download"
Hoặc: "MobileNetSSD_deploy.prototxt download"

## Sau khi tải xong:

Đặt 2 file này vào cùng thư mục với `esp32_optimized_detector.py`:
```
d:\python_esp32cam\
├── esp32_optimized_detector.py
├── MobileNetSSD_deploy.prototxt  ← Đặt file này ở đây
└── MobileNetSSD_deploy.caffemodel ← Đặt file này ở đây
```

## Kiểm tra:

Sau khi tải xong, chạy lại chương trình:
```bash
python esp32_optimized_detector.py
```

Nếu có cả 2 file, chương trình sẽ chạy ngay!


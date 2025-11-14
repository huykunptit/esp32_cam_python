# -*- coding: utf-8 -*-
import sys
import os
# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import cv2
import numpy as np
import urllib.request

# Cấu hình ESP32-CAM
ESP32_CAM_IP = "10.13.20.248"  # Thay đổi IP của bạn
# Các endpoint có thể thử
ESP32_CAM_ENDPOINTS = ["/capture", "/cam-hi.jpg", "/cam-lo.jpg", "/stream", "/jpg"]

# Khởi tạo model MobileNet-SSD
prototxt = "MobileNetSSD_deploy.prototxt"
model = "MobileNetSSD_deploy.caffemodel"

# Thư mục MobileNet-SSD đã tải về
MOBILENET_SSD_DIR = "MobileNet-SSD-master"

def copy_from_local_directory():
    """Copy file từ thư mục MobileNet-SSD-master nếu có"""
    copied = False
    
    # Kiểm tra thư mục có tồn tại không
    if not os.path.exists(MOBILENET_SSD_DIR):
        return False
    
    import shutil
    
    # Copy prototxt file (từ deploy.prototxt -> MobileNetSSD_deploy.prototxt)
    local_prototxt = os.path.join(MOBILENET_SSD_DIR, "deploy.prototxt")
    if os.path.exists(local_prototxt) and not os.path.exists(prototxt):
        shutil.copy(local_prototxt, prototxt)
        print(f"[OK] Đã copy {prototxt} từ {MOBILENET_SSD_DIR}/deploy.prototxt")
        copied = True
    
    # Copy caffemodel file (từ mobilenet_iter_73000.caffemodel -> MobileNetSSD_deploy.caffemodel)
    local_model = os.path.join(MOBILENET_SSD_DIR, "mobilenet_iter_73000.caffemodel")
    if os.path.exists(local_model) and not os.path.exists(model):
        shutil.copy(local_model, model)
        print(f"[OK] Đã copy {model} từ {MOBILENET_SSD_DIR}/mobilenet_iter_73000.caffemodel")
        copied = True
    
    # Hoặc tìm file deploy caffemodel trong thư mục (nếu có)
    local_deploy_model = os.path.join(MOBILENET_SSD_DIR, "MobileNetSSD_deploy.caffemodel")
    if os.path.exists(local_deploy_model) and not os.path.exists(model):
        shutil.copy(local_deploy_model, model)
        print(f"[OK] Đã copy {model} từ {MOBILENET_SSD_DIR}")
        copied = True
    
    return copied

# Tải model files nếu chưa có
def download_model_files():
    """Tải model files nếu chưa tồn tại"""
    # URL từ GitHub repository chính thức: https://github.com/chuanqi305/MobileNet-SSD
    # Tên file trong repo: deploy.prototxt (không phải MobileNetSSD_deploy.prototxt)
    prototxt_urls = [
        "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt",
        "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/template/MobileNetSSD_deploy.prototxt"
    ]
    
    # Deploy weights từ README của repo: 
    # https://drive.google.com/file/d/0B3gersZ2cHIxRm5PMWRoTkdHdHc/view
    model_urls = [
        "https://drive.google.com/uc?export=download&id=0B3gersZ2cHIxRm5PMWRoTkdHdHc",
        "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel"
    ]
    
    # Tải prototxt
    if not os.path.exists(prototxt):
        print(f"[INFO] Đang tải {prototxt}...")
        success = False
        for url in prototxt_urls:
            try:
                # Tải file (có thể là deploy.prototxt)
                temp_file = "deploy.prototxt" if "deploy.prototxt" in url else prototxt
                urllib.request.urlretrieve(url, temp_file)
                
                # Nếu tải được deploy.prototxt, đổi tên thành MobileNetSSD_deploy.prototxt
                if temp_file != prototxt and os.path.exists(temp_file):
                    if os.path.exists(prototxt):
                        os.remove(prototxt)
                    os.rename(temp_file, prototxt)
                
                print(f"[OK] Đã tải {prototxt}")
                success = True
                break
            except Exception as e:
                print(f"[WARNING] Không thể tải từ {url}: {e}")
        
        if not success:
            print(f"[ERROR] Không thể tải {prototxt} từ bất kỳ nguồn nào")
            print("[INFO] Vui lòng tải thủ công từ:")
            print("  - https://github.com/chuanqi305/MobileNet-SSD (file: deploy.prototxt)")
            return False
    
    # Tải caffemodel
    if not os.path.exists(model):
        print(f"[INFO] Đang tải {model} (khoảng 23MB, có thể mất vài phút)...")
        success = False
        for url in model_urls:
            try:
                # Tải file (có thể là mobilenet_iter_73000.caffemodel)
                temp_file = "mobilenet_iter_73000.caffemodel" if "mobilenet_iter" in url else model
                urllib.request.urlretrieve(url, temp_file)
                
                # Nếu tải được mobilenet_iter_73000.caffemodel, đổi tên
                if temp_file != model and os.path.exists(temp_file):
                    if os.path.exists(model):
                        os.remove(model)
                    os.rename(temp_file, model)
                
                print(f"[OK] Đã tải {model}")
                success = True
                break
            except Exception as e:
                print(f"[WARNING] Không thể tải từ {url}: {e}")
        
        if not success:
            print(f"[ERROR] Không thể tải {model} từ bất kỳ nguồn nào")
            print("[INFO] Vui lòng tải thủ công từ:")
            print("  - Google Drive: https://drive.google.com/file/d/0B3gersZ2cHIxRm5PMWRoTkdHdHc/view")
            print("  - Hoặc: https://github.com/chuanqi305/MobileNet-SSD")
            return False
    
    return True

# Kiểm tra và tải model files
# Ưu tiên copy từ thư mục local trước
if not os.path.exists(prototxt) or not os.path.exists(model):
    print("[INFO] Đang tìm model files...")
    
    # Thử copy từ thư mục local trước
    if copy_from_local_directory():
        print("[OK] Đã tìm thấy và copy file từ thư mục local!")
    else:
        # Nếu không có trong local, tải từ internet
        print("[INFO] Không tìm thấy trong thư mục local, đang tải từ internet...")
        if not download_model_files():
            print("\n[ERROR] Không thể tải model files tự động.")
            print("[INFO] Vui lòng tải thủ công theo hướng dẫn trong file: HUONG_DAN_TAI_MODEL.md")
            print(f"[INFO] Hoặc đặt thư mục {MOBILENET_SSD_DIR} vào cùng thư mục với script này.")
            exit(1)

print("[INFO] Đang tải model...")
net = cv2.dnn.readNetFromCaffe(prototxt, model)
print("[OK] Model đã sẵn sàng!")

# Các class mà MobileNet-SSD có thể nhận diện
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

# Màu sắc ngẫu nhiên cho mỗi class
COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))

# Độ tin cậy tối thiểu
confidence_threshold = 0.5

print("[INFO] Bắt đầu video stream từ ESP32-CAM...")

# Đọc video stream từ ESP32-CAM
current_endpoint_index = 0

def get_frame():
    """Lấy frame từ ESP32-CAM - thử nhiều endpoint"""
    global current_endpoint_index
    
    # Thử từng endpoint
    for i in range(len(ESP32_CAM_ENDPOINTS)):
        endpoint = ESP32_CAM_ENDPOINTS[(current_endpoint_index + i) % len(ESP32_CAM_ENDPOINTS)]
        url = f"http://{ESP32_CAM_IP}{endpoint}"
        
        try:
            img_resp = urllib.request.urlopen(url, timeout=3)
            img_np = np.array(bytearray(img_resp.read()), dtype=np.uint8)
            frame = cv2.imdecode(img_np, -1)
            
            if frame is not None and frame.size > 0:
                # Nếu thành công với endpoint này, dùng tiếp
                current_endpoint_index = (current_endpoint_index + i) % len(ESP32_CAM_ENDPOINTS)
                return frame
        except Exception as e:
            # Thử endpoint tiếp theo
            continue
    
    # Nếu tất cả đều fail, in thông báo
    return None

# FPS counter
fps_start_time = cv2.getTickCount()
fps = 0
frame_count = 0

while True:
    # Lấy frame từ ESP32-CAM
    frame = get_frame()
    
    if frame is None:
        # In thông báo lỗi chi tiết lần đầu
        if not hasattr(get_frame, 'error_shown'):
            print(f"[WARNING] Không thể kết nối ESP32-CAM tại {ESP32_CAM_IP}")
            print(f"[INFO] Đã thử các endpoint: {', '.join(ESP32_CAM_ENDPOINTS)}")
            print(f"[INFO] Vui lòng kiểm tra:")
            print(f"  1. IP ESP32-CAM có đúng không?")
            print(f"  2. ESP32-CAM có đang chạy không?")
            print(f"  3. Cùng mạng WiFi không?")
            get_frame.error_shown = True
        continue
    
    # Lấy kích thước frame
    (h, w) = frame.shape[:2]
    
    # Tạo blob từ frame
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
                                 0.007843, (300, 300), 127.5)
    
    # Đưa blob vào network
    net.setInput(blob)
    detections = net.forward()
    
    # Đếm số lượng object được phát hiện
    detected_objects = {}
    
    # Duyệt qua các detection
    for i in range(detections.shape[2]):
        # Lấy confidence
        confidence = detections[0, 0, i, 2]
        
        # Lọc các detection yếu
        if confidence > confidence_threshold:
            # Lấy class index
            idx = int(detections[0, 0, i, 1])
            
            # Tính toán tọa độ bounding box
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")
            
            # Đảm bảo bounding box nằm trong frame
            startX = max(0, startX)
            startY = max(0, startY)
            endX = min(w, endX)
            endY = min(h, endY)
            
            # Đếm số lượng mỗi loại object
            label = CLASSES[idx]
            if label in detected_objects:
                detected_objects[label] += 1
            else:
                detected_objects[label] = 1
            
            # Vẽ bounding box và label
            label_text = f"{label}: {confidence*100:.2f}%"
            cv2.rectangle(frame, (startX, startY), (endX, endY),
                         COLORS[idx], 2)
            
            # Vẽ background cho text
            y = startY - 15 if startY - 15 > 15 else startY + 15
            cv2.rectangle(frame, (startX, y-15), (startX + len(label_text)*9, y+5),
                         COLORS[idx], -1)
            cv2.putText(frame, label_text, (startX, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    
    # Tính FPS
    frame_count += 1
    if frame_count >= 10:
        fps_end_time = cv2.getTickCount()
        time_diff = (fps_end_time - fps_start_time) / cv2.getTickFrequency()
        fps = frame_count / time_diff
        frame_count = 0
        fps_start_time = cv2.getTickCount()
    
    # Hiển thị FPS
    cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    # Hiển thị số lượng objects được phát hiện
    y_offset = 60
    for obj, count in detected_objects.items():
        text = f"{obj}: {count}"
        cv2.putText(frame, text, (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += 30
    
    # Hiển thị frame
    cv2.imshow("ESP32-CAM Object Detection", frame)
    
    # Nhấn 'q' để thoát
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key == ord("s"):
        # Nhấn 's' để chụp ảnh
        cv2.imwrite("captured_frame.jpg", frame)
        print("[INFO] Đã lưu ảnh!")

print("[INFO] Dọn dẹp...")
cv2.destroyAllWindows()
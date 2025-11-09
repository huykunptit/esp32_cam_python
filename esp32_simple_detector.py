import cv2
import numpy as np
import time

# ==== CẤU HÌNH ====
# Đổi thành IP của bạn nếu khác
ESP32_IP = "192.168.0.109"
# Thử các endpoint phổ biến; thứ tự ưu tiên: stream -> capture
STREAM_URLS = [
    f"http://{ESP32_IP}/stream",
    f"http://{ESP32_IP}:81/stream",
    f"http://{ESP32_IP}/video",      # một số firmware
    f"http://{ESP32_IP}/capture"     # nếu không có stream (lấy từng frame)
]

# Model files (đặt cùng folder với script)
PROTOTXT = "MobileNetSSD_deploy.prototxt"
MODEL = "MobileNetSSD_deploy.caffemodel"

# Threshhold để hiển thị detection
CONF_THRESHOLD = 0.5

# Danh sách lớp MobileNet-SSD (21 class)
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant",
           "sheep", "sofa", "train", "tvmonitor"]

# Bạn có thể chỉ quan tâm 1 vài lớp (ví dụ person + bottle + chair)
INTERESTING = {"person", "bottle", "chair", "tvmonitor", "car", "dog", "cat"}

# ==== LOAD MODEL ====
print("[INFO] Loading model...")
net = cv2.dnn.readNetFromCaffe(PROTOTXT, MODEL)

# ==== MỞ CAMERA (thử các URL) ====
cap = None
for url in STREAM_URLS:
    print(f"[INFO] Thử mở stream: {url}")
    cap = cv2.VideoCapture(url)
    # đợi 1 giây để xác nhận
    time.sleep(0.8)
    if cap.isOpened():
        print(f"[OK] Mở được: {url}")
        break
    else:
        cap.release()
        cap = None

if cap is None:
    print("[ERROR] Không mở được stream nào. Kiểm tra URL/ESP32.")
    exit(1)

# ==== VÒNG LẶP NHẬN DIỆN ====
while True:
    ret, frame = cap.read()
    if not ret or frame is None:
        # nếu stream dùng /capture (trả về single jpeg), cần thử lại
        print("[WARN] Không nhận frame, thử reconnect...")
        time.sleep(0.5)
        continue

    (h, w) = frame.shape[:2]
    # chuẩn bị blob cho DNN
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
                                 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    # duyệt detections
    for i in range(0, detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > CONF_THRESHOLD:
            idx = int(detections[0, 0, i, 1])
            label = CLASSES[idx] if idx < len(CLASSES) else str(idx)
            if label not in INTERESTING:
                continue  # bỏ qua những lớp không quan tâm

            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")

            # vẽ bbox và nhãn
            text = f"{label}: {confidence:.2f}"
            y = startY - 10 if startY - 10 > 10 else startY + 10
            cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2)
            cv2.putText(frame, text, (startX, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # hiển thị
    cv2.imshow("ESP32-CAM Detection", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

# cleanup
cap.release()
cv2.destroyAllWindows()

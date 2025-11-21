import cv2
import requests
from PIL import Image
import io
import numpy as np
import time
import json

# pip install ultralytics opencv-python requests pillow
from ultralytics import YOLO

class ESP32CamYOLOv8Detector:
    def __init__(self, esp32_ip=None, esp32_ap_ip="192.168.4.1", model_path="yolov8n.pt"):
        """
        Khởi tạo detector
        
        Args:
            esp32_ip: IP của ESP32-CAM (nếu None, sẽ tự động lấy từ AP)
            esp32_ap_ip: IP của AP của ESP32-CAM (mặc định 192.168.4.1)
            model_path: Đường dẫn đến model YOLOv8
        """
        # Nếu không có IP, tự động lấy từ ESP32-CAM AP
        if esp32_ip is None:
            print("🔍 Tự động tìm IP của ESP32-CAM...")
            esp32_ip = self.get_esp32_ip_from_ap(esp32_ap_ip)
            if esp32_ip is None:
                print(f"⚠️ Không tìm thấy IP từ AP {esp32_ap_ip}, sử dụng IP mặc định")
                esp32_ip = esp32_ap_ip
        
        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}/capture"
        self.distance_url = f"http://{esp32_ip}/distance"
        self.results_url = f"http://{esp32_ip}/results"
        self.ip_url = f"http://{esp32_ip}/ip"

        print(f"✅ ESP32-CAM IP: {esp32_ip}")
        print("Loading YOLOv8 model...")
        self.model = YOLO(model_path)
        print("Model loaded!")
    
    def get_esp32_ip_from_ap(self, ap_ip="192.168.4.1", timeout=5):
        """
        Lấy IP WiFi của ESP32-CAM từ AP
        
        Args:
            ap_ip: IP của AP (mặc định 192.168.4.1)
            timeout: Timeout cho request
            
        Returns:
            IP của ESP32-CAM hoặc None nếu không tìm thấy
        """
        try:
            ip_endpoint = f"http://{ap_ip}/ip"
            response = requests.get(ip_endpoint, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                wifi_ip = data.get("ip", "")
                if wifi_ip and data.get("status") == "connected":
                    print(f"✅ Tìm thấy ESP32-CAM IP: {wifi_ip}")
                    return wifi_ip
                else:
                    print(f"⚠️ ESP32-CAM chưa kết nối WiFi, sử dụng AP IP: {ap_ip}")
                    return ap_ip
            else:
                print(f"⚠️ Không thể kết nối đến {ap_ip}, status: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Lỗi khi lấy IP từ AP: {e}")
            print(f"💡 Đảm bảo bạn đã kết nối vào WiFi '{ap_ip}' hoặc ESP32-CAM đang phát AP")
            return None

    def get_frame_from_esp32(self):
        """Lấy frame từ ESP32-CAM"""
        try:
            response = requests.get(self.stream_url, timeout=3)
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                # Resize nếu cần
                h, w = frame.shape[:2]
                if w > 640:
                    scale = 640 / w
                    frame = cv2.resize(frame, (640, int(h * scale)))
                return frame
            else:
                print(f"[ESP32] HTTP {response.status_code} when requesting {self.stream_url}")
                return None
        except Exception as e:
            print(f"[ESP32] Error getting frame: {e}")
            return None

    def get_distance_from_esp32(self):
        """Lấy distance + pip từ ESP32 endpoint"""
        try:
            response = requests.get(self.distance_url, timeout=1)
            if response.status_code == 200:
                data = response.json()
                distance = int(data.get("distance_mm", -1))
                pip = str(data.get("pip", "NONE"))
                return distance, pip
            else:
                return -1, "NONE"
        except Exception as e:
            print(f"[ESP32 Distance] Error: {e}")
            return -1, "NONE"

    def detect_objects(self, frame):
        """Nhận diện objects với YOLOv8"""
        results = self.model(frame)[0]  # Lấy kết quả đầu tiên
        detections = []

        for box, cls, conf in zip(results.boxes.xyxy, results.boxes.cls, results.boxes.conf):
            x1, y1, x2, y2 = map(int, box)
            class_name = self.model.names[int(cls)]
            confidence = float(conf)
            detections.append({
                "class": class_name,
                "bbox": [x1, y1, x2 - x1, y2 - y1],
                "confidence": confidence
            })
            # Vẽ bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)
            cv2.putText(frame, f"{class_name}:{confidence:.2f}", (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
        return frame, detections

    def run_detection(self):
        """Chạy detection loop chính"""
        print("🚀 Bắt đầu nhận diện YOLOv8 từ ESP32-CAM + distance...")
        cv2.namedWindow("ESP32-CAM YOLOv8 Detection", cv2.WINDOW_NORMAL)
        
        last_ip_check = time.time()
        ip_check_interval = 10  # Kiểm tra IP mỗi 10 giây

        while True:
            # Kiểm tra và cập nhật IP định kỳ
            current_time = time.time()
            if current_time - last_ip_check > ip_check_interval:
                self.update_esp32_ip()
                last_ip_check = current_time
            
            frame = self.get_frame_from_esp32()
            distance_mm, pip_type = self.get_distance_from_esp32()

            if frame is None:
                placeholder = np.zeros((360, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, "No frame from ESP32-CAM", (10,180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255),2)
                cv2.imshow("ESP32-CAM YOLOv8 Detection", placeholder)
                key = cv2.waitKey(100) & 0xFF
                if key == ord('q'):
                    break
                continue

            frame, detections = self.detect_objects(frame)

            # Tạo JSON kết quả
            result_json = {
                "distance_mm": distance_mm,
                "pip": pip_type,
                "pip_alert": pip_type not in ("NONE", "", None),
                "objects": detections
            }

            print(json.dumps(result_json))
            self.send_results_to_esp32(result_json)

            # Hiển thị thông tin
            cv2.putText(frame, f"Distance: {distance_mm} mm ({pip_type})", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
            cv2.imshow("ESP32-CAM YOLOv8 Detection", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

        cv2.destroyAllWindows()

    def update_esp32_ip(self):
        """Cập nhật IP của ESP32-CAM nếu thay đổi"""
        try:
            response = requests.get(self.ip_url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                new_ip = data.get("ip", "")
                if new_ip and new_ip != self.esp32_ip and data.get("status") == "connected":
                    print(f"🔄 ESP32-CAM IP đã thay đổi: {self.esp32_ip} -> {new_ip}")
                    self.esp32_ip = new_ip
                    self.stream_url = f"http://{new_ip}/capture"
                    self.distance_url = f"http://{new_ip}/distance"
                    self.results_url = f"http://{new_ip}/results"
                    self.ip_url = f"http://{new_ip}/ip"
                    return True
        except:
            pass
        return False
    
    def send_results_to_esp32(self, data):
        """Gửi JSON kết quả về endpoint /results trên ESP32"""
        try:
            response = requests.post(self.results_url, json=data, timeout=1)
            if response.status_code != 200:
                print(f"[ESP32 Results] HTTP {response.status_code}: {response.text}")
        except Exception as exc:
            print(f"[ESP32 Results] Error sending data: {exc}")
            # Thử cập nhật IP nếu lỗi kết nối
            self.update_esp32_ip()


if __name__ == "__main__":
    # Tự động lấy IP từ ESP32-CAM AP
    # Nếu muốn dùng IP cố định, truyền vào: ESP32CamYOLOv8Detector("192.168.1.100", ...)
    detector = ESP32CamYOLOv8Detector(esp32_ip=None, model_path="yolov8n.pt")
    detector.run_detection()

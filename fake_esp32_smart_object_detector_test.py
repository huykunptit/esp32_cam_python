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
    def __init__(self, esp32_ip="10.13.20.248", model_path="yolov8n.pt"):

        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}/capture"
        self.distance_url = f"http://{esp32_ip}/distance"

        print("Loading YOLOv8 model...")
        self.model = YOLO(model_path)
        print("Model loaded!")

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

        while True:
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
                "objects": detections
            }

            print(json.dumps(result_json))

            # Hiển thị thông tin
            cv2.putText(frame, f"Distance: {distance_mm} mm ({pip_type})", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
            cv2.imshow("ESP32-CAM YOLOv8 Detection", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

        cv2.destroyAllWindows()


if __name__ == "__main__":
    detector = ESP32CamYOLOv8Detector("10.13.20.248", model_path="yolov8n.pt")
    detector.run_detection()

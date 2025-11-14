import cv2
import numpy as np
import requests
from PIL import Image
import io
import time
from collections import defaultdict, deque

class ESP32CamSmartObjectDetector:
    def __init__(self, esp32_ip="10.13.20.248"):
        """
        Detector đồ vật thông minh sử dụng MobileNet SSD
        
        Args:
            esp32_ip (str): IP address của ESP32-CAM
        """
        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}/capture"
        
        # Load MobileNet SSD model
        print("Loading MobileNet SSD model...")
        self.net = cv2.dnn.readNetFromCaffe(
            "MobileNetSSD_deploy.prototxt",
            "MobileNetSSD_deploy.caffemodel"
        )
        
        # Danh sách các classes mà model có thể nhận diện
        self.classes = ["background", "aeroplane", "bicycle", "bird", "boat",
                       "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
                       "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
                       "sofa", "train", "tvmonitor"]
        
        # Màu cho mỗi class (random colors)
        np.random.seed(42)
        self.colors = np.random.uniform(0, 255, size=(len(self.classes), 3))
        
        # Confidence threshold cho detection
        self.confidence_threshold = 0.5
        
        # Buffer để smoothing và lọc false positive
        self.detection_history = defaultdict(lambda: deque(maxlen=5))
        
        # Thống kê
        self.detection_stats = defaultdict(int)
        self.total_frames = 0
        
        print(f"Kết nối ESP32-CAM tại: {self.stream_url}")
        print(f"Đã tải MobileNet SSD model với {len(self.classes)} classes")
        
    def get_frame_from_esp32(self):
        """Lấy frame từ ESP32-CAM"""
        try:
            response = requests.get(self.stream_url, timeout=3)
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

                # Resize để tối ưu
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))

                return frame
            else:
                print(f"[ESP32] HTTP {response.status_code} when requesting {self.stream_url}")
                return None
        except Exception as e:
            print(f"[ESP32] Error getting frame: {e}")
            return None
    
    def update_detection_history(self, detections_info):
        """
        Cập nhật lịch sử detections cho smoothing
        
        Args:
            detections_info: List of detection information
        """
        # Reset counts
        current_counts = defaultdict(int)
        
        # Count detections by class
        for detection in detections_info:
            current_counts[detection['class']] += 1
            
        # Update history for each class
        for class_name in self.classes:
            self.detection_history[class_name].append(current_counts[class_name])
    
    def detect_objects(self, frame):
        """Nhận diện đồ vật sử dụng MobileNet SSD"""
        (h, w) = frame.shape[:2]
        # Tạo blob từ image
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
        
        # Đưa blob qua network
        self.net.setInput(blob)
        detections = self.net.forward()
        
        detections_info = []
        object_counts = defaultdict(int)
        
        # Lọc và vẽ các detections
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            if confidence > self.confidence_threshold:
                # Lấy index của class
                class_id = int(detections[0, 0, i, 1])
                class_name = self.classes[class_id]
                
                # Tính toán coordinates của bounding box
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                
                # Vẽ bounding box và label
                color = self.colors[class_id].astype('int').tolist()
                cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
                
                label = f"{class_name}: {confidence * 100:.1f}%"
                y = startY - 15 if startY - 15 > 15 else startY + 15
                cv2.putText(frame, label, (startX, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                detections_info.append({
                    'class': class_name,
                    'bbox': (startX, startY, endX - startX, endY - startY),
                    'confidence': confidence
                })
                
                object_counts[class_name] += 1
        
        return frame, detections_info, dict(object_counts)
    
    def run_detection(self):
        """Chạy detection loop chính"""
        print("🚀 Bắt đầu nhận diện đồ vật thông minh từ ESP32-CAM...")
        print("📋 Điều khiển:")
        print("   - 'q': Thoát")
        print("   - 's': Chụp ảnh")
        print("   - 'r': Reset thống kê")
        print("   - 'c': Thay đổi confidence threshold")
        print("   - 'i': Thông tin cascade")
        
        fps_counter = 0
        fps_start_time = time.time()
        last_print_time = time.time()
        # Ensure a named window exists so the GUI shows even when no frame is received
        window_name = 'ESP32-CAM Smart Object Detection'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        while True:
            current_time = time.time()
            
            # Lấy frame
            frame = self.get_frame_from_esp32()
            # Nếu không nhận được frame, hiển thị placeholder để cửa sổ vẫn xuất hiện
            if frame is None:
                placeholder = np.zeros((360, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, "No frame from ESP32-CAM", (10, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(placeholder, f"URL: {self.stream_url}", (10, 210),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                cv2.imshow(window_name, placeholder)
                # Allow user to press 'q' to quit even when no frames
                key = cv2.waitKey(100) & 0xFF
                if key == ord('q'):
                    break
                # small sleep to avoid busy loop
                time.sleep(0.1)
                continue
            
            # Nhận diện objects
            frame_with_detections, detections, object_counts = self.detect_objects(frame)
            
            # Tính FPS
            fps_counter += 1
            if fps_counter % 30 == 0:
                fps = fps_counter / (current_time - fps_start_time)
                fps_counter = 0
                fps_start_time = current_time
            else:
                fps = 0
            
            # Hiển thị thông tin
            total_objects = sum(object_counts.values())
            cv2.putText(frame_with_detections, f"Objects: {total_objects}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if fps > 0:
                cv2.putText(frame_with_detections, f"FPS: {fps:.1f}", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.putText(frame_with_detections, f"Confidence: {self.confidence_threshold:.1f}", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            
            cv2.putText(frame_with_detections, f"ESP32: {self.esp32_ip}", 
                       (10, frame_with_detections.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Hiển thị chi tiết objects
            y_offset = 120
            for obj_name, count in object_counts.items():
                cv2.putText(frame_with_detections, f"{obj_name.title()}: {count}", 
                           (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                y_offset += 20
            
            # Hiển thị frame
            cv2.imshow('ESP32-CAM Smart Object Detection', frame_with_detections)
            
            # Cập nhật thống kê
            self.total_frames += 1
            for obj_name, count in object_counts.items():
                self.detection_stats[obj_name] += count
            
            # In thông tin định kỳ
            if current_time - last_print_time > 5:
                if object_counts:
                    print(f"📊 Detections: {total_objects} objects - {object_counts}")
                last_print_time = current_time
            
            # Xử lý phím
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                filename = f"esp32_smart_objects_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame_with_detections)
                print(f"📸 Đã chụp ảnh: {filename}")
            elif key == ord('r'):
                self.detection_stats = defaultdict(int)
                self.total_frames = 0
                for obj_name in self.detection_history:
                    self.detection_history[obj_name].clear()
                print("🔄 Đã reset thống kê")
            elif key == ord('c'):
                # Thay đổi confidence threshold
                self.confidence_threshold = min(0.9, self.confidence_threshold + 0.1) if self.confidence_threshold < 0.9 else 0.3
                print(f"🔄 Confidence threshold: {self.confidence_threshold:.1f}")
            elif key == ord('i'):
                self._print_model_info()
        
        cv2.destroyAllWindows()
        self._print_final_stats()
    
    def _print_model_info(self):
        """In thông tin về model MobileNet SSD"""
        print("\n📋 Thông tin Model:")
        print("   - Model: MobileNet SSD")
        print(f"   - Classes ({len(self.classes)}): {', '.join(self.classes[1:])}")  # Skip background
        print(f"   - Confidence Threshold: {self.confidence_threshold:.2f}")
    
    def _print_final_stats(self):
        """In thống kê cuối"""
        print("\n📊 Thống kê cuối:")
        print(f"   - Tổng frames: {self.total_frames}")
        print(f"   - Tổng objects: {sum(self.detection_stats.values())}")
        
        if self.detection_stats:
            print("   - Chi tiết:")
            for obj_name, count in sorted(self.detection_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"     {obj_name.title()}: {count}")

if __name__ == "__main__":
    detector = ESP32CamSmartObjectDetector("10.13.20.248")
    detector.run_detection()

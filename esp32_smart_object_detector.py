import cv2
import numpy as np
import requests
from PIL import Image
import io
import time
from collections import defaultdict, deque

class ESP32CamSmartObjectDetector:
    def __init__(self, esp32_ip="192.168.0.109"):
        """
        Detector đồ vật thông minh với logic lọc tốt hơn
        
        Args:
            esp32_ip (str): IP address của ESP32-CAM
        """
        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}/capture"
        
        # Khởi tạo các cascade với tham số tối ưu
        self.cascades = {}
        self.cascade_info = {
            'car': ('haarcascade_car.xml', (0, 255, 0), {'minNeighbors': 4, 'minSize': (50, 50)}),
            'eye': ('haarcascade_eye.xml', (255, 0, 0), {'minNeighbors': 5, 'minSize': (15, 15)}),
            'watch': ('haarcascade_watch.xml', (255, 0, 255), {'minNeighbors': 6, 'minSize': (25, 25)}),
            'clock': ('haarcascade_clock.xml', (255, 255, 0), {'minNeighbors': 5, 'minSize': (30, 30)})
        }
        
        # Loại bỏ smile cascade vì nó quá nhạy
        # self.cascade_info['smile'] = ('haarcascade_smile.xml', (0, 255, 255), {'minNeighbors': 10, 'minSize': (40, 40)})
        
        # Tải các cascade có sẵn
        for obj_name, (cascade_file, color, params) in self.cascade_info.items():
            cascade_path = cv2.data.haarcascades + cascade_file
            cascade = cv2.CascadeClassifier(cascade_path)
            if not cascade.empty():
                self.cascades[obj_name] = (cascade, color, params)
                print(f"✓ Đã tải cascade cho {obj_name}")
            else:
                print(f"⚠️ Không tìm thấy cascade cho {obj_name}")
        
        # Buffer để smoothing và lọc false positive
        self.detection_history = defaultdict(lambda: deque(maxlen=5))
        self.confidence_threshold = 0.6  # Threshold cho confidence
        
        # Thống kê
        self.detection_stats = defaultdict(int)
        self.total_frames = 0
        
        print(f"Kết nối ESP32-CAM tại: {self.stream_url}")
        print(f"Đã tải {len(self.cascades)} cascade(s) (đã loại bỏ smile cascade)")
        
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
    
    def calculate_detection_confidence(self, obj_name, detections):
        """
        Tính confidence cho detections dựa trên lịch sử
        
        Args:
            obj_name: Tên object
            detections: List of detections
            
        Returns:
            List of (detection, confidence)
        """
        if not detections:
            return []
        
        # Tính confidence dựa trên kích thước và vị trí
        confidences = []
        for detection in detections:
            x, y, w, h = detection
            
            # Confidence dựa trên kích thước (objects quá nhỏ hoặc quá lớn có confidence thấp)
            size_score = 1.0
            if obj_name == 'car':
                if w < 60 or h < 40 or w > 300 or h > 200:
                    size_score = 0.3
            elif obj_name == 'eye':
                if w < 10 or h < 10 or w > 50 or h > 50:
                    size_score = 0.3
            elif obj_name in ['watch', 'clock']:
                if w < 20 or h < 20 or w > 100 or h > 100:
                    size_score = 0.3
            
            # Confidence dựa trên vị trí (objects ở góc có thể là false positive)
            position_score = 1.0
            frame_height, frame_width = 480, 640  # Giả định kích thước frame
            if x < 10 or y < 10 or x + w > frame_width - 10 or y + h > frame_height - 10:
                position_score = 0.7
            
            # Confidence tổng hợp
            confidence = size_score * position_score
            confidences.append((detection, confidence))
        
        return confidences
    
    def filter_detections(self, obj_name, detections):
        """
        Lọc detections dựa trên confidence và lịch sử
        
        Args:
            obj_name: Tên object
            detections: List of detections
            
        Returns:
            List of filtered detections
        """
        if not detections:
            return []
        
        # Tính confidence
        detections_with_conf = self.calculate_detection_confidence(obj_name, detections)
        
        # Lọc theo confidence threshold
        filtered = []
        for detection, confidence in detections_with_conf:
            if confidence >= self.confidence_threshold:
                filtered.append(detection)
        
        # Cập nhật lịch sử
        self.detection_history[obj_name].append(len(filtered))
        
        # Smoothing: chỉ hiển thị nếu có ít nhất 2 detections trong 5 frames gần nhất
        if len(self.detection_history[obj_name]) >= 3:
            recent_detections = list(self.detection_history[obj_name])[-3:]
            avg_detections = sum(recent_detections) / len(recent_detections)
            
            # Chỉ hiển thị nếu trung bình >= 1.5 detections
            if avg_detections < 1.5:
                return []
        
        return filtered
    
    def detect_objects(self, frame):
        """Nhận diện đồ vật với logic lọc thông minh"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections_info = []
        object_counts = defaultdict(int)
        
        # Nhận diện từng loại đồ vật
        for obj_name, (cascade, color, params) in self.cascades.items():
            objects = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=params['minNeighbors'],
                minSize=params['minSize'],
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # Lọc detections
            filtered_objects = self.filter_detections(obj_name, objects)
            
            # Vẽ bounding box cho mỗi object
            for i, (x, y, w, h) in enumerate(filtered_objects):
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(frame, f'{obj_name.title()} {i+1}', 
                           (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                detections_info.append({
                    'class': obj_name,
                    'bbox': (x, y, w, h),
                    'confidence': 1.0
                })
                
                object_counts[obj_name] += 1
        
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
                self.confidence_threshold = 0.9 if self.confidence_threshold == 0.6 else 0.6
                print(f"🔄 Confidence threshold: {self.confidence_threshold}")
            elif key == ord('i'):
                self._print_cascade_info()
        
        cv2.destroyAllWindows()
        self._print_final_stats()
    
    def _print_cascade_info(self):
        """In thông tin về các cascade"""
        print("\n📋 Thông tin Cascade:")
        for obj_name, (cascade, color, params) in self.cascades.items():
            print(f"   - {obj_name.title()}: {self.cascade_info[obj_name][0]}")
            print(f"     MinNeighbors: {params['minNeighbors']}, MinSize: {params['minSize']}")
    
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
    detector = ESP32CamSmartObjectDetector("192.168.0.109")
    detector.run_detection()

import cv2
import numpy as np
import requests
from PIL import Image
import io
import time
from collections import defaultdict

class ESP32CamSimpleObjectDetector:
    def __init__(self, esp32_ip="10.13.20.248"):
        """
        Detector đồ vật đơn giản cho ESP32-CAM sử dụng Haar Cascade có sẵn
        
        Args:
            esp32_ip (str): IP address của ESP32-CAM
        """
        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}/capture"
        
        # Khởi tạo các cascade cho đồ vật
        self.cascades = {}
        self.cascade_info = {
            'car': ('haarcascade_car.xml', (0, 255, 0)),
            'eye': ('haarcascade_eye.xml', (255, 0, 0)),
            'smile': ('haarcascade_smile.xml', (0, 255, 255)),
            'watch': ('haarcascade_watch.xml', (255, 0, 255)),
            'clock': ('haarcascade_clock.xml', (255, 255, 0))
        }
        
        # Tải các cascade có sẵn
        for obj_name, (cascade_file, color) in self.cascade_info.items():
            cascade_path = cv2.data.haarcascades + cascade_file
            cascade = cv2.CascadeClassifier(cascade_path)
            if not cascade.empty():
                self.cascades[obj_name] = (cascade, color)
                print(f"✓ Đã tải cascade cho {obj_name}")
            else:
                print(f"⚠️ Không tìm thấy cascade cho {obj_name}")
        
        # Thống kê
        self.detection_stats = defaultdict(int)
        self.total_frames = 0
        
        print(f"Kết nối ESP32-CAM tại: {self.stream_url}")
        print(f"Đã tải {len(self.cascades)} cascade(s)")
        
    def get_frame_from_esp32(self):
        """
        Lấy frame từ ESP32-CAM
        
        Returns:
            numpy.ndarray: Frame image hoặc None nếu lỗi
        """
        try:
            response = requests.get(self.stream_url, timeout=2)
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
                return None
        except Exception as e:
            return None
    
    def detect_objects(self, frame):
        """
        Nhận diện đồ vật bằng Haar Cascade
        
        Args:
            frame: Input frame
            
        Returns:
            tuple: (frame_with_detections, detections_info)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections_info = []
        object_counts = defaultdict(int)
        
        # Nhận diện từng loại đồ vật với tham số tối ưu
        for obj_name, (cascade, color) in self.cascades.items():
            # Tham số khác nhau cho từng loại object
            if obj_name == 'smile':
                # Tăng độ nghiêm ngặt cho smile để giảm false positive
                objects = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.2,
                    minNeighbors=8,  # Tăng để giảm false positive
                    minSize=(30, 30),  # Tăng kích thước tối thiểu
                    flags=cv2.CASCADE_SCALE_IMAGE
                )
            elif obj_name == 'eye':
                # Tham số cho mắt
                objects = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(15, 15),
                    flags=cv2.CASCADE_SCALE_IMAGE
                )
            elif obj_name == 'car':
                # Tham số cho xe
                objects = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=4,
                    minSize=(50, 50),  # Xe thường lớn hơn
                    flags=cv2.CASCADE_SCALE_IMAGE
                )
            else:
                # Tham số mặc định cho các object khác
                objects = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(25, 25),
                    flags=cv2.CASCADE_SCALE_IMAGE
                )
            
            # Vẽ bounding box cho mỗi object
            for i, (x, y, w, h) in enumerate(objects):
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
        """
        Chạy detection loop chính
        """
        print("🚀 Bắt đầu nhận diện đồ vật đơn giản từ ESP32-CAM...")
        print("📋 Điều khiển:")
        print("   - 'q': Thoát")
        print("   - 's': Chụp ảnh")
        print("   - 'r': Reset thống kê")
        print("   - 'i': Thông tin cascade")
        
        fps_counter = 0
        fps_start_time = time.time()
        last_print_time = time.time()
        
        while True:
            current_time = time.time()
            
            # Lấy frame
            frame = self.get_frame_from_esp32()
            
            if frame is None:
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
            
            cv2.putText(frame_with_detections, f"ESP32: {self.esp32_ip}", 
                       (10, frame_with_detections.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Hiển thị chi tiết objects
            y_offset = 90
            for obj_name, count in object_counts.items():
                cv2.putText(frame_with_detections, f"{obj_name.title()}: {count}", 
                           (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                y_offset += 20
            
            # Hiển thị frame
            cv2.imshow('ESP32-CAM Simple Object Detection', frame_with_detections)
            
            # Cập nhật thống kê
            self.total_frames += 1
            for obj_name, count in object_counts.items():
                self.detection_stats[obj_name] += count
            
            # In thông tin định kỳ
            if current_time - last_print_time > 5:  # Mỗi 5 giây
                if object_counts:
                    print(f"📊 Detections: {total_objects} objects - {object_counts}")
                last_print_time = current_time
            
            # Xử lý phím
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                filename = f"esp32_simple_objects_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame_with_detections)
                print(f"📸 Đã chụp ảnh: {filename}")
            elif key == ord('r'):
                self.detection_stats = defaultdict(int)
                self.total_frames = 0
                print("🔄 Đã reset thống kê")
            elif key == ord('i'):
                self._print_cascade_info()
        
        cv2.destroyAllWindows()
        self._print_final_stats()
    
    def _print_cascade_info(self):
        """In thông tin về các cascade"""
        print("\n📋 Thông tin Cascade:")
        for obj_name, (cascade, color) in self.cascades.items():
            print(f"   - {obj_name.title()}: {self.cascade_info[obj_name][0]}")
    
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
    detector = ESP32CamSimpleObjectDetector("10.13.20.248")
    detector.run_detection()

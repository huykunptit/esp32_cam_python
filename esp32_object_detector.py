import cv2
import numpy as np
import requests
from PIL import Image
import io
import time
import threading
from collections import deque
import urllib.request
import os

class ESP32CamObjectDetector:
    def __init__(self, esp32_ip="192.168.0.109"):
        """
        Detector đồ vật cho ESP32-CAM sử dụng MobileNet SSD
        
        Args:
            esp32_ip (str): IP address của ESP32-CAM
        """
        self.esp32_ip = esp32_ip
        self.stream_url = f"http://{esp32_ip}/capture"
        
        # Danh sách các class có thể nhận diện
        self.classes = [
            'background', 'person', 'bicycle', 'car', 'motorcycle', 'airplane',
            'bus', 'train', 'truck', 'boat', 'traffic light', 'fire hydrant',
            'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse',
            'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
            'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis',
            'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
            'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass',
            'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
            'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed',
            'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
            'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
            'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
            'hair drier', 'toothbrush'
        ]
        
        # Màu sắc cho bounding box
        self.colors = np.random.uniform(0, 255, size=(len(self.classes), 3))
        
        # Khởi tạo MobileNet SSD
        self.net = None
        self.model_loaded = False
        
        # Buffer để smoothing detections
        self.detection_buffer = deque(maxlen=3)
        
        # Thống kê
        self.detection_stats = {
            'total_objects': 0,
            'object_counts': {},
            'total_frames': 0
        }
        
        print(f"Kết nối ESP32-CAM tại: {self.stream_url}")
        print("Đang khởi tạo model nhận diện đồ vật...")
        
        # Tải model
        self._load_model()
        
    def _load_model(self):
        """Tải MobileNet SSD model"""
        prototxt_file = "MobileNetSSD_deploy.prototxt.txt"
        model_file = "MobileNetSSD_deploy.caffemodel"
        
        if not os.path.exists(prototxt_file) or not os.path.exists(model_file):
            print("Model files chưa tồn tại. Đang tải xuống...")
            if self._download_model_files():
                self._initialize_network()
            else:
                print("Không thể tải model files. Sử dụng chế độ đơn giản.")
                self.model_loaded = False
        else:
            self._initialize_network()
    
    def _download_model_files(self):
        """Tải xuống model files"""
        try:
            print("Đang tải prototxt file...")
            urllib.request.urlretrieve(
                "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/MobileNetSSD_deploy.prototxt",
                "MobileNetSSD_deploy.prototxt.txt"
            )
            
            print("Đang tải model file...")
            urllib.request.urlretrieve(
                "https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel",
                "MobileNetSSD_deploy.caffemodel"
            )
            
            print("✓ Đã tải xong model files!")
            return True
        except Exception as e:
            print(f"Lỗi khi tải model files: {e}")
            return False
    
    def _initialize_network(self):
        """Khởi tạo neural network"""
        try:
            self.net = cv2.dnn.readNetFromCaffe(
                'MobileNetSSD_deploy.prototxt.txt',
                'MobileNetSSD_deploy.caffemodel'
            )
            self.model_loaded = True
            print("✓ Model đã được tải thành công!")
        except Exception as e:
            print(f"Lỗi khi khởi tạo model: {e}")
            self.model_loaded = False
    
    def get_frame_from_esp32(self):
        """
        Lấy frame từ ESP32-CAM với tối ưu hóa
        
        Returns:
            numpy.ndarray: Frame image hoặc None nếu lỗi
        """
        try:
            response = requests.get(self.stream_url, timeout=2)
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # Resize để tối ưu hiệu suất
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
    
    def detect_objects_advanced(self, frame):
        """
        Nhận diện đồ vật bằng MobileNet SSD
        
        Args:
            frame: Input frame
            
        Returns:
            tuple: (frame_with_detections, detections_info)
        """
        if not self.model_loaded:
            return frame, []
        
        height, width = frame.shape[:2]
        
        # Chuẩn bị blob cho MobileNet SSD
        blob = cv2.dnn.blobFromImage(
            frame, 0.007843, (300, 300), 127.5
        )
        
        # Đưa blob vào network
        self.net.setInput(blob)
        detections = self.net.forward()
        
        detections_info = []
        object_counts = {}
        
        # Xử lý kết quả detection
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            # Chỉ hiển thị detections với confidence > 0.4 (giảm để tăng độ nhạy)
            if confidence > 0.4:
                class_id = int(detections[0, 0, i, 1])
                class_name = self.classes[class_id]
                
                # Tính toán bounding box
                x_left = int(detections[0, 0, i, 3] * width)
                y_top = int(detections[0, 0, i, 4] * height)
                x_right = int(detections[0, 0, i, 5] * width)
                y_bottom = int(detections[0, 0, i, 6] * height)
                
                # Đảm bảo coordinates hợp lệ
                x_left = max(0, x_left)
                y_top = max(0, y_top)
                x_right = min(width, x_right)
                y_bottom = min(height, y_bottom)
                
                # Vẽ bounding box
                color = self.colors[class_id]
                cv2.rectangle(frame, (x_left, y_top), (x_right, y_bottom), color, 2)
                
                # Vẽ label
                label = f"{class_name}: {confidence:.2f}"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                
                # Vẽ background cho label
                cv2.rectangle(
                    frame, 
                    (x_left, y_top - label_size[1] - 10),
                    (x_left + label_size[0], y_top),
                    color, -1
                )
                
                cv2.putText(
                    frame, label,
                    (x_left, y_top - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2
                )
                
                detections_info.append({
                    'class': class_name,
                    'confidence': confidence,
                    'bbox': (x_left, y_top, x_right, y_bottom)
                })
                
                # Đếm objects
                if class_name in object_counts:
                    object_counts[class_name] += 1
                else:
                    object_counts[class_name] = 1
        
        return frame, detections_info, object_counts
    
    def detect_objects_simple(self, frame):
        """
        Nhận diện đồ vật đơn giản bằng Haar Cascade
        
        Args:
            frame: Input frame
            
        Returns:
            tuple: (frame_with_detections, detections_info)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections_info = []
        object_counts = {}
        
        # Nhận diện xe hơi
        car_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_car.xml')
        if not car_cascade.empty():
            cars = car_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(30, 30)
            )
            
            for i, (x, y, w, h) in enumerate(cars):
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, f'Car {i+1}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                detections_info.append({
                    'class': 'car',
                    'confidence': 1.0,
                    'bbox': (x, y, w, h)
                })
                object_counts['car'] = object_counts.get('car', 0) + 1
        
        return frame, detections_info, object_counts
    
    def run_detection(self):
        """
        Chạy detection loop chính
        """
        print("🚀 Bắt đầu nhận diện đồ vật từ ESP32-CAM...")
        print("📋 Điều khiển:")
        print("   - 'q': Thoát")
        print("   - 's': Chụp ảnh")
        print("   - 'r': Reset thống kê")
        print("   - 'm': Chuyển đổi chế độ (Advanced/Simple)")
        
        fps_counter = 0
        fps_start_time = time.time()
        last_print_time = time.time()
        use_advanced = self.model_loaded
        
        while True:
            current_time = time.time()
            
            # Lấy frame
            frame = self.get_frame_from_esp32()
            
            if frame is None:
                time.sleep(0.1)
                continue
            
            # Nhận diện objects
            if use_advanced and self.model_loaded:
                frame_with_detections, detections, object_counts = self.detect_objects_advanced(frame)
                mode_text = "Advanced (MobileNet SSD)"
            else:
                frame_with_detections, detections, object_counts = self.detect_objects_simple(frame)
                mode_text = "Simple (Haar Cascade)"
            
            # Tính FPS
            fps_counter += 1
            if fps_counter % 30 == 0:
                fps = fps_counter / (current_time - fps_start_time)
                fps_counter = 0
                fps_start_time = current_time
            else:
                fps = 0
            
            # Hiển thị thông tin
            cv2.putText(frame_with_detections, f"Objects: {len(detections)}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if fps > 0:
                cv2.putText(frame_with_detections, f"FPS: {fps:.1f}", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.putText(frame_with_detections, f"Mode: {mode_text}", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            
            cv2.putText(frame_with_detections, f"ESP32: {self.esp32_ip}", 
                       (10, frame_with_detections.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Hiển thị top objects
            if object_counts:
                sorted_objects = sorted(object_counts.items(), key=lambda x: x[1], reverse=True)
                y_offset = 120
                for i, (obj_name, count) in enumerate(sorted_objects[:3]):  # Top 3
                    cv2.putText(frame_with_detections, f"{obj_name}: {count}", 
                               (10, y_offset + i*20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Hiển thị frame
            cv2.imshow('ESP32-CAM Object Detection', frame_with_detections)
            
            # Cập nhật thống kê
            self.detection_stats['total_objects'] += len(detections)
            self.detection_stats['total_frames'] += 1
            
            for obj_name, count in object_counts.items():
                if obj_name in self.detection_stats['object_counts']:
                    self.detection_stats['object_counts'][obj_name] += count
                else:
                    self.detection_stats['object_counts'][obj_name] = count
            
            # In thông tin định kỳ
            if current_time - last_print_time > 5:  # Mỗi 5 giây
                print(f"📊 Detections: {len(detections)} objects")
                if object_counts:
                    print(f"   Top objects: {dict(list(sorted_objects)[:3])}")
                last_print_time = current_time
            
            # Xử lý phím
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                filename = f"esp32_objects_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame_with_detections)
                print(f"📸 Đã chụp ảnh: {filename}")
            elif key == ord('r'):
                self.detection_stats = {'total_objects': 0, 'object_counts': {}, 'total_frames': 0}
                print("🔄 Đã reset thống kê")
            elif key == ord('m'):
                if self.model_loaded:
                    use_advanced = not use_advanced
                    print(f"🔄 Chuyển sang chế độ: {'Advanced' if use_advanced else 'Simple'}")
                else:
                    print("⚠️ Chế độ Advanced không khả dụng (model chưa tải)")
        
        cv2.destroyAllWindows()
        self._print_final_stats()
    
    def _print_final_stats(self):
        """In thống kê cuối"""
        print("\n📊 Thống kê cuối:")
        print(f"   - Tổng frames: {self.detection_stats['total_frames']}")
        print(f"   - Tổng objects: {self.detection_stats['total_objects']}")
        
        if self.detection_stats['object_counts']:
            print("   - Top objects được nhận diện:")
            sorted_objects = sorted(self.detection_stats['object_counts'].items(), 
                                  key=lambda x: x[1], reverse=True)
            for obj_name, count in sorted_objects[:10]:  # Top 10
                print(f"     {obj_name}: {count}")

if __name__ == "__main__":
    detector = ESP32CamObjectDetector("192.168.0.109")
    detector.run_detection()
